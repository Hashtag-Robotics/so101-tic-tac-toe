from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hashtag_robotics_ttt.strands_agent import (
    CAMERA_TO_MODEL_CELL,
    MODEL_TO_CAMERA_CELL,
    MOVE_TOOL_NAME,
    BoardError,
    BoardState,
    TerminalOperatorGate,
    TicTacToeAgentConfig,
    TicTacToeAgentError,
    TicTacToeRolloutController,
    build_tic_tac_toe_tools,
    expected_camera_board,
    move_id_for_agent_cell,
    sanitize_strands_messages,
    tic_tac_toe_system_prompt,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_top_camera_and_model_cells_are_rotated_180_degrees() -> None:
    assert {cell: 10 - cell for cell in range(1, 10)} == CAMERA_TO_MODEL_CELL
    assert {cell: 10 - cell for cell in range(1, 10)} == MODEL_TO_CAMERA_CELL

    # Model top-left (X-1) is bottom-right in the top-camera image.
    assert expected_camera_board(".../.../...", "X-1") == ".../.../..X"
    # It is now O's turn. Model bottom-right (O-9) is top-left in camera space.
    assert expected_camera_board(".../.../..X", "O-9") == "O../.../..X"


def test_board_contract_refuses_wrong_turn_occupied_target_and_finished_game() -> None:
    with pytest.raises(BoardError, match="It is X's turn"):
        expected_camera_board(".../.../...", "O-5")

    with pytest.raises(BoardError, match="already occupied"):
        expected_camera_board(".../.../..X", "O-1")

    won = BoardState.parse("XXX/OO./...")
    assert won.winner == "X"
    with pytest.raises(BoardError, match="already has winner"):
        expected_camera_board(str(won), "O-4")

    with pytest.raises(BoardError, match="Impossible turn count"):
        _ = BoardState.parse("XX./.../...").next_piece


def test_terminal_gate_uses_captured_tty_and_requires_exact_move() -> None:
    output = FakeTTY()
    gate = TerminalOperatorGate(
        FakeTTY("I approve supervised automatic robot moves for this game\n"), output
    )
    gate("X-5", "put the red X in the middle center cell", "120000")
    gate("X-3", "put the red X in the top right cell", "120000")
    assert output.getvalue().count("PHYSICAL GAME SESSION") == 1
    assert "I approve supervised automatic robot moves for this game" in output.getvalue()

    with pytest.raises(TicTacToeAgentError, match="did not authorize"):
        TerminalOperatorGate(FakeTTY("I approve only this move\n"), FakeTTY())(
            "X-5", "put the red X in the middle center cell", "120000"
        )

    with pytest.raises(TicTacToeAgentError, match="interactive operator terminal"):
        TerminalOperatorGate(
            io.StringIO("I approve supervised automatic robot moves for this game\n"),
            FakeTTY(),
        )("X-5", "put the red X in the middle center cell", "120000")


def test_single_move_tool_keeps_symbol_and_training_task_out_of_the_model_schema() -> None:
    class ConfigStub:
        forced_agent_symbol = "X"

    class ControllerStub:
        config = ConfigStub()

        def observe(self, wait_seconds: float = 0.0):  # pragma: no cover - not invoked
            raise AssertionError(wait_seconds)

        def choose_agent_symbol(self, symbol: str, board_camera: str, rationale: str):
            raise AssertionError((symbol, board_camera, rationale))

        def acknowledge_human_move(self, board_camera: str, diagnosis: str):
            raise AssertionError((board_camera, diagnosis))

        def confirm_workspace_clear(self, board_camera: str, workspace_clear: bool, evidence: str):
            raise AssertionError((board_camera, workspace_clear, evidence))

        def start_move(self, move_id: str, board_camera: str, rationale: str):
            raise AssertionError((move_id, board_camera, rationale))

        def finish_move(self, board_camera_after: str, outcome: str, diagnosis: str):
            raise AssertionError((board_camera_after, outcome, diagnosis))

    tools = build_tic_tac_toe_tools(ControllerStub())  # type: ignore[arg-type]
    names = {item.tool_name for item in tools}

    assert len(tools) == 6
    assert names == {
        "observe_board",
        "choose_game_symbol",
        "acknowledge_human_move",
        "confirm_workspace_clear",
        "finish_active_move",
        MOVE_TOOL_NAME,
    }
    assert "emergency_stop" not in names

    configs = {item.tool_name: item.tool_spec for item in tools}
    move_config = configs[MOVE_TOOL_NAME]
    assert "exact X SmolVLA move" in move_config["description"]
    assert "180-degree TOP CAMERA transform" in move_config["description"]
    assert set(move_config["inputSchema"]["json"]["properties"]) == {
        "model_cell",
        "board_camera",
        "rationale",
    }
    assert "symbol" not in move_config["inputSchema"]["json"]["properties"]
    assert "instruction" not in move_config["inputSchema"]["json"]["properties"]


def test_move_tool_parameter_resolves_only_the_locked_agent_symbol() -> None:
    assert move_id_for_agent_cell("x", 1) == "X-1"
    assert move_id_for_agent_cell("O", 9) == "O-9"

    with pytest.raises(BoardError, match="agent_symbol must be X or O"):
        move_id_for_agent_cell("red", 5)
    with pytest.raises(BoardError, match="integer from 1 through 9"):
        move_id_for_agent_cell("X", True)
    with pytest.raises(BoardError, match="integer from 1 through 9"):
        move_id_for_agent_cell("X", 10)


def test_system_prompt_forces_observation_lifecycle_and_no_freeform_control() -> None:
    prompt = tic_tac_toe_system_prompt("120000")

    assert "checkpoint 120000" in prompt
    assert "First call observe_board" in prompt
    assert "you always make the first move" in prompt
    assert "You are X for the entire game and the human is O" in prompt
    assert "Never play O or act during the human's turns" in prompt
    assert f"only {MOVE_TOOL_NAME} with model_cell=1..9" in prompt
    assert "never choose the piece or write the policy instruction" in prompt
    assert "independently choose the opening cell from all nine legal" in prompt
    assert "No opening cell is predetermined" in prompt
    assert "Do not assume center" in prompt
    assert "wait_seconds=5" in prompt
    assert "acknowledge_human_move" in prompt
    assert "TOP CAMERA is rotated 180 degrees" in prompt
    assert "finish_active_move exactly once" in prompt
    assert "Never invent a prompt, shell command, joint command" in prompt
    assert "physical E-STOP" in prompt
    assert "Speak naturally in Turkish" in prompt
    assert "You have no emergency_stop tool" in prompt
    assert "no dashboard stop permission" in prompt
    assert "manual piece assistance are diagnostic observations only" in prompt
    assert "confirm_workspace_clear" in prompt
    assert "retry_scheduled=true" in prompt
    assert "at most three automatic retries" in prompt
    assert "SAME model_cell" in prompt


def test_static_preflight_is_pinned_to_the_checkpoint_manifest(monkeypatch) -> None:
    monkeypatch.delenv("HASHTAG_TTT_AGENT_TOP_CAMERA_UID", raising=False)
    monkeypatch.delenv("HASHTAG_TTT_AGENT_SYMBOL", raising=False)
    config = TicTacToeAgentConfig.from_environment(
        ROOT,
        "120000",
        physical_enabled=False,
        explicit_physical_opt_in=False,
    )
    manifest = json.loads(config.manifest_path.read_text())
    preflight = config.static_preflight()

    assert preflight["model_variant"] == "games-1-15"
    assert preflight["model_repo_id"] == ("HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k")
    assert preflight["model_revision"] == manifest["model_revision"]
    assert preflight["checkpoint"] == "120000"
    assert preflight["checkpoint_path"].endswith("checkpoints/120000/pretrained_model")
    assert preflight["launcher_count"] == 18
    assert preflight["missing_launchers"] == []
    assert preflight["physical_env_enabled"] is False
    assert preflight["physical_cli_opt_in"] is False
    assert config.max_retries_per_move == 3
    assert config.forced_agent_symbol == "X"


def test_trace_sanitizer_never_persists_camera_bytes() -> None:
    sanitized = sanitize_strands_messages(
        [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "jpeg",
                            "source": {"bytes": b"camera-payload"},
                        }
                    }
                ],
            }
        ]
    )

    source = sanitized[0]["content"][0]["image"]["source"]
    assert source == {"bytes": {"binary_bytes": len(b"camera-payload")}}
    assert "camera-payload" not in json.dumps(sanitized)


