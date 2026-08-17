from __future__ import annotations

import json
from pathlib import Path

import pytest

from hashtag_robotics.config import Settings
from hashtag_robotics.hardware import (
    CommandPlan,
    LeRobotCliAdapter,
    LeRobotCommandBuilder,
    PhysicalExecutionError,
    execution_timeout_seconds,
)
from hashtag_robotics.models import (
    JobCreateRequest,
    JobInputKey,
    JobKind,
    JobRecord,
    TargetMode,
    TelemetryKind,
    TelemetrySample,
)
from hashtag_robotics.repository import Repository
from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_PROFILE,
    canonical_tic_tac_toe_parameters,
)


def real_request(kind: JobKind, **parameters: object) -> JobCreateRequest:
    return JobCreateRequest(
        kind=kind,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )


def test_teleoperation_command_is_an_argument_array_without_shell() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.TELEOPERATION,
            robot_port="/dev/follower",
            robot_id="mert_follower",
            teleop_port="/dev/leader",
            teleop_id="mert_leader",
            max_relative_target=5.0,
            fps=30,
            teleop_time_s=120,
            cameras={
                "front": {
                    "type": "opencv",
                    "index_or_path": 0,
                    "width": 640,
                    "height": 480,
                    "fps": 30,
                }
            },
        )
    )
    assert plan.executable == "lerobot-teleoperate"
    assert "--robot.type=so101_follower" in plan.arguments
    assert "--teleop.type=so101_leader" in plan.arguments
    assert "--robot.max_relative_target=5.0" in plan.arguments
    assert "--fps=30" in plan.arguments
    assert "--teleop_time_s=120.0" in plan.arguments
    assert "--display_data=false" in plan.arguments
    assert plan.as_dict()["uses_shell"] is False


def test_teleoperation_without_duration_runs_until_operator_cancel() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.TELEOPERATION,
            robot_port="/dev/follower",
            robot_id="follower",
            teleop_port="/dev/leader",
            teleop_id="leader",
            fps=60,
        )
    )

    assert "--fps=60" in plan.arguments
    assert all(not argument.startswith("--teleop_time_s=") for argument in plan.arguments)


def test_manual_teleoperation_has_no_server_watchdog_unless_explicit() -> None:
    manual = JobRecord(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters={},
        requested_by="test",
    )
    bounded = JobRecord(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters={"timeout_seconds": 45},
        requested_by="test",
    )
    recording = JobRecord(
        kind=JobKind.RECORDING,
        target_mode=TargetMode.REAL,
        parameters={},
        requested_by="test",
    )

    assert execution_timeout_seconds(manual, 900) is None
    assert execution_timeout_seconds(bounded, 900) == 45
    assert execution_timeout_seconds(recording, 900) == 900


def test_only_camera_jobs_receive_a_job_scoped_dashboard_relay(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, open_browser=False)
    adapter = LeRobotCliAdapter(settings, Repository(settings.database_path))
    recording = JobRecord(
        kind=JobKind.RECORDING,
        target_mode=TargetMode.REAL,
        parameters={},
        requested_by="test",
    )
    teleoperation = JobRecord(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters={},
        requested_by="test",
    )

    recording_environment = adapter.environment(recording)

    assert recording_environment["HASHTAG_RECORDING_LIVE_DIR"] == str(
        settings.recording_live_root / recording.id
    )
    assert recording_environment["HASHTAG_MANUAL_RECORDING_CONTROL"] == "1"
    assert (settings.recording_live_root / recording.id).is_dir()
    assert "HASHTAG_RECORDING_LIVE_DIR" not in adapter.environment(teleoperation)
    assert "HASHTAG_MANUAL_RECORDING_CONTROL" not in adapter.environment(teleoperation)


def test_recording_command_requires_repo_and_task() -> None:
    with pytest.raises(PhysicalExecutionError, match="repo_id"):
        LeRobotCommandBuilder().build(
            real_request(
                JobKind.RECORDING,
                robot_port="/dev/follower",
                robot_id="follower",
                teleop_port="/dev/leader",
                teleop_id="leader",
            )
        )


