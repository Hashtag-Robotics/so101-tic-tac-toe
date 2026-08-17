"""Driving the simulated arm with the real leader, and recording what it does.

The point of simulation here is not to watch an arm move. It is to collect
demonstrations without needing the follower, the workspace or the operator's
whole afternoon -- and then to train on them together with real ones.

That last word is what shapes this module. Co-training only works if the two
datasets speak the same language, and on this machine they did not:

    real  so101_hil_t7_kamerali   state/action named `shoulder_pan.pos`, LeRobot
                                  normalised units (-100..100), images [H,W,3]
    sim   so101_sim_cube_teleop   state/action named `1`..`6`, radians,
                                  images [3,H,W]

Three separate mismatches, none of which raises anything; a policy trained on
both would simply learn less than it should. So a recording made here is written
in the *real* convention, and the trick that makes it free is that the leader is
the same physical arm in both cases: its action is already normalised, and the
simulated joint angles are converted back through the inverse of the mapping
that drove them.

The mapping itself comes from `so101-sim-lab/ornekler/08_teleop_sim.py`, where
the units were confirmed against the hardware rather than assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hashtag_robotics.simulation import JOINT_NAMES, SimulationError

# LeRobot addresses the leader as `<joint>.pos`; the generated SO-101 model names
# its joints "1".."6" in the same order.
LEADER_KEYS = tuple(f"{name}.pos" for name in JOINT_NAMES)
SIM_JOINTS = ("1", "2", "3", "4", "5", "6")

GRIPPER_KEY = "gripper.pos"
# The sim gripper joint's own limits, which the leader's 0..100 maps onto.
GRIPPER_RANGE_RAD = (-0.175, 1.745)

# On the real follower the gripper is carried sideways so the wrist camera can
# see the table; the simulated model's roll zero is upright. This closes the gap.
DEFAULT_OFFSETS_DEG = {"wrist_roll.pos": -90.0}

# No affine by default, and the reason is worth keeping.
#
# There used to be one for `shoulder_lift`: (-57.9, 152.0) -> (-100, 100),
# measured when that leader's calibration midpoint sat well forward of centre.
# It was measured against a calibration that was later replaced, and a leader
# reports normalised units *relative to its calibration* -- so after the swap
# the correction was applied to numbers that no longer needed it. Measured on
# the bench: leader -100 became -140.1 degrees against a joint that stops at
# -100, and the arm sat pinned against its own limit for most of a session
# while the recording kept writing the angle it never reached.
#
# Calibration already normalises each joint to +-100, which is the whole point
# of it, and the simulated shoulder_lift's range is exactly +-100. Nothing is
# left to correct. Verified against 81 episodes of real-arm data: every joint
# stayed inside +-100.
#
# The mechanism stays, because one arm may genuinely differ from another --
# `LeaderMapping.for_profile` reads it from the teleoperator profile. What is
# gone is a single arm's numbers baked in as everyone's default.
DEFAULT_AFFINE_DEG: dict[str, tuple[float, float, float, float]] = {}


@dataclass(frozen=True)
class LeaderMapping:
    """How one physical leader's readings become simulated joint targets."""

    offsets_deg: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_OFFSETS_DEG))
    affine_deg: dict[str, tuple[float, float, float, float]] = field(
        default_factory=lambda: dict(DEFAULT_AFFINE_DEG)
    )
    inverted: frozenset[str] = frozenset()
    gripper_range_rad: tuple[float, float] = GRIPPER_RANGE_RAD

    @classmethod
    def for_profile(cls, mapping: dict[str, Any] | None) -> LeaderMapping:
        """Take whatever the teleoperator profile recorded, fall back to measured."""
        if not mapping:
            return cls()
        affine = {
            key: tuple(float(value) for value in values)
            for key, values in (mapping.get("affine_deg") or {}).items()
        }
        return cls(
            offsets_deg={
                key: float(value) for key, value in (mapping.get("offsets_deg") or {}).items()
            },
            affine_deg=affine or dict(DEFAULT_AFFINE_DEG),
            inverted=frozenset(mapping.get("inverted") or ()),
        )

    def to_sim(self, action: dict[str, float]) -> list[float]:
        """Leader reading -> six simulated joint targets in radians."""
        targets = [0.0] * len(SIM_JOINTS)
        for index, key in enumerate(LEADER_KEYS):
            if key not in action:
                continue
            if key == GRIPPER_KEY:
                low, high = self.gripper_range_rad
                targets[index] = low + (float(action[key]) / 100.0) * (high - low)
                continue
            degrees = float(action[key]) + self.offsets_deg.get(key, 0.0)
            if key in self.affine_deg:
                leader_min, leader_max, sim_min, sim_max = self.affine_deg[key]
                span = leader_max - leader_min
                if span:
                    degrees = sim_min + (degrees - leader_min) * (sim_max - sim_min) / span
            radians = math.radians(degrees)
            if key in self.inverted:
                radians = -radians
            targets[index] = radians
        return targets

    def to_leader_units(self, radians: list[float]) -> list[float]:
        """The inverse: simulated joint angles back into the leader's own units.

        This is what makes a simulated recording co-trainable with a real one.
        `observation.state` in a real dataset is the follower reported in
        normalised units; here it is the simulated joint reported in the same
        units, so a policy sees one number line instead of two.
        """
        values: list[float] = []
        for index, key in enumerate(LEADER_KEYS):
            radian = float(radians[index]) if index < len(radians) else 0.0
            if key == GRIPPER_KEY:
                low, high = self.gripper_range_rad
                span = high - low
                values.append(((radian - low) / span * 100.0) if span else 0.0)
                continue
            if key in self.inverted:
                radian = -radian
            degrees = math.degrees(radian)
            if key in self.affine_deg:
                leader_min, leader_max, sim_min, sim_max = self.affine_deg[key]
                span = sim_max - sim_min
                if span:
                    degrees = leader_min + (degrees - sim_min) * (leader_max - leader_min) / span
            values.append(degrees - self.offsets_deg.get(key, 0.0))
        return values


