"""Software-first Strands Robots contract for the tic-tac-toe project.

The production game still uses the proven rollout launchers. This module is the
small, explicit seam for validating a native Strands Robots migration without
probing USB, opening cameras, or silently selecting real hardware.
"""

from __future__ import annotations

import importlib.util
import math
import os
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from packaging.version import InvalidVersion, Version

from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_MAX_RELATIVE_TARGET,
    TIC_TAC_TOE_POLICY_REPO,
    TIC_TAC_TOE_POLICY_REVISION,
    task_for_move,
)

STRANDS_ROBOTS_DISTRIBUTION = "strands-robots"
STRANDS_ROBOTS_VERSION = "0.5.1"
LEROBOT_DISTRIBUTION = "lerobot"
LEROBOT_MIN_VERSION = Version("0.6.1")
LEROBOT_MAX_VERSION = Version("0.7.0")
TRUST_REMOTE_CODE_ENV = "STRANDS_TRUST_REMOTE_CODE"

NATIVE_POLICY_TYPE = "smolvla"
NATIVE_POLICY_CHECKPOINT = "120000"
NATIVE_CAMERA_KEY_MAP = {
    "top": "observation.images.camera1",
    "wrist": "observation.images.camera2",
}

NATIVE_ACTION_HORIZON = 50
NATIVE_CONTROL_FREQUENCY = 30.0


class StrandsRobotsContractError(RuntimeError):
    """Raised before a native runtime can cross an unverified contract boundary."""


def _distribution_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _parsed_version(value: str | None) -> Version | None:
    if value is None:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


def inspect_strands_robots_runtime() -> dict[str, Any]:
    """Inspect package/model contracts without importing a robot backend."""

    strands_robots_version = _distribution_version(STRANDS_ROBOTS_DISTRIBUTION)
    lerobot_version = _distribution_version(LEROBOT_DISTRIBUTION)
    parsed_strands_robots = _parsed_version(strands_robots_version)
    parsed_lerobot = _parsed_version(lerobot_version)
    blockers: list[str] = []

    if parsed_strands_robots is None:
        blockers.append(f"Install {STRANDS_ROBOTS_DISTRIBUTION}=={STRANDS_ROBOTS_VERSION}.")
    elif parsed_strands_robots != Version(STRANDS_ROBOTS_VERSION):
        blockers.append(
            f"Expected {STRANDS_ROBOTS_DISTRIBUTION}=={STRANDS_ROBOTS_VERSION}, "
            f"found {strands_robots_version}."
        )

    if parsed_lerobot is None:
        blockers.append("Install LeRobot >=0.6.1,<0.7.0.")
    elif not LEROBOT_MIN_VERSION <= parsed_lerobot < LEROBOT_MAX_VERSION:
        blockers.append(f"Expected LeRobot >=0.6.1,<0.7.0, found {lerobot_version}.")

    module_importable = importlib.util.find_spec("strands_robots") is not None
    if parsed_strands_robots is not None and not module_importable:
        blockers.append("The strands_robots distribution exists but its module is not importable.")

    return {
        "inspection_mode": "software-only",
        "serial_probed": False,
        "cameras_opened": False,
        "robot_created": False,
        "policy_loaded": False,
        "strands_robots_version": strands_robots_version,
        "required_strands_robots_version": STRANDS_ROBOTS_VERSION,
        "lerobot_version": lerobot_version,
        "required_lerobot_range": ">=0.6.1,<0.7.0",
        "module_importable": module_importable,
        "compatible": not blockers,
        "blockers": blockers,
        "policy": {
            "provider": "lerobot_local",
            "repo_id": TIC_TAC_TOE_POLICY_REPO,
            "revision": TIC_TAC_TOE_POLICY_REVISION,
            "checkpoint": NATIVE_POLICY_CHECKPOINT,
            "policy_type": NATIVE_POLICY_TYPE,
            "camera_key_map": dict(NATIVE_CAMERA_KEY_MAP),
            "strict_keys": True,
            "chunk_size": NATIVE_ACTION_HORIZON,
            "n_action_steps": NATIVE_ACTION_HORIZON,
        },
        "production_backend": "existing guarded ttt-rollouts launchers",
        "native_hardware_status": "requires hardware-in-the-loop validation",
    }


def _require_supported_runtime() -> None:
    report = inspect_strands_robots_runtime()
    if not report["compatible"]:
        raise StrandsRobotsContractError(" ".join(report["blockers"]))


def build_native_policy_kwargs(
    *,
    checkpoint_path: Path,
    device: str = "cpu",
) -> dict[str, Any]:
    """Return strict kwargs for a locally fetched, revision-pinned checkpoint."""

    normalized_device = device.strip().lower()
    if normalized_device not in {"cpu", "mps", "cuda"}:
        raise StrandsRobotsContractError("device must be cpu, mps or cuda.")

    resolved = checkpoint_path.expanduser().resolve()
    if not resolved.is_dir():
        raise StrandsRobotsContractError(f"Local checkpoint directory is missing: {resolved}")

    return {
        "pretrained_name_or_path": str(resolved),
        "policy_type": NATIVE_POLICY_TYPE,
        "device": normalized_device,
        "camera_key_map": dict(NATIVE_CAMERA_KEY_MAP),
        "strict_keys": True,
    }


def _trust_remote_code_enabled() -> bool:
    return os.environ.get(TRUST_REMOTE_CODE_ENV, "").strip().lower() in {"1", "true", "yes"}