def test_recording_arguments_are_nested_under_the_dataset_config() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.RECORDING,
            robot_port="/dev/follower",
            robot_id="follower01",
            teleop_port="/dev/leader",
            teleop_id="leader01",
            repo_id="mertkirgil/hashtag-test",
            task="Put the red cube into the yellow bin",
            episodes=1,
            episode_time_s=19,
            reset_time_s=10,
            dataset_root="/tmp/hashtag/dataset",
        )
    )
    assert plan.executable == "lerobot-record"
    assert plan.interactive is True
    assert "--dataset.repo_id=mertkirgil/hashtag-test" in plan.arguments
    assert "--dataset.single_task=Put the red cube into the yellow bin" in plan.arguments
    assert "--dataset.num_episodes=1" in plan.arguments
    assert "--dataset.episode_time_s=19" in plan.arguments
    assert "--dataset.reset_time_s=10" in plan.arguments
    assert "--dataset.push_to_hub=false" in plan.arguments
    assert "--dataset.root=/tmp/hashtag/dataset" in plan.arguments
    assert all(not argument.startswith("--repo_id") for argument in plan.arguments)
    assert all(not argument.startswith("--num_episodes") for argument in plan.arguments)


def test_unique_id_camera_recording_uses_the_registered_wrapper() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.RECORDING,
            robot_port="/dev/follower",
            robot_id="follower01",
            teleop_port="/dev/leader",
            teleop_id="leader01",
            repo_id="local/two-cameras",
            task="play tic tac toe",
            cameras={
                "wrist": {
                    "type": "avfoundation_uid",
                    "unique_id": "usb-wrist",
                    "helper_path": "/tmp/capture",
                    "width": 640,
                    "height": 480,
                    "fps": 30,
                }
            },
        )
    )

    assert plan.executable == "hashtag-lerobot-record"
    assert any("avfoundation_uid" in argument for argument in plan.arguments)


def test_a_planned_recording_uses_one_task_per_episode(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, open_browser=False)
    adapter = LeRobotCliAdapter(settings, Repository(settings.database_path))
    parameters = {
        "robot_port": "/dev/follower",
        "robot_id": "follower01",
        "teleop_port": "/dev/leader",
        "teleop_id": "leader01",
        "repo_id": "hashtagrobotics/tic-tac-toe-so101",
        "task": "first",
        "episodes": 2,
        "episode_tasks": ["first", "second"],
    }
    plan = adapter.builder.build(real_request(JobKind.RECORDING, **parameters))
    job = JobRecord(
        kind=JobKind.RECORDING,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )

    assert plan.executable == "hashtag-lerobot-record"
    assert json.loads(adapter.environment(job)["HASHTAG_EPISODE_TASKS_JSON"]) == [
        "first",
        "second",
    ]


def test_a_planned_recording_rejects_a_task_count_mismatch() -> None:
    with pytest.raises(PhysicalExecutionError, match="count must match"):
        LeRobotCommandBuilder().build(
            real_request(
                JobKind.RECORDING,
                robot_port="/dev/follower",
                robot_id="follower01",
                teleop_port="/dev/leader",
                teleop_id="leader01",
                repo_id="hashtagrobotics/tic-tac-toe-so101",
                task="first",
                episodes=2,
                episode_tasks=["first"],
            )
        )


def test_replay_arguments_are_nested_under_the_dataset_config() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.REPLAY,
            robot_port="/dev/follower",
            robot_id="follower01",
            repo_id="mertkirgil/hashtag-test",
            episode=2,
        )
    )
    assert plan.executable == "lerobot-replay"
    assert "--dataset.repo_id=mertkirgil/hashtag-test" in plan.arguments
    assert "--dataset.episode=2" in plan.arguments
    assert all(not argument.startswith("--teleop.") for argument in plan.arguments)


def test_replay_never_carries_cameras() -> None:
    """lerobot-replay is the one script that does not import the camera configs.

    Passing --robot.cameras made draccus fail with 'Couldn't find a choice class
    for opencv' before a single action was replayed. Replay records nothing, so
    it has no use for a camera either.
    """
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.REPLAY,
            robot_port="/dev/follower",
            robot_id="follower01",
            repo_id="mertkirgil/hashtag-test",
            cameras={"wrist": {"type": "opencv", "index_or_path": "/dev/video0"}},
        )
    )
    assert all(not argument.startswith("--robot.cameras") for argument in plan.arguments)

    # The commands whose output depends on the frames keep their cameras.
    # Teleoperation is deliberately not among them any more: it records nothing
    # and runs with `display_data=false`, so it read every frame and dropped it
    # while holding the camera the operator wanted for framing the next take.
    for kind in (JobKind.RECORDING, JobKind.POLICY_ROLLOUT):
        with_cameras = LeRobotCommandBuilder().build(
            real_request(
                kind,
                robot_port="/dev/follower",
                robot_id="follower01",
                teleop_port="/dev/leader",
                teleop_id="leader01",
                repo_id="mertkirgil/hashtag-test",
                task="pick",
                policy_path="outputs/train/act",
                cameras={"wrist": {"type": "opencv", "index_or_path": "/dev/video0"}},
            )
        )
        assert any(argument.startswith("--robot.cameras") for argument in with_cameras.arguments), (
            f"{kind.value} should still receive its cameras"
        )


