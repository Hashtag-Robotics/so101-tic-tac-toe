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
from hashtag_robotics.config import Settings

FAKE_CALIBRATE = """#!{interpreter}
import sys

print("-------------------------------------------", flush=True)
print("NAME            |    MIN |    POS |    MAX", flush=True)
print("shoulder_pan    |   1114 |   2000 |   3027", flush=True)
print("gripper         |    209 |   1000 |   2100", flush=True)
sys.stdout.write("Move follower01 to the middle of its range of motion and press ENTER....")
sys.stdout.flush()
input()
print("Calibration saved to /tmp/hashtag/follower01.json", flush=True)
"""


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


def calibration_job(robot_profile_id: str) -> dict[str, Any]:
    """Ports, ids and limits are resolved by the server, never sent by the client."""
    return {
        "kind": "calibration",
        "target_mode": "real",
        "parameters": {
            "role": "robot",
            "robot_profile_id": robot_profile_id,
            "workspace_confirmed": True,
        },
        "resources": [],
        "requested_by": "test",
    }


@pytest.fixture
def serial_ports() -> list[FakePort]:
    return [FakePort("/dev/ttyACM0", "SO101FOLLOWER", "SO-101 Follower")]


@pytest.fixture
def physical_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "state",
        open_browser=False,
        enable_physical=True,
        simulation_step_seconds=0.001,
    )


