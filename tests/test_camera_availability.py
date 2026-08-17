"""One V4L2 node serves one program, and this bench has one camera.

So "live view while recording" is arithmetic, not a missing feature. What is a
missing feature is holding the camera for a job that does not use it -- which
teleoperation did, reading every frame with `display_data=false` and throwing it
away, while the operator could not open the preview to frame the next take.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hashtag_robotics.config import Settings
from hashtag_robotics.hardware import LeRobotCommandBuilder
from hashtag_robotics.models import (
    CAMERA_JOB_KINDS,
    JobCreateRequest,
    JobKind,
    ResolvedTargets,
    TargetMode,
)

CAMERAS = {
    "wrist": {
        "type": "opencv",
        "index_or_path": "/dev/v4l/by-id/usb-cam-video-index0",
        "fps": 30,
        "width": 640,
        "height": 480,
    }
}


def plan_for(kind: JobKind) -> tuple[str, ...]:
    parameters = {
        "robot_type": "so101_follower",
        "robot_id": "follower01",
        "robot_port": "/dev/serial/by-id/follower",
        "teleop_type": "so101_leader",
        "teleop_id": "leader01",
        "teleop_port": "/dev/serial/by-id/leader",
        "cameras": CAMERAS,
        "repo_id": "mertkirgil/pens",
        "task": "pick",
        "policy_path": "outputs/train/checkpoints/last/pretrained_model",
    }
    request = JobCreateRequest(
        kind=kind,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )
    return LeRobotCommandBuilder().build(request).arguments


def test_teleoperation_no_longer_opens_the_camera() -> None:
    """It records nothing and displays nothing, so every frame was read and dropped."""
    assert not [item for item in plan_for(JobKind.TELEOPERATION) if "cameras" in item]


def test_recording_still_opens_the_camera() -> None:
    """The frames are the point here; dropping them would silently record no video."""
    assert [item for item in plan_for(JobKind.RECORDING) if "cameras" in item]


def test_teleoperation_does_not_claim_the_camera_lease_either() -> None:
    """Dropping the argument is not enough: the lease alone locks out the preview."""
    resolved = ResolvedTargets(
        robot_profile_id="robot_1",
        teleoperator_profile_id="teleop_1",
        camera_profile_ids={"wrist": "camera_wrist_01"},
    )

    teleop = {item.resource_type for item in resolved.resource_requests(JobKind.TELEOPERATION)}
    recording = {item.resource_type for item in resolved.resource_requests(JobKind.RECORDING)}

    assert "camera" not in teleop
    assert "camera" in recording
    assert {"robot", "teleoperator"} <= teleop, "the arms are still exclusive"


def test_an_unknown_kind_still_claims_everything() -> None:
    """Omitting the kind must stay conservative rather than quietly freeing devices."""
    resolved = ResolvedTargets(camera_profile_ids={"wrist": "camera_wrist_01"})

    assert [item.resource_type for item in resolved.resource_requests()] == ["camera"]


def test_the_camera_kinds_are_the_ones_that_consume_frames() -> None:
    expected = {
        JobKind.RECORDING,
        JobKind.EVALUATION,
        JobKind.POLICY_ROLLOUT,
        JobKind.CAMERA_PREVIEW,
    }

    assert expected == CAMERA_JOB_KINDS


@pytest.fixture
def camera_client(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from hashtag_robotics.api import create_app
    from hashtag_robotics.models import CameraProfile

    monkeypatch.setattr("hashtag_robotics.discovery.list_ports.comports", list)
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")
    camera_root = tmp_path / "v4l-by-id"
    camera_root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", camera_root)

    settings = Settings(data_dir=tmp_path, open_browser=False, enable_physical=False)
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        client.app.state.runtime.repository.upsert_entity(
            "camera",
            CameraProfile(
                id="camera_wrist_01",
                name="Wrist",
                semantic_name="wrist",
                device_fingerprint="cam-1",
            ),
        )
        yield client


def test_availability_says_yes_when_nothing_holds_the_camera(camera_client) -> None:
    payload = camera_client.get("/api/cameras/camera_wrist_01/availability").json()

    assert payload["available"] is True
    assert payload["held_by"] is None


def test_availability_names_the_job_holding_the_camera(camera_client) -> None:
    """'No' without 'because the recording owns it' sends the operator hunting."""
    from hashtag_robotics.models import JobRecord, ResourceRequest

    runtime = camera_client.app.state.runtime
    job = JobRecord(
        kind=JobKind.RECORDING,
        target_mode=TargetMode.REAL,
        requested_by="test",
    )
    runtime.repository.create_job(job)
    runtime.repository.acquire_leases(
        job.id,
        [ResourceRequest(resource_id="camera_wrist_01", resource_type="camera", mode="exclusive")],
    )

    payload = camera_client.get("/api/cameras/camera_wrist_01/availability").json()

    assert payload["available"] is False
    assert payload["held_by"] == job.id
    assert payload["held_by_kind"] == "recording"
    assert "one program at a time" in payload["reason"]


def test_an_expired_lease_does_not_keep_the_camera_busy(camera_client) -> None:
    """Expired rows are only swept on acquire, so a reader must filter them itself."""
    from hashtag_robotics.models import JobRecord, ResourceRequest

    runtime = camera_client.app.state.runtime
    job = JobRecord(kind=JobKind.RECORDING, target_mode=TargetMode.REAL, requested_by="test")
    runtime.repository.create_job(job)
    runtime.repository.acquire_leases(
        job.id,
        [ResourceRequest(resource_id="camera_wrist_01", resource_type="camera", mode="exclusive")],
        ttl_seconds=-1,
    )

    assert runtime.repository.lease_owner("camera_wrist_01") is None


def test_availability_404s_for_a_camera_that_does_not_exist(camera_client) -> None:
    assert camera_client.get("/api/cameras/nope/availability").status_code == 404
