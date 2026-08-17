"""An assistant that can read a serial number and not write it down is a notepad.

The lab surface was the last part of the dashboard with no door into it. An
agent could run the discovery job and then had no way to record what it found,
so the operator retyped a fingerprint the assistant had just read out to them.

The interesting question here is not whether an agent may write a profile -- it
may, nothing about it moves -- but which fields it may write. Two sets come back
out: the calibration binding, which belongs to the calibration store, and the
fields that are a claim about a bench the agent cannot see.
"""

from __future__ import annotations

from hashtag_robotics.models import CameraProfile, JobKind, RobotProfile


def command(client, action: str, session: str = "agent_lab_assistant", **parameters):
    return client.post(
        "/api/agents/commands",
        json={"session_id": session, "action": action, "parameters": parameters},
    ).json()


def register_camera(client, camera_id: str, name: str) -> None:
    client.post(
        "/api/cameras",
        json=CameraProfile(
            id=camera_id, name=name, semantic_name=name, device_fingerprint=f"fp-{name}"
        ).model_dump(mode="json"),
    )


# --- reading the lab --------------------------------------------------------


def test_the_assistant_can_enumerate_devices(client) -> None:
    """Both halves: what is connected now, and what is remembered and gone."""
    result = command(client, "inspect_devices")

    assert result["accepted"] is True
    assert "devices" in result["data"]


def test_the_assistant_can_read_the_arms_and_cameras_on_file(client) -> None:
    register_camera(client, "camera_wrist", "wrist")

    robots = command(client, "inspect_robots")
    cameras = command(client, "inspect_cameras")
    calibrations = command(client, "inspect_calibrations")

    assert robots["accepted"] and cameras["accepted"] and calibrations["accepted"]
    assert any(item["id"] == "camera_wrist" for item in cameras["data"]["cameras"])


# --- writing the lab --------------------------------------------------------


def test_the_assistant_can_write_down_what_it_found(client) -> None:
    result = command(
        client,
        "save_robot_profile",
        name="Follower 01",
        port="/dev/serial/by-id/bench",
        device_fingerprint="fp-follower",
    )

    assert result["accepted"] is True
    stored = client.get("/api/robots").json()
    assert any(item["name"] == "Follower 01" for item in stored)


def test_an_agent_cannot_vouch_for_the_bench(client) -> None:
    """`joint_limits_verified` is a person recording that they checked.

    An agent setting it asserts something about a room it is not in, which is
    the `workspace_confirmed` mistake with a different name. Nothing reads these
    two fields yet -- that is the argument for closing it now, before a check
    reads one and inherits an opening nobody chose.
    """
    result = command(
        client,
        "save_robot_profile",
        name="Follower 01",
        joint_limits_verified=True,
        emergency_stop_ready=True,
    )

    assert result["accepted"] is True
    assert result["data"]["robot"]["joint_limits_verified"] is False
    assert result["data"]["robot"]["emergency_stop_ready"] is False


def test_the_fields_it_could_not_write_are_named_rather_than_dropped(client) -> None:
    """Silently discarding them would read as having worked."""
    result = command(client, "save_robot_profile", name="Follower 01", joint_limits_verified=True)

    assert "joint_limits_verified" in result["data"]["ignored_fields"]
    assert "cannot vouch" in result["message"]


def test_an_agent_cannot_unbind_a_calibration(client) -> None:
    """A profile that overwrote the binding would separate an arm from the
    numbers that make it safe, and nothing would say so."""
    client.post(
        "/api/robots",
        json=RobotProfile(id="robot_bench", name="Follower 01").model_dump(mode="json"),
    )

    result = command(
        client,
        "save_robot_profile",
        id="robot_bench",
        name="Follower 01",
        calibration_verified=True,
        calibration_revision="invented",
    )

    assert result["data"]["robot"]["calibration_verified"] is False
    assert result["data"]["robot"]["calibration_revision"] is None


def test_updating_a_profile_keeps_the_fields_it_did_not_mention(client) -> None:
    """Otherwise correcting a name silently clears the port."""
    client.post(
        "/api/robots",
        json=RobotProfile(
            id="robot_bench", name="Old name", port="/dev/serial/by-id/bench"
        ).model_dump(mode="json"),
    )

    command(client, "save_robot_profile", id="robot_bench", name="Follower 01")

    stored = next(item for item in client.get("/api/robots").json() if item["id"] == "robot_bench")
    assert stored["name"] == "Follower 01"
    assert stored["port"] == "/dev/serial/by-id/bench"


def test_a_profile_that_does_not_validate_says_what_is_wrong(client) -> None:
    result = command(client, "save_robot_profile", port="/dev/ttyACM0")

    assert result["accepted"] is False
    assert result["data"]["problems"]