def dataset_features(cameras: dict[str, tuple[int, int]]) -> dict[str, Any]:
    """The schema of a recording, matching what the real arm writes.

    Names and layout are copied from a real SO-101 recording on purpose --
    `<joint>.pos`, `[height, width, channels]` -- because the whole reason to
    record in simulation is to train on both together.
    """
    features: dict[str, Any] = {
        "action": {"dtype": "float32", "shape": (len(LEADER_KEYS),), "names": list(LEADER_KEYS)},
        "observation.state": {
            "dtype": "float32",
            "shape": (len(LEADER_KEYS),),
            "names": list(LEADER_KEYS),
        },
    }
    for name, (width, height) in cameras.items():
        features[f"observation.images.{name}"] = {
            "dtype": "video",
            "shape": (height, width, 3),
            "names": ["height", "width", "channels"],
        }
    return features


class SimArm:
    """The simulated follower: take joint targets, step physics, report back."""

    def __init__(self, scene: Any, width: int = 640, height: int = 480) -> None:
        import mujoco

        self.scene = scene
        self.model = scene.model
        self.data = scene.data
        self.width = width
        self.height = height
        self._renderer = mujoco.Renderer(self.model, height=height, width=width)
        self.physics_hz = round(1 / self.model.opt.timestep)

    @property
    def cameras(self) -> dict[str, tuple[int, int]]:
        return {name: (self.width, self.height) for name in self.scene.camera_names}

    def apply(self, targets: list[float]) -> list[float]:
        """Drive the joints, and report back what the model actually accepted.

        MuJoCo does not refuse a command outside a joint's range and does not
        clamp it either -- `actuator_ctrllimited` is off on this model -- it
        just pushes the joint against its stop. The arm ends up somewhere other
        than where it was told, and a recording that stored the asked-for value
        would claim an angle the arm never reached.

        So the command is clamped here, and the clamped value is what gets
        recorded. The last few degrees of the leader's travel become a dead zone
        in simulation, which is true and visible, rather than a number in a
        dataset that nothing produced.
        """
        accepted: list[float] = []
        for index, target in enumerate(targets[: self.model.nu]):
            joint = int(self.model.actuator_trnid[index][0])
            value = float(target)
            if self.model.jnt_limited[joint]:
                low, high = self.model.jnt_range[joint]
                value = min(max(value, float(low)), float(high))
            self.data.ctrl[index] = value
            accepted.append(value)
        return accepted

    def step(self, substeps: int) -> None:
        import mujoco

        for _ in range(max(1, substeps)):
            mujoco.mj_step(self.model, self.data)

    def joint_positions(self) -> list[float]:
        return [float(value) for value in self.data.qpos[: len(SIM_JOINTS)]]

    def frames(self) -> dict[str, Any]:
        images: dict[str, Any] = {}
        for name in self.scene.camera_names:
            self._renderer.update_scene(self.data, camera=name)
            images[name] = self._renderer.render()
        return images

    def body_position(self, name: str) -> list[float] | None:
        import mujoco

        body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
        if body < 0:
            return None
        return [float(value) for value in self.data.xpos[body]]

    def reset(self) -> None:
        import mujoco

        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)

    def close(self) -> None:
        self._renderer.close()


