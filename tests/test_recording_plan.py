from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from hashtag_robotics.api import create_app
from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import DatasetStore
from hashtag_robotics.lerobot_wrappers import (
    _decode_episode_tasks,
    _decode_ttt_demo_preset,
    _install_async_chunk_append_compat,
    _install_camera_quality_gate,
    _install_discard_cleanup,
    _install_episode_tasks,
    _install_manual_recording_control,
    _install_recording_lifecycle,
    _install_rollout_episode_tasks,
    _install_ttt_demo_preset,
    _seed_rollout_from_env,
)
from hashtag_robotics.recording_plan import RecordingPlanError, parse_recording_roadmap
from hashtag_robotics.repository import Repository


def mini_board(classes: list[str]) -> str:
    return '<div class="mb">' + "".join(f'<i class="{name}"></i>' for name in classes) + "</div>"


GAME_HTML = f"""
<details class="game" data-done="0">
  <summary><span class="gname">Oyun 1</span><span class="grange">blok A · #001–#002</span></summary>
  <div class="reset-note">Tahta tamamen boş.</div>
  <label class="ep"><input type="checkbox" data-id="1">
    {mini_board(["", "", "t", "", "", "", "", "", ""])}
    <button class="cmdline">put the red X in the top right cell</button>
    <span class="chip cube"><span class="dot x"></span>X3 · sağ üst</span>
    <span class="chip leave">bırak</span>
  </label>
  <label class="ep"><input type="checkbox" data-id="2">
    {mini_board(["", "", "x", "", "t", "", "", "", ""])}
    <button class="cmdline">put the white O in the middle center cell</button>
    <span class="chip cube"><span class="dot o"></span>O5 · merkez</span>
    <span class="chip undo">geri al</span>
  </label>
</details>
"""


def test_the_html_roadmap_becomes_an_ordered_episode_queue() -> None:
    roadmap = parse_recording_roadmap("roadmap.html", GAME_HTML)

    assert roadmap.total_episodes == 2
    assert roadmap.games[0].block == "A"
    assert [episode.instruction for episode in roadmap.games[0].episodes] == [
        "put the red X in the top right cell",
        "put the white O in the middle center cell",
    ]
    assert roadmap.games[0].episodes[0].board_before == ".../.../..."
    assert roadmap.games[0].episodes[1].board_before == "..X/.../..."
    assert roadmap.games[0].episodes[1].after == "undo"
    assert roadmap.games[0].episodes[1].piece == "white O"
    assert roadmap.games[0].episodes[1].target_cell == "middle center"


def test_a_broken_mini_board_is_rejected() -> None:
    with pytest.raises(RecordingPlanError, match="9 yerine 8"):
        parse_recording_roadmap("bad.html", GAME_HTML.replace('<i class="t"></i>', "", 1))


def test_the_plan_parser_is_available_over_the_local_api(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(_env_file=None, data_dir=tmp_path, open_browser=False)),
        base_url="http://localhost",
    )
    client.get("/api/session")

    response = client.post(
        "/api/recording-plans/parse",
        json={"source_name": "roadmap.html", "content": GAME_HTML},
    )

    assert response.status_code == 200
    assert response.json()["games"][0]["episodes"][0]["global_episode"] == 1


def test_the_wrapper_changes_task_only_after_an_accepted_take() -> None:
    calls: list[str] = []
    dataset = SimpleNamespace(num_episodes=7)

    def original(*_args, **kwargs):
        calls.append(kwargs["single_task"])

    module = SimpleNamespace(record_loop=original)
    _install_episode_tasks(module, ["first", "second"])

    # Re-entering the recording loop without a durable save keeps the task,
    # even if the operator rejected it during the intervening reset loop.
    module.record_loop(dataset=dataset, events={}, single_task="fallback")
    module.record_loop(dataset=None, events={}, single_task="reset")
    module.record_loop(dataset=dataset, events={}, single_task="fallback")
    dataset.num_episodes += 1
    module.record_loop(dataset=dataset, events={}, single_task="fallback")

    assert calls == ["first", "reset", "first", "second"]


def test_dashboard_recording_boundaries_wait_indefinitely_for_operator_input() -> None:
    calls: list[tuple[object, float]] = []

    def original(*_args, **kwargs):
        calls.append((kwargs.get("dataset"), kwargs["control_time_s"]))

    module = SimpleNamespace(record_loop=original)
    _install_manual_recording_control(module)
    dataset = SimpleNamespace(num_episodes=2)

    module.record_loop(dataset=dataset, control_time_s=600)
    module.record_loop(dataset=None, control_time_s=600)

    assert calls == [(dataset, float("inf")), (None, float("inf"))]


