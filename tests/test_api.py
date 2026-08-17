from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FOLLOWER_MOTORS = {
    "shoulder_pan": {
        "id": 1,
        "drive_mode": 0,
        "homing_offset": -180,
        "range_min": 1114,
        "range_max": 3027,
    },
    "gripper": {
        "id": 6,
        "drive_mode": 0,
        "homing_offset": 209,
        "range_min": 2000,
        "range_max": 3400,
    },
}


def wait_for_terminal(client: TestClient, job_id: str, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["state"] in {"completed", "failed", "blocked", "aborted", "interrupted"}:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not reach a terminal state.")


def test_health_summary_and_seeded_profiles(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "software-only"

    summary = client.get("/api/summary").json()
    assert summary["physical_enabled"] is False
    assert summary["robots"] == 1
    assert summary["policies"] == 1

    robots = client.get("/api/robots").json()
    assert robots[0]["target_mode"] == "sim"
    assert robots[0]["calibration_verified"] is True


def test_tic_tac_toe_rollout_catalogue_is_complete_and_server_owned(
    client: TestClient,
) -> None:
    response = client.get("/api/policy-rollouts/tic-tac-toe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "tic_tac_toe_games_1_15_120k"
    assert payload["policy_repo_id"] == ("HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k")
    assert payload["policy_revision"] == "48a6313b7e4983781dd72919105ca691a77cd26c"
    assert len(payload["moves"]) == 18
    x7 = next(move for move in payload["moves"] if move["id"] == "X-7")
    assert x7["episode_index"] == 45
    assert x7["board_camera"] == ".../OXO/..."


def test_frontend_shell_is_never_reused_after_a_dashboard_rebuild(
    settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import hashtag_robotics.api as api_module

    package_root = tmp_path / "package"
    web_root = package_root / "web"
    web_root.mkdir(parents=True)
    (web_root / "index.html").write_text("<!doctype html><title>test dashboard</title>")
    monkeypatch.setattr(api_module, "__file__", str(package_root / "api.py"))

    with TestClient(api_module.create_app(settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        root = client.get("/")
        fallback = client.get("/collect")

    assert root.status_code == 200
    assert fallback.status_code == 200
    assert root.headers["cache-control"] == "no-store"
    assert fallback.headers["cache-control"] == "no-store"


def test_physical_gate_requires_confirmation_and_is_process_scoped(client: TestClient) -> None:
    refused = client.post(
        "/api/safety/physical-gate",
        json={"enabled": True, "confirmed": False},
    )
    assert refused.status_code == 409
    assert client.get("/api/summary").json()["physical_enabled"] is False

    opened = client.post(
        "/api/safety/physical-gate",
        json={"enabled": True, "confirmed": True},
    )
    assert opened.status_code == 200
    assert opened.json()["physical_enabled"] is True
    assert client.get("/api/summary").json()["physical_enabled"] is True
    assert client.get("/api/health").json()["mode"] == "hil"

    closed = client.post(
        "/api/safety/physical-gate",
        json={"enabled": False, "confirmed": False},
    )
    assert closed.status_code == 200
    assert closed.json()["physical_enabled"] is False

    events = client.get("/api/audit").json()
    gate_events = [event for event in events if event["action"] == "safety.physical_gate"]
    assert [event["outcome"] for event in gate_events[:2]] == ["disabled", "enabled"]


def test_physical_gate_cannot_open_while_estop_is_latched(client: TestClient) -> None:
    client.post("/api/safety/emergency-stop")

    response = client.post(
        "/api/safety/physical-gate",
        json={"enabled": True, "confirmed": True},
    )

    assert response.status_code == 409
    assert "E-STOP" in response.json()["detail"]


def test_read_only_discovery_persists_safe_simulated_devices(client: TestClient) -> None:
    response = client.post("/api/devices/discover?include_simulated=true")
    assert response.status_code == 200
    devices = response.json()
    assert any(device["id"] == "sim_so101" for device in devices)
    assert any(device["kind"] == "gpu" for device in devices)

    inventory = client.get("/api/devices").json()
    assert len(inventory) >= 2


def test_simulation_job_completes_and_is_audited(client: TestClient) -> None:
    pytest.importorskip("mujoco", reason="The contract model ships with the [sim] extra.")
    response = client.post(
        "/api/jobs",
        json={
            "kind": "simulation",
            "target_mode": "sim",
            "parameters": {"scenario_id": "scenario_tabletop"},
            "resources": [
                {
                    "resource_id": "sim-so101",
                    "resource_type": "robot",
                    "mode": "exclusive",
                }
            ],
            "requested_by": "test",
        },
    )
    assert response.status_code == 200
    job = wait_for_terminal(client, response.json()["id"])
    assert job["state"] == "completed"
    assert job["result"]["constraint_violations"] == 0

    audit = client.get("/api/audit").json()
    actions = {event["action"] for event in audit}
    assert {"job.submit", "job.start", "job.complete"} <= actions


def test_real_teleoperation_is_blocked_before_hil(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "teleoperation",
            "target_mode": "real",
            "parameters": {
                "robot_profile_id": "robot_sim_so101",
                "teleoperator_profile_id": "teleop_sim_so101",
                "workspace_confirmed": True,
                "robot_port": "/dev/injected-by-the-client",
                "robot_id": "injected",
            },
            "resources": [],
            "requested_by": "test",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "blocked"
    assert payload["error_code"] == "preflight_blocked"
    assert "locked" in payload["error_message"].lower()
    # The client cannot smuggle a port past the server-side resolution.
    assert payload["parameters"].get("robot_port") != "/dev/injected-by-the-client"
    assert payload["parameters"].get("robot_id") != "injected"


def test_asking_to_record_in_simulation_gets_the_recorder_that_records(
    client: TestClient,
) -> None:
    """This used to finish green having written nothing.

    `recording` with `target_mode='sim'` reached no command at all: it walked
    five cosmetic progress strings and reported success. The dashboard's own
    button did it, and so would any agent reasoning the obvious way. The request
    is now canonicalised on the server, so every door gets the real recorder.
    """
    response = client.post(
        "/api/jobs",
        json={
            "kind": "recording",
            "target_mode": "sim",
            "parameters": {
                "name": "Contract dataset",
                "task": "Move the test cube",
                "episodes": 4,
                "fps": 30,
            },
            "resources": [],
            "requested_by": "test",
        },
    )
    job = response.json()

    assert job["kind"] == "sim_recording", "asking to record in sim must record in sim"
    recording = wait_for_terminal(client, job["id"])
    # No leader is commissioned in this fixture, so it is refused rather than
    # pretending. Being blocked for a real reason beats succeeding for none.
    assert recording["state"] in {"blocked", "failed", "aborted"}
    assert client.get("/api/datasets").json() == []


def test_a_simulated_evaluation_reports_physics_not_a_success_rate(client: TestClient) -> None:
    pytest.importorskip("mujoco", reason="The contract model ships with the [sim] extra.")
    response = client.post(
        "/api/jobs",
        json={
            "kind": "evaluation",
            "target_mode": "sim",
            "parameters": {"policy_id": "policy_safe_baseline", "episodes": 5},
            "resources": [],
            "requested_by": "test",
        },
    )
    evaluation = wait_for_terminal(client, response.json()["id"])

    assert evaluation["state"] == "completed"
    result = evaluation["result"]
    assert "success_rate" not in result
    assert "successes" not in result
    assert result["episodes_completed"] == 0
    assert result["constraint_violations"] == 0
    assert result["simulated"] is True


def test_episode_success_comes_from_the_operator(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "evaluation",
            "target_mode": "sim",
            "parameters": {"policy_id": "policy_safe_baseline", "episodes": 3},
            "resources": [],
            "requested_by": "test",
        },
    )
    job_id = response.json()["id"]
    wait_for_terminal(client, job_id)

    for episode, outcome in ((0, "success"), (1, "failure"), (2, "success")):
        annotated = client.post(
            f"/api/jobs/{job_id}/annotate",
            json={"episode": episode, "outcome": outcome},
        )
        assert annotated.status_code == 200

    evaluation = annotated.json()["result"]["evaluation"]
    assert evaluation == {
        "annotated": 3,
        "successes": 2,
        "failures": 1,
        "success_rate": 0.6667,
        "source": "operator-annotation",
    }

    # Re-marking an episode replaces the earlier verdict instead of double counting.
    corrected = client.post(
        f"/api/jobs/{job_id}/annotate",
        json={"episode": 1, "outcome": "success", "note": "Operator misread the drop."},
    ).json()
    assert corrected["result"]["evaluation"]["successes"] == 3
    assert corrected["result"]["evaluation"]["annotated"] == 3

    actions = {event["action"] for event in client.get("/api/audit").json()}
    assert "job.annotate" in actions


def test_only_episode_bearing_jobs_can_be_annotated(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "simulation",
            "target_mode": "sim",
            "parameters": {},
            "resources": [],
            "requested_by": "test",
        },
    )
    job_id = wait_for_terminal(client, response.json()["id"])["id"]

    refused = client.post(f"/api/jobs/{job_id}/annotate", json={"episode": 0, "outcome": "success"})
    assert refused.status_code == 409
    assert "no episodes to annotate" in refused.json()["detail"]
    assert (
        client.post(
            "/api/jobs/job_missing/annotate", json={"episode": 0, "outcome": "success"}
        ).status_code
        == 404
    )


def test_agent_permissions_and_deterministic_job_conversion(client: TestClient) -> None:
    denied = client.post(
        "/api/agents/commands",
        json={
            "session_id": "agent_lab_assistant",
            "action": "prepare_training",
            "parameters": {"target_mode": "sim"},
        },
    ).json()
    assert denied["accepted"] is False

    inspection = client.post(
        "/api/agents/commands",
        json={
            "session_id": "agent_lab_assistant",
            "action": "inspect_lab",
            "parameters": {},
        },
    ).json()
    assert inspection["accepted"] is True
    assert "capabilities" in inspection["data"]

    # An agent cannot start training without naming a dataset.
    without_dataset = client.post(
        "/api/agents/commands",
        json={
            "session_id": "agent_training_advisor",
            "action": "prepare_training",
            "parameters": {"target_mode": "sim", "policy_type": "act"},
        },
    ).json()
    assert without_dataset["accepted"] is False
    assert without_dataset["job"]["state"] == "blocked"
    assert "repo_id" in without_dataset["job"]["error_message"]

    command = client.post(
        "/api/agents/commands",
        json={
            "session_id": "agent_training_advisor",
            "action": "prepare_training",
            "parameters": {
                "target_mode": "sim",
                "policy_type": "act",
                "repo_id": "pausiber/so101_demo",
            },
        },
    ).json()
    assert command["accepted"] is True
    job = wait_for_terminal(client, command["job"]["id"])
    assert job["state"] == "completed"
    # Sim mode only plans; it must not register a policy it never trained.
    assert job["result"]["executed"] is False
    assert job["result"]["policy_id"] is None
    assert "--dataset.repo_id=pausiber/so101_demo" in job["result"]["planned_arguments"]


def test_strands_runtime_is_optional_and_requires_explicit_model(client: TestClient) -> None:
    runtime = client.get("/api/agents/runtime")
    assert runtime.status_code == 200
    assert runtime.json()["execution_boundary"] == "deterministic-command-gateway"
    assert runtime.json()["raw_robot_tools_exposed"] is False

    response = client.post(
        "/api/agents/plan",
        json={
            "session_id": "agent_lab_assistant",
            "prompt": "Inspect the lab safely.",
            "execute": False,
        },
    )
    assert response.status_code == 409
    assert "HASHTAG_AGENT_MODEL" in response.json()["detail"]


def test_remote_probe_rejects_plaintext_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "remote_inference_probe",
            "target_mode": "sim",
            "parameters": {"url": "http://unsafe.example", "tls_required": True},
            "resources": [],
            "requested_by": "test",
        },
    )
    job = wait_for_terminal(client, response.json()["id"])
    assert job["state"] == "failed"
    assert "TLS" in job["error_message"]


def test_emergency_stop_aborts_queued_or_active_jobs(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "simulation",
            "target_mode": "sim",
            "parameters": {},
            "resources": [],
            "requested_by": "test",
        },
    )
    job_id = response.json()["id"]
    stopped = client.post("/api/safety/emergency-stop")
    assert stopped.status_code == 200
    job = wait_for_terminal(client, job_id)
    assert job["state"] in {"aborted", "completed"}


def test_operator_input_is_a_closed_vocabulary_behind_running_jobs(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "kind": "simulation",
            "target_mode": "sim",
            "parameters": {"scenario_id": "scenario_tabletop"},
            "resources": [],
            "requested_by": "test",
        },
    )
    job_id = response.json()["id"]
    wait_for_terminal(client, job_id)

    assert client.post("/api/jobs/job_missing/input", json={"key": "enter"}).status_code == 404
    assert client.post(f"/api/jobs/{job_id}/input", json={"key": "raw"}).status_code == 422

    denied = client.post(f"/api/jobs/{job_id}/input", json={"key": "enter"})
    assert denied.status_code == 409
    assert "running job" in denied.json()["detail"]

    telemetry = client.get(f"/api/jobs/{job_id}/telemetry")
    assert telemetry.status_code == 200
    assert client.get("/api/jobs/job_missing/telemetry").status_code == 404


def test_teleoperator_and_calibration_endpoints(client: TestClient, tmp_path: Path) -> None:
    teleoperator = client.post(
        "/api/teleoperators",
        json={
            "name": "Leader 01",
            "device_fingerprint": "fp-leader",
            "port": "/dev/serial/by-id/usb-leader",
            "calibration_id": "leader01",
        },
    ).json()
    assert teleoperator["teleoperator_type"] == "so101_leader"
    assert teleoperator["target_robot_types"] == ["so101_follower"]
    listed = client.get("/api/teleoperators").json()
    assert {item["id"] for item in listed} >= {teleoperator["id"], "teleop_sim_so101"}

    external = tmp_path / "external" / "calibration" / "robots" / "so_follower"
    external.mkdir(parents=True)
    (external / "follower01.json").write_text(json.dumps(FOLLOWER_MOTORS))

    imported = client.post(
        "/api/calibrations/import",
        json={"directory": str(tmp_path / "external" / "calibration")},
    ).json()
    assert len(imported) == 1
    artifact = imported[0]
    assert artifact["source"] == "imported"
    assert artifact["role"] == "follower"
    assert artifact["validation_result"]["valid"] is True
    assert (external / "follower01.json").read_text() == json.dumps(FOLLOWER_MOTORS)

    assert client.post(f"/api/calibrations/{artifact['id']}/restore").status_code == 200
    assert client.post("/api/calibrations/calib_missing/restore").status_code == 422
    assert (
        client.post("/api/calibrations/import", json={"directory": "/nowhere"}).status_code == 422
    )

    stored = {item["id"] for item in client.get("/api/calibrations").json()}
    assert artifact["id"] in stored

    checks = client.post("/api/robots/robot_sim_so101/validate").json()
    codes = {check["code"] for check in checks}
    assert {"target.device_fingerprint", "limits.max_relative_target"} <= codes
    assert client.post("/api/robots/robot_missing/validate").status_code == 404