def test_evaluation_uses_the_rollout_strategy_contract() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.EVALUATION,
            robot_port="/dev/follower",
            robot_id="follower01",
            policy_path="/tmp/models/smolvla",
            repo_id="mertkirgil/hashtag-eval",
            task="Put the red cube into the yellow bin",
            episodes=1,
        )
    )
    assert plan.executable == "lerobot-rollout"
    assert plan.interactive is True
    assert "--strategy.type=episodic" in plan.arguments
    assert "--policy.path=/tmp/models/smolvla" in plan.arguments
    assert "--dataset.num_episodes=1" in plan.arguments
    assert all(not argument.startswith("--num_episodes") for argument in plan.arguments)


def test_base_strategy_rollout_is_duration_bound_and_needs_no_dataset() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.POLICY_ROLLOUT,
            robot_port="/dev/follower",
            robot_id="follower01",
            policy_path="/tmp/models/smolvla",
            strategy="base",
            duration=20,
        )
    )
    assert "--strategy.type=base" in plan.arguments
    assert "--duration=20.0" in plan.arguments
    # It records nothing, but it still connects to an arm and therefore still
    # meets the calibration prompt, so it needs a terminal like the rest.
    assert plan.interactive is True
    assert all(not argument.startswith("--dataset.") for argument in plan.arguments)


def test_tic_tac_toe_rollout_uses_the_bench_validated_recorded_contract(
    tmp_path: Path,
) -> None:
    parameters = canonical_tic_tac_toe_parameters(
        {
            "rollout_profile": TIC_TAC_TOE_PROFILE,
            "move_id": "X-7",
            "device": "mps",
        }
    )
    parameters.update(
        {
            "robot_port": "/dev/follower",
            "robot_id": "test_follower",
            "robot_calibration_dir": "/tmp/calibration/robots/so_follower",
            "max_relative_target": 5.0,
            "policy_path": "/tmp/models/smolvla",
            "cameras": {
                "top": {"type": "opencv", "index_or_path": 0},
                "wrist": {"type": "opencv", "index_or_path": 1},
            },
            "rename_map": {
                "observation.images.top": "observation.images.camera1",
                "observation.images.wrist": "observation.images.camera2",
            },
        }
    )

    settings = Settings(_env_file=None, data_dir=tmp_path, open_browser=False)
    adapter = LeRobotCliAdapter(settings, Repository(settings.database_path))
    plan = adapter.builder.build(real_request(JobKind.POLICY_ROLLOUT, **parameters))
    job = JobRecord(
        kind=JobKind.POLICY_ROLLOUT,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )
    environment = adapter.environment(job)

    assert plan.executable == "hashtag-lerobot-rollout"
    assert "--strategy.type=episodic" in plan.arguments
    assert "--strategy.reset_to_initial_position=true" in plan.arguments
    assert "--inference.type=rtc" in plan.arguments
    assert "--inference.queue_threshold=18" in plan.arguments
    assert "--inference.rtc.enabled=false" in plan.arguments
    assert "--return_to_initial_position=true" in plan.arguments
    assert "--robot.disable_torque_on_disconnect=true" in plan.arguments
    assert "--robot.max_relative_target=5.0" in plan.arguments
    assert "--dataset.num_episodes=1" in plan.arguments
    assert "--dataset.episode_time_s=86400" in plan.arguments
    assert "--dataset.video=true" in plan.arguments
    assert all(not argument.startswith("--duration=") for argument in plan.arguments)
    assert environment["HASHTAG_ASYNC_CHUNK_APPEND"] == "1"
    assert environment["HASHTAG_UNBOUNDED_ROLLOUT"] == "1"
    assert "episode_index" in environment["HASHTAG_TTT_DEMO_PRESET_JSON"]
    assert "bottom left" in environment["HASHTAG_ROLLOUT_EPISODE_TASKS_JSON"]
    assert execution_timeout_seconds(job, 900) is None


def test_policy_rollout_passes_the_server_resolved_camera_rename_map() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.POLICY_ROLLOUT,
            robot_port="/dev/follower",
            robot_id="follower01",
            policy_path="/tmp/models/smolvla",
            strategy="base",
            duration=20,
            rename_map={
                "observation.images.top": "observation.images.camera1",
                "observation.images.wrist": "observation.images.camera2",
            },
        )
    )

    assert (
        '--rename_map={"observation.images.top":"observation.images.camera1",'
        '"observation.images.wrist":"observation.images.camera2"}'
    ) in plan.arguments