def cube_is_in_bin(arm: SimArm, xy_tolerance: float = 0.07, z_tolerance: float = 0.07) -> bool:
    """Did the episode succeed?

    Deliberately geometric and deliberately simple: an episode is worth keeping
    when the cube ended up over the bin floor. Anything cleverer would be a
    judgement the operator can make faster by looking.
    """
    cube = arm.body_position("cube")
    bin_floor = arm.body_position("bin")
    if cube is None or bin_floor is None:
        return False
    return (
        abs(cube[0] - bin_floor[0]) <= xy_tolerance
        and abs(cube[1] - bin_floor[1]) <= xy_tolerance
        and abs(cube[2] - bin_floor[2]) <= z_tolerance
    )


def open_leader(port: str, leader_id: str, calibration_dir: str | None) -> Any:
    """Connect to the physical leader that will drive the simulation."""
    from pathlib import Path

    from lerobot.teleoperators.so_leader import SOLeader, SOLeaderConfig

    config = SOLeaderConfig(port=port)
    # `id` and `calibration_dir` are read by `Teleoperator.__init__` but are not
    # constructor arguments of this config -- draccus fills them from the command
    # line, which is why every LeRobot example passes `--teleop.id=...`. Building
    # one in-process means setting them afterwards.
    config.id = leader_id
    config.calibration_dir = Path(calibration_dir) if calibration_dir else None
    leader = SOLeader(config)
    try:
        leader.connect(calibrate=False)
    except Exception as error:  # noqa: BLE001 - surfaced as a job failure, not a traceback
        raise SimulationError(f"The leader arm on '{port}' could not be opened: {error}") from error
    return leader


@dataclass
class RecordingPlan:
    """What to record. Mirrors the real recording job's parameters on purpose."""

    repo_id: str
    task: str
    tasks: list[str] | None = None
    root: str | None = None
    episodes: int = 1
    episode_time_s: float = 30.0
    reset_time_s: float = 3.0
    fps: int = 30
    width: int = 640
    height: int = 480
    keep_only_successes: bool = False


def _emit(message: str) -> None:
    """Speak the vocabulary the dashboard's telemetry parser already knows.

    `lerobot-record` prints `Recording episode N` and `Teleop loop time: X ms
    (Y Hz)`; matching those exactly means a simulated recording shows up in the
    live panel with no new parser and no new frontend.
    """
    print(message, flush=True)


def run_teleop(
    leader: Any,
    arm: SimArm,
    mapping: LeaderMapping,
    seconds: float | None,
    fps: int,
    live: LiveFrames | None = None,
    viewer: Any = None,
) -> dict[str, Any]:
    """Drive the simulated arm until its deadline or an operator interrupt.

    Nothing physical moves: the follower is not opened, and the leader is only
    read -- the same read that identification does. A simulated session cannot
    injure anybody or overload a servo, which is exactly why it is the right
    place to practise a task before recording it for real.
    """
    import time as _time

    period = 1 / max(1, fps)
    substeps = max(1, round(arm.physics_hz / max(1, fps)))
    deadline = None if seconds is None else _time.monotonic() + seconds
    loops: list[float] = []
    ticks = 0
    while deadline is None or _time.monotonic() < deadline:
        started = _time.monotonic()
        action = leader.get_action()
        targets = mapping.to_sim(action)
        arm.apply(targets)
        arm.step(substeps)
        if viewer is not None:
            viewer.sync()
        if live is not None:
            # A rehearsal renders nothing for a dataset, so this is the only
            # render it does -- and only when somebody is watching.
            live.offer(arm.frames()[arm.scene.camera_names[0]])
        elapsed = _time.monotonic() - started
        loops.append(elapsed * 1000)
        ticks += 1
        if ticks % max(1, fps) == 0:
            recent = sum(loops[-fps:]) / len(loops[-fps:])
            _emit(f"Teleop loop time: {recent:.2f} ms ({1000 / max(recent, 1e-6):.2f} Hz)")
        remaining = period - elapsed
        if remaining > 0:
            _time.sleep(remaining)
    average = sum(loops) / len(loops) if loops else 0.0
    return {"ticks": ticks, "mean_loop_ms": round(average, 3)}