# --- camera mapping ---------------------------------------------------------


def test_the_assistant_can_map_a_camera_to_a_view(client) -> None:
    register_camera(client, "camera_wrist", "wrist")
    client.post(
        "/api/robots",
        json=RobotProfile(id="robot_bench", name="Follower 01").model_dump(mode="json"),
    )

    result = command(
        client,
        "save_camera_mapping",
        robot_profile_id="robot_bench",
        camera_mapping={"wrist": "camera_wrist"},
    )

    assert result["accepted"] is True
    assert result["data"]["robot"]["camera_mapping"] == {"wrist": "camera_wrist"}


def test_mapping_to_a_camera_that_does_not_exist_is_refused(client) -> None:
    """It reads as configured and fails at the recording, by which point the
    demonstration is gone."""
    client.post(
        "/api/robots",
        json=RobotProfile(id="robot_bench", name="Follower 01").model_dump(mode="json"),
    )

    result = command(
        client,
        "save_camera_mapping",
        robot_profile_id="robot_bench",
        camera_mapping={"wrist": "camera_imaginary"},
    )

    assert result["accepted"] is False
    assert "camera_imaginary" in result["message"]


def test_a_mapping_that_is_not_an_object_is_refused(client) -> None:
    client.post(
        "/api/robots",
        json=RobotProfile(id="robot_bench", name="Follower 01").model_dump(mode="json"),
    )

    result = command(
        client, "save_camera_mapping", robot_profile_id="robot_bench", camera_mapping=["wrist"]
    )

    assert result["accepted"] is False


# --- calibration ------------------------------------------------------------


def test_asking_for_a_calibration_is_offered_and_asking_is_not_performing(client) -> None:
    """Withheld at first on the grounds that an agent could not do the work.

    That confused doing it with asking for it: the procedure is a person moving
    each joint to its stops, so a human is at the bench for the whole of it.
    """
    payload = client.get("/api/agents/catalogue?role=robot_operator").json()
    entry = next(item for item in payload["actions"] if item["action"] == "request_calibration")

    assert entry["needs_human_approval"] is True
    assert entry["job_kind"] == JobKind.CALIBRATION.value
    assert entry["target_modes"] == ["real"]


def test_no_role_can_mark_an_arm_calibrated(client) -> None:
    """The calibration store writes that, never a job's parameters."""
    from hashtag_robotics.agents import ROLE_PERMISSIONS

    granted = {action for actions in ROLE_PERMISSIONS.values() for action in actions}

    assert not {action for action in granted if "verify" in action or "verified" in action}


def test_the_curator_cannot_rewrite_the_lab(client) -> None:
    """Setting up arms is the assistant's job, not everybody's."""
    result = command(client, "save_robot_profile", session="agent_dataset_curator", name="x")

    assert result["accepted"] is False
    assert "cannot run" in result["message"]


# --- the trail ---------------------------------------------------------------


def test_a_command_that_only_read_something_still_leaves_a_trail(client) -> None:
    """Job-creating actions were traceable; reads were invisible.

    Which recordings an agent listed, which arm it looked up -- none of it was
    recorded anywhere, and the roadmap asks for every tool call to be traceable.
    """
    command(client, "inspect_devices")

    events = client.get("/api/audit?limit=50").json()
    entry = next(item for item in events if item["action"] == "agent.inspect_devices")
    assert entry["actor"] == "agent:agent_lab_assistant"
    assert entry["outcome"] == "accepted"


def test_a_refusal_is_recorded_too(client) -> None:
    """The half worth having when a plan does something surprising."""
    command(client, "request_rollout", policy_id="policy_x")

    events = client.get("/api/audit?limit=50").json()
    entry = next(item for item in events if item["action"] == "agent.request_rollout")
    assert entry["outcome"] == "refused"


def test_the_trail_says_what_the_command_was_given(client) -> None:
    register_camera(client, "camera_wrist", "wrist")

    command(client, "save_robot_profile", name="Follower 01", port="/dev/serial/by-id/bench")

    events = client.get("/api/audit?limit=50").json()
    entry = next(item for item in events if item["action"] == "agent.save_robot_profile")
    assert entry["details"]["parameters"]["port"] == "/dev/serial/by-id/bench"


def test_a_huge_parameter_is_bounded_rather_than_stored_whole(client) -> None:
    """An audit log nobody scrolls is one nobody reads."""
    command(client, "save_robot_profile", name="x" * 5_000)

    events = client.get("/api/audit?limit=50").json()
    entry = next(item for item in events if item["action"] == "agent.save_robot_profile")
    assert len(entry["details"]["parameters"]["name"]) < 300
