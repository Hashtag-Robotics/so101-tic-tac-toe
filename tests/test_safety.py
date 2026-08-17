from __future__ import annotations

import json
from pathlib import Path

import pytest

from hashtag_robotics.calibration import CalibrationStore
from hashtag_robotics.camera import CameraService
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.models import (
    CalibrationSource,
    CameraProfile,
    CheckStatus,
    JobCreateRequest,
    JobKind,
    PolicyManifest,
    ResolvedTargets,
    RobotProfile,
    TargetMode,
    TeleoperatorProfile,
)
from hashtag_robotics.repository import Repository
from hashtag_robotics.safety import SafetyService
from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_POLICY_REPO,
    TIC_TAC_TOE_POLICY_REVISION,
    TIC_TAC_TOE_PROFILE,
    canonical_tic_tac_toe_parameters,
)


def motors(offsets: list[int]) -> dict[str, dict[str, int]]:
    names = (
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    )
    return {
        name: {
            "id": index + 1,
            "drive_mode": 0,
            "homing_offset": offsets[index],
            "range_min": 800,
            "range_max": 3200,
        }
        for index, name in enumerate(names)
    }


FOLLOWER_MOTORS = motors([-180, 763, 300, 352, 132, 209])
LEADER_MOTORS = motors([475, 1002, 41, 130, 2036, 12])


class FakePort:
    """Mimics the pyserial ListPortInfo surface that discovery reads."""

    def __init__(self, device: str, serial_number: str, product: str) -> None:
        self.device = device
        self.vid = 0x1A86
        self.pid = 0x7523
        self.serial_number = serial_number
        self.manufacturer = "QinHeng Electronics"
        self.product = product
        self.description = product
        self.hwid = f"USB VID:PID=1A86:7523 SER={serial_number}"


class Lab:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        calibration: CalibrationStore,
        discovery: DiscoveryService,
        safety: SafetyService,
        ports: list[FakePort],
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.calibration = calibration
        self.discovery = discovery
        self.safety = safety
        self.ports = ports
        self.robot: RobotProfile
        self.teleoperator: TeleoperatorProfile
        self.follower_port: str
        self.leader_port: str
        self.camera_root: Path

    def connect_camera(self, name: str = "usb-SO101_Front_0001-video-index0") -> str:
        """Publish a fake /dev/v4l/by-id entry and return its path."""
        target = self.camera_root / "video-node"
        target.write_bytes(b"")
        link = self.camera_root / name
        link.symlink_to(target)
        return str(link)

    def write_calibration(
        self,
        device_type: str,
        device_id: str,
        payload: dict[str, dict[str, int]],
    ) -> None:
        path = self.calibration.live_path(device_type, device_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))


@pytest.fixture
def lab(tmp_path: Path, monkeypatch) -> Lab:
    monkeypatch.setattr("hashtag_robotics.safety.resolve_command", lambda _: "/test/command")
    ports = [
        FakePort("/dev/ttyACM0", "SO101FOLLOWER", "SO-101 Follower"),
        FakePort("/dev/ttyACM1", "SO101LEADER", "SO-101 Leader"),
    ]
    monkeypatch.setattr("hashtag_robotics.discovery.list_ports.comports", lambda: list(ports))
    # Serial needs the same isolation: on a machine with real arms attached the
    # host's /dev/serial/by-id resolves a fake port to a real cable.
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")
    # Point camera discovery at a controlled tree so the host webcam stays out of the tests.
    camera_root = tmp_path / "v4l-by-id"
    camera_root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", camera_root)

    settings = Settings(data_dir=tmp_path, enable_physical=True, open_browser=False)
    settings.ensure_directories()
    repository = Repository(settings.database_path)
    calibration = CalibrationStore(settings, repository)
    discovery = DiscoveryService(repository)
    cameras = CameraService(settings, repository, discovery)
    safety = SafetyService(settings, repository, calibration, discovery, cameras)
    fixture = Lab(settings, repository, calibration, discovery, safety, ports)
    fixture.camera_root = camera_root

    connected = {
        record.serial_number: record for record in discovery.snapshot(include_simulated=False)
    }
    follower = connected["SO101FOLLOWER"]
    leader = connected["SO101LEADER"]
    fixture.follower_port = follower.stable_path or follower.transient_path or ""
    fixture.leader_port = leader.stable_path or leader.transient_path or ""

    fixture.write_calibration("so101_follower", "follower01", FOLLOWER_MOTORS)
    fixture.write_calibration("so101_leader", "leader01", LEADER_MOTORS)

    robot = RobotProfile(
        name="Follower 01",
        robot_type="so101_follower",
        device_fingerprint=follower.stable_fingerprint,
        port=fixture.follower_port,
        safety_profile={"max_relative_target": 5.0},
    )
    repository.upsert_entity("robot", robot)
    calibration.bind_robot(
        robot,
        calibration.capture("so101_follower", "follower01", CalibrationSource.IMPORTED),
    )

    teleoperator = TeleoperatorProfile(
        name="Leader 01",
        teleoperator_type="so101_leader",
        device_fingerprint=leader.stable_fingerprint,
        port=fixture.leader_port,
    )
    repository.upsert_entity("teleoperator", teleoperator)
    calibration.bind_teleoperator(
        teleoperator,
        calibration.capture("so101_leader", "leader01", CalibrationSource.IMPORTED),
    )

    fixture.robot = robot
    fixture.teleoperator = teleoperator
    return fixture


