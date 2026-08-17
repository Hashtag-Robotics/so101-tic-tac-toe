from __future__ import annotations

import argparse
from typing import Any

import pytest

from hashtag_robotics.hardware import LeRobotCommandBuilder
from hashtag_robotics.models import JobCreateRequest, JobKind, TargetMode

draccus = pytest.importorskip("draccus")
draccus_utils = pytest.importorskip("draccus.utils")
lerobot_parser = pytest.importorskip("lerobot.configs.parser")
train_config = pytest.importorskip("lerobot.configs.train")
rollout_configs = pytest.importorskip("lerobot.rollout.configs")
calibrate_script = pytest.importorskip("lerobot.scripts.lerobot_calibrate")
record_script = pytest.importorskip("lerobot.scripts.lerobot_record")
replay_script = pytest.importorskip("lerobot.scripts.lerobot_replay")
rollout_script = pytest.importorskip("lerobot.scripts.lerobot_rollout")
setup_motors_script = pytest.importorskip("lerobot.scripts.lerobot_setup_motors")
teleoperate_script = pytest.importorskip("lerobot.scripts.lerobot_teleoperate")
train_script = pytest.importorskip("lerobot.scripts.lerobot_train")

ROBOT = {"robot_port": "/dev/follower", "robot_id": "follower01"}
TELEOP = {"teleop_port": "/dev/leader", "teleop_id": "leader01"}


def real_request(kind: JobKind, **parameters: object) -> JobCreateRequest:
    return JobCreateRequest(
        kind=kind,
        target_mode=TargetMode.REAL,
        parameters=parameters,
        requested_by="test",
    )


def build(kind: JobKind, **parameters: object) -> list[str]:
    return list(LeRobotCommandBuilder().build(real_request(kind, **parameters)).arguments)


def parse(config_class: type, arguments: list[str]) -> Any:
    return draccus.parse(config_class=config_class, args=arguments, exit_on_error=False)


def test_teleoperate_arguments_parse_against_lerobot() -> None:
    config = parse(
        teleoperate_script.TeleoperateConfig,
        build(
            JobKind.TELEOPERATION,
            **ROBOT,
            **TELEOP,
            fps=30,
            teleop_time_s=120,
            max_relative_target=5.0,
        ),
    )
    assert config.robot.port == "/dev/follower"
    assert config.teleop.id == "leader01"
    assert config.robot.max_relative_target == 5.0
    assert config.fps == 30
    assert config.teleop_time_s == 120.0
    assert config.display_data is False


def test_record_arguments_parse_against_lerobot() -> None:
    config = parse(
        record_script.RecordConfig,
        build(
            JobKind.RECORDING,
            **ROBOT,
            **TELEOP,
            repo_id="mertkirgil/hashtag-test",
            task="Put the red cube into the yellow bin",
            episodes=1,
            episode_time_s=19,
            reset_time_s=10,
            cameras={
                "wrist": {
                    "type": "opencv",
                    "index_or_path": "/dev/video0",
                    "width": 640,
                    "height": 480,
                    "fps": 30,
                }
            },
        ),
    )
    assert config.dataset.repo_id == "mertkirgil/hashtag-test"
    assert config.dataset.single_task == "Put the red cube into the yellow bin"
    assert config.dataset.num_episodes == 1
    assert config.dataset.episode_time_s == 19
    assert config.dataset.reset_time_s == 10
    assert config.dataset.push_to_hub is False
    assert "wrist" in config.robot.cameras


def test_replay_arguments_parse_against_lerobot() -> None:
    config = parse(
        replay_script.ReplayConfig,
        build(JobKind.REPLAY, **ROBOT, repo_id="mertkirgil/hashtag-test", episode=2),
    )
    assert config.dataset.repo_id == "mertkirgil/hashtag-test"
    assert config.dataset.episode == 2


def test_robot_calibration_arguments_parse_against_lerobot() -> None:
    config = parse(calibrate_script.CalibrateConfig, build(JobKind.CALIBRATION, **ROBOT))
    assert config.teleop is None
    assert config.robot.id == "follower01"


def test_teleoperator_calibration_arguments_parse_against_lerobot() -> None:
    config = parse(
        calibrate_script.CalibrateConfig,
        build(JobKind.CALIBRATION, role="teleoperator", **TELEOP),
    )
    assert config.robot is None
    assert config.teleop.id == "leader01"


def test_setup_motors_arguments_parse_against_lerobot() -> None:
    arguments = build(JobKind.MOTOR_SETUP, **ROBOT)
    config = parse(setup_motors_script.SetupConfig, arguments)

    assert "--robot.type=so101_follower" in arguments
    assert config.robot.port == "/dev/follower"
    assert isinstance(
        config.robot,
        setup_motors_script.RobotConfig.get_choice_class("so101_follower"),
    )
    assert config.teleop is None
    assert config.device is config.robot


def test_training_arguments_parse_against_lerobot() -> None:
    config = parse(
        train_config.TrainPipelineConfig,
        build(
            JobKind.TRAINING,
            repo_id="mertkirgil/hashtag-test",
            policy_type="act",
            output_dir="/tmp/hashtag-train",
            steps=10,
        ),
    )
    assert config.dataset.repo_id == "mertkirgil/hashtag-test"
    assert config.policy.type == "act"
    assert config.steps == 10


def test_rollout_arguments_are_accepted_except_the_pretrained_path() -> None:
    arguments = build(
        JobKind.EVALUATION,
        **ROBOT,
        policy_path="/tmp/hashtag-policy",
        repo_id="mertkirgil/hashtag-eval",
        task="Evaluate the selected policy",
        episodes=1,
    )
    assert "--policy.path=/tmp/hashtag-policy" in arguments
    path_fields = rollout_configs.RolloutConfig.__get_path_fields__()
    assert "policy" in path_fields

    filtered = lerobot_parser.filter_path_args(path_fields, arguments)
    with pytest.raises(draccus_utils.ParsingError) as failure:
        parse(rollout_configs.RolloutConfig, filtered)
    assert "--policy.path is required" in str(failure.value.__cause__)


def test_directory_style_robot_type_is_rejected_by_lerobot() -> None:
    arguments = [
        argument.replace("so101_follower", "so_follower")
        for argument in build(JobKind.CALIBRATION, **ROBOT)
    ]
    with pytest.raises(argparse.ArgumentError, match="so_follower"):
        parse(calibrate_script.CalibrateConfig, arguments)


def test_flat_dataset_arguments_are_rejected_by_lerobot() -> None:
    arguments = [
        argument.replace("--dataset.", "--")
        for argument in build(
            JobKind.RECORDING,
            **ROBOT,
            **TELEOP,
            repo_id="mertkirgil/hashtag-test",
            task="Put the red cube into the yellow bin",
        )
    ]
    with pytest.raises(draccus_utils.DraccusException, match="unrecognized arguments"):
        parse(record_script.RecordConfig, arguments)
