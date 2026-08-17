from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = ROOT / "ttt-rollouts"
CHECKPOINT_LAUNCHERS = ROOT / "ttt-checkpoints"
CHECKPOINT_MANIFEST = ROOT / "src" / "hashtag_robotics" / "ttt_checkpoint_sweep.json"
BASELINE_MANIFEST = ROOT / "src" / "hashtag_robotics" / "ttt_games_1_5_80k.json"
PRESETS = ROOT / "src" / "hashtag_robotics" / "ttt_training_presets.json"
CELLS = {
    1: "top left",
    2: "top center",
    3: "top right",
    4: "middle left",
    5: "middle center",
    6: "middle right",
    7: "bottom left",
    8: "bottom center",
    9: "bottom right",
}


def test_all_eighteen_tic_tac_toe_launchers_are_present_and_executable() -> None:
    expected = {f"{piece}-{cell}" for piece in ("X", "O") for cell in CELLS}
    actual = {path.name for path in LAUNCHERS.iterdir() if path.is_file()}

    assert actual == expected
    assert all(os.access(LAUNCHERS / name, os.X_OK) for name in expected)


def test_each_launcher_uses_the_exact_training_task_for_its_cell() -> None:
    for piece, object_name in (("X", "red X"), ("O", "white O")):
        for cell_number, cell_name in CELLS.items():
            name = f"{piece}-{cell_number}"
            source = (LAUNCHERS / name).read_text()

            assert f'TTT_RUN_LABEL="{name}"' in source
            assert f'TTT_SINGLE_TASK="put the {object_name} in the {cell_name} cell"' in source
            assert "run_ttt_recorded_rollout.zsh" in source


def test_single_cell_launchers_use_async_full_chunks_without_relaxing_the_safety_limit() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()

    assert '"--inference.type=rtc"' in runner
    assert '"--inference.queue_threshold=18"' in runner
    assert '"--inference.rtc.enabled=false"' in runner
    assert '"--inference.rtc.execution_horizon=10"' not in runner
    assert '"--inference.rtc.max_guidance_weight=10.0"' not in runner
    assert '"--robot.max_relative_target=5.0"' in runner
    assert 'rollout_inference_label="async full-chunk"' in runner
    assert "HASHTAG_ASYNC_CHUNK_APPEND=1" in runner


def test_runner_uses_the_pinned_games_1_15_checkpoint_sweep() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()
    manifest = json.loads(CHECKPOINT_MANIFEST.read_text())

    assert manifest["model_repo_id"] == "HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k"
    assert manifest["model_revision"] == "48a6313b7e4983781dd72919105ca691a77cd26c"
    assert manifest["expected_training_steps"] == 120000
    assert manifest["expected_batch_size"] == 16
    assert manifest["default_checkpoint"] == "120000"
    assert manifest["checkpoints"] == [
        "020000",
        "040000",
        "060000",
        "080000",
        "100000",
        "120000",
    ]
    assert manifest["checkpoint_path_template"] == ("checkpoints/{checkpoint}/pretrained_model")
    assert manifest["model_slug_template"] == "games_1_15_step_{checkpoint}"
    checkpoint_default = (
        'rollout_model_checkpoint="${TTT_MODEL_CHECKPOINT:-$rollout_default_checkpoint}"'
    )
    assert checkpoint_default in runner
    assert ".checkpoints | index($checkpoint) != null" in runner
    assert 'scripts/fetch_ttt_checkpoint.py"' in runner
    assert 'rollout_model_variant="${TTT_MODEL_VARIANT:-games-1-15}"' in runner
    assert "ttt_checkpoint_sweep.json" in runner
    assert "rollout_tic_tac_toe_${rollout_model_slug}" in runner


def test_runner_requires_a_portable_local_hardware_profile() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()
    profile = json.loads((ROOT / "config" / "ttt-hardware.example.json").read_text())

    assert "HASHTAG_TTT_HARDWARE_CONFIG" in runner
    assert ".local-data/ttt-hardware.json" in runner
    for key in (
        "robot_port",
        "robot_id",
        "calibration_dir",
        "camera_helper",
        "top_camera_uid",
        "wrist_camera_uid",
        "inference_device",
    ):
        assert key in profile
        assert f".{key}" in runner
    assert "/Users/" not in runner
    assert "/dev/cu.usbmodem" not in runner
    assert "0x110000" not in runner
    assert "0x120000" not in runner


