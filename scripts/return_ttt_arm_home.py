#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hashtag_robotics_ttt.lerobot_wrappers import (  # noqa: E402
    _TTT_JOINT_KEYS,
    _move_robot_to_ttt_demo_pose,
)
from hashtag_robotics_ttt.settings import TicTacToeSettings  # noqa: E402
from hashtag_robotics_ttt.tic_tac_toe import preset_for_move, task_for_move  # noqa: E402


class HomeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Return the SO-101 to one recorded tic-tac-toe demo home without inference."
    )
    parser.add_argument("--move", default="X-5", help="Demo home preset (default: X-5).")
    parser.add_argument("--physical", action="store_true", help="Required physical opt-in.")
    parser.add_argument(
        "--hardware-config",
        type=Path,
        default=Path(
            os.environ.get(
                "HASHTAG_TTT_HARDWARE_CONFIG",
                REPO_ROOT / ".local-data" / "ttt-hardware.json",
            )
        ),
        help="Local hardware profile (default: .local-data/ttt-hardware.json).",
    )
    return parser.parse_args()


def load_hardware_profile(path: Path) -> tuple[str, str, Path]:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    try:
        profile = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HomeError(f"Cannot read hardware profile {resolved}: {error}") from error
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise HomeError(f"Hardware profile {resolved} must use schema_version 1.")
    robot_port = str(profile.get("robot_port", "")).strip()
    robot_id = str(profile.get("robot_id", "")).strip()
    calibration_raw = str(profile.get("calibration_dir", "")).strip()
    if not robot_port or not robot_id or not calibration_raw:
        raise HomeError("Hardware profile requires robot_port, robot_id and calibration_dir.")
    calibration_dir = Path(calibration_raw).expanduser()
    if not calibration_dir.is_absolute():
        calibration_dir = (REPO_ROOT / calibration_dir).resolve()
    return robot_port, robot_id, calibration_dir


def assert_resources_ready(robot_port: str, robot_id: str, calibration_dir: Path) -> None:
    if not Path(robot_port).exists():
        raise HomeError(f"Follower port is missing: {robot_port}")
    calibration_file = calibration_dir / f"{robot_id}.json"
    if not calibration_file.is_file():
        raise HomeError(f"Follower calibration is missing: {calibration_file}")
    if (
        subprocess.run(
            ["pgrep", "-f", "[h]ashtag-lerobot-rollout"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    ):
        raise HomeError("A LeRobot rollout is still active; home recovery was refused.")
    if (
        subprocess.run(
            ["lsof", robot_port],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    ):
        raise HomeError("The follower serial port is owned by another process.")


def request_approval(move_id: str, task: str) -> None:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise HomeError("Home recovery requires an interactive operator terminal.")
    sys.stderr.write(
        "\n"
        f"ARM HOME RECOVERY: {move_id}\n"
        f"Reference task: {task}\n"
        "Remove hands, pieces and cables from the entire arm sweep volume.\n"
        "Keep the physical E-STOP reachable. The arm will move for about 7 seconds.\n"
        "Type the exact phrase below to approve only this recovery move:\n"
        f"APPROVE HOME RECOVERY {move_id}: "
    )
    sys.stderr.flush()
    if sys.stdin.readline().strip().casefold() != f"APPROVE HOME RECOVERY {move_id}".casefold():
        raise HomeError("Operator did not authorize home recovery.")


def main() -> int:
    args = parse_args()
    move_id = str(args.move).strip().upper()
    settings = TicTacToeSettings.from_environment()
    if not settings.enable_physical or not args.physical:
        raise HomeError("Set HASHTAG_ENABLE_PHYSICAL=true and pass --physical.")
    task = task_for_move(move_id)
    pose = preset_for_move(move_id)["start_pose"]
    target = dict(zip(_TTT_JOINT_KEYS, pose, strict=True))
    robot_port, robot_id, calibration_dir = load_hardware_profile(args.hardware_config)
    assert_resources_ready(robot_port, robot_id, calibration_dir)
    request_approval(move_id, task)

    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    robot = SO101Follower(
        SO101FollowerConfig(
            port=robot_port,
            id=robot_id,
            calibration_dir=calibration_dir,
            max_relative_target=5.0,
            disable_torque_on_disconnect=True,
            cameras={},
        )
    )
    connected = False
    try:
        robot.connect()
        connected = True
        context = SimpleNamespace(hardware=SimpleNamespace(robot_wrapper=robot))
        errors = _move_robot_to_ttt_demo_pose(context, target, duration_s=7.0, fps=50)
        worst_error = max(errors.values(), default=0.0)
        if worst_error > 3.0:
            details = ", ".join(f"{key}={value:.1f} deg" for key, value in errors.items())
            raise HomeError(f"Home verification failed ({worst_error:.1f} deg): {details}")
        print(f"ARM_HOME_OK move={move_id} worst_error_deg={worst_error:.2f}", flush=True)
        return 0
    except KeyboardInterrupt as error:
        raise HomeError("Home recovery was interrupted; torque will be disabled.") from error
    finally:
        if connected:
            with contextlib.suppress(Exception):
                robot.disconnect()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HomeError as error:
        print(f"Home recovery refused: {error}", file=sys.stderr)
        raise SystemExit(2) from error