def load_native_policy(
    *,
    checkpoint_path: Path,
    device: str = "cpu",
    acknowledge_remote_code: bool = False,
    policy_factory: Callable[..., Any] | None = None,
) -> Any:
    """Load the pinned policy only after two explicit remote-code acknowledgements."""

    if not acknowledge_remote_code:
        raise StrandsRobotsContractError(
            "Set acknowledge_remote_code=True only after reviewing the pinned model repository."
        )
    if not _trust_remote_code_enabled():
        raise StrandsRobotsContractError(
            f"Set {TRUST_REMOTE_CODE_ENV}=1 after reviewing the pinned model repository."
        )

    if policy_factory is None:
        _require_supported_runtime()
        from strands_robots.policies import create_policy

        policy_factory = create_policy

    return policy_factory(
        "lerobot_local",
        **build_native_policy_kwargs(
            checkpoint_path=checkpoint_path,
            device=device,
        ),
    )


def create_so101_simulation(
    *,
    backend: str = "mujoco",
    robot_factory: Callable[..., Any] | None = None,
) -> Any:
    """Create an SO-101 simulation with explicit sim mode and mesh disabled."""

    if robot_factory is None:
        _require_supported_runtime()
        from strands_robots import Robot

        robot_factory = Robot
    return robot_factory("so101", mode="sim", backend=backend, mesh=False)


def assert_native_hardware_authorized(
    *,
    physical_enabled: bool,
    explicit_physical_opt_in: bool,
) -> None:
    """Require both the persistent and per-invocation physical gates."""

    if not physical_enabled:
        raise StrandsRobotsContractError("Physical runtime is disabled by configuration.")
    if not explicit_physical_opt_in:
        raise StrandsRobotsContractError("This invocation has no explicit physical opt-in.")


def _opencv_camera_config(
    camera_devices: Mapping[str, str | int],
) -> dict[str, dict[str, Any]]:
    if set(camera_devices) != {"top", "wrist"}:
        raise StrandsRobotsContractError("camera_devices must contain exactly top and wrist.")

    cameras: dict[str, dict[str, Any]] = {}
    for name in ("top", "wrist"):
        device = camera_devices[name]
        if isinstance(device, bool) or not isinstance(device, (str, int)):
            raise StrandsRobotsContractError(
                f"{name} camera must be an OpenCV index or device path."
            )
        if isinstance(device, int) and device < 0:
            raise StrandsRobotsContractError(f"{name} camera index cannot be negative.")
        if isinstance(device, str) and not device.strip():
            raise StrandsRobotsContractError(f"{name} camera path cannot be empty.")
        cameras[name] = {
            "type": "opencv",
            "index_or_path": device,
            "fps": 30,
            "width": 640,
            "height": 480,
        }
    return cameras


def create_so101_hardware_robot(
    *,
    port: str,
    robot_id: str,
    calibration_dir: Path,
    camera_devices: Mapping[str, str | int],
    physical_enabled: bool,
    explicit_physical_opt_in: bool,
    robot_factory: Callable[..., Any] | None = None,
) -> Any:
    """Build the experimental native hardware backend behind strict preflight gates."""

    assert_native_hardware_authorized(
        physical_enabled=physical_enabled,
        explicit_physical_opt_in=explicit_physical_opt_in,
    )
    if not port.strip() or not Path(port).exists():
        raise StrandsRobotsContractError(f"Robot serial port is missing: {port!r}")
    if not robot_id.strip():
        raise StrandsRobotsContractError("robot_id cannot be empty.")
    resolved_calibration_dir = calibration_dir.expanduser().resolve()
    calibration_file = resolved_calibration_dir / f"{robot_id}.json"
    if not calibration_file.is_file():
        raise StrandsRobotsContractError(f"Calibration file is missing: {calibration_file}")
    cameras = _opencv_camera_config(camera_devices)

    if robot_factory is None:
        _require_supported_runtime()
        from strands_robots import Robot

        robot_factory = Robot

    return robot_factory(
        "so101",
        mode="real",
        mesh=False,
        port=port,
        id=robot_id,
        calibration_dir=resolved_calibration_dir,
        cameras=cameras,
        action_horizon=NATIVE_ACTION_HORIZON,
        control_frequency=NATIVE_CONTROL_FREQUENCY,
        max_relative_target=TIC_TAC_TOE_MAX_RELATIVE_TARGET,
        disable_torque_on_disconnect=True,
    )


def run_native_move(
    robot: Any,
    policy: Any,
    move_id: str,
    *,
    execution_mode: Literal["sim", "real"] = "sim",
    duration: float = 120.0,
    n_steps: int = NATIVE_ACTION_HORIZON,
    physical_enabled: bool = False,
    explicit_physical_opt_in: bool = False,
) -> dict[str, Any]:
    """Run one exact training task through a pre-built native policy object."""

    if execution_mode not in {"sim", "real"}:
        raise StrandsRobotsContractError("execution_mode must be sim or real; auto is forbidden.")
    if execution_mode == "real":
        assert_native_hardware_authorized(
            physical_enabled=physical_enabled,
            explicit_physical_opt_in=explicit_physical_opt_in,
        )
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise StrandsRobotsContractError("duration must be a positive finite number.")
    if not math.isfinite(float(duration)) or duration <= 0:
        raise StrandsRobotsContractError("duration must be a positive finite number.")
    if isinstance(n_steps, bool) or not isinstance(n_steps, int) or n_steps <= 0:
        raise StrandsRobotsContractError("n_steps must be a positive integer.")

    task = task_for_move(move_id)
    return robot.run_policy(
        policy_object=policy,
        instruction=task,
        duration=float(duration),
        n_steps=n_steps,
    )
