from __future__ import annotations

from hashtag_robotics.agents import ROLE_PERMISSIONS
from hashtag_robotics.models import (
    AgentSession,
    CameraProfile,
    PolicyManifest,
    RobotProfile,
    SimulationScenario,
    TargetMode,
    TeleoperatorProfile,
)
from hashtag_robotics.repository import Repository


def seed_repository(repository: Repository) -> None:
    if repository.get_entity("robot", "robot_sim_so101", RobotProfile) is None:
        repository.upsert_entity(
            "robot",
            RobotProfile(
                id="robot_sim_so101",
                name="SO-101 Safe Simulator",
                serial_number="SIM-SO101-001",
                hardware_revision="simulation-v1",
                device_fingerprint="sim-so101-v1",
                calibration_revision="sim-calibration-v1",
                camera_mapping={"front": "camera_sim_front"},
                safety_profile={"max_relative_target": 5.0, "control_hz": 30},
                supported_features=["teleoperation", "recording", "replay", "evaluation"],
                joint_limits_verified=True,
                calibration_verified=True,
                emergency_stop_ready=True,
                target_mode=TargetMode.SIM,
            ),
        )

    if repository.get_entity("teleoperator", "teleop_sim_so101", TeleoperatorProfile) is None:
        repository.upsert_entity(
            "teleoperator",
            TeleoperatorProfile(
                id="teleop_sim_so101",
                name="SO-101 Safe Leader Simulator",
                serial_number="SIM-SO101-LEADER-001",
                hardware_revision="simulation-v1",
                device_fingerprint="sim-so101-leader-v1",
                calibration_revision="sim-calibration-v1",
                target_mode=TargetMode.SIM,
            ),
        )

    if repository.get_entity("camera", "camera_sim_front", CameraProfile) is None:
        repository.upsert_entity(
            "camera",
            CameraProfile(
                id="camera_sim_front",
                name="Virtual Front Camera",
                device_fingerprint="sim-camera-front-v1",
                backend="safe-mock",
                semantic_name="front",
                latency_baseline_ms=4.0,
            ),
        )

    # The two scenarios that used to live here -- a "safety baseline" and a
    # "contract model" -- ran a fixed sine wave and produced a table of numbers
    # nobody could act on. What a simulation is for here is collecting
    # demonstrations, so the seeded scenario is a task that can be recorded.
    if repository.get_entity("scenario", "scenario_cube_to_bin", SimulationScenario) is None:
        repository.upsert_entity(
            "scenario",
            SimulationScenario(
                id="scenario_cube_to_bin",
                name="Kırmızı küpü kutuya bırak",
                backend="mujoco",
                model="so101",
                scene="cube-to-bin",
                task="pick up the red cube and drop it in the bin",
                camera_mapping={
                    "front": "observation.images.front",
                    "wrist": "observation.images.wrist",
                },
            ),
        )

    if repository.get_entity("policy", "policy_safe_baseline", PolicyManifest) is None:
        repository.upsert_entity(
            "policy",
            PolicyManifest(
                id="policy_safe_baseline",
                name="SO-101 feature contract",
                policy_type="contract",
                # No weights exist; this entry only fixes the feature contract a
                # real checkpoint has to match. It is never runnable.
                checkpoint=None,
                expected_features=[
                    "observation.state",
                    "action",
                    "observation.images.front",
                ],
                processor_chain=[],
                action_shape=[6],
                camera_mapping={"front": "observation.images.front"},
                runtime="none",
                compatibility_status="unverified",
            ),
        )

    # Written on every boot, not only when the table is empty.
    #
    # Seeding once meant the stored permission list was a snapshot of whatever
    # the roles happened to be the first time this installation started. Two
    # permissions were added afterwards -- `inspect_safety` and `emergency_stop`
    # -- and no existing installation ever saw them. Execution reads
    # ROLE_PERMISSIONS live, so the agent could still run them; it was only the
    # published list that lied, which is worse than either being wrong alone.
    # The dashboard reads that list, decided `emergency_stop` was not permitted,
    # and reset the selection every time an operator chose it.
    #
    # Nothing else writes an agent session, so there is no operator edit to
    # overwrite here: the role owns its permissions and this is where the role
    # is written down.
    labels = {
        "lab_assistant": "Lab Assistant",
        "dataset_curator": "Dataset Curator",
        "training_advisor": "Training Advisor",
        "evaluation_analyst": "Evaluation Analyst",
        "robot_operator": "Robot Operator",
    }
    for role, permissions in ROLE_PERMISSIONS.items():
        granted = sorted(permissions)
        existing = repository.get_entity("agent_session", f"agent_{role}", AgentSession)
        if existing is None:
            repository.upsert_entity(
                "agent_session",
                AgentSession(
                    id=f"agent_{role}",
                    role=role,
                    name=labels[role],
                    permissions=granted,
                ),
            )
        elif existing.permissions != granted:
            # model_copy keeps created_at: the session is being corrected, not
            # replaced, and its age is the one thing here a boot cannot restate.
            repository.upsert_entity(
                "agent_session",
                existing.model_copy(update={"permissions": granted}),
            )
