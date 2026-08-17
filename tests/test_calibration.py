from __future__ import annotations

import json
from pathlib import Path

import pytest

from hashtag_robotics.calibration import CalibrationError, CalibrationStore, validate_motors
from hashtag_robotics.config import Settings
from hashtag_robotics.models import CalibrationSource, DeviceRecord, DeviceRole, RobotProfile
from hashtag_robotics.repository import Repository

FOLLOWER = {
    "shoulder_pan": {
        "id": 1,
        "drive_mode": 0,
        "homing_offset": -180,
        "range_min": 1114,
        "range_max": 3027,
    },
    "shoulder_lift": {
        "id": 2,
        "drive_mode": 0,
        "homing_offset": 763,
        "range_min": 800,
        "range_max": 3168,
    },
    "elbow_flex": {
        "id": 3,
        "drive_mode": 0,
        "homing_offset": 300,
        "range_min": 955,
        "range_max": 3168,
    },
    "wrist_flex": {
        "id": 4,
        "drive_mode": 0,
        "homing_offset": 352,
        "range_min": 930,
        "range_max": 3232,
    },
    "wrist_roll": {
        "id": 5,
        "drive_mode": 0,
        "homing_offset": 132,
        "range_min": 0,
        "range_max": 4095,
    },
    "gripper": {
        "id": 6,
        "drive_mode": 0,
        "homing_offset": 209,
        "range_min": 2000,
        "range_max": 3400,
    },
}

LEADER = {
    "shoulder_pan": {
        "id": 1,
        "drive_mode": 0,
        "homing_offset": 475,
        "range_min": 1370,
        "range_max": 3302,
    },
    "gripper": {
        "id": 6,
        "drive_mode": 0,
        "homing_offset": 12,
        "range_min": 2020,
        "range_max": 3300,
    },
}


@pytest.fixture
def store(tmp_path: Path) -> CalibrationStore:
    settings = Settings(data_dir=tmp_path, open_browser=False, enable_physical=False)
    settings.ensure_directories()
    return CalibrationStore(settings, Repository(settings.database_path))


def write_live(store: CalibrationStore, device_type: str, device_id: str, motors: dict) -> Path:
    path = store.live_path(device_type, device_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(motors, indent=4))
    return path


def external_root(tmp_path: Path) -> Path:
    root = tmp_path / "external" / "calibration"
    follower = root / "robots" / "so_follower"
    leader = root / "teleoperators" / "so_leader"
    follower.mkdir(parents=True)
    leader.mkdir(parents=True)
    (follower / "follower01.json").write_text(json.dumps(FOLLOWER, indent=4))
    (leader / "leader01.json").write_text(json.dumps(LEADER, indent=4))
    return root


def test_live_paths_use_the_lerobot_class_directory_not_the_cli_type(
    store: CalibrationStore,
) -> None:
    follower = store.live_path("so101_follower", "follower01")
    leader = store.live_path("so101_leader", "leader01")
    assert follower.parent.name == "so_follower"
    assert follower.parent.parent.name == "robots"
    assert leader.parent.name == "so_leader"
    assert leader.parent.parent.name == "teleoperators"
    assert store.role_for("so101_follower") == DeviceRole.FOLLOWER
    assert store.role_for("so101_leader") == DeviceRole.LEADER


def test_unknown_device_type_is_refused(store: CalibrationStore) -> None:
    with pytest.raises(CalibrationError, match="Unknown LeRobot device type"):
        store.live_path("so_follower", "follower01")


def test_validate_motors_rejects_an_empty_range() -> None:
    broken = {"wrist_roll": {**FOLLOWER["wrist_roll"], "range_min": 4095}}
    result = validate_motors(broken)
    assert result["valid"] is False
    assert "empty range of motion" in result["problems"][0]


def test_validate_motors_rejects_duplicate_ids() -> None:
    duplicated = {"a": FOLLOWER["shoulder_pan"], "b": FOLLOWER["shoulder_pan"]}
    assert validate_motors(duplicated)["problems"] == ["Motor ids are not unique."]


def test_capture_records_a_checksummed_immutable_copy(store: CalibrationStore) -> None:
    live = write_live(store, "so101_follower", "follower01", FOLLOWER)
    artifact = store.capture("so101_follower", "follower01", CalibrationSource.USER)

    assert artifact.validation_result["valid"] is True
    assert artifact.validation_result["motor_count"] == 6
    assert artifact.motors["gripper"]["id"] == 6
    assert store.matches_disk(artifact) is True

    stored = Path(artifact.stored_path)
    assert stored.is_file()
    assert stored != live
    assert json.loads(stored.read_text()) == FOLLOWER


def test_backup_returns_nothing_when_there_is_no_live_calibration(
    store: CalibrationStore,
) -> None:
    assert store.backup("so101_follower", "follower01") is None


def test_backup_then_overwrite_keeps_the_previous_revision(store: CalibrationStore) -> None:
    write_live(store, "so101_follower", "follower01", FOLLOWER)
    backup = store.backup("so101_follower", "follower01")
    assert backup is not None
    assert backup.source == CalibrationSource.BACKUP

    replaced = {**FOLLOWER, "gripper": {**FOLLOWER["gripper"], "range_max": 9999}}
    write_live(store, "so101_follower", "follower01", replaced)
    latest = store.capture("so101_follower", "follower01", CalibrationSource.USER)

    assert latest.supersedes == backup.id
    assert latest.checksum != backup.checksum
    assert json.loads(Path(backup.stored_path).read_text())["gripper"]["range_max"] == 3400


