from __future__ import annotations

import json
import math
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

EPISODE_TASKS_ENV = "HASHTAG_EPISODE_TASKS_JSON"
MANUAL_RECORDING_CONTROL_ENV = "HASHTAG_MANUAL_RECORDING_CONTROL"
ROLLOUT_EPISODE_TASKS_ENV = "HASHTAG_ROLLOUT_EPISODE_TASKS_JSON"
UNBOUNDED_ROLLOUT_ENV = "HASHTAG_UNBOUNDED_ROLLOUT"
ASYNC_CHUNK_APPEND_ENV = "HASHTAG_ASYNC_CHUNK_APPEND"
TTT_DEMO_PRESET_ENV = "HASHTAG_TTT_DEMO_PRESET_JSON"
ROLLOUT_SEED_ENV = "HASHTAG_ROLLOUT_SEED"

_TTT_JOINT_KEYS = (
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
)


def _seed_rollout_from_env() -> int | None:
    raw_seed = os.environ.get(ROLLOUT_SEED_ENV)
    if raw_seed is None:
        return None
    try:
        seed = int(raw_seed)
    except ValueError as error:
        raise ValueError(f"{ROLLOUT_SEED_ENV} must be an integer.") from error
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError(f"{ROLLOUT_SEED_ENV} must be between 0 and {2**32 - 1}.")

    from lerobot.utils.random_utils import set_seed

    set_seed(seed)
    print(f"Hashtag rollout inference seed: {seed}", flush=True)
    return seed


def _register_camera() -> None:
    # Importing the config registers the choice before draccus parses
    # --robot.cameras. The device class itself remains lazy.
    import hashtag_robotics.config_avfoundation_uid  # noqa: F401


def record_main() -> None:
    _register_camera()
    from lerobot.scripts import lerobot_record

    _force_terminal_recording_controls()
    _install_recording_lifecycle(lerobot_record)
    _install_discard_cleanup(lerobot_record)
    _install_camera_quality_gate(lerobot_record)
    if os.environ.get(MANUAL_RECORDING_CONTROL_ENV) == "1":
        _install_manual_recording_control(lerobot_record)
    raw_tasks = os.environ.get(EPISODE_TASKS_ENV)
    if raw_tasks:
        _install_episode_tasks(lerobot_record, _decode_episode_tasks(raw_tasks))

    lerobot_record.main()


def _force_terminal_recording_controls() -> None:
    """Make the recorder PTY, not a process-global key hook, authoritative.

    The dashboard sends controls into the child PTY.  On macOS, upstream
    LeRobot otherwise prefers a trusted pynput listener, which watches every
    app on the desktop and never reads those PTY bytes.  That made the API say
    "sent" while the recorder did nothing.  For this wrapper the PTY is the
    explicit control channel, so selecting upstream's terminal backend is both
    deterministic and safer than accepting global arrow/Escape presses.
    """
    from lerobot.utils import keyboard_input

    keyboard_input.pynput_can_capture = lambda: False


def _decode_episode_tasks(raw: str) -> list[str]:
    try:
        tasks = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{EPISODE_TASKS_ENV} is not valid JSON.") from error
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"{EPISODE_TASKS_ENV} must be a non-empty JSON list.")
    cleaned = [str(task).strip() for task in tasks]
    if any(not task for task in cleaned):
        raise ValueError(f"{EPISODE_TASKS_ENV} contains an empty task.")
    return cleaned


def _decode_ttt_demo_preset(raw: str) -> dict[str, Any]:
    try:
        preset = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{TTT_DEMO_PRESET_ENV} is not valid JSON.") from error
    if not isinstance(preset, dict):
        raise ValueError(f"{TTT_DEMO_PRESET_ENV} must be a JSON object.")

    pose = preset.get("start_pose")
    if not isinstance(pose, list) or len(pose) != len(_TTT_JOINT_KEYS):
        raise ValueError(f"{TTT_DEMO_PRESET_ENV}.start_pose must contain six joints.")
    numeric_pose = [float(value) for value in pose]
    if not all(math.isfinite(value) for value in numeric_pose):
        raise ValueError(f"{TTT_DEMO_PRESET_ENV}.start_pose must contain finite values.")

    for key in ("board_robot", "board_camera"):
        board = preset.get(key)
        if not isinstance(board, str) or len(board) != 11 or board[3] != "/" or board[7] != "/":
            raise ValueError(f"{TTT_DEMO_PRESET_ENV}.{key} is not a 3x3 board.")
        if any(cell not in "XO./" for cell in board):
            raise ValueError(f"{TTT_DEMO_PRESET_ENV}.{key} contains an invalid cell.")

    return {
        "episode_index": int(preset["episode_index"]),
        "board_robot": preset["board_robot"],
        "board_camera": preset["board_camera"],
        "start_pose": dict(zip(_TTT_JOINT_KEYS, numeric_pose, strict=True)),
    }