# What an operator can ask for mid-recording.  LeRobot documents the one-byte
# n/r/q aliases specifically for reliable remote control; legacy arrow/Escape
# sequences remain accepted so older clients do not break.
END_EPISODE = "end_episode"
RERECORD_EPISODE = "rerecord_episode"
STOP_RECORDING = "stop_recording"

_SEQUENCES = {b"\x1b[C": END_EPISODE, b"\x1b[D": RERECORD_EPISODE}
_SINGLE_BYTES = {b"n": END_EPISODE, b"r": RERECORD_EPISODE, b"q": STOP_RECORDING}


def decode_episode_keys(buffer: bytes, *, flush: bool = False) -> tuple[list[str], bytes]:
    """Turn terminal bytes into requests, keeping what is not yet decidable.

    A lone escape means stop; an escape followed by `[C` means end this episode.
    Reading one byte at a time cannot tell them apart yet, so a trailing escape
    stays in the buffer until a later poll finds nothing after it -- that is
    what `flush` says. Guessing early would turn "next episode" into "stop
    recording", which is the one mistake here that loses a take.
    """
    actions: list[str] = []
    while buffer:
        single = _SINGLE_BYTES.get(buffer[0:1].lower())
        if single is not None:
            actions.append(single)
            buffer = buffer[1:]
            continue
        if buffer[0:1] != b"\x1b":
            buffer = buffer[1:]
            continue
        if len(buffer) >= 3 and buffer[0:3] in _SEQUENCES:
            actions.append(_SEQUENCES[buffer[0:3]])
            buffer = buffer[3:]
            continue
        if len(buffer) >= 3 or (len(buffer) >= 2 and buffer[1:2] != b"["):
            # An escape sequence this recorder does not answer to.
            buffer = buffer[3:] if len(buffer) >= 3 else b""
            continue
        if flush and len(buffer) == 1:
            actions.append(STOP_RECORDING)
            buffer = b""
            continue
        break
    return actions, buffer


class EpisodeKeyReader:
    """Non-blocking reader for the operator's mid-recording requests.

    The recording loop runs at the dataset's frame rate and must not wait on a
    key that may never come, so every poll takes whatever is already there and
    returns immediately.
    """

    def __init__(self, stream: Any = None) -> None:
        import sys

        self.stream = stream if stream is not None else sys.stdin
        self._buffer = b""
        self._quiet = False

    def poll(self) -> list[str]:
        import os
        import select

        try:
            fileno = self.stream.fileno()
        except (AttributeError, OSError, ValueError):
            return []
        chunk = b""
        try:
            while select.select([fileno], [], [], 0)[0]:
                piece = os.read(fileno, 64)
                if not piece:
                    break
                chunk += piece
        except OSError:
            return []
        self._buffer += chunk
        # Nothing new since the last poll: a trailing escape is now a lone one.
        actions, self._buffer = decode_episode_keys(self._buffer, flush=not chunk and self._quiet)
        self._quiet = not chunk
        return actions


def wait_for_episode_advance(keys: EpisodeKeyReader, seconds: float) -> bool:
    """Wait for Space/right-arrow during reset; return True only for stop."""
    import time as _time

    deadline = _time.monotonic() + max(0.0, seconds)
    while _time.monotonic() < deadline:
        for request in keys.poll():
            _emit_recording_control_ack(request)
            if request == STOP_RECORDING:
                return True
            if request == END_EPISODE:
                return False
        _time.sleep(0.05)
    return False


