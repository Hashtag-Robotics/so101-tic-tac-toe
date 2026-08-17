"""A simulated take that carries a camera the bench does not have cannot be used.

Merging requires identical features, so the mismatch is not discovered when the
recording is made -- it is discovered at the merge, after the demonstrations are
already collected. The default therefore follows the physical arm.
"""

from __future__ import annotations

from hashtag_robotics.jobs import apply_server_defaults
from hashtag_robotics.models import (
    CameraProfile,
    JobCreateRequest,
    JobKind,
    RobotProfile,
    TargetMode,
)


def register_arm(client, cameras: dict[str, str]) -> None:
    for name, camera_id in cameras.items():
        client.post(
            "/api/cameras",
            json=CameraProfile(
                id=camera_id,
                name=name,
                semantic_name=name,
                device_fingerprint=f"fp-{name}",
            ).model_dump(mode="json"),
        )
    client.post(
        "/api/robots",
        json=RobotProfile(
            id="robot_bench",
            name="Follower 01",
            port="/dev/serial/by-id/bench",
            camera_mapping=cameras,
        ).model_dump(mode="json"),
    )


def submit_sim_recording(client, **parameters):
    return client.post(
        "/api/jobs",
        json={
            "kind": JobKind.SIM_RECORDING.value,
            "target_mode": "sim",
            "requested_by": "test",
            "parameters": {"repo_id": "u/take", "task": "pick", **parameters},
        },
    ).json()


def test_the_simulation_records_the_cameras_the_arm_has(client) -> None:
    register_arm(client, {"wrist": "camera_wrist"})

    job = submit_sim_recording(client)

    assert job["parameters"]["cameras"] == "wrist"


def test_two_cameras_are_listed_in_a_stable_order(client) -> None:
    register_arm(client, {"wrist": "camera_wrist", "front": "camera_front"})

    job = submit_sim_recording(client)

    assert job["parameters"]["cameras"] == "front,wrist"


def test_an_explicit_choice_is_left_alone(client) -> None:
    """The operator may want a view the arm lacks; that is their call to make."""
    register_arm(client, {"wrist": "camera_wrist"})

    job = submit_sim_recording(client, cameras="front,wrist")

    assert job["parameters"]["cameras"] == "front,wrist"


def test_without_a_physical_arm_the_scene_default_stands(client) -> None:
    job = submit_sim_recording(client)

    assert "cameras" not in job["parameters"]


def test_the_command_carries_the_selection() -> None:
    """The parameter is worth nothing if it stops at the job record."""
    from hashtag_robotics.hardware import LeRobotCommandBuilder
    from hashtag_robotics.models import JobCreateRequest, TargetMode

    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_RECORDING,
            target_mode=TargetMode.SIM,
            requested_by="test",
            parameters={
                "repo_id": "u/take",
                "task": "pick",
                "teleop_port": "/dev/ttyACM1",
                "cameras": "wrist",
            },
        )
    )

    assert "--cameras=wrist" in plan.arguments


def test_a_list_of_cameras_becomes_one_flag() -> None:
    from hashtag_robotics.hardware import LeRobotCommandBuilder
    from hashtag_robotics.models import JobCreateRequest, TargetMode

    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_RECORDING,
            target_mode=TargetMode.SIM,
            requested_by="test",
            parameters={
                "repo_id": "u/take",
                "task": "pick",
                "teleop_port": "/dev/ttyACM1",
                "cameras": ["front", "wrist"],
            },
        )
    )

    assert "--cameras=front,wrist" in plan.arguments


def test_the_default_is_one_function_every_door_can_call(client) -> None:
    """The preview promises the command the server would run, not the asked-for one.

    Applying the default on submission alone made that promise false in exactly
    the case it matters: the operator reads the command, sees no camera flag,
    and gets one anyway. The preview cannot be driven end to end from here --
    resolving a leader port needs a device physically connected -- so what is
    checked is the helper it shares with every other entry point. The end-to-end
    behaviour was verified against the running server on the bench.
    """
    register_arm(client, {"wrist": "camera_wrist"})
    request = JobCreateRequest(
        kind=JobKind.SIM_RECORDING,
        target_mode=TargetMode.SIM,
        requested_by="test",
        parameters={"repo_id": "u/take", "task": "pick"},
    )

    filled = apply_server_defaults(request, client.app.state.runtime.repository)

    assert filled.parameters["cameras"] == "wrist"


def test_the_agent_gateway_gets_the_same_default_as_the_browser(client) -> None:
    """The door nobody was watching.

    The default used to live in the HTTP layer, and the agent gateway submits
    jobs without passing through it -- so an agent recording in simulation got
    no cameras at all. That is the exact outcome the default exists to prevent,
    arriving through the one entry point that had no test.
    """
    register_arm(client, {"wrist": "camera_wrist"})

    result = client.post(
        "/api/agents/commands",
        json={
            "session_id": "agent_robot_operator",
            "action": "prepare_recording",
            "parameters": {
                "repo_id": "u/take",
                "task": "pick",
                "target_mode": "sim",
                "teleoperator_profile_id": "teleop_sim_so101",
            },
        },
    ).json()

    assert result["job"] is not None, result["message"]
    assert result["job"]["kind"] == JobKind.SIM_RECORDING.value
    assert result["job"]["parameters"]["cameras"] == "wrist"