def teleoperation(lab: Lab, **overrides: object) -> JobCreateRequest:
    parameters: dict[str, object] = {
        "robot_profile_id": lab.robot.id,
        "teleoperator_profile_id": lab.teleoperator.id,
        "workspace_confirmed": True,
    }
    parameters.update(overrides)
    return JobCreateRequest(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )


def codes(result, status: CheckStatus) -> set[str]:
    return {check.code for check in result.checks if check.status == status}


def test_tic_tac_toe_profile_pins_policy_calibration_and_motion_limit(lab: Lab) -> None:
    policy = PolicyManifest(
        name="Tic-Tac-Toe 120K",
        policy_type="smolvla",
        model_repo_id=TIC_TAC_TOE_POLICY_REPO,
        model_revision=TIC_TAC_TOE_POLICY_REVISION,
    )
    lab.repository.upsert_entity("policy", policy)
    parameters = canonical_tic_tac_toe_parameters(
        {
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": "X-7",
            "policy_id": policy.id,
        }
    )
    request = JobCreateRequest(
        kind=JobKind.POLICY_ROLLOUT,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )
    resolved = ResolvedTargets(
        robot_id="portable_follower",
        robot_calibration_revision="calibration-sha256",
        max_relative_target=5.0,
    )

    checks = lab.safety._tic_tac_toe_checks(request, resolved)

    assert all(check.status == CheckStatus.PASS for check in checks)


def test_tic_tac_toe_profile_rejects_an_unvalidated_policy_revision(lab: Lab) -> None:
    policy = PolicyManifest(
        name="Different revision",
        policy_type="smolvla",
        model_repo_id=TIC_TAC_TOE_POLICY_REPO,
        model_revision="a" * 40,
    )
    lab.repository.upsert_entity("policy", policy)
    parameters = canonical_tic_tac_toe_parameters(
        {
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": "O-3",
            "policy_id": policy.id,
        }
    )
    request = JobCreateRequest(
        kind=JobKind.POLICY_ROLLOUT,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )

    checks = lab.safety._tic_tac_toe_checks(
        request,
        ResolvedTargets(robot_id="test_follower", max_relative_target=5.0),
    )

    assert next(check for check in checks if check.code == "ttt.policy_revision").status == (
        CheckStatus.BLOCKED
    )


def test_client_cannot_self_certify_physical_readiness(lab: Lab) -> None:
    request = JobCreateRequest(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters={
            "calibration_verified": True,
            "joint_limits_verified": True,
            "emergency_stop_ready": True,
            "robot_port": "/dev/injected",
            "robot_id": "injected",
        },
        requested_by="test",
    )
    result = lab.safety.preflight(request)

    assert result.allowed is False
    assert not any(check.code.startswith("safety.") for check in result.checks)
    assert {
        "target.robot_resolved",
        "target.teleoperator_resolved",
        "workspace.confirmed",
    } <= codes(result, CheckStatus.BLOCKED)
    assert result.resolved is not None
    assert result.resolved.robot_port is None


def test_resolved_teleoperation_is_allowed_and_carries_server_owned_parameters(lab: Lab) -> None:
    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is True
    assert result.requires_approval is True
    resolved = result.resolved
    assert resolved is not None
    assert resolved.robot_port == lab.follower_port
    assert resolved.teleop_port == lab.leader_port
    assert resolved.robot_id == "follower01"
    assert resolved.teleop_id == "leader01"
    assert resolved.max_relative_target == 5.0
    assert resolved.action_shape == [6]
    assert resolved.robot_calibration_dir is not None
    assert resolved.robot_calibration_dir.endswith("robots/so_follower")
    assert resolved.teleop_calibration_dir is not None
    assert resolved.teleop_calibration_dir.endswith("teleoperators/so_leader")

    parameters = resolved.command_parameters()
    assert parameters["robot_port"] == lab.follower_port
    assert parameters["robot_type"] == "so101_follower"
    assert "workspace_confirmed" not in parameters

    leases = resolved.resource_requests()
    assert {lease.resource_type for lease in leases} == {"robot", "teleoperator"}
    assert all(lease.mode == "exclusive" for lease in leases)