@pytest.fixture
def physical_client(
    tmp_path: Path,
    monkeypatch,
    serial_ports: list[FakePort],
    physical_settings: Settings,
) -> Iterator[TestClient]:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "lerobot-calibrate"
    shim.write_text(FAKE_CALIBRATE.format(interpreter=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(
        "hashtag_robotics.discovery.list_ports.comports",
        lambda: list(serial_ports),
    )
    # Without this the host's own /dev/serial/by-id resolves the fake port to a
    # real cable, so the suite only fails on a machine with arms attached.
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")

    with TestClient(create_app(physical_settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        yield client


@pytest.fixture
def robot_profile_id(physical_client: TestClient) -> str:
    devices = physical_client.post("/api/devices/discover?include_simulated=false").json()
    follower = next(item for item in devices if item["serial_number"] == "SO101FOLLOWER")
    profile = physical_client.post(
        "/api/robots",
        json={
            "name": "Follower 01",
            "robot_type": "so101_follower",
            "device_fingerprint": follower["stable_fingerprint"],
            "calibration_id": "follower01",
            "port": follower["stable_path"] or follower["transient_path"],
            "safety_profile": {"max_relative_target": 5.0},
        },
    )
    assert profile.status_code == 200
    return str(profile.json()["id"])


def wait_for(probe: Callable[[], Any], timeout: float = 25.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("The expected control plane state never arrived.")


def wait_for_state(client: TestClient, job_id: str, states: set[str]) -> dict[str, Any]:
    def probe() -> dict[str, Any] | None:
        job = client.get(f"/api/jobs/{job_id}").json()
        return job if job["state"] in states else None

    return wait_for(probe)


def test_calibration_runs_over_a_pty_and_accepts_operator_enter(
    physical_client: TestClient,
    robot_profile_id: str,
) -> None:
    job = calibration_job(robot_profile_id)
    preview = physical_client.post("/api/hardware/command-preview", json=job).json()
    assert preview["executable"] == "lerobot-calibrate"
    assert preview["interactive"] is True
    assert preview["uses_shell"] is False
    assert preview["execution_allowed"] is True
    assert "--robot.type=so101_follower" in preview["arguments"]
    assert "--robot.id=follower01" in preview["arguments"]
    assert "--robot.port=/dev/ttyACM0" in preview["arguments"]
    assert preview["preflight"]["allowed"] is True

    submitted = physical_client.post("/api/jobs", json=job).json()
    assert submitted["state"] == "awaiting_confirmation"
    assert submitted["resolved_targets"]["robot_port"] == "/dev/ttyACM0"
    assert submitted["resources"][0]["resource_id"] == robot_profile_id
    job_id = submitted["id"]

    confirmed = physical_client.post(
        f"/api/jobs/{job_id}/confirm",
        json={"approval_id": submitted["approval_id"]},
    ).json()
    assert confirmed["state"] == "queued"

    running = wait_for(
        lambda: physical_client.get(f"/api/jobs/{job_id}").json().get("process"),
    )
    assert running["pty"] is True
    assert running["pid"] == running["pgid"]
    assert running["boot_id"] is not None

    telemetry = wait_for(
        lambda: physical_client.get(f"/api/jobs/{job_id}/telemetry").json().get("prompt")
    )
    assert telemetry["expects"] == "enter"
    ranges = physical_client.get(f"/api/jobs/{job_id}/telemetry").json()["ranges"]
    assert ranges["shoulder_pan"] == {"min": 1114, "pos": 2000, "max": 3027}

    accepted = physical_client.post(f"/api/jobs/{job_id}/input", json={"key": "enter"})
    assert accepted.status_code == 200

    finished = wait_for_state(physical_client, job_id, {"completed", "failed", "aborted"})
    assert finished["state"] == "completed"
    assert finished["result"]["return_code"] == 0
    assert finished["process"] is None
    assert finished["result"]["telemetry"]["ranges"]["gripper"]["max"] == 2100

    audit = physical_client.get("/api/audit").json()
    actions = {event["action"] for event in audit}
    assert {"job.submit", "job.confirm", "job.start", "job.input", "job.complete"} <= actions


def test_episode_keys_are_rejected_on_a_calibration_job(
    physical_client: TestClient,
    robot_profile_id: str,
) -> None:
    submitted = physical_client.post("/api/jobs", json=calibration_job(robot_profile_id)).json()
    job_id = submitted["id"]
    physical_client.post(
        f"/api/jobs/{job_id}/confirm",
        json={"approval_id": submitted["approval_id"]},
    )
    wait_for_state(physical_client, job_id, {"running"})

    denied = physical_client.post(f"/api/jobs/{job_id}/input", json={"key": "end_episode"})
    assert denied.status_code == 409
    assert "not accepted by a 'calibration' job" in denied.json()["detail"]

    physical_client.post("/api/safety/emergency-stop")


def test_a_latched_emergency_stop_blocks_new_physical_jobs_until_cleared(
    physical_client: TestClient,
    robot_profile_id: str,
) -> None:
    stopped = physical_client.post("/api/safety/emergency-stop")
    assert stopped.status_code == 200
    assert physical_client.get("/api/safety/status").json()["emergency_stop_engaged"] is True

    blocked = physical_client.post("/api/jobs", json=calibration_job(robot_profile_id)).json()
    assert blocked["state"] == "blocked"
    assert "latched" in blocked["error_message"].lower()

    cleared = physical_client.post("/api/safety/clear-estop").json()
    assert cleared["was_engaged"] is True
    assert cleared["engaged"] is False

    allowed = physical_client.post("/api/jobs", json=calibration_job(robot_profile_id)).json()
    assert allowed["state"] == "awaiting_confirmation"

    actions = {event["action"] for event in physical_client.get("/api/audit").json()}
    assert {"safety.emergency_stop", "safety.clear_emergency_stop"} <= actions


def test_an_approval_does_not_survive_the_arm_moving_to_another_port(
    physical_client: TestClient,
    robot_profile_id: str,
    serial_ports: list[FakePort],
) -> None:
    submitted = physical_client.post("/api/jobs", json=calibration_job(robot_profile_id)).json()
    assert submitted["state"] == "awaiting_confirmation"

    # Same arm, re-enumerated by the kernel at a different path after a replug.
    serial_ports[0].device = "/dev/ttyACM3"

    confirmed = physical_client.post(
        f"/api/jobs/{submitted['id']}/confirm",
        json={"approval_id": submitted["approval_id"]},
    ).json()
    assert confirmed["state"] == "blocked"
    assert confirmed["error_code"] == "targets_changed"
    assert confirmed["resolved_targets"]["robot_port"] == "/dev/ttyACM3"


def test_a_real_calibration_archives_the_previous_revision_first(
    physical_client: TestClient,
    physical_settings: Settings,
    robot_profile_id: str,
) -> None:
    live = physical_settings.calibration_dir / "robots" / "so_follower" / "follower01.json"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text(
        json.dumps(
            {
                "gripper": {
                    "id": 6,
                    "drive_mode": 0,
                    "homing_offset": 1,
                    "range_min": 1,
                    "range_max": 2,
                }
            }
        )
    )

    submitted = physical_client.post("/api/jobs", json=calibration_job(robot_profile_id)).json()
    physical_client.post(
        f"/api/jobs/{submitted['id']}/confirm",
        json={"approval_id": submitted["approval_id"]},
    )
    running = wait_for_state(physical_client, submitted["id"], {"running"})
    backup_id = running["result"]["calibration_backup_id"]
    assert backup_id

    archived = list(physical_settings.calibration_archive_dir.rglob("*.json"))
    assert any(backup_id in path.name for path in archived)
    assert json.loads(live.read_text())["gripper"]["range_max"] == 2

    physical_client.post(f"/api/jobs/{submitted['id']}/input", json={"key": "enter"})
    wait_for_state(physical_client, submitted["id"], {"completed", "failed", "aborted"})
