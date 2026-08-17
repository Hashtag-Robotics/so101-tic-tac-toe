from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.version import InvalidVersion, Version
from serial.tools import list_ports

from hashtag_robotics import __version__
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import discover_macos_cameras
from hashtag_robotics.hardware import resolve_command
from hashtag_robotics.identify import TORQUE_ENABLE, lerobot_torque_register
from hashtag_robotics.models import (
    CapabilityManifest,
    CheckStatus,
    DoctorCheck,
    DoctorReport,
)

PACKAGE_DISTRIBUTIONS = {
    "lerobot": "lerobot",
    "strands-agents": "strands-agents",
    "strands-robots": "strands-robots",
    "torch": "torch",
    "mujoco": "mujoco",
    "opencv": "opencv-python",
    "pyserial": "pyserial",
    "feetech-servo-sdk": "feetech-servo-sdk",
}

LEROBOT_CONSOLE_SCRIPTS = (
    "lerobot-find-port",
    "lerobot-find-cameras",
    "lerobot-setup-motors",
    "lerobot-calibrate",
    "lerobot-teleoperate",
    "lerobot-record",
    "lerobot-replay",
    "lerobot-train",
    "lerobot-rollout",
)

SO101_RUNTIME_MODULES = {
    "scservo_sdk": "feetech-servo-sdk",
    "serial": "pyserial",
    "cv2": "opencv-python-headless",
    "datasets": "datasets",
}


def package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _version(value: str | None) -> Version | None:
    if value is None:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


class DoctorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capabilities(self) -> CapabilityManifest:
        packages = {
            label: package_version(distribution)
            for label, distribution in PACKAGE_DISTRIBUTIONS.items()
        }
        camera_backends: list[str] = []
        if module_available("cv2"):
            camera_backends.append("opencv")
        if module_available("pyrealsense2"):
            camera_backends.append("realsense")

        robot_adapters = ["safe-mock"]
        teleoperator_adapters = ["safe-mock"]
        if module_available("lerobot"):
            robot_adapters.append("lerobot")
            teleoperator_adapters.append("lerobot")
        if module_available("scservo_sdk"):
            robot_adapters.append("feetech")
            teleoperator_adapters.append("feetech")

        policy_adapters = ["mock-policy"]
        if module_available("lerobot"):
            policy_adapters.append("lerobot-local")
        if module_available("strands_robots"):
            policy_adapters.append("strands-robots")

        simulation_backends = ["safe-mock"]
        if module_available("mujoco"):
            simulation_backends.append("mujoco")

        accelerator = "cpu"
        if module_available("torch"):
            import torch

            if torch.cuda.is_available():
                accelerator = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                accelerator = "mps"

        return CapabilityManifest(
            platform_version=__version__,
            python_version=platform.python_version(),
            os=platform.system().lower(),
            architecture=platform.machine(),
            packages=packages,
            accelerator=accelerator,
            ffmpeg=shutil.which("ffmpeg"),
            camera_backends=camera_backends,
            robot_adapters=robot_adapters,
            teleoperator_adapters=teleoperator_adapters,
            policy_adapters=policy_adapters,
            simulation_backends=simulation_backends,
            physical_enabled=self.settings.enable_physical,
        )

    def run(self) -> DoctorReport:
        capabilities = self.capabilities()
        checks: list[DoctorCheck] = []

        python_supported = (3, 12) <= sys.version_info[:2] < (3, 14)
        checks.append(
            DoctorCheck(
                code="python.version",
                label="Python runtime",
                status=CheckStatus.PASS if python_supported else CheckStatus.BLOCKED,
                detail=f"Python {platform.python_version()}",
                remediation=None if python_supported else "Use Python 3.12 or 3.13.",
            )
        )

        os_supported = platform.system().lower() in {"darwin", "linux", "windows"}
        checks.append(
            DoctorCheck(
                code="os.support",
                label="Operating system",
                status=CheckStatus.PASS if os_supported else CheckStatus.WARNING,
                detail=f"{platform.system()} {platform.release()} ({platform.machine()})",
                remediation=None if os_supported else "Run compatibility tests for this OS.",
            )
        )

        ffmpeg = shutil.which("ffmpeg")
        checks.append(
            DoctorCheck(
                code="binary.ffmpeg",
                label="FFmpeg",
                status=CheckStatus.PASS if ffmpeg else CheckStatus.WARNING,
                detail=ffmpeg or "Not found",
                remediation=None if ffmpeg else "Install FFmpeg before video recording.",
            )
        )

        disk = shutil.disk_usage(self.settings.data_dir)
        free_gb = disk.free / (1024**3)
        checks.append(
            DoctorCheck(
                code="storage.free",
                label="Artifact storage",
                status=CheckStatus.PASS if free_gb >= 10 else CheckStatus.WARNING,
                detail=f"{free_gb:.1f} GB free at {self.settings.data_dir}",
                remediation=None if free_gb >= 10 else "Free at least 10 GB for datasets.",
            )
        )

        for label in ("lerobot", "strands-agents", "strands-robots", "torch"):
            value = capabilities.packages[label]
            required_for_core = label == "torch"
            status = (
                CheckStatus.PASS
                if value
                else (CheckStatus.WARNING if required_for_core else CheckStatus.NOT_APPLICABLE)
            )
            checks.append(
                DoctorCheck(
                    code=f"package.{label}",
                    label=label,
                    status=status,
                    detail=value or "Optional package is not installed",
                    remediation=(
                        None if value else f"Install the matching feature pack to enable {label}."
                    ),
                )
            )

        lerobot = _version(capabilities.packages["lerobot"])
        strands_robots = _version(capabilities.packages["strands-robots"])
        pair_installed = lerobot is not None and strands_robots is not None
        legacy_conflict = bool(
            pair_installed and lerobot >= Version("0.6") and strands_robots <= Version("0.4.1")
        )
        native_contract_conflict = bool(
            pair_installed
            and strands_robots >= Version("0.5.1")
            and not Version("0.6.1") <= lerobot < Version("0.7")
        )
        if not pair_installed:
            compatibility_status = CheckStatus.NOT_APPLICABLE
            compatibility_detail = "Install both optional packages to check their version pair."
            compatibility_remediation = None
        elif legacy_conflict:
            compatibility_status = CheckStatus.BLOCKED
            compatibility_detail = (
                "Known conflict: Strands Robots 0.4.1 and older require LeRobot below 0.6."
            )
            compatibility_remediation = (
                "Use the strands-robots feature pack pinned by this project."
            )
        elif native_contract_conflict:
            compatibility_status = CheckStatus.BLOCKED
            compatibility_detail = (
                "Strands Robots 0.5.1+ requires LeRobot >=0.6.1,<0.7.0 for this runtime."
            )
            compatibility_remediation = (
                "Resolve the environment from this project's lock file and feature pack."
            )
        else:
            compatibility_status = CheckStatus.PASS
            compatibility_detail = "No known blocked version pair detected."
            compatibility_remediation = None
        checks.append(
            DoctorCheck(
                code="compat.lerobot-strands-robots",
                label="LeRobot / Strands Robots compatibility",
                status=compatibility_status,
                detail=compatibility_detail,
                remediation=compatibility_remediation,
            )
        )

        lerobot_installed = module_available("lerobot")
        missing_scripts = [
            command for command in LEROBOT_CONSOLE_SCRIPTS if resolve_command(command) is None
        ]
        checks.append(
            DoctorCheck(
                code="binary.lerobot-scripts",
                label="LeRobot console scripts",
                status=(
                    CheckStatus.NOT_APPLICABLE
                    if not lerobot_installed
                    else CheckStatus.PASS
                    if not missing_scripts
                    else CheckStatus.BLOCKED
                ),
                detail=(
                    "The so101 feature pack is not installed."
                    if not lerobot_installed
                    else f"All {len(LEROBOT_CONSOLE_SCRIPTS)} console scripts resolved."
                    if not missing_scripts
                    else f"Missing: {', '.join(missing_scripts)}"
                ),
                remediation=(
                    None
                    if not lerobot_installed or not missing_scripts
                    else "Reinstall the so101 feature pack: uv sync --extra so101"
                ),
            )
        )

        missing_modules = [
            distribution
            for module, distribution in SO101_RUNTIME_MODULES.items()
            if not module_available(module)
        ]
        checks.append(
            DoctorCheck(
                code="package.so101-runtime",
                label="SO-101 runtime packages",
                status=(
                    CheckStatus.NOT_APPLICABLE
                    if not lerobot_installed
                    else CheckStatus.PASS
                    if not missing_modules
                    else CheckStatus.BLOCKED
                ),
                detail=(
                    "The so101 feature pack is not installed."
                    if not lerobot_installed
                    else "Feetech, serial, camera and dataset runtimes are importable."
                    if not missing_modules
                    else f"Missing: {', '.join(missing_modules)}"
                ),
                remediation=(
                    None
                    if not lerobot_installed or not missing_modules
                    else "Install lerobot[core_scripts,feetech] via: uv sync --extra so101"
                ),
            )
        )

        checks.append(self._torque_register_check())
        checks.append(self._serial_access_check())
        checks.append(self._keyboard_path_check())
        checks.append(self._camera_device_check())

        checks.append(
            DoctorCheck(
                code="physical.mode",
                label="Physical actuation gate",
                status=(CheckStatus.WARNING if self.settings.enable_physical else CheckStatus.PASS),
                detail=(
                    "Physical adapters are enabled."
                    if self.settings.enable_physical
                    else "Physical adapters are locked; sim/read-only workflows only."
                ),
                remediation=(
                    "Keep disabled until the HIL checklist is complete."
                    if self.settings.enable_physical
                    else None
                ),
            )
        )

        statuses = {check.status for check in checks}
        overall = (
            CheckStatus.BLOCKED
            if CheckStatus.BLOCKED in statuses
            else CheckStatus.WARNING
            if CheckStatus.WARNING in statuses
            else CheckStatus.PASS
        )
        return DoctorReport(overall=overall, checks=checks, capabilities=capabilities)

    def _torque_register_check(self) -> DoctorCheck:
        """Prove the address the emergency stop writes is still the right one.

        `release_torque` writes a constant rather than resolving LeRobot's
        control table, because that resolution imports torch and was measured at
        3.46 s on this machine -- too long to spend before de-energising an arm.
        The constant is only safe if something checks it, and this is the calm
        moment to do it: a firmware revision that moved the register would
        otherwise be discovered during an emergency, by the arm not going limp.
        """
        shipped = lerobot_torque_register()
        if shipped is None:
            return DoctorCheck(
                code="safety.torque-register",
                label="Emergency stop torque register",
                status=CheckStatus.NOT_APPLICABLE,
                detail=(
                    "LeRobot is not installed, so the built-in Torque_Enable address "
                    f"{TORQUE_ENABLE[0]} cannot be cross-checked."
                ),
                remediation=None,
            )
        if shipped == TORQUE_ENABLE:
            return DoctorCheck(
                code="safety.torque-register",
                label="Emergency stop torque register",
                status=CheckStatus.PASS,
                detail=(
                    f"LeRobot agrees Torque_Enable is at address {TORQUE_ENABLE[0]}, "
                    "which is what the emergency stop writes."
                ),
                remediation=None,
            )
        return DoctorCheck(
            code="safety.torque-register",
            label="Emergency stop torque register",
            status=CheckStatus.BLOCKED,
            detail=(
                f"The emergency stop writes address {TORQUE_ENABLE[0]} but LeRobot's "
                f"control table now says {shipped[0]}. The stop would not de-energise "
                "the arm."
            ),
            remediation=(
                "Update TORQUE_ENABLE in hashtag_robotics/identify.py to match the "
                "installed LeRobot control table, then re-run the physical stop test."
            ),
        )

    def _serial_access_check(self) -> DoctorCheck:
        ports = [port.device for port in list_ports.comports() if port.vid is not None]
        if not ports:
            return DoctorCheck(
                code="serial.access",
                label="Serial port access",
                status=CheckStatus.NOT_APPLICABLE,
                detail="No USB serial device is connected.",
                remediation=None,
            )
        denied = [port for port in ports if not os.access(port, os.R_OK | os.W_OK)]
        return DoctorCheck(
            code="serial.access",
            label="Serial port access",
            status=CheckStatus.PASS if not denied else CheckStatus.BLOCKED,
            detail=(
                f"{len(ports)} serial device(s) readable and writable."
                if not denied
                else f"Permission denied: {', '.join(denied)}"
            ),
            remediation=(
                None
                if not denied
                else f"Add the user to the dialout group: sudo usermod -aG dialout {_user_name()}"
            ),
        )

    def _keyboard_path_check(self) -> DoctorCheck:
        wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or (
            os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        )
        headless = platform.system() == "Linux" and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        )
        global_capture = module_available("pynput") and not wayland and not headless
        return DoctorCheck(
            code="session.keyboard",
            label="Interactive keyboard path",
            status=CheckStatus.PASS if global_capture else CheckStatus.WARNING,
            detail=(
                "Global keyboard capture is available for LeRobot interactive commands."
                if global_capture
                else "Global keyboard capture is unavailable on this session."
            ),
            remediation=(
                None
                if global_capture
                else "Send episode and calibration keys from the dashboard input channel."
            ),
        )

    def _camera_device_check(self) -> DoctorCheck:
        if platform.system() == "Darwin":
            # Doctor is polled by the dashboard. macOS camera enumeration is
            # active I/O (system_profiler + AVFoundation) and can stall a UVC
            # stream that LeRobot already owns, so this health read must never
            # refresh topology. Startup and the explicit scan action populate
            # the shared snapshot through the lease-aware DiscoveryService.
            cameras = discover_macos_cameras(auto_refresh=False)
            return DoctorCheck(
                code="camera.devices",
                label="Camera devices",
                status=CheckStatus.PASS if cameras else CheckStatus.WARNING,
                detail=(
                    f"{len(cameras)} camera(s) resolved through AVFoundation."
                    if cameras
                    else "No AVFoundation camera found; no-camera teleoperation stays available."
                ),
                remediation=None if cameras else "Connect a USB camera and scan again.",
            )
        by_id = Path("/dev/v4l/by-id")
        cameras = sorted(item.name for item in by_id.iterdir()) if by_id.is_dir() else []
        if platform.system() != "Linux":
            return DoctorCheck(
                code="camera.devices",
                label="Camera devices",
                status=CheckStatus.NOT_APPLICABLE,
                detail="Stable camera paths are only enumerated on Linux.",
                remediation=None,
            )
        return DoctorCheck(
            code="camera.devices",
            label="Camera devices",
            status=CheckStatus.PASS if cameras else CheckStatus.WARNING,
            detail=(
                f"{len(cameras)} stable camera path(s) under /dev/v4l/by-id."
                if cameras
                else "No camera found; no-camera teleoperation stays available."
            ),
            remediation=None if cameras else "Connect a USB camera before recording.",
        )


def _user_name() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or "<user>"


def diagnostics_payload(settings: Settings) -> dict[str, object]:
    report = DoctorService(settings).run()
    return {
        "doctor": report.model_dump(mode="json"),
        "paths": {
            "data_dir": str(Path(settings.data_dir).resolve()),
        },
        "safety": {
            "physical_enabled": settings.enable_physical,
            "network_bind": settings.host,
        },
    }