def test_controller_drives_launcher_pty_and_persists_move_result(tmp_path, monkeypatch) -> None:
    manifest = {
        "model_repo_id": "HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k",
        "model_revision": "test-revision",
        "checkpoint_path_template": "checkpoints/{checkpoint}/pretrained_model",
        "checkpoints": ["120000"],
    }
    package = tmp_path / "src" / "hashtag_robotics_ttt"
    package.mkdir(parents=True)
    (package / "ttt_checkpoint_sweep.json").write_text(json.dumps(manifest))
    checkpoint = (
        tmp_path
        / ".local-data"
        / "policies"
        / "HashtagRobotics--smolvla-tic-tac-toe-games-1-15-120k"
        / "test-revision"
        / "checkpoints"
        / "120000"
        / "pretrained_model"
    )
    checkpoint.mkdir(parents=True)
    helper = tmp_path / ".local-data" / "bin" / "avfoundation-uid-capture"
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/bin/zsh\nexit 0\n")
    helper.chmod(0o755)
    robot_port = tmp_path / "fake-follower-port"
    robot_port.touch()
    calibration_dir = tmp_path / ".local-data" / "calibration"
    calibration_dir.mkdir()
    (calibration_dir / "test_follower.json").write_text("{}")
    hardware_profile = tmp_path / ".local-data" / "ttt-hardware.json"
    hardware_profile.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "robot_port": str(robot_port),
                "robot_id": "test_follower",
                "calibration_dir": str(calibration_dir),
                "camera_helper": str(helper),
                "top_camera_uid": "top-test-uid",
                "wrist_camera_uid": "wrist-test-uid",
                "inference_device": "cpu",
            }
        )
    )

    launcher_source = """#!/usr/bin/env python3
import os
import sys
import termios

if os.environ.get("TTT_MODEL_VARIANT") != "games-1-15":
    raise SystemExit(10)
if sys.stdin.readline().strip() != "HOME":
    raise SystemExit(9)
attributes = termios.tcgetattr(sys.stdin.fileno())
attributes[3] &= ~(termios.ICANON | termios.ECHO)
termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attributes)
print("Ready: press Right Arrow or n", flush=True)
if sys.stdin.read(1) != "n":
    raise SystemExit(8)
print("Board confirmed; model inference is starting.", flush=True)
if sys.stdin.read(1) != "n":
    raise SystemExit(7)
print("Rollout complete. Dataset: /tmp/fake-dataset", flush=True)
print("Terminal log saved: /tmp/fake-rollout.log", flush=True)
"""
    launchers = tmp_path / "ttt-rollouts"
    launchers.mkdir()
    for piece in "XO":
        for cell in range(1, 10):
            launcher = launchers / f"{piece}-{cell}"
            launcher.write_text(launcher_source)
            launcher.chmod(0o755)

    monkeypatch.setenv("HASHTAG_TTT_AGENT_SYMBOL", "O")
    config = TicTacToeAgentConfig.from_environment(
        tmp_path,
        "120000",
        physical_enabled=True,
        explicit_physical_opt_in=True,
        model_variant="games-1-15",
    )
    controller = TicTacToeRolloutController(
        config,
        operator_gate=lambda _move, _task, _checkpoint: None,
    )
    monkeypatch.setattr(controller, "_assert_no_external_camera_owner", lambda: None)
    controller.observation_index = 1
    with pytest.raises(BoardError, match="locks the agent to O"):
        controller.choose_agent_symbol("X", ".../.../...", "Forbidden symbol choice.")
    selected = controller.choose_agent_symbol(
        "O", ".../.../...", "Agent is locked to O for this game."
    )
    assert selected["phase"] == "agent_turn"
    assert selected["agent_symbol"] == "O"
    assert selected["human_symbol"] == "X"
    with pytest.raises(TicTacToeAgentError, match="locked to O"):
        controller.start_move("X-1", ".../.../...", "Forbidden opponent move.")

    started = controller.start_move("O-1", ".../.../...", "Empty board opening move.")
    assert started["state"] == "active"
    assert started["expected_board_camera_after"] == ".../.../..O"

    failed = controller.finish_move(
        ".../.../...",
        "no_motion",
        "The gripper did not acquire a piece and the board stayed unchanged.",
    )
    assert failed["retry_scheduled"] is True
    assert failed["retry_number"] == 1
    assert failed["game"]["phase"] == "waiting_for_workspace_clear"
    controller.observation_index += 1
    with pytest.raises(BoardError, match="does not match the controller's confirmed board"):
        controller.confirm_workspace_clear(
            ".../.X./...", True, "The board changed, so retry must be blocked."
        )
    first_retry_clear = controller.confirm_workspace_clear(
        ".../.../...", True, "Board and immediate path are clear."
    )
    assert first_retry_clear["phase"] == "waiting_for_workspace_clear"
    controller.observation_index += 1
    assert controller.workspace_clear_last_confirmed_at is not None
    controller.workspace_clear_last_confirmed_at -= 3.0
    second_retry_clear = controller.confirm_workspace_clear(
        ".../.../...", True, "Board is unchanged and the path remains clear."
    )
    assert second_retry_clear["phase"] == "agent_turn"
    with pytest.raises(TicTacToeAgentError, match="controlled retry is locked to O-1"):
        controller.start_move("O-2", ".../.../...", "Changing target is forbidden.")

    retried = controller.start_move("O-1", ".../.../...", "Controlled same-move retry.")
    assert retried["retry_number"] == 1
    finished = controller.finish_move(
        ".../.../..O",
        "success",
        "The expected O is visible in top-camera cell 9.",
    )
    assert finished["return_code"] == 0
    assert finished["dataset_path"] == "/tmp/fake-dataset"
    assert finished["rollout_log_path"] == "/tmp/fake-rollout.log"
    assert Path(finished["terminal_transcript"]).is_file()
    assert controller.active is None
    assert finished["game"]["phase"] == "waiting_for_human"
    with pytest.raises(TicTacToeAgentError, match="Observe both cameras"):
        controller.acknowledge_human_move(
            "X../.../..O", "Claim made without a post-move camera observation."
        )
    controller.observation_index += 1
    with pytest.raises(BoardError, match="exactly one cell"):
        controller.acknowledge_human_move(
            ".../.../..O", "Board is unchanged, so the human has not moved."
        )
    with pytest.raises(BoardError, match="only allowed human change"):
        controller.acknowledge_human_move("O../.../..O", "Wrong symbol appeared in the human turn.")
    human = controller.acknowledge_human_move("X../.../..O", "Human placed X in top-camera cell 1.")
    assert human["phase"] == "waiting_for_workspace_clear"
    assert human["changed_camera_cell"] == 1
    assert human["changed_model_cell"] == 9
    with pytest.raises(TicTacToeAgentError, match="new camera observation"):
        controller.confirm_workspace_clear("X../.../..O", True, "Hands are clear in both views.")
    controller.observation_index += 1
    first_clear = controller.confirm_workspace_clear(
        "X../.../..O", True, "Hands are clear in both views."
    )
    assert first_clear["phase"] == "waiting_for_workspace_clear"
    with pytest.raises(TicTacToeAgentError, match="new camera observation"):
        controller.confirm_workspace_clear("X../.../..O", True, "Same image cannot count twice.")
    controller.observation_index += 1
    assert controller.workspace_clear_last_confirmed_at is not None
    controller.workspace_clear_last_confirmed_at -= 3.0
    second_clear = controller.confirm_workspace_clear(
        "X../.../..O", True, "Still clear after two seconds."
    )
    assert second_clear["phase"] == "agent_turn"
    controller.close()