def _emit_recording_control_ack(request: str) -> None:
    """Use LeRobot's own messages so one telemetry parser serves both recorders."""
    if request == END_EPISODE:
        _emit("Right arrow key pressed. Exiting loop...")
    elif request == RERECORD_EPISODE:
        _emit("Left arrow key pressed. Exiting loop and rerecord the last episode...")
    elif request == STOP_RECORDING:
        _emit("Escape key pressed. Stopping data recording...")


def record(
    plan: RecordingPlan,
    leader: Any,
    arm: SimArm,
    mapping: LeaderMapping,
    live: LiveFrames | None = None,
    viewer: Any = None,
) -> dict[str, Any]:
    """Record demonstrations in simulation, in the real arm's dataset convention."""
    import time as _time

    import numpy as np
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    # Stamp the name the way `lerobot-record` does. Without it a second run of
    # the same task fails on an existing directory, and the salvage path then
    # re-registers the FIRST run's episodes as the second run's output -- the
    # exact silent-wrong-data shape that `resolve_recorded` exists to prevent.
    # `datetime.now()` and not utcnow: this has to match the format LeRobot
    # stamps and the dashboard parses, which is local time.
    stamped_repo_id = f"{plan.repo_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dataset = LeRobotDataset.create(
        repo_id=stamped_repo_id,
        fps=plan.fps,
        features=dataset_features(arm.cameras),
        root=plan.root,
        # The same string LeRobot writes for the physical arm, so the two
        # datasets do not differ on the one field a loader might branch on.
        robot_type="so_follower",
        use_videos=True,
    )

    period = 1 / max(1, plan.fps)
    substeps = max(1, round(arm.physics_hz / max(1, plan.fps)))
    saved = 0
    discarded = 0
    # The operator's three requests, read the way `lerobot-record` reads them so
    # one set of buttons drives both recorders. Without this a simulated session
    # ran to the end whatever happened: a take that went wrong at second three
    # still cost its full thirty, and there was no way to say so.
    keys = EpisodeKeyReader()
    episode = 0
    stopping = False
    while episode < plan.episodes and not stopping:
        _emit(f"Recording episode {episode}")
        arm.reset()
        rerecord = False
        deadline = _time.monotonic() + plan.episode_time_s
        frames = 0
        loops: list[float] = []
        while _time.monotonic() < deadline:
            started = _time.monotonic()
            ending = False
            for request in keys.poll():
                _emit_recording_control_ack(request)
                if request == RERECORD_EPISODE:
                    rerecord = True
                elif request == STOP_RECORDING:
                    stopping = True
                elif request == END_EPISODE:
                    ending = True
            if rerecord or stopping or ending:
                break

            action = leader.get_action()
            targets = mapping.to_sim(action)
            accepted = arm.apply(targets)
            arm.step(substeps)

            frame: dict[str, Any] = {
                # What the arm was actually told, not what the leader asked for.
                # The two differ only where the leader reaches past a simulated
                # joint's limit; recording the request there would store an
                # angle nothing produced. Converted back through the exact
                # inverse of the mapping, so it lands in the same units a real
                # recording stores and matches `observation.state` below.
                "action": np.asarray(mapping.to_leader_units(accepted), dtype=np.float32),
                "observation.state": np.asarray(
                    mapping.to_leader_units(arm.joint_positions()), dtype=np.float32
                ),
                # LeRobot 0.6 carries the task inside the frame, not beside it.
                "task": plan.tasks[episode] if plan.tasks else plan.task,
            }
            images = arm.frames()
            for name, image in images.items():
                frame[f"observation.images.{name}"] = image
            dataset.add_frame(frame)
            if viewer is not None:
                viewer.sync()
            if live is not None:
                # Already rendered for the dataset; publishing it costs a JPEG.
                live.offer(images[arm.scene.camera_names[0]])
            frames += 1

            elapsed = _time.monotonic() - started
            loops.append(elapsed * 1000)
            if frames % max(1, plan.fps) == 0:
                recent = sum(loops[-plan.fps :]) / len(loops[-plan.fps :])
                _emit(f"Teleop loop time: {recent:.2f} ms ({1000 / max(recent, 1e-6):.2f} Hz)")
            remaining = period - elapsed
            if remaining > 0:
                _time.sleep(remaining)

        if rerecord:
            # The operator's judgement, so the episode index does not advance:
            # they asked for this take again, not for the next one.
            dataset.clear_episode_buffer()
            discarded += 1
            _emit(f"Re-record episode {episode}: the operator asked for this take again")
            if plan.reset_time_s > 0:
                _emit("Reset the environment")
                stopping = wait_for_episode_advance(keys, plan.reset_time_s)
            continue

        succeeded = cube_is_in_bin(arm)
        if plan.keep_only_successes and not succeeded:
            dataset.clear_episode_buffer()
            discarded += 1
            _emit(f"Re-record episode {episode}: the cube did not reach the bin, so it was dropped")
        elif frames == 0:
            # Stopped before a single frame was written. Saving an empty episode
            # would put a zero-frame take in the dataset and call it a take.
            dataset.clear_episode_buffer()
            _emit(f"Episode {episode} had no frames, so nothing was saved")
        else:
            _emit(f"Hashtag recorder: Encoding episode {episode}")
            dataset.save_episode()
            saved += 1
            _emit(f"Hashtag recorder: Saved episode {episode}")
            _emit(f"Episode {episode} saved ({frames} frames, success={succeeded})")

        episode += 1
        if not stopping and episode < plan.episodes and plan.reset_time_s > 0:
            _emit("Reset the environment")
            stopping = wait_for_episode_advance(keys, plan.reset_time_s)

    if stopping:
        _emit(f"Stopped by the operator after {saved} episode(s)")

    # LeRobot's own words: "Must be called after data collection, otherwise
    # footer metadata won't be written to the parquet files and the dataset will
    # be invalid." A __del__ safety net exists, but this command ends with
    # os._exit(0) to dodge a Tegra GL crash -- and os._exit runs no finalisers.
    # The dataset surviving so far was refcounting luck, not design.
    dataset.finalize()
    _emit("Stop recording")
    return {
        "repo_id": stamped_repo_id,
        "episodes_saved": saved,
        "episodes_discarded": discarded,
        "stopped_by_operator": stopping,
        "root": str(dataset.root),
    }


