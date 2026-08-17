from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

TIC_TAC_TOE_PROFILE = "tic_tac_toe_games_1_15_120k"
TIC_TAC_TOE_POLICY_REPO = "HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k"
TIC_TAC_TOE_POLICY_REVISION = "48a6313b7e4983781dd72919105ca691a77cd26c"
TIC_TAC_TOE_MAX_RELATIVE_TARGET = 5.0

TIC_TAC_TOE_CELLS = {
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
TIC_TAC_TOE_PIECES = {"X": "red X", "O": "white O"}

# A browser may choose the move, device, policy and follower. Everything below
# is the tested rollout contract and is therefore re-derived by the server.
_CONTROLLED_PARAMETERS = {
    "dataset_root",
    "dataset_video",
    "disable_torque_on_disconnect",
    "display_data",
    "duration",
    "episode_time_s",
    "episodes",
    "fps",
    "inference_queue_threshold",
    "inference_rtc_enabled",
    "inference_type",
    "name",
    "play_sounds",
    "push_to_hub",
    "repo_id",
    "reset_time_s",
    "reset_to_initial_position",
    "return_to_initial_position",
    "strategy",
    "task",
    "timeout_seconds",
    "ttt_preset",
    "video_encoding_batch_size",
}


class TicTacToePresetError(ValueError):
    pass


@lru_cache(maxsize=1)
def training_presets() -> dict[str, dict[str, Any]]:
    resource = files("hashtag_robotics_ttt").joinpath("ttt_training_presets.json")
    decoded = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict) or len(decoded) != 18:
        raise TicTacToePresetError("The packaged tic-tac-toe preset catalogue is incomplete.")
    return decoded


def task_for_move(move_id: str) -> str:
    normalized = str(move_id).strip().upper()
    try:
        piece, raw_cell = normalized.split("-", 1)
        object_name = TIC_TAC_TOE_PIECES[piece]
        cell = TIC_TAC_TOE_CELLS[int(raw_cell)]
    except (KeyError, ValueError) as error:
        raise TicTacToePresetError("move_id must be one of X-1..X-9 or O-1..O-9.") from error
    return f"put the {object_name} in the {cell} cell"


def preset_for_move(move_id: str) -> dict[str, Any]:
    task = task_for_move(move_id)
    try:
        preset = training_presets()[task]
    except KeyError as error:
        raise TicTacToePresetError(f"No training preset exists for '{task}'.") from error
    return {
        "episode_index": int(preset["episode_index"]),
        "board_robot": str(preset["board_robot"]),
        "board_camera": str(preset["board_camera"]),
        "start_pose": [float(value) for value in preset["start_pose"]],
    }


def tic_tac_toe_catalogue() -> list[dict[str, Any]]:
    catalogue: list[dict[str, Any]] = []
    for piece, object_name in TIC_TAC_TOE_PIECES.items():
        for cell_number, cell in TIC_TAC_TOE_CELLS.items():
            move_id = f"{piece}-{cell_number}"
            task = task_for_move(move_id)
            catalogue.append(
                {
                    "id": move_id,
                    "piece": piece,
                    "object_name": object_name,
                    "cell_number": cell_number,
                    "cell": cell,
                    "task": task,
                    **preset_for_move(move_id),
                }
            )
    return catalogue


def is_tic_tac_toe_parameters(parameters: dict[str, Any]) -> bool:
    return str(parameters.get("rollout_profile", "")).strip() == TIC_TAC_TOE_PROFILE


def canonical_tic_tac_toe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    if not is_tic_tac_toe_parameters(parameters):
        return dict(parameters)

    move_id = str(parameters.get("move_id", "")).strip().upper()
    task = task_for_move(move_id)
    preset = preset_for_move(move_id)
    device = str(parameters.get("device", "mps")).strip().lower()
    if device not in {"mps", "cuda", "cpu"}:
        raise TicTacToePresetError("device must be one of mps, cuda or cpu.")

    canonical = {
        key: value for key, value in parameters.items() if key not in _CONTROLLED_PARAMETERS
    }
    canonical.update(
        {
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": move_id,
            "task": task,
            "ttt_preset": preset,
            "name": f"Tic-Tac-Toe {move_id} rollout",
            "strategy": "episodic",
            "fps": 30,
            "device": device,
            "display_data": False,
            "play_sounds": False,
            "reset_to_initial_position": True,
            "return_to_initial_position": True,
            "disable_torque_on_disconnect": True,
            "inference_type": "rtc",
            "inference_queue_threshold": 18,
            "inference_rtc_enabled": False,
            "repo_id": f"hashtagrobotics/rollout_tic_tac_toe_games_1_15_120k_{move_id}",
            "episodes": 1,
            "episode_time_s": 86400,
            "reset_time_s": 0,
            "push_to_hub": False,
            "dataset_video": True,
            "video_encoding_batch_size": 1,
        }
    )
    return canonical