def test_restore_backs_up_the_current_file_before_writing(store: CalibrationStore) -> None:
    write_live(store, "so101_follower", "follower01", FOLLOWER)
    original = store.capture("so101_follower", "follower01", CalibrationSource.USER)

    damaged = {**FOLLOWER, "gripper": {**FOLLOWER["gripper"], "range_max": 9999}}
    write_live(store, "so101_follower", "follower01", damaged)

    store.restore(original.id)
    live_motors, digest = store.read(store.live_path("so101_follower", "follower01"))
    assert live_motors == FOLLOWER
    assert digest == original.checksum

    archived = store.repository.list_entities("calibration", type(original))
    assert any(item.source == CalibrationSource.BACKUP for item in archived)


def test_restore_refuses_an_unknown_artifact(store: CalibrationStore) -> None:
    with pytest.raises(CalibrationError, match="was not found"):
        store.restore("calib_missing")


def test_import_copies_without_touching_the_source_tree(
    store: CalibrationStore,
    tmp_path: Path,
) -> None:
    root = external_root(tmp_path)
    source_bytes = (root / "robots" / "so_follower" / "follower01.json").read_bytes()

    imported = store.import_directory(root)
    assert {artifact.device_id for artifact in imported} == {"follower01", "leader01"}
    assert all(artifact.source == CalibrationSource.IMPORTED for artifact in imported)

    assert (root / "robots" / "so_follower" / "follower01.json").read_bytes() == source_bytes
    follower = next(item for item in imported if item.device_id == "follower01")
    assert store.matches_disk(follower) is True
    assert store.live_path("so101_follower", "follower01").is_file()


def test_import_refuses_a_missing_directory(store: CalibrationStore, tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="was not found"):
        store.import_directory(tmp_path / "nowhere")


def test_validate_robot_blocks_when_the_live_file_drifted(store: CalibrationStore) -> None:
    write_live(store, "so101_follower", "follower01", FOLLOWER)
    artifact = store.capture("so101_follower", "follower01", CalibrationSource.USER)
    profile = RobotProfile(
        id="robot_follower01",
        name="Follower 01",
        device_fingerprint="fp-follower",
        port="/dev/serial/by-id/usb-follower",
        calibration_revision=artifact.id,
        safety_profile={"max_relative_target": 5.0},
    )
    device = DeviceRecord(
        kind="serial",
        name="SO-101 follower",
        stable_fingerprint="fp-follower",
        stable_path="/dev/serial/by-id/usb-follower",
    )

    healthy = {check.code: check.status.value for check in store.validate_robot(profile, [device])}
    assert healthy["target.device_fingerprint"] == "pass"
    assert healthy["target.stable_port"] == "pass"
    assert healthy["calibration.checksum_match"] == "pass"
    assert healthy["limits.max_relative_target"] == "pass"

    write_live(store, "so101_follower", "follower01", LEADER)
    drifted = {check.code: check.status.value for check in store.validate_robot(profile, [device])}
    assert drifted["calibration.checksum_match"] == "blocked"


def test_validate_robot_blocks_a_disconnected_or_unlimited_profile(
    store: CalibrationStore,
) -> None:
    profile = RobotProfile(id="robot_ghost", name="Ghost", device_fingerprint="fp-missing")
    codes = {check.code: check.status.value for check in store.validate_robot(profile, [])}
    assert codes["target.device_fingerprint"] == "blocked"
    assert codes["calibration.artifact_present"] == "blocked"
    assert codes["limits.max_relative_target"] == "blocked"


def test_bind_robot_records_the_motor_layout(store: CalibrationStore) -> None:
    write_live(store, "so101_follower", "follower01", FOLLOWER)
    artifact = store.capture("so101_follower", "follower01", CalibrationSource.USER)
    profile = store.bind_robot(RobotProfile(name="Follower 01"), artifact)

    assert profile.calibration_revision == artifact.id
    assert profile.calibration_id == "follower01"
    assert profile.calibration_verified is True
    assert profile.motor_layout == {
        "shoulder_pan": 1,
        "shoulder_lift": 2,
        "elbow_flex": 3,
        "wrist_flex": 4,
        "wrist_roll": 5,
        "gripper": 6,
    }


def test_restore_rebinds_the_profile_to_the_restored_revision(
    store: CalibrationStore,
) -> None:
    """A restored revision has to become the active one, binding included.

    Without the rebind the profile keeps pointing at the superseded revision,
    whose checksum no longer matches disk, so every physical job stays blocked
    even though the operator just restored a known-good calibration.
    """
    repository = store.repository
    profile = RobotProfile(name="Follower 01", calibration_id="follower01")
    repository.upsert_entity("robot", profile)

    write_live(store, "so101_follower", "follower01", FOLLOWER)
    original = store.capture("so101_follower", "follower01", CalibrationSource.IMPORTED)
    store.bind_robot(profile, original)

    narrow = {name: dict(values) for name, values in FOLLOWER.items()}
    narrow["shoulder_pan"]["range_max"] = 1614
    write_live(store, "so101_follower", "follower01", narrow)
    replacement = store.capture("so101_follower", "follower01", CalibrationSource.USER)
    store.bind_robot(repository.get_entity("robot", profile.id, RobotProfile), replacement)
    assert (
        repository.get_entity("robot", profile.id, RobotProfile).calibration_revision
        == replacement.id
    )

    restored = store.restore(original.id)

    bound = repository.get_entity("robot", profile.id, RobotProfile)
    assert restored.id == original.id
    assert bound.calibration_revision == original.id
    assert store.matches_disk(restored) is True
