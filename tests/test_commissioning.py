from __future__ import annotations

import json
import os
import stat
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hashtag_robotics.api import create_app
from hashtag_robotics.calibration import validate_motors
from hashtag_robotics.config import Settings

FAKE_CALIBRATE = """#!{interpreter}
import json, sys
from pathlib import Path

target = Path(sys.argv[-1])
target.parent.mkdir(parents=True, exist_ok=True)
motors = {{
    "shoulder_pan": {{"id": 1, "drive_mode": 0, "homing_offset": 0,
                      "range_min": 1000, "range_max": 3000}},
    "shoulder_lift": {{"id": 2, "drive_mode": 0, "homing_offset": 0,
                       "range_min": 900, "range_max": 3100}},
    "elbow_flex": {{"id": 3, "drive_mode": 0, "homing_offset": 0,
                    "range_min": 950, "range_max": 3050}},
    "wrist_flex": {{"id": 4, "drive_mode": 0, "homing_offset": 0,
                    "range_min": 930, "range_max": 3200}},
    "wrist_roll": {{"id": 5, "drive_mode": 0, "homing_offset": 0,
                    "range_min": 0, "range_max": 4095}},
    # Never swept: the mistake a min < max test cannot see.
    "gripper": {{"id": 6, "drive_mode": 0, "homing_offset": 0,
                 "range_min": 2046, "range_max": 2052}},
}}
target.write_text(json.dumps(motors))
print("Calibration saved to " + str(target), flush=True)
"""


class FakePort:
    def __init__(self, device: str, serial_number: str, product: str) -> None:
        self.device = device
        self.vid = 0x1A86
        self.pid = 0x7523
        self.serial_number = serial_number
        self.manufacturer = "QinHeng Electronics"
        self.product = product
        self.description = product
        self.hwid = f"USB VID:PID=1A86:7523 SER={serial_number}"


@pytest.fixture
def ports() -> list[FakePort]:
    return [
        FakePort("/dev/ttyACM0", "SO101FOLLOWER", "SO-101 Follower"),
        FakePort("/dev/ttyACM1", "SO101LEADER", "SO-101 Leader"),
    ]