def test_games_1_5_80k_has_a_separate_pinned_launcher_and_65_episode_contract() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()
    launcher = (ROOT / "scripts" / "run_ttt_games_1_5_80k.zsh").read_text()
    manifest = json.loads(BASELINE_MANIFEST.read_text())
    presets = json.loads(PRESETS.read_text())

    assert manifest["model_repo_id"] == ("HashtagRobotics/smolvla-tic-tac-toe-games-1-5-80k")
    assert manifest["model_revision"] == ("d65f5ec4f771b4e6d21c5be78ddc18af242895a6")
    assert manifest["dataset_revision"] == ("527021f455d6af0ae6e4a9be0e2bd665d21b05be")
    assert manifest["expected_episodes"] == 65
    assert manifest["expected_training_steps"] == 80000
    assert manifest["expected_batch_size"] == 16
    assert manifest["checkpoint_path_template"] == "."
    assert manifest["checkpoints"] == ["080000"]
    assert all(preset["episode_index"] < 65 for preset in presets.values())

    assert "ttt_games_1_5_80k.json" in runner
    assert 'export TTT_MODEL_VARIANT="games-1-5-80k"' in launcher
    assert 'export TTT_MODEL_CHECKPOINT="080000"' in launcher
    assert 'export HASHTAG_ROLLOUT_SEED="${TTT_ROLLOUT_SEED:-42}"' in launcher
    assert "ttt-rollouts/$task_launcher" in launcher


def test_checkpoint_launchers_cover_the_requested_sweep_and_keep_operator_gates() -> None:
    expected = {
        "20k": "020000",
        "40k": "040000",
        "60k": "060000",
        "80k": "080000",
        "100k": "100000",
        "120k": "120000",
    }
    actual = {path.name for path in CHECKPOINT_LAUNCHERS.iterdir() if path.is_file()}

    assert actual == {*expected, "all", "games-1-5-80k"}
    assert all(os.access(CHECKPOINT_LAUNCHERS / name, os.X_OK) for name in actual)
    for name, checkpoint in expected.items():
        source = (CHECKPOINT_LAUNCHERS / name).read_text()
        assert f'run_ttt_checkpoint.zsh" {checkpoint}' in source

    runner = (ROOT / "scripts" / "run_ttt_checkpoint.zsh").read_text()
    assert 'export TTT_MODEL_CHECKPOINT="$checkpoint"' in runner
    assert 'export HASHTAG_ROLLOUT_SEED="${TTT_ROLLOUT_SEED:-42}"' in runner
    assert "ttt-rollouts/$task_launcher" in runner

    sweep = (CHECKPOINT_LAUNCHERS / "all").read_text()
    assert "checkpoint_launchers=(20k 40k 60k 80k 100k 120k)" in sweep
    assert "games-1-5-80k" not in sweep
    assert '!= "NEXT"' in sweep
    assert "HOME ve E-STOP kapıları yeniden uygulanır" in sweep


def test_runner_streams_and_persists_runtime_errors() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()

    assert 'rollout_log_dir="$rollout_repo_dir/.local-data/rollout-logs"' in runner
    assert '2>&1 | tee "$rollout_log"' in runner
    assert "RTC inference error" in runner
    assert "Hashtag camera incident" in runner
    assert "Rollout hata/incident özeti" in runner


def test_runner_requires_the_target_cell_to_be_empty_before_move_confirmation() -> None:
    runner = (ROOT / "scripts" / "run_ttt_recorded_rollout.zsh").read_text()

    assert "rollout_target_cell=" in runner
    assert "ttt_training_presets.json" in runner
    assert "HASHTAG_TTT_DEMO_PRESET_JSON" in runner
    assert "Robot önce eğitim başlangıç pozuna gidecek" in runner
    assert '!= "HOME"' in runner


def test_all_launchers_have_an_in_distribution_training_preset() -> None:
    presets = json.loads(PRESETS.read_text())
    expected_tasks = {
        f"put the {piece} in the {cell} cell"
        for piece in ("red X", "white O")
        for cell in CELLS.values()
    }

    assert set(presets) == expected_tasks
    for task, preset in presets.items():
        assert isinstance(preset["episode_index"], int)
        assert len(preset["start_pose"]) == 6
        robot_rows = preset["board_robot"].split("/")
        camera_rows = preset["board_camera"].split("/")
        assert len(robot_rows) == len(camera_rows) == 3
        assert all(len(row) == 3 and set(row) <= set("XO.") for row in robot_rows)
        assert camera_rows == [row[::-1] for row in robot_rows[::-1]]

        cell_name = task.removesuffix(" cell").rsplit(" in the ", 1)[1]
        cell_index = list(CELLS.values()).index(cell_name)
        assert "".join(robot_rows)[cell_index] == "."