def test_a_client_supplied_port_never_reaches_the_resolved_targets(lab: Lab) -> None:
    result = lab.safety.preflight(teleoperation(lab, robot_port="/dev/attacker", robot_id="evil"))

    assert result.allowed is True
    assert result.resolved is not None
    assert result.resolved.robot_port == lab.follower_port
    assert result.resolved.robot_id == "follower01"


def test_a_drifted_calibration_file_blocks_actuation(lab: Lab) -> None:
    drifted = json.loads(json.dumps(FOLLOWER_MOTORS))
    drifted["gripper"]["range_max"] = 3999
    lab.write_calibration("so101_follower", "follower01", drifted)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is False
    assert "calibration.robot.checksum_match" in codes(result, CheckStatus.BLOCKED)


def test_a_calibration_job_does_not_require_an_existing_revision(lab: Lab) -> None:
    request = JobCreateRequest(
        kind=JobKind.CALIBRATION,
        target_mode=TargetMode.REAL,
        parameters={
            "role": "robot",
            "robot_profile_id": lab.robot.id,
            "workspace_confirmed": True,
        },
        requested_by="test",
    )
    result = lab.safety.preflight(request)

    assert result.allowed is True
    skipped = codes(result, CheckStatus.NOT_APPLICABLE)
    assert {
        "calibration.robot.artifact_present",
        "calibration.robot.checksum_match",
        "limits.max_relative_target",
        "target.teleoperator_resolved",
    } <= skipped


def test_a_latched_emergency_stop_blocks_physical_work(lab: Lab) -> None:
    lab.safety.engage_estop("test")
    assert lab.safety.estop_engaged() is True

    result = lab.safety.preflight(teleoperation(lab))
    assert result.allowed is False
    assert "estop.armed" in codes(result, CheckStatus.BLOCKED)

    lab.safety.clear_estop()
    assert lab.safety.preflight(teleoperation(lab)).allowed is True


def test_a_relative_target_above_the_server_ceiling_is_blocked(lab: Lab) -> None:
    lab.robot.safety_profile = {"max_relative_target": lab.settings.max_relative_target_ceiling + 1}
    lab.repository.upsert_entity("robot", lab.robot)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is False
    assert "limits.max_relative_target" in codes(result, CheckStatus.BLOCKED)
    assert result.resolved is not None
    assert result.resolved.max_relative_target is None


def test_the_leader_and_the_follower_must_be_different_devices(lab: Lab) -> None:
    lab.teleoperator.device_fingerprint = lab.robot.device_fingerprint
    lab.repository.upsert_entity("teleoperator", lab.teleoperator)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is False
    assert "target.role_distinct" in codes(result, CheckStatus.BLOCKED)


def test_a_mapped_camera_is_resolved_into_the_lerobot_command(lab: Lab) -> None:
    path = lab.connect_camera()
    device = next(
        item
        for item in lab.discovery.snapshot(include_simulated=False)
        if item.kind.value == "camera"
    )
    camera = CameraProfile(
        name="Front",
        device_fingerprint=device.stable_fingerprint,
        semantic_name="front",
        width=640,
        height=480,
        fps=30,
    )
    lab.repository.upsert_entity("camera", camera)
    lab.robot.camera_mapping = {"front": camera.id}
    lab.repository.upsert_entity("robot", lab.robot)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is True
    assert "camera.mapping_resolved" in codes(result, CheckStatus.PASS)
    resolved = result.resolved
    assert resolved is not None
    assert resolved.cameras["front"] == {
        "type": "opencv",
        "index_or_path": path,
        "fps": 30,
        "width": 640,
        "height": 480,
        "rotation": 0,
    }
    assert resolved.command_parameters()["cameras"]["front"]["index_or_path"] == path
    leases = {(lease.resource_type, lease.mode) for lease in resolved.resource_requests()}
    assert ("camera", "exclusive") in leases