def test_teleoperator_calibration_does_not_require_robot_port() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.CALIBRATION,
            role="teleoperator",
            teleop_port="/dev/leader",
            teleop_id="leader",
        )
    )
    assert plan.executable == "lerobot-calibrate"
    assert plan.interactive is True
    assert all(not argument.startswith("--robot.") for argument in plan.arguments)
    assert "--teleop.port=/dev/leader" in plan.arguments


def test_calibration_omits_camera_and_limit_arguments() -> None:
    plan = LeRobotCommandBuilder().build(
        real_request(
            JobKind.CALIBRATION,
            robot_port="/dev/follower",
            robot_id="follower01",
            robot_calibration_dir="/tmp/hashtag/calibration",
            max_relative_target=5.0,
            cameras={"front": {"type": "opencv", "index_or_path": 0}},
        )
    )
    assert "--robot.calibration_dir=/tmp/hashtag/calibration" in plan.arguments
    assert all(not argument.startswith("--robot.cameras") for argument in plan.arguments)
    assert all(
        not argument.startswith("--robot.max_relative_target") for argument in plan.arguments
    )


def test_training_command_is_non_actuating_and_typed() -> None:
    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.TRAINING,
            target_mode=TargetMode.READ_ONLY,
            parameters={
                "repo_id": "hashtag/test-dataset",
                "policy_type": "act",
                "output_dir": "outputs/train/act-test",
                "steps": 2000,
            },
            requested_by="test",
        )
    )
    assert plan.executable == "lerobot-train"
    assert plan.requires_actuation is False
    assert plan.interactive is False
    assert "--dataset.repo_id=hashtag/test-dataset" in plan.arguments
    assert "--policy.type=act" in plan.arguments
    assert "--steps=2000" in plan.arguments


def test_every_command_that_connects_to_an_arm_gets_a_terminal() -> None:
    """LeRobot asks whether to use the calibration file on every connect.

    Without a pty that prompt reads EOF and the command dies with exit code 1
    before a single joint moves, which is what happened on the first real
    teleoperation attempt.
    """
    builder = LeRobotCommandBuilder()
    parameters = {
        "robot_port": "/dev/ttyACM0",
        "robot_id": "follower01",
        "teleop_port": "/dev/ttyACM1",
        "teleop_id": "leader01",
        "repo_id": "lab/session",
        "task": "pick",
        "policy_path": "outputs/train/act",
    }

    for kind in (
        JobKind.TELEOPERATION,
        JobKind.RECORDING,
        JobKind.REPLAY,
        JobKind.POLICY_ROLLOUT,
    ):
        plan = builder.build(
            JobCreateRequest(kind=kind, target_mode=TargetMode.REAL, parameters=parameters)
        )
        assert plan.interactive is True, f"{kind.value} needs a terminal"

    # A rollout that records is not the only interactive rollout any more.
    streaming = builder.build(
        JobCreateRequest(
            kind=JobKind.POLICY_ROLLOUT,
            target_mode=TargetMode.REAL,
            parameters={**parameters, "strategy": "streaming"},
        )
    )
    assert streaming.interactive is True


def test_the_calibration_prompt_is_answered_for_jobs_that_only_consume_it(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path, open_browser=False, enable_physical=True)
    adapter = LeRobotCliAdapter(settings, Repository(settings.database_path))
    plan = CommandPlan(
        executable="lerobot-teleoperate",
        arguments=(),
        required_parameters=(),
        description="",
        requires_actuation=True,
        interactive=True,
    )
    prompt = TelemetrySample(
        kind=TelemetryKind.PROMPT,
        prompt="Press ENTER to use provided calibration file ... or type 'c' and press ENTER",
        expects=JobInputKey.RECALIBRATE,
    )

    teleop = JobRecord(kind=JobKind.TELEOPERATION, target_mode=TargetMode.REAL, requested_by="test")
    assert adapter._should_auto_confirm(teleop, plan, prompt, 0) is True
    # Two arms, two prompts, then it stops.
    assert adapter._should_auto_confirm(teleop, plan, prompt, 2) is False

    # Choosing the calibration is the whole point of a calibration job.
    calibrate = JobRecord(
        kind=JobKind.CALIBRATION, target_mode=TargetMode.REAL, requested_by="test"
    )
    assert adapter._should_auto_confirm(calibrate, plan, prompt, 0) is False

    # The 'move to the middle of its range' prompt is never answered for anyone.
    move = TelemetrySample(
        kind=TelemetryKind.PROMPT,
        prompt="Move follower01 to the middle of its range of motion and press ENTER",
        expects=JobInputKey.ENTER,
    )
    assert adapter._should_auto_confirm(teleop, plan, move, 0) is False