def _install_recording_lifecycle(module: Any) -> None:
    """Emit durable save boundaries that upstream LeRobot does not log.

    ``Reset the environment`` ends before ``save_episode()`` starts, and video
    encoding can take many seconds.  Without these two messages the dashboard
    cannot distinguish a frozen recorder from a healthy encode, nor can it say
    exactly when an episode became durable on disk.
    """
    dataset_class = module.LeRobotDataset
    original: Callable[..., Any] = dataset_class.save_episode
    if getattr(original, "_hashtag_lifecycle", False):
        return

    def save_episode_with_lifecycle(dataset: Any, *args: Any, **kwargs: Any) -> Any:
        episode = int(dataset.num_episodes)
        print(f"Hashtag recorder: Encoding episode {episode}", flush=True)
        result = original(dataset, *args, **kwargs)
        print(f"Hashtag recorder: Saved episode {episode}", flush=True)
        return result

    save_episode_with_lifecycle._hashtag_lifecycle = True  # type: ignore[attr-defined]
    dataset_class.save_episode = save_episode_with_lifecycle


def _install_discard_cleanup(module: Any) -> None:
    """Remove video staging frames when an operator rejects a take.

    LeRobot 0.6.0 only deletes ``meta.image_keys`` in
    ``clear_episode_buffer()``.  Ordinary robot cameras are ``dtype=video``,
    so their PNG staging directories survive a re-record.  The next take uses
    the same episode index, overwrites its first frames, and encodes every old
    frame left after its new end.  Upstream fixed this after 0.6.0 by deleting
    all ``camera_keys`` on the discard path; this compatibility wrapper gives
    the released runtime the same behaviour and stays harmless once upstream
    already does it.
    """
    dataset_class = module.LeRobotDataset
    original: Callable[..., Any] = dataset_class.clear_episode_buffer
    if getattr(original, "_hashtag_discards_video_staging", False):
        return

    def clear_episode_with_camera_cleanup(
        dataset: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        delete_images = bool(kwargs.get("delete_images", args[0] if args else True))
        writer = getattr(dataset, "writer", None)
        meta = getattr(dataset, "meta", None)
        staging_dirs: list[Path] = []

        if delete_images and writer is not None and meta is not None:
            wait = getattr(writer, "_wait_image_writer", None)
            if callable(wait):
                wait()

            episode_buffer = getattr(writer, "episode_buffer", None) or {}
            episode_index = episode_buffer.get("episode_index")
            if hasattr(episode_index, "item"):
                try:
                    episode_index = episode_index.item()
                except ValueError:
                    episode_index = episode_index[0]

            directory_for = getattr(writer, "_get_image_file_dir", None)
            if episode_index is not None and callable(directory_for):
                for camera_key in getattr(meta, "camera_keys", ()):
                    staging_dirs.append(Path(directory_for(int(episode_index), camera_key)))

        result = original(dataset, *args, **kwargs)
        removed = 0
        for directory in staging_dirs:
            if directory.is_dir():
                shutil.rmtree(directory)
                removed += 1
        if removed:
            print(
                f"Hashtag recorder: Discarded take and removed {removed} camera buffers",
                flush=True,
            )
        return result

    clear_episode_with_camera_cleanup._hashtag_discards_video_staging = True  # type: ignore[attr-defined]
    dataset_class.clear_episode_buffer = clear_episode_with_camera_cleanup


def _install_camera_quality_gate(module: Any) -> None:
    """Reject a take if an AVFoundation helper restarted while it was recorded.

    Reopening only the affected camera keeps teleoperation alive and prevents
    stale images from being paired with newer actions.  It still creates a
    wall-clock discontinuity, however, so imitation-learning data must not be
    accepted silently.  Upstream's existing rerecord path performs the actual
    buffer and camera-staging cleanup after the operator ends the take.
    """
    from hashtag_robotics.avfoundation_uid import camera_incident_generation

    original: Callable[..., Any] = module.record_loop
    if getattr(original, "_hashtag_camera_quality_gate", False):
        return

    def camera_guarded_record_loop(*args: Any, **kwargs: Any) -> Any:
        dataset = kwargs.get("dataset")
        events = kwargs.get("events")
        before = camera_incident_generation()
        result = original(*args, **kwargs)
        after = camera_incident_generation()
        if dataset is not None and after > before and isinstance(events, dict):
            episode = int(dataset.num_episodes)
            events["rerecord_episode"] = True
            print(
                "Hashtag recorder: Camera incident invalidated episode "
                f"{episode}; take will be discarded and re-recorded",
                flush=True,
            )
        return result

    camera_guarded_record_loop._hashtag_camera_quality_gate = True  # type: ignore[attr-defined]
    module.record_loop = camera_guarded_record_loop


def _install_manual_recording_control(module: Any) -> None:
    """Make both take and reset boundaries depend only on operator input.

    LeRobot's numeric durations are useful for unattended collection but are a
    dangerous fallback in this dashboard: an expired reset timer saves a take
    and starts the next one while the operator is still arranging the board.
    An infinite loop duration remains interruptible through the normal Space,
    rerecord, stop, cancellation, and emergency-stop channels.
    """
    original: Callable[..., Any] = module.record_loop
    if getattr(original, "_hashtag_manual_recording_control", False):
        return

    def manual_record_loop(*args: Any, **kwargs: Any) -> Any:
        dataset = kwargs.get("dataset")
        kwargs["control_time_s"] = float("inf")
        if dataset is None:
            print(
                "Hashtag recorder: Manual reset gate armed; press SPACE to save and continue",
                flush=True,
            )
        else:
            print(
                "Hashtag recorder: Manual take gate armed; press SPACE to end this take",
                flush=True,
            )
        return original(*args, **kwargs)

    manual_record_loop._hashtag_manual_recording_control = True  # type: ignore[attr-defined]
    module.record_loop = manual_record_loop


def _install_episode_tasks(module: Any, tasks: list[str]) -> None:
    """Give upstream LeRobot one task per durable episode.

    The task cursor must follow ``dataset.num_episodes``, not calls to
    ``record_loop``.  A take can be rejected while the reset loop is active;
    in that case the recording loop has already returned but no episode was
    saved.  Advancing on loop return shifted every later label by one and made
    the final planned task unreachable.
    """
    original: Callable[..., Any] = module.record_loop
    dataset_start: int | None = None

    def planned_record_loop(*args: Any, **kwargs: Any) -> Any:
        nonlocal dataset_start
        dataset = kwargs.get("dataset")
        if dataset is None:
            return original(*args, **kwargs)
        if dataset_start is None:
            dataset_start = int(dataset.num_episodes)
        task_index = int(dataset.num_episodes) - dataset_start
        if task_index >= len(tasks):
            raise RuntimeError(
                "The recorder requested more episodes than the loaded plan contains."
            )

        kwargs["single_task"] = tasks[task_index]
        print(
            f"Planned task {task_index + 1}/{len(tasks)}: {tasks[task_index]}",
            flush=True,
        )
        return original(*args, **kwargs)

    module.record_loop = planned_record_loop


def _install_rollout_episode_tasks(
    strategy_class: type,
    tasks: list[str],
    *,
    unbounded: bool = False,
) -> None:
    """Change both inference prompt and dataset label after each accepted move.

    Upstream's episodic strategy reads ``single_task`` once before its episode
    loop.  Changing only the frame label would therefore create plausible
    metadata while the policy kept receiving the first move forever.  The sync
    and RTC engines keep the active language instruction in ``_task``; update
    that value at the same durable episode boundary used by the recorder.

    ``dataset.num_episodes`` advances only after ``save_episode()``, so a
    rejected/re-recorded take keeps the same move.  When ``unbounded`` is set,
    the operator's Right/q controls become the only ordinary episode boundary.
    """
    original: Callable[..., Any] = strategy_class._policy_loop
    if getattr(original, "_hashtag_rollout_episode_tasks", False):
        return

    dataset_start: int | None = None

    def planned_policy_loop(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal dataset_start
        dataset = kwargs.get("dataset")
        if dataset is None:
            return original(self, *args, **kwargs)
        if dataset_start is None:
            dataset_start = int(dataset.num_episodes)
        task_index = int(dataset.num_episodes) - dataset_start
        if task_index >= len(tasks):
            raise RuntimeError(
                "The rollout requested more episodes than the loaded game plan contains."
            )

        task = tasks[task_index]
        engine = getattr(self, "_engine", None)
        if engine is None or not hasattr(engine, "_task"):
            raise RuntimeError("The active rollout engine cannot change tasks between moves.")
        engine._task = task
        kwargs["single_task"] = task
        if unbounded:
            kwargs["control_time_s"] = float("inf")
        print(f"Game move {task_index + 1}/{len(tasks)}: {task}", flush=True)
        return original(self, *args, **kwargs)

    planned_policy_loop._hashtag_rollout_episode_tasks = True  # type: ignore[attr-defined]
    strategy_class._policy_loop = planned_policy_loop


def _install_async_chunk_append_compat() -> None:
    """Silence an inapplicable delay warning in non-guided async mode.

    ``ActionQueue.merge`` appends the complete new chunk when RTC guidance is
    disabled, so its inference-delay value is intentionally unused. LeRobot
    0.6.1 still compares that estimated delay with the concurrently consumed
    action count and warns on harmless one-frame scheduler differences. Keep
    the validation unchanged for real RTC replacement mode and bypass it only
    for append mode.
    """
    from lerobot.policies.rtc.action_queue import ActionQueue

    original: Callable[..., int] = ActionQueue._check_and_resolve_delays
    if getattr(original, "_hashtag_async_chunk_append", False):
        return

    def check_delay_for_queue_mode(
        queue: Any,
        real_delay: int,
        action_index_before_inference: int | None = None,
    ) -> int:
        if not queue.cfg.enabled:
            return max(0, real_delay)
        return original(queue, real_delay, action_index_before_inference)

    check_delay_for_queue_mode._hashtag_async_chunk_append = True  # type: ignore[attr-defined]
    ActionQueue._check_and_resolve_delays = check_delay_for_queue_mode


def _move_robot_to_ttt_demo_pose(
    ctx: Any,
    target: dict[str, float],
    *,
    duration_s: float = 5.0,
    fps: int = 50,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, float]:
    """Move to a recorded demonstration start pose and return final errors.

    The move happens before policy inference and before episode recording.  A
    dense joint-space interpolation plus the follower's existing relative
    target clamp avoids issuing a single large servo goal.  The caller must
    keep the sweep volume clear, as required by the terminal HOME gate.
    """
    robot = ctx.hardware.robot_wrapper
    current_obs = robot.get_observation()
    current = {key: float(current_obs[key]) for key in target}

    largest_delta = max(abs(target[key] - current[key]) for key in target)
    if largest_delta > 120.0:
        raise RuntimeError(
            "Demo home move refused: a joint is more than 120 degrees from its target. "
            "Power down and place the arm near its normal upright start pose first."
        )

    steps = max(int(duration_s * fps), 1)
    for step in range(1, steps + 1):
        if should_stop is not None and should_stop():
            raise InterruptedError("operator stopped demo homing")
        ratio = step / steps
        interpolated = {key: current[key] * (1 - ratio) + target[key] * ratio for key in target}
        robot.send_action(interpolated)
        time.sleep(1 / fps)

    final_obs = robot.get_observation()
    return {key: abs(float(final_obs[key]) - target[key]) for key in target}


def _hold_current_ttt_pose_for_shutdown(ctx: Any, target_keys: tuple[str, ...]) -> None:
    """Prevent teardown from retracing an interrupted or failed homing path."""
    try:
        observation = ctx.hardware.robot_wrapper.get_observation()
        ctx.hardware.initial_position = {
            key: float(observation[key]) for key in target_keys if key in observation
        }
    except Exception:
        # The teardown path still disconnects the robot. If observation itself
        # failed, retaining the startup pose is the only available fallback.
        pass


def _print_ttt_board(title: str, board: str) -> None:
    print(title, flush=True)
    for row in board.split("/"):
        print(f"  {row}", flush=True)


def _install_ttt_demo_preset(strategy_class: type, preset: dict[str, Any]) -> None:
    """Gate rollout on an in-distribution board and demonstration start pose.

    The 65-episode training set contains only a handful of examples for each
    cell, with specific board states and arm poses.  Standalone evaluation must
    recreate one of those states; otherwise this checkpoint converges to an
    idle pose instead of beginning the pick.  Homing is performed before the
    episode starts.  The operator then arranges the displayed board and presses
    Right/n to begin inference, or q to abort and disconnect.
    """
    original: Callable[..., Any] = strategy_class.run
    if getattr(original, "_hashtag_ttt_demo_preset", False):
        return

    def run_with_demo_preset(self: Any, ctx: Any, *args: Any, **kwargs: Any) -> Any:
        events = getattr(self, "_events", None)
        if not isinstance(events, dict):
            raise RuntimeError("Tic-tac-toe demo setup requires terminal keyboard controls.")

        target = preset["start_pose"]
        print(
            f"Demo episode {preset['episode_index']} başlangıç pozuna 5 saniyede gidiliyor...",
            flush=True,
        )
        try:
            errors = _move_robot_to_ttt_demo_pose(
                ctx,
                target,
                should_stop=lambda: events["stop_recording"] or ctx.runtime.shutdown_event.is_set(),
            )
        except Exception as error:
            print(f"Demo homing başarısız: {error}", flush=True)
            _hold_current_ttt_pose_for_shutdown(ctx, tuple(target))
            events["stop_recording"] = True
            return original(self, ctx, *args, **kwargs)

        worst_error = max(errors.values(), default=0.0)
        if worst_error > 3.0:
            details = ", ".join(f"{key}={value:.1f}°" for key, value in errors.items())
            print(
                f"Demo homing doğrulaması başarısız (maksimum hata {worst_error:.1f}°): {details}",
                flush=True,
            )
            _hold_current_ttt_pose_for_shutdown(ctx, tuple(target))
            events["stop_recording"] = True
            return original(self, ctx, *args, **kwargs)

        # This is now the real home for reset and q/Right shutdown behavior.
        ctx.hardware.initial_position = dict(target)
        print(f"Demo home hazır (maksimum eklem hatası {worst_error:.1f}°).", flush=True)
        _print_ttt_board("TOP KAMERA görünümünde tahtayı aynen kur:", preset["board_camera"])
        _print_ttt_board("Robot/model yönündeki karşılığı:", preset["board_robot"])
        print(
            "İstenen taşı kaynak alana koy. Hazır olunca sağ ok veya n; iptal için q.",
            flush=True,
        )

        events["exit_early"] = False
        events["rerecord_episode"] = False
        while not events["stop_recording"] and not ctx.runtime.shutdown_event.is_set():
            if events["rerecord_episode"]:
                events["rerecord_episode"] = False
                events["exit_early"] = False
                print("Başlatmak için sağ ok veya n kullan; iptal için q.", flush=True)
            elif events["exit_early"]:
                events["exit_early"] = False
                print("Tahta onaylandı; model inference başlıyor.", flush=True)
                break
            time.sleep(0.05)

        return original(self, ctx, *args, **kwargs)

    run_with_demo_preset._hashtag_ttt_demo_preset = True  # type: ignore[attr-defined]
    strategy_class.run = run_with_demo_preset


def rollout_main() -> None:
    _register_camera()
    from lerobot.rollout.strategies.episodic import EpisodicStrategy
    from lerobot.scripts.lerobot_rollout import main

    # This command is intentionally terminal-operated: Right accepts the
    # current move and q saves/exits.  Do not let a process-global macOS key
    # hook steal those controls from the terminal that launched the rollout.
    _force_terminal_recording_controls()
    if os.environ.get(ASYNC_CHUNK_APPEND_ENV) == "1":
        _install_async_chunk_append_compat()
    raw_preset = os.environ.get(TTT_DEMO_PRESET_ENV)
    if raw_preset:
        _install_ttt_demo_preset(EpisodicStrategy, _decode_ttt_demo_preset(raw_preset))
    raw_tasks = os.environ.get(ROLLOUT_EPISODE_TASKS_ENV)
    if raw_tasks:
        _install_rollout_episode_tasks(
            EpisodicStrategy,
            _decode_episode_tasks(raw_tasks),
            unbounded=os.environ.get(UNBOUNDED_ROLLOUT_ENV) == "1",
        )

    _seed_rollout_from_env()
    main()
