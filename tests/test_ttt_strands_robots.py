from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import hashtag_robotics.ttt_strands_robots as native


@pytest.mark.skipif(
    native._distribution_version("strands-robots") is None,
    reason="The optional strands-robots feature pack is not installed.",
)
def test_installed_optional_runtime_matches_the_pinned_version_pair() -> None:
    report = native.inspect_strands_robots_runtime()

    assert report["strands_robots_version"] == "0.5.1"
    assert report["lerobot_version"] == "0.6.1"
    assert report["compatible"] is True
    assert report["blockers"] == []


def test_runtime_inspection_is_metadata_only_and_reports_the_pinned_contract(
    monkeypatch,
) -> None:
    versions = {"strands-robots": "0.5.1", "lerobot": "0.6.1"}
    monkeypatch.setattr(native, "_distribution_version", versions.get)
    monkeypatch.setattr(native.importlib.util, "find_spec", lambda _name: object())

    report = native.inspect_strands_robots_runtime()

    assert report["inspection_mode"] == "software-only"
    assert report["compatible"] is True
    assert report["serial_probed"] is False
    assert report["cameras_opened"] is False
    assert report["robot_created"] is False
    assert report["policy_loaded"] is False
    assert report["policy"] == {
        "provider": "lerobot_local",
        "repo_id": "HashtagRobotics/smolvla-tic-tac-toe-games-1-15-120k",
        "revision": "48a6313b7e4983781dd72919105ca691a77cd26c",
        "checkpoint": "120000",
        "policy_type": "smolvla",
        "camera_key_map": {
            "top": "observation.images.camera1",
            "wrist": "observation.images.camera2",
        },
        "strict_keys": True,
        "chunk_size": 50,
        "n_action_steps": 50,
    }


def test_runtime_inspection_blocks_unpinned_or_incompatible_packages(monkeypatch) -> None:
    versions = {"strands-robots": "0.5.0", "lerobot": "0.6.0"}
    monkeypatch.setattr(native, "_distribution_version", versions.get)
    monkeypatch.setattr(native.importlib.util, "find_spec", lambda _name: object())

    report = native.inspect_strands_robots_runtime()

    assert report["compatible"] is False
    assert "Expected strands-robots==0.5.1" in " ".join(report["blockers"])
    assert "Expected LeRobot >=0.6.1,<0.7.0" in " ".join(report["blockers"])


def test_local_policy_kwargs_pin_camera_mapping_and_strict_keys(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    policy_kwargs = native.build_native_policy_kwargs(
        checkpoint_path=checkpoint,
        device="MPS",
    )

    assert policy_kwargs == {
        "pretrained_name_or_path": str(checkpoint.resolve()),
        "policy_type": "smolvla",
        "device": "mps",
        "camera_key_map": {
            "top": "observation.images.camera1",
            "wrist": "observation.images.camera2",
        },
        "strict_keys": True,
    }

    with pytest.raises(native.StrandsRobotsContractError, match="directory is missing"):
        native.build_native_policy_kwargs(
            checkpoint_path=tmp_path / "missing",
            device="cpu",
        )


def test_policy_load_requires_explicit_remote_code_acknowledgements(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()

    def fake_factory(provider: str, **kwargs: Any) -> object:
        calls.append((provider, kwargs))
        return object()

    monkeypatch.delenv(native.TRUST_REMOTE_CODE_ENV, raising=False)
    with pytest.raises(native.StrandsRobotsContractError, match="acknowledge_remote_code=True"):
        native.load_native_policy(
            checkpoint_path=checkpoint,
            policy_factory=fake_factory,
        )
    with pytest.raises(native.StrandsRobotsContractError, match="STRANDS_TRUST_REMOTE_CODE=1"):
        native.load_native_policy(
            checkpoint_path=checkpoint,
            acknowledge_remote_code=True,
            policy_factory=fake_factory,
        )
    assert calls == []

    monkeypatch.setenv(native.TRUST_REMOTE_CODE_ENV, "1")
    policy = native.load_native_policy(
        checkpoint_path=checkpoint,
        acknowledge_remote_code=True,
        policy_factory=fake_factory,
    )
    assert policy is not None
    assert calls[0][0] == "lerobot_local"
    assert calls[0][1]["pretrained_name_or_path"] == str(checkpoint.resolve())
    assert "revision" not in calls[0][1]


def test_simulation_factory_is_explicitly_sim_and_never_uses_auto_mode() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_robot_factory(name: str, **kwargs: Any) -> object:
        calls.append((name, kwargs))
        return object()

    simulation = native.create_so101_simulation(robot_factory=fake_robot_factory)

    assert simulation is not None
    assert calls == [("so101", {"mode": "sim", "backend": "mujoco", "mesh": False})]


def test_hardware_factory_requires_both_gates_before_building_a_robot(tmp_path: Path) -> None:
    port = tmp_path / "fake-serial-port"
    port.touch()
    calibration_dir = tmp_path / "calibration"
    calibration_dir.mkdir()
    (calibration_dir / "follower.json").write_text("{}")
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_robot_factory(name: str, **kwargs: Any) -> object:
        calls.append((name, kwargs))
        return object()

    common = {
        "port": str(port),
        "robot_id": "follower",
        "calibration_dir": calibration_dir,
        "camera_devices": {"top": 0, "wrist": 1},
        "robot_factory": fake_robot_factory,
    }
    with pytest.raises(native.StrandsRobotsContractError, match="disabled"):
        native.create_so101_hardware_robot(
            **common,
            physical_enabled=False,
            explicit_physical_opt_in=True,
        )
    with pytest.raises(native.StrandsRobotsContractError, match="explicit physical opt-in"):
        native.create_so101_hardware_robot(
            **common,
            physical_enabled=True,
            explicit_physical_opt_in=False,
        )
    assert calls == []

    robot = native.create_so101_hardware_robot(
        **common,
        physical_enabled=True,
        explicit_physical_opt_in=True,
    )
    assert robot is not None
    name, kwargs = calls[0]
    assert name == "so101"
    assert kwargs["mode"] == "real"
    assert kwargs["mesh"] is False
    assert kwargs["action_horizon"] == 50
    assert kwargs["control_frequency"] == 30.0
    assert kwargs["max_relative_target"] == 5.0
    assert kwargs["disable_torque_on_disconnect"] is True
    assert kwargs["cameras"]["top"]["type"] == "opencv"
    assert kwargs["cameras"]["wrist"]["index_or_path"] == 1


def test_native_move_uses_exact_training_prompt_and_real_mode_keeps_both_gates() -> None:
    class FakeRobot:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def run_policy(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"status": "success"}

    robot = FakeRobot()
    policy = object()

    result = native.run_native_move(robot, policy, "X-5", execution_mode="sim")
    assert result == {"status": "success"}
    assert robot.calls == [
        {
            "policy_object": policy,
            "instruction": "put the red X in the middle center cell",
            "duration": 120.0,
            "n_steps": 50,
        }
    ]

    with pytest.raises(native.StrandsRobotsContractError, match="disabled"):
        native.run_native_move(robot, policy, "O-1", execution_mode="real")
    assert len(robot.calls) == 1