def test_agent_entrypoint_requires_explicit_physical_opt_in_and_uses_no_generic_shell_tool() -> (
    None
):
    source = (ROOT / "scripts" / "run_ttt_strands_agent.py").read_text()
    controller_source = (ROOT / "src" / "hashtag_robotics_ttt" / "strands_agent.py").read_text()
    entrypoint = (ROOT / "agent.py").read_text()
    docs = (ROOT / "STRANDS_AGENT.md").read_text()

    assert '"--physical"' in source
    assert "SequentialToolExecutor" in source
    assert "strands_tools" not in source
    assert "strands_robots" not in source
    assert "I approve supervised automatic robot moves for this game" in controller_source
    assert "_runner_arguments(sys.argv[1:])" in entrypoint
    assert 'if "--inspect" in arguments or "--physical" in arguments:' in entrypoint
    assert 'return ["--physical", *arguments]' in entrypoint
    assert 'default="120000"' in source
    assert "default=DEFAULT_MODEL_VARIANT" in source
    assert "Local policy path:" in source
    assert '"TTT_MODEL_VARIANT": self.config.model_variant' in controller_source
    assert "python agent.py" in docs
    assert "HASHTAG_ENABLE_PHYSICAL=true" in docs
    assert "launcher_count: 18" in docs
