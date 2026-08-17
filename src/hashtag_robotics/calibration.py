from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from hashtag_robotics.config import Settings
from hashtag_robotics.models import (
    CalibrationArtifact,
    CalibrationSource,
    CheckStatus,
    DeviceRecord,
    DeviceRole,
    RobotProfile,
    SafetyCheck,
    TeleoperatorProfile,
    utc_now,
)
from hashtag_robotics.repository import Repository

MOTOR_FIELDS = ("id", "drive_mode", "homing_offset", "range_min", "range_max")

# A Feetech STS3215 reports a 12-bit position, so a joint that was actually
# swept end to end spans hundreds of counts. Anything under this was almost
# certainly never moved during calibration -- the single most common mistake,
# and one a min < max test cannot see.
FULL_SCALE_COUNTS = 4096
NARROW_SPAN_COUNTS = 200

DEVICE_DIRECTORIES: dict[str, tuple[str, str, DeviceRole]] = {
    "so101_follower": ("robots", "so_follower", DeviceRole.FOLLOWER),
    "so100_follower": ("robots", "so_follower", DeviceRole.FOLLOWER),
    "so101_leader": ("teleoperators", "so_leader", DeviceRole.LEADER),
    "so100_leader": ("teleoperators", "so_leader", DeviceRole.LEADER),
}


class CalibrationError(RuntimeError):
    pass


def checksum_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def motor_spans(motors: dict[str, Any]) -> dict[str, int]:
    """Recorded range of motion per joint, in raw encoder counts."""
    spans: dict[str, int] = {}
    for name, values in motors.items():
        if isinstance(values, dict) and "range_min" in values and "range_max" in values:
            spans[name] = int(values["range_max"]) - int(values["range_min"])
    return spans