def test_rollout_game_plan_changes_inference_and_label_only_after_an_accepted_move() -> None:
    calls: list[tuple[str, str, float]] = []

    class Strategy:
        def _policy_loop(self, *_args, **kwargs):
            calls.append((self._engine._task, kwargs["single_task"], kwargs["control_time_s"]))

    _install_rollout_episode_tasks(Strategy, ["X center", "O bottom"], unbounded=True)
    strategy = Strategy()
    strategy._engine = SimpleNamespace(_task="fallback")
    dataset = SimpleNamespace(num_episodes=4)

    strategy._policy_loop(dataset=dataset, single_task="fallback", control_time_s=5)
    # A re-record has not advanced the durable dataset episode, so it remains X.
    strategy._policy_loop(dataset=dataset, single_task="fallback", control_time_s=5)
    dataset.num_episodes += 1
    strategy._policy_loop(dataset=dataset, single_task="fallback", control_time_s=5)

    assert calls == [
        ("X center", "X center", float("inf")),
        ("X center", "X center", float("inf")),
        ("O bottom", "O bottom", float("inf")),
    ]


def test_rollout_game_plan_refuses_to_reuse_the_last_move_silently() -> None:
    class Strategy:
        def _policy_loop(self, *_args, **_kwargs):
            return None

    _install_rollout_episode_tasks(Strategy, ["only move"])
    strategy = Strategy()
    strategy._engine = SimpleNamespace(_task="fallback")
    dataset = SimpleNamespace(num_episodes=8)

    strategy._policy_loop(dataset=dataset, single_task="fallback", control_time_s=5)
    dataset.num_episodes += 1
    with pytest.raises(RuntimeError, match="more episodes"):
        strategy._policy_loop(dataset=dataset, single_task="fallback", control_time_s=5)


def test_async_append_mode_ignores_unused_delay_mismatch_without_affecting_rtc(caplog) -> None:
    from lerobot.policies.rtc.action_queue import ActionQueue
    from lerobot.policies.rtc.configuration_rtc import RTCConfig

    _install_async_chunk_append_compat()

    append_queue = ActionQueue(RTCConfig(enabled=False))
    append_queue.last_index = 7
    assert append_queue._check_and_resolve_delays(8, 0) == 8
    assert "Indexes diff" not in caplog.text

    rtc_queue = ActionQueue(RTCConfig(enabled=True))
    rtc_queue.last_index = 7
    assert rtc_queue._check_and_resolve_delays(8, 0) == 8
    assert "Indexes diff is not equal to real delay" in caplog.text


def test_checkpoint_sweep_seed_is_applied_to_rollout_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setenv("HASHTAG_ROLLOUT_SEED", "42")
    monkeypatch.setattr("lerobot.utils.random_utils.set_seed", calls.append)

    assert _seed_rollout_from_env() == 42
    assert calls == [42]