def test_a_mapped_avfoundation_uid_camera_is_reported_without_an_index(
    lab: Lab, monkeypatch
) -> None:
    lab.connect_camera()
    device = next(
        item
        for item in lab.discovery.snapshot(include_simulated=False)
        if item.kind.value == "camera"
    )
    camera = CameraProfile(
        name="Wrist",
        device_fingerprint=device.stable_fingerprint,
        semantic_name="wrist",
    )
    lab.repository.upsert_entity("camera", camera)
    lab.robot.camera_mapping = {"wrist": camera.id}
    lab.repository.upsert_entity("robot", lab.robot)
    config = {
        "type": "avfoundation_uid",
        "unique_id": "test-wrist-camera-uid",
        "helper_path": "/tmp/avfoundation-uid-capture",
        "fps": 30,
        "width": 640,
        "height": 480,
        "rotation": 0,
    }
    monkeypatch.setattr(lab.safety.cameras, "lerobot_config", lambda *_, **__: config)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is True
    check = next(item for item in result.checks if item.code == "camera.mapping_resolved")
    assert "wrist=test-wrist-camera-uid" in check.message
    assert result.resolved is not None
    assert result.resolved.cameras["wrist"] == config


def test_a_mapped_camera_that_is_unplugged_blocks_actuation(lab: Lab) -> None:
    camera = CameraProfile(
        name="Front",
        device_fingerprint="camera-that-is-not-here",
        semantic_name="front",
    )
    lab.repository.upsert_entity("camera", camera)
    lab.robot.camera_mapping = {"front": camera.id}
    lab.repository.upsert_entity("robot", lab.robot)

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is False
    assert "camera.mapping_resolved" in codes(result, CheckStatus.BLOCKED)
    assert result.resolved is not None
    assert result.resolved.cameras == {}


def test_policy_rollout_resolves_checkpoint_and_camera_mapping_on_the_server(
    lab: Lab,
    tmp_path: Path,
) -> None:
    for link_name in (
        "usb-SO101_Top_0001-video-index0",
        "usb-SO101_Wrist_0002-video-index0",
    ):
        lab.connect_camera(link_name)
    camera_devices = [
        item
        for item in lab.discovery.snapshot(include_simulated=False)
        if item.kind.value == "camera"
    ]
    assert len(camera_devices) == 2
    camera_ids: dict[str, str] = {}
    for semantic, device in zip(("top", "wrist"), camera_devices, strict=True):
        profile = CameraProfile(
            name=semantic,
            device_fingerprint=device.stable_fingerprint,
            semantic_name=semantic,
            width=640,
            height=480,
            fps=30,
        )
        lab.repository.upsert_entity("camera", profile)
        camera_ids[semantic] = profile.id
    lab.robot.camera_mapping = camera_ids
    lab.repository.upsert_entity("robot", lab.robot)

    checkpoint = tmp_path / "policy"
    checkpoint.mkdir()
    (checkpoint / "config.json").write_text("{}")
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    policy = PolicyManifest(
        name="Tic-Tac-Toe SmolVLA",
        policy_type="smolvla",
        checkpoint=str(checkpoint),
        model_revision="b" * 40,
        expected_features=[
            "observation.state",
            "observation.images.camera1",
            "observation.images.camera2",
            "observation.images.camera3",
            "action",
        ],
        action_shape=[6],
        camera_mapping={
            "observation.images.top": "observation.images.camera1",
            "observation.images.wrist": "observation.images.camera2",
        },
        empty_cameras=1,
        compatibility_status="hub-checkpoint-read",
    )
    lab.repository.upsert_entity("policy", policy)

    request = JobCreateRequest(
        kind=JobKind.POLICY_ROLLOUT,
        target_mode=TargetMode.REAL,
        parameters={
            "policy_id": policy.id,
            "policy_path": "/tmp/client-injected",
            "robot_profile_id": lab.robot.id,
            "workspace_confirmed": True,
        },
        requested_by="test",
    )
    preflight = lab.safety.preflight(request)

    assert preflight.allowed is True
    assert preflight.resolved is not None
    assert preflight.resolved.policy_checkpoint == str(checkpoint)
    assert "policy.checkpoint_present" in codes(preflight, CheckStatus.PASS)
    assert "policy.camera_mapping" in codes(preflight, CheckStatus.PASS)

    effective = lab.safety.apply_resolution(request, preflight.resolved)
    assert effective.parameters["policy_path"] == str(checkpoint)
    assert effective.parameters["rename_map"] == {
        "observation.images.top": "observation.images.camera1",
        "observation.images.wrist": "observation.images.camera2",
    }


def test_a_disconnected_arm_blocks_actuation(lab: Lab) -> None:
    lab.ports.clear()

    result = lab.safety.preflight(teleoperation(lab))

    assert result.allowed is False
    assert {
        "device.robot_fingerprint_match",
        "device.teleop_fingerprint_match",
    } <= codes(result, CheckStatus.BLOCKED)