@pytest.fixture
def lab(tmp_path: Path, monkeypatch, ports: list[FakePort]) -> Iterator[TestClient]:
    monkeypatch.setattr("hashtag_robotics.discovery.list_ports.comports", lambda: list(ports))
    # The host's own by-id trees must stay out of a hermetic test.
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", tmp_path / "v4l-by-id")

    settings = Settings(
        data_dir=tmp_path / "state",
        open_browser=False,
        enable_physical=True,
        simulation_step_seconds=0.001,
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        yield client


def device_id(client: TestClient, serial: str) -> str:
    devices = client.post("/api/devices/discover?include_simulated=false").json()
    return next(item["id"] for item in devices if item["serial_number"] == serial)


def assign(client: TestClient, role: str, serial: str | None) -> Any:
    body: dict[str, Any] = {"role": role}
    body["device_id"] = device_id(client, serial) if serial else None
    return client.post("/api/setup/slots", json=body)


def step(status: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(item for item in status["steps"] if item["id"] == step_id)


def slot(status: dict[str, Any], role: str) -> dict[str, Any]:
    return next(item for item in status["slots"] if item["role"] == role)


def wait_for(probe: Callable[[], Any], timeout: float = 25.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("The expected control plane state never arrived.")


def valid_calibration() -> dict[str, dict[str, int]]:
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
            "id": index,
            "drive_mode": 0,
            "homing_offset": 0,
            "range_min": 500,
            "range_max": 3500,
        }
        for index, name in enumerate(names, start=1)
    }


def test_a_slot_holds_one_arm_and_derives_its_lerobot_id(lab: TestClient) -> None:
    response = assign(lab, "follower", "SO101FOLLOWER")
    assert response.status_code == 200
    status = response.json()

    follower = slot(status, "follower")
    assert follower["profile_id"] is not None
    assert follower["device_serial"] == "SO101FOLLOWER"
    # The operator never types this; a mistyped id silently breaks calibration.
    assert follower["lerobot_id"] == "follower01"
    assert follower["max_relative_target"] == 10.0
    assert slot(status, "leader")["profile_id"] is None

    real = [item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim"]
    assert len(real) == 1


def test_follower_limit_can_be_tuned_without_losing_profile_bindings(lab: TestClient) -> None:
    assign(lab, "follower", "SO101FOLLOWER")
    robot = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")
    saved = lab.post(
        "/api/robots",
        json={**robot, "camera_mapping": {"wrist": "camera_so101"}},
    )
    assert saved.status_code == 200

    changed = lab.post("/api/setup/follower-limit", json={"max_relative_target": 12})
    assert changed.status_code == 200
    assert slot(changed.json(), "follower")["max_relative_target"] == 12.0

    updated = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")
    assert updated["safety_profile"]["max_relative_target"] == 12.0
    assert updated["camera_mapping"] == {"wrist": "camera_so101"}

    assert lab.post("/api/setup/follower-limit", json={"max_relative_target": 0}).status_code == 422
    assert (
        lab.post("/api/setup/follower-limit", json={"max_relative_target": 31}).status_code == 422
    )


def test_the_same_arm_cannot_fill_both_slots(lab: TestClient) -> None:
    assert assign(lab, "follower", "SO101FOLLOWER").status_code == 200

    clash = assign(lab, "leader", "SO101FOLLOWER")
    assert clash.status_code == 409
    assert "already fills the follower slot" in clash.json()["detail"]

    # The rejected assignment must not have created a second profile.
    teleoperators = [
        item for item in lab.get("/api/teleoperators").json() if item["target_mode"] != "sim"
    ]
    assert teleoperators == []


def test_the_profile_endpoint_also_refuses_a_second_role(lab: TestClient) -> None:
    assign(lab, "follower", "SO101FOLLOWER")
    robot = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")

    clash = lab.post(
        "/api/teleoperators",
        json={
            "name": "Leader 01",
            "device_fingerprint": robot["device_fingerprint"],
            "calibration_id": "leader01",
        },
    )
    assert clash.status_code == 409


def test_releasing_a_slot_removes_the_profile(lab: TestClient) -> None:
    assign(lab, "follower", "SO101FOLLOWER")
    status = assign(lab, "follower", None).json()
    assert slot(status, "follower")["profile_id"] is None
    assert [item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim"] == []


def test_saving_a_profile_cannot_clear_its_calibration_binding(lab: TestClient) -> None:
    """Renaming an arm used to unbind its calibration without saying so."""
    assign(lab, "follower", "SO101FOLLOWER")
    robot = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")

    runtime = lab.app.state.runtime
    calibration_dir = runtime.settings.calibration_dir / "robots" / "so_follower"
    calibration_dir.mkdir(parents=True, exist_ok=True)
    (calibration_dir / "follower01.json").write_text(
        json.dumps(
            {
                "shoulder_pan": {
                    "id": 1,
                    "drive_mode": 0,
                    "homing_offset": 0,
                    "range_min": 1000,
                    "range_max": 3000,
                }
            }
        )
    )
    artifact = runtime.calibration.capture("so101_follower", "follower01", "user")
    from hashtag_robotics.models import RobotProfile

    runtime.calibration.bind_robot(RobotProfile.model_validate(robot), artifact)

    renamed = lab.post(
        "/api/robots",
        json={**robot, "name": "Sag kol", "calibration_revision": None, "motor_layout": {}},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Sag kol"
    assert renamed.json()["calibration_revision"] == artifact.id
    assert renamed.json()["motor_layout"] == {"shoulder_pan": 1}


def test_imported_calibrations_can_be_bound_to_setup_slots(
    lab: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    assign(lab, "follower", "SO101FOLLOWER")
    assign(lab, "leader", "SO101LEADER")

    home = tmp_path / "home"
    root = home / "legacy-calibration"
    follower = root / "robots" / "so_follower"
    leader = root / "teleoperators" / "so_leader"
    follower.mkdir(parents=True)
    leader.mkdir(parents=True)
    (follower / "mert_follower.json").write_text(json.dumps(valid_calibration()))
    (leader / "mert_leader.json").write_text(json.dumps(valid_calibration()))
    monkeypatch.setenv("HOME", str(home))

    imported = lab.post("/api/calibrations/import", json={"directory": "~/legacy-calibration"})
    assert imported.status_code == 200
    artifacts = imported.json()
    follower_artifact = next(item for item in artifacts if item["role"] == "follower")
    leader_artifact = next(item for item in artifacts if item["role"] == "leader")

    wrong_role = lab.post(
        "/api/setup/calibrations/bind",
        json={"role": "leader", "artifact_id": follower_artifact["id"]},
    )
    assert wrong_role.status_code == 422

    follower_status = lab.post(
        "/api/setup/calibrations/bind",
        json={"role": "follower", "artifact_id": follower_artifact["id"]},
    )
    assert follower_status.status_code == 200
    leader_status = lab.post(
        "/api/setup/calibrations/bind",
        json={"role": "leader", "artifact_id": leader_artifact["id"]},
    )
    assert leader_status.status_code == 200

    status = leader_status.json()
    assert slot(status, "follower")["lerobot_id"] == "mert_follower"
    assert slot(status, "leader")["lerobot_id"] == "mert_leader"
    assert slot(status, "follower")["calibration_revision"] == follower_artifact["id"]
    assert slot(status, "leader")["calibration_revision"] == leader_artifact["id"]

    robot = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")
    assert robot["calibration_verified"] is True
    assert robot["motor_layout"] == {
        name: index for index, name in enumerate(valid_calibration(), start=1)
    }


def test_setup_status_explains_every_blocked_step(lab: TestClient) -> None:
    status = lab.get("/api/setup/status").json()
    assert status["commissioned"] is False

    identify = step(status, "identify")
    assert identify["state"] == "ready"
    assert any("yuvası boş" in blocker for blocker in identify["blockers"])

    calibrate = step(status, "calibrate")
    assert calibrate["state"] == "blocked"
    assert calibrate["blockers"], "a blocked step must say what is missing"

    verify = step(status, "verify")
    assert verify["state"] == "blocked"
    assert verify["blockers"]


def test_calibration_registers_a_user_artifact_and_binds_it(
    lab: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A successful calibration used to leave the profile still unbound."""
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "lerobot-calibrate"
    shim.write_text(FAKE_CALIBRATE.format(interpreter=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ['PATH']}")

    assign(lab, "follower", "SO101FOLLOWER")
    robot = next(item for item in lab.get("/api/robots").json() if item["target_mode"] != "sim")
    runtime = lab.app.state.runtime
    target = runtime.settings.calibration_dir / "robots" / "so_follower" / "follower01.json"

    submitted = lab.post(
        "/api/jobs",
        json={
            "kind": "calibration",
            "target_mode": "real",
            "parameters": {
                "role": "robot",
                "robot_profile_id": robot["id"],
                "workspace_confirmed": True,
                # The shim writes wherever its last argument points.
                "timeout_seconds": 30,
            },
            "resources": [],
            "requested_by": "test",
        },
    ).json()
    assert submitted["state"] == "awaiting_confirmation"

    # The command builder ends with the calibration dir, so the shim writes there.
    monkeypatch.setattr(
        "hashtag_robotics.hardware.LeRobotCommandBuilder._device_arguments",
        lambda self, parameters: ([str(target)], ("robot_port", "robot_id")),
    )

    lab.post(
        f"/api/jobs/{submitted['id']}/confirm",
        json={"approval_id": submitted["approval_id"]},
    )
    finished = wait_for(
        lambda: (
            lab.get(f"/api/jobs/{submitted['id']}").json()
            if lab.get(f"/api/jobs/{submitted['id']}").json()["state"]
            in {"completed", "failed", "aborted", "blocked"}
            else None
        )
    )
    assert finished["state"] == "completed", finished.get("error_message")

    result = finished["result"]
    assert result["calibration_source"] == "user"
    assert result["bound_to_profile"] is True
    assert result["calibration_warnings"], "an unswept gripper has to be reported"

    bound = next(item for item in lab.get("/api/robots").json() if item["id"] == robot["id"])
    assert bound["calibration_revision"] == result["calibration_revision"]
    assert len(bound["motor_layout"]) == 6


def test_a_half_swept_joint_is_caught_by_comparing_the_pair(lab: TestClient) -> None:
    """503 counts is not 'narrow', but it is a third of the matching joint."""
    service = lab.app.state.runtime.commissioning
    evidence = {
        "Follower": {"spans": {"shoulder_pan": 503, "elbow_flex": 2215, "gripper": 1478}},
        "Leader": {"spans": {"shoulder_pan": 1561, "elbow_flex": 2211, "gripper": 1298}},
    }

    mismatches = service._span_mismatches(evidence)

    assert len(mismatches) == 1
    assert "shoulder_pan" in mismatches[0]
    assert "follower" in mismatches[0]
    # Joints that agree, and a gripper that differs mechanically, stay quiet.
    assert all("elbow_flex" not in item and "gripper" not in item for item in mismatches)


def test_span_comparison_needs_both_arms(lab: TestClient) -> None:
    service = lab.app.state.runtime.commissioning
    assert service._span_mismatches({"Follower": {"spans": {"shoulder_pan": 503}}}) == []


def test_a_joint_that_was_never_swept_is_reported() -> None:
    motors = {
        "shoulder_pan": {
            "id": 1,
            "drive_mode": 0,
            "homing_offset": 0,
            "range_min": 1000,
            "range_max": 3000,
        },
        "gripper": {
            "id": 6,
            "drive_mode": 0,
            "homing_offset": 0,
            "range_min": 2046,
            "range_max": 2052,
        },
    }
    result = validate_motors(motors)

    # It is structurally valid, which is exactly why a span check is needed.
    assert result["valid"] is True
    assert result["spans"] == {"shoulder_pan": 2000, "gripper": 6}
    assert len(result["warnings"]) == 1
    assert "gripper" in result["warnings"][0]