def test_ttt_demo_preset_homes_then_waits_for_operator_before_rollout(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    calls: list[str] = []

    class Strategy:
        def run(self, ctx) -> None:
            calls.append("run")

    preset = _decode_ttt_demo_preset(
        json.dumps(
            {
                "episode_index": 45,
                "board_robot": ".../OXO/...",
                "board_camera": ".../OXO/...",
                "start_pose": [-2.5, -54.4, 13.8, 100.2, 5.3, 1.3],
            }
        )
    )
    _install_ttt_demo_preset(Strategy, preset)
    strategy = Strategy()
    strategy._events = {
        "exit_early": False,
        "rerecord_episode": False,
        "stop_recording": False,
    }
    ctx = SimpleNamespace(
        hardware=SimpleNamespace(initial_position={"old.pos": 1.0}),
        runtime=SimpleNamespace(shutdown_event=SimpleNamespace(is_set=lambda: False)),
    )
    monkeypatch.setattr(
        "hashtag_robotics.lerobot_wrappers._move_robot_to_ttt_demo_pose",
        lambda _ctx, target, **_kwargs: {key: 0.2 for key in target},
    )

    def release_setup_gate(_seconds: float) -> None:
        strategy._events["exit_early"] = True

    monkeypatch.setattr("hashtag_robotics.lerobot_wrappers.time.sleep", release_setup_gate)

    strategy.run(ctx)

    assert calls == ["run"]
    assert ctx.hardware.initial_position == preset["start_pose"]
    output = capsys.readouterr().out
    assert "TOP KAMERA" in output
    assert "model inference başlıyor" in output


def test_ttt_demo_preset_rejects_malformed_pose_or_board() -> None:
    with pytest.raises(ValueError, match="six joints"):
        _decode_ttt_demo_preset(
            json.dumps(
                {
                    "episode_index": 1,
                    "board_robot": ".../.../...",
                    "board_camera": ".../.../...",
                    "start_pose": [1, 2],
                }
            )
        )

    with pytest.raises(ValueError, match="3x3 board"):
        _decode_ttt_demo_preset(
            json.dumps(
                {
                    "episode_index": 1,
                    "board_robot": "bad",
                    "board_camera": ".../.../...",
                    "start_pose": [1, 2, 3, 4, 5, 6],
                }
            )
        )


def test_a_camera_restart_marks_only_the_active_take_for_rerecord(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generations = iter((4, 5))
    monkeypatch.setattr(
        "hashtag_robotics.avfoundation_uid.camera_incident_generation",
        lambda: next(generations),
    )
    events = {"rerecord_episode": False}
    dataset = SimpleNamespace(num_episodes=9)

    module = SimpleNamespace(record_loop=lambda *_args, **_kwargs: None)
    _install_camera_quality_gate(module)
    module.record_loop(dataset=dataset, events=events)

    assert events["rerecord_episode"] is True


def test_a_camera_restart_during_reset_does_not_reject_the_next_take(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generations = iter((10, 11))
    monkeypatch.setattr(
        "hashtag_robotics.avfoundation_uid.camera_incident_generation",
        lambda: next(generations),
    )
    events = {"rerecord_episode": False}

    module = SimpleNamespace(record_loop=lambda *_args, **_kwargs: None)
    _install_camera_quality_gate(module)
    module.record_loop(dataset=None, events=events)

    assert events["rerecord_episode"] is False


def test_episode_task_environment_requires_a_non_empty_json_list() -> None:
    assert _decode_episode_tasks(json.dumps(["one", "two"])) == ["one", "two"]
    with pytest.raises(ValueError, match="non-empty"):
        _decode_episode_tasks("[]")


def test_the_wrapper_reports_when_an_episode_is_encoding_and_durable(capsys) -> None:
    class Dataset:
        def __init__(self) -> None:
            self.num_episodes = 4

        def save_episode(self) -> str:
            self.num_episodes += 1
            return "saved"

    module = SimpleNamespace(LeRobotDataset=Dataset)
    _install_recording_lifecycle(module)

    assert Dataset().save_episode() == "saved"
    assert capsys.readouterr().out.splitlines() == [
        "Hashtag recorder: Encoding episode 4",
        "Hashtag recorder: Saved episode 4",
    ]


def test_rejecting_a_take_removes_video_camera_staging(tmp_path: Path, capsys) -> None:
    class Writer:
        def __init__(self) -> None:
            self.episode_buffer = {"episode_index": 9}
            self.waited = False

        def _wait_image_writer(self) -> None:
            self.waited = True

        def _get_image_file_dir(self, episode_index: int, camera_key: str) -> Path:
            return tmp_path / camera_key / f"episode-{episode_index:06d}"

    class Dataset:
        def __init__(self) -> None:
            self.writer = Writer()
            self.meta = SimpleNamespace(
                camera_keys=["observation.images.top", "observation.images.wrist"]
            )
            for camera_key in self.meta.camera_keys:
                directory = self.writer._get_image_file_dir(9, camera_key)
                directory.mkdir(parents=True)
                (directory / "frame-000000.png").touch()

        def clear_episode_buffer(self, delete_images: bool = True) -> str:
            return "cleared"

    module = SimpleNamespace(LeRobotDataset=Dataset)
    _install_discard_cleanup(module)
    dataset = Dataset()

    assert dataset.clear_episode_buffer() == "cleared"
    assert dataset.writer.waited is True
    assert all(
        not dataset.writer._get_image_file_dir(9, camera_key).exists()
        for camera_key in dataset.meta.camera_keys
    )
    assert "removed 2 camera buffers" in capsys.readouterr().out


def test_game_metadata_is_written_as_a_dataset_episode_sidecar(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "app", open_browser=False)
    store = DatasetStore(settings, Repository(settings.database_path))
    root = tmp_path / "dataset"

    path = store.write_episode_plan(
        root,
        [
            {
                "global_episode": 14,
                "game": 2,
                "block": "A",
                "instruction": "put the white O in the middle right cell",
            }
        ],
        dataset_episode_start=13,
    )

    row = json.loads(path.read_text())
    assert row["dataset_episode_index"] == 13
    assert row["global_episode"] == 14
    assert row["game"] == 2