def validate_motors(motors: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    warnings: list[str] = []
    if not motors:
        problems.append("The calibration file contains no motors.")
    identifiers: list[int] = []
    for name, values in motors.items():
        if not isinstance(values, dict):
            problems.append(f"Motor '{name}' is not a calibration object.")
            continue
        missing = [field for field in MOTOR_FIELDS if field not in values]
        if missing:
            problems.append(f"Motor '{name}' is missing {', '.join(missing)}.")
            continue
        span = int(values["range_max"]) - int(values["range_min"])
        if span <= 0:
            problems.append(f"Motor '{name}' has an empty range of motion.")
        elif span < NARROW_SPAN_COUNTS:
            percent = span / FULL_SCALE_COUNTS * 100
            warnings.append(
                f"Motor '{name}' only spans {span} counts ({percent:.1f}% of full scale); "
                "it was almost certainly never swept during calibration."
            )
        identifiers.append(int(values["id"]))
    if len(identifiers) != len(set(identifiers)):
        problems.append("Motor ids are not unique.")
    return {
        "valid": not problems,
        "motor_count": len(motors),
        "problems": problems,
        "warnings": warnings,
        "spans": motor_spans(motors),
    }


def compare_motors(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> list[dict[str, Any]]:
    """Per-joint span diff, so a collapsed range is visible instead of implied."""
    old_spans = motor_spans(previous or {})
    new_spans = motor_spans(current)
    rows: list[dict[str, Any]] = []
    for name in current:
        new = new_spans.get(name)
        old = old_spans.get(name)
        change = None
        if new is not None and old:
            change = round((new - old) / old * 100, 1)
        rows.append(
            {
                "motor": name,
                "previous_span": old,
                "span": new,
                "change_percent": change,
                "range": [current[name].get("range_min"), current[name].get("range_max")]
                if isinstance(current[name], dict)
                else None,
                "suspicious": new is not None and new < NARROW_SPAN_COUNTS,
            }
        )
    return rows


class CalibrationStore:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def live_path(self, device_type: str, device_id: str) -> Path:
        entry = DEVICE_DIRECTORIES.get(device_type)
        if entry is None:
            raise CalibrationError(f"Unknown LeRobot device type '{device_type}'.")
        group, class_name, _ = entry
        return self.settings.calibration_dir / group / class_name / f"{device_id}.json"

    def role_for(self, device_type: str) -> DeviceRole:
        entry = DEVICE_DIRECTORIES.get(device_type)
        if entry is None:
            raise CalibrationError(f"Unknown LeRobot device type '{device_type}'.")
        return entry[2]

    def read(self, path: Path) -> tuple[dict[str, dict[str, int]], str]:
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise CalibrationError(f"Calibration file '{path}' cannot be read.") from error
        try:
            motors = json.loads(payload)
        except json.JSONDecodeError as error:
            raise CalibrationError(f"Calibration file '{path}' is not valid JSON.") from error
        if not isinstance(motors, dict):
            raise CalibrationError(f"Calibration file '{path}' is not a motor map.")
        return motors, checksum_bytes(payload)

    def capture(
        self,
        device_type: str,
        device_id: str,
        source: CalibrationSource,
        target_profile_id: str | None = None,
        supersedes: str | None = None,
        origin: Path | None = None,
    ) -> CalibrationArtifact:
        live = origin or self.live_path(device_type, device_id)
        motors, digest = self.read(live)
        validation = validate_motors(motors)

        artifact = CalibrationArtifact(
            role=self.role_for(device_type),
            device_type=device_type,
            device_id=device_id,
            target_profile_id=target_profile_id,
            source=source,
            checksum=digest,
            live_path=str(self.live_path(device_type, device_id)),
            stored_path="",
            motors=motors,
            validation_result=validation,
            supersedes=supersedes or self.latest_id(device_type, device_id),
        )
        stored = self._archive_path(artifact)
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live, stored)
        artifact.stored_path = str(stored)
        self.repository.upsert_entity("calibration", artifact)
        return artifact

    def backup(
        self,
        device_type: str,
        device_id: str,
        target_profile_id: str | None = None,
    ) -> CalibrationArtifact | None:
        live = self.live_path(device_type, device_id)
        if not live.is_file():
            return None
        return self.capture(
            device_type,
            device_id,
            CalibrationSource.BACKUP,
            target_profile_id=target_profile_id,
        )

    def restore(self, artifact_id: str) -> CalibrationArtifact:
        artifact = self.repository.get_entity("calibration", artifact_id, CalibrationArtifact)
        if artifact is None:
            raise CalibrationError(f"Calibration artifact '{artifact_id}' was not found.")
        stored = Path(artifact.stored_path)
        if not stored.is_file():
            raise CalibrationError(f"Stored calibration '{stored}' is missing.")

        self.backup(artifact.device_type, artifact.device_id, artifact.target_profile_id)
        live = self.live_path(artifact.device_type, artifact.device_id)
        live.parent.mkdir(parents=True, exist_ok=True)
        staging = live.with_suffix(".json.tmp")
        shutil.copy2(stored, staging)
        staging.replace(live)
        # Restoring a revision means making it the active one. Without rebinding,
        # the profile keeps pointing at the superseded revision and every
        # physical job is blocked by a checksum that no longer matches disk.
        self.rebind(artifact)
        return artifact

    def rebind(self, artifact: CalibrationArtifact) -> str | None:
        """Point the profile this artifact belongs to at this revision."""
        role = self.role_for(artifact.device_type)
        kind = "robot" if role == DeviceRole.FOLLOWER else "teleoperator"
        model: type[RobotProfile] | type[TeleoperatorProfile] = (
            RobotProfile if role == DeviceRole.FOLLOWER else TeleoperatorProfile
        )

        profile = (
            self.repository.get_entity(kind, artifact.target_profile_id, model)
            if artifact.target_profile_id
            else None
        )
        if profile is None:
            profile = next(
                (
                    item
                    for item in self.repository.list_entities(kind, model)
                    if item.calibration_id == artifact.device_id
                    and (
                        item.robot_type
                        if isinstance(item, RobotProfile)
                        else item.teleoperator_type
                    )
                    == artifact.device_type
                ),
                None,
            )
        if profile is None:
            return None

        if isinstance(profile, RobotProfile):
            self.bind_robot(profile, artifact)
        else:
            self.bind_teleoperator(profile, artifact)
        return profile.id

    def import_directory(self, root: Path) -> list[CalibrationArtifact]:
        if not root.is_dir():
            raise CalibrationError(f"Calibration directory '{root}' was not found.")
        imported: list[CalibrationArtifact] = []
        for device_type, (group, class_name, _) in DEVICE_DIRECTORIES.items():
            if not device_type.startswith("so101"):
                continue
            source_dir = root / group / class_name
            if not source_dir.is_dir():
                continue
            for candidate in sorted(source_dir.glob("*.json")):
                artifact = self.capture(
                    device_type,
                    candidate.stem,
                    CalibrationSource.IMPORTED,
                    origin=candidate,
                )
                imported.append(self.adopt(artifact))
        return imported

    def adopt(self, artifact: CalibrationArtifact) -> CalibrationArtifact:
        live = self.live_path(artifact.device_type, artifact.device_id)
        if live.is_file():
            return artifact
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(artifact.stored_path), live)
        return artifact

    def latest(self, device_type: str, device_id: str) -> CalibrationArtifact | None:
        matches = [
            artifact
            for artifact in self.repository.list_entities("calibration", CalibrationArtifact)
            if artifact.device_type == device_type and artifact.device_id == device_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda artifact: artifact.created_at)

    def latest_id(self, device_type: str, device_id: str) -> str | None:
        artifact = self.latest(device_type, device_id)
        return artifact.id if artifact else None

    def matches_disk(self, artifact: CalibrationArtifact) -> bool:
        live = Path(artifact.live_path)
        if not live.is_file():
            return False
        return checksum_bytes(live.read_bytes()) == artifact.checksum

    def bind_robot(self, profile: RobotProfile, artifact: CalibrationArtifact) -> RobotProfile:
        profile.calibration_revision = artifact.id
        profile.calibration_id = artifact.device_id
        profile.calibration_verified = bool(artifact.validation_result.get("valid"))
        profile.motor_layout = {
            name: int(values["id"]) for name, values in artifact.motors.items() if "id" in values
        }
        self.repository.upsert_entity("robot", profile)
        return profile

    def bind_teleoperator(
        self,
        profile: TeleoperatorProfile,
        artifact: CalibrationArtifact,
    ) -> TeleoperatorProfile:
        profile.calibration_revision = artifact.id
        profile.calibration_id = artifact.device_id
        self.repository.upsert_entity("teleoperator", profile)
        return profile

    def validate_robot(
        self,
        profile: RobotProfile,
        devices: list[DeviceRecord],
    ) -> list[SafetyCheck]:
        checks: list[SafetyCheck] = []
        device = next(
            (item for item in devices if item.stable_fingerprint == profile.device_fingerprint),
            None,
        )
        checks.append(
            SafetyCheck(
                code="target.device_fingerprint",
                label="Resolved device",
                status=CheckStatus.PASS if device else CheckStatus.BLOCKED,
                message=(
                    f"Fingerprint resolves to {device.stable_path or device.transient_path}."
                    if device
                    else "No connected device matches this profile fingerprint."
                ),
            )
        )
        if device is not None:
            stable = device.stable_path or device.transient_path
            matching = bool(profile.port) and profile.port == stable
            checks.append(
                SafetyCheck(
                    code="target.stable_port",
                    label="Stable port path",
                    status=CheckStatus.PASS if matching else CheckStatus.WARNING,
                    message=(
                        f"Profile port matches {stable}."
                        if matching
                        else f"Profile port is '{profile.port}' but the device is at '{stable}'."
                    ),
                )
            )

        artifact = (
            self.repository.get_entity(
                "calibration", profile.calibration_revision, CalibrationArtifact
            )
            if profile.calibration_revision
            else None
        )
        checks.append(
            SafetyCheck(
                code="calibration.artifact_present",
                label="Calibration artifact",
                status=CheckStatus.PASS if artifact else CheckStatus.BLOCKED,
                message=(
                    f"Bound to revision {artifact.id} ({artifact.source.value})."
                    if artifact
                    else "The profile has no bound calibration revision."
                ),
            )
        )
        if artifact is not None:
            matches = self.matches_disk(artifact)
            checks.append(
                SafetyCheck(
                    code="calibration.checksum_match",
                    label="Calibration checksum",
                    status=CheckStatus.PASS if matches else CheckStatus.BLOCKED,
                    message=(
                        "The live calibration file matches the bound revision."
                        if matches
                        else "The live calibration file drifted from the bound revision."
                    ),
                )
            )
            valid = bool(artifact.validation_result.get("valid"))
            problems = artifact.validation_result.get("problems", [])
            checks.append(
                SafetyCheck(
                    code="calibration.contents_valid",
                    label="Calibration contents",
                    status=CheckStatus.PASS if valid else CheckStatus.BLOCKED,
                    message=(
                        f"{artifact.validation_result.get('motor_count', 0)} motors validated."
                        if valid
                        else "; ".join(problems)
                    ),
                )
            )

        limit = profile.safety_profile.get("max_relative_target")
        checks.append(
            SafetyCheck(
                code="limits.max_relative_target",
                label="Relative target limit",
                status=CheckStatus.PASS if limit else CheckStatus.BLOCKED,
                message=(
                    f"Relative target is capped at {limit}."
                    if limit
                    else "The safety profile does not define max_relative_target."
                ),
            )
        )
        return checks

    def _archive_path(self, artifact: CalibrationArtifact) -> Path:
        stamp = utc_now().strftime("%Y%m%dT%H%M%S")
        return (
            self.settings.calibration_archive_dir
            / artifact.device_type
            / artifact.device_id
            / f"{stamp}-{artifact.source.value}-{artifact.id}.json"
        )
