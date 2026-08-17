from __future__ import annotations

import pytest

from hashtag_robotics.jobs import apply_server_defaults
from hashtag_robotics.models import JobCreateRequest, JobKind, TargetMode
from hashtag_robotics.repository import Repository
from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_PROFILE,
    TicTacToePresetError,
    canonical_tic_tac_toe_parameters,
    preset_for_move,
    task_for_move,
    tic_tac_toe_catalogue,
)


def test_catalogue_exposes_all_eighteen_training_backed_moves() -> None:
    catalogue = tic_tac_toe_catalogue()

    assert [move["id"] for move in catalogue] == [
        *(f"X-{index}" for index in range(1, 10)),
        *(f"O-{index}" for index in range(1, 10)),
    ]
    assert all(len(move["start_pose"]) == 6 for move in catalogue)
    assert all(move["task"] == task_for_move(move["id"]) for move in catalogue)


def test_x7_is_pinned_to_the_successful_episode_45_contract() -> None:
    canonical = canonical_tic_tac_toe_parameters(
        {
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": "x-7",
            "policy_id": "policy",
            "robot_profile_id": "robot",
            "workspace_confirmed": True,
            # Client attempts to weaken or replace the tested contract.
            "duration": 2,
            "fps": 5,
            "repo_id": "client/injected",
            "inference_rtc_enabled": True,
        }
    )

    assert canonical["move_id"] == "X-7"
    assert canonical["task"] == "put the red X in the bottom left cell"
    assert canonical["ttt_preset"] == preset_for_move("X-7")
    assert canonical["ttt_preset"]["episode_index"] == 45
    assert canonical["ttt_preset"]["board_camera"] == ".../OXO/..."
    assert canonical["fps"] == 30
    assert canonical["inference_rtc_enabled"] is False
    assert canonical["repo_id"] == ("hashtagrobotics/rollout_tic_tac_toe_games_1_15_120k_X-7")
    assert "duration" not in canonical


def test_unknown_move_is_rejected_before_a_command_can_be_built() -> None:
    with pytest.raises(TicTacToePresetError, match="X-1"):
        canonical_tic_tac_toe_parameters(
            {"rollout_profile": TIC_TAC_TOE_PROFILE, "move_id": "X-10"}
        )


def test_job_submission_canonicalizes_the_dashboard_request(tmp_path) -> None:
    request = JobCreateRequest(
        kind=JobKind.POLICY_ROLLOUT,
        target_mode=TargetMode.REAL,
        parameters={
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": "O-5",
            "policy_id": "policy",
            "robot_profile_id": "robot",
            "workspace_confirmed": True,
            "task": "client injected",
            "duration": 1,
        },
        requested_by="dashboard",
    )

    normalized = apply_server_defaults(request, Repository(tmp_path / "state.db"))

    assert normalized.parameters["task"] == "put the white O in the middle center cell"
    assert normalized.parameters["episodes"] == 1
    assert "duration" not in normalized.parameters