class LiveFrames:
    """Publish what the driven simulation looks like, for whoever is watching.

    The recording process already renders every frame for the dataset. Without
    this, the panel had nothing to show and fell back to its own separate
    simulation running a canned trajectory -- so the operator watched an arm
    swinging by itself while their leader drove a different, invisible one.
    That is worse than showing nothing: it looks exactly like the whole thing
    being fake.

    Written atomically and rate-limited, because a viewer needs to see what is
    happening, not every frame of it.
    """

    def __init__(self, path: str | None, fps: float = 10.0) -> None:
        from pathlib import Path

        self.path = Path(path) if path else None
        self.interval = 1 / max(0.1, fps)
        self._last = 0.0
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def offer(self, image: Any) -> None:
        import time as _time

        if self.path is None:
            return
        now = _time.monotonic()
        if now - self._last < self.interval:
            return
        self._last = now
        try:
            import cv2

            ok, buffer = cv2.imencode(
                ".jpg", image[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), 75]
            )
            if not ok:
                return
            # Replace, never truncate-and-write: a reader must not be able to
            # catch half a frame.
            temporary = self.path.with_suffix(".tmp")
            temporary.write_bytes(buffer.tobytes())
            temporary.replace(self.path)
        except Exception:  # noqa: BLE001 - a viewer's convenience never fails a recording
            return

    def clear(self) -> None:
        if self.path is None:
            return
        with __import__("contextlib").suppress(OSError):
            self.path.unlink()


def open_session_viewer(arm: SimArm) -> Any:
    """Open MuJoCo's window onto the simulation this session is actually driving.

    Not a second simulation: the same model and the same data the leader is
    moving, which is the whole point. Returns a handle to sync each tick, or
    None when there is no desktop session to open a window on.
    """
    import os

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    try:
        import mujoco.viewer

        return mujoco.viewer.launch_passive(arm.model, arm.data)
    except Exception:  # noqa: BLE001 - a window is a convenience, not the job
        return None
