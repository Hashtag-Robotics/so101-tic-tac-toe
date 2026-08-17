"""A simulated recording only earns its keep if it can be trained on with a real one.

The whole reason to collect demonstrations in simulation is co-training, and
co-training is silently defeated by a schema mismatch: on this machine the
existing sim dataset named its joints `1`..`6` in radians with CHW images, while
every real recording used `<joint>.pos` in normalised units with HWC. Nothing
raises. The policy just learns less.

So these tests pin the contract rather than the plumbing.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from conftest import requires_lerobot

from hashtag_robotics.hardware import LeRobotCommandBuilder
from hashtag_robotics.models import JobCreateRequest, JobKind, TargetMode
from hashtag_robotics.sim_teleop import (
    LEADER_KEYS,
    LeaderMapping,
    SimArm,
    dataset_features,
)

REAL_STATE_NAMES = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]


def test_the_schema_matches_what_the_real_arm_writes() -> None:
    """Copied from a real SO-101 recording, because they have to be merged."""
    features = dataset_features({"wrist": (640, 480)})

    assert features["action"]["names"] == REAL_STATE_NAMES
    assert features["observation.state"]["names"] == REAL_STATE_NAMES
    assert features["action"]["dtype"] == "float32"
    image = features["observation.images.wrist"]
    assert image["shape"] == (480, 640, 3), "height, width, channels -- not CHW"
    assert image["names"] == ["height", "width", "channels"]


def test_the_mapping_round_trips_exactly() -> None:
    """`observation.state` is the simulated joint reported in the leader's units.

    If the inverse drifted from the forward mapping, a recording's state and its
    action would sit on two different number lines and nothing would say so.
    """
    mapping = LeaderMapping()
    reading = dict(zip(LEADER_KEYS, [12.0, 40.0, -20.0, 5.0, 0.0, 50.0], strict=True))

    back = mapping.to_leader_units(mapping.to_sim(reading))

    for key, value in zip(LEADER_KEYS, back, strict=True):
        assert value == pytest.approx(reading[key], abs=1e-9)


def test_the_gripper_maps_its_whole_travel() -> None:
    mapping = LeaderMapping()
    low, high = mapping.gripper_range_rad

    closed = mapping.to_sim(dict.fromkeys(LEADER_KEYS, 0.0))
    opened = mapping.to_sim({**dict.fromkeys(LEADER_KEYS, 0.0), "gripper.pos": 100.0})

    assert closed[-1] == pytest.approx(low)
    assert opened[-1] == pytest.approx(high)


def test_by_default_a_calibrated_leader_needs_no_correction() -> None:
    """Calibration already normalises each joint to +-100, which is the point of
    it, and the simulated shoulder_lift's range is exactly +-100.

    A default affine here was measured against one calibration and outlived it:
    after the leader was recalibrated the correction was applied to numbers that
    no longer needed it, and leader -100 became -140 degrees against a joint
    that stops at -100.
    """
    default = LeaderMapping()

    assert default.affine_deg == {}
    assert default.to_sim(dict.fromkeys(LEADER_KEYS, -100.0))[1] == pytest.approx(
        math.radians(-100.0)
    )


def test_a_profile_can_still_describe_an_arm_that_differs() -> None:
    """The mechanism stays; only one arm's numbers stopped being everyone's."""
    default = LeaderMapping()
    other = LeaderMapping.for_profile(
        {"affine_deg": {"shoulder_lift.pos": [-57.9, 152.0, -100.0, 100.0]}}
    )
    reading = dict.fromkeys(LEADER_KEYS, 45.0)

    assert default.to_sim(reading)[1] != pytest.approx(other.to_sim(reading)[1])


def test_a_simulated_session_is_not_actuation() -> None:
    """The follower is never opened, so the physical gate has nothing to gate."""
    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_RECORDING,
            target_mode=TargetMode.SIM,
            parameters={"teleop_port": "/dev/leader", "repo_id": "mertkirgil/sim"},
            requested_by="test",
        )
    )

    assert plan.requires_actuation is False
    assert plan.executable == "hashtag-robotics"
    assert "--leader-port=/dev/leader" in plan.arguments
    assert "--no-teleop-only" in plan.arguments


def test_a_rehearsal_records_nothing() -> None:
    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_TELEOPERATION,
            target_mode=TargetMode.SIM,
            parameters={"teleop_port": "/dev/leader"},
            requested_by="test",
        )
    )

    assert "--teleop-only" in plan.arguments
    assert "--episode-time-s=0.0" in plan.arguments


def test_the_useless_scenarios_are_gone(client) -> None:
    """A fixed sine wave producing a table nobody could act on."""
    scenarios = client.get("/api/simulation/scenarios").json()
    identifiers = {item["id"] for item in scenarios}

    assert "scenario_tabletop" not in identifiers
    assert "scenario_mujoco_contract" not in identifiers
    assert "scenario_cube_to_bin" in identifiers, "a task that can actually be recorded"


def test_the_seeded_task_names_the_cameras_a_recording_will_carry(client) -> None:
    scenario = next(
        item
        for item in client.get("/api/simulation/scenarios").json()
        if item["id"] == "scenario_cube_to_bin"
    )

    assert scenario["backend"] == "mujoco"
    assert set(scenario["camera_mapping"]) == {"front", "wrist"}


# -- what the operator is shown ----------------------------------------------


def test_the_command_publishes_what_it_is_driving(tmp_path) -> None:
    """The panel must show the simulation the leader moves, not another one.

    It showed another one: a canned trajectory rendered by the server, running
    beside the real session and visible during it. An operator watching an arm
    swing by itself while their own leader drove an invisible one cannot tell
    that from the whole feature being fake.
    """
    from hashtag_robotics.config import Settings

    settings = Settings(data_dir=tmp_path, open_browser=False)
    plan = LeRobotCommandBuilder(settings).build(
        JobCreateRequest(
            kind=JobKind.SIM_RECORDING,
            target_mode=TargetMode.SIM,
            parameters={"teleop_port": "/dev/leader", "open_viewer": True},
            requested_by="test",
        )
    )

    assert f"--live-frame-path={settings.sim_live_frame_path}" in plan.arguments
    assert "--viewer" in plan.arguments


def test_a_live_frame_is_replaced_whole_never_truncated(tmp_path) -> None:
    """A reader polling the file must not be able to catch half of one."""
    import numpy as np

    from hashtag_robotics.sim_teleop import LiveFrames

    target = tmp_path / "live.jpg"
    live = LiveFrames(str(target), fps=1000)
    live.offer(np.zeros((32, 32, 3), dtype=np.uint8))

    assert target.is_file()
    assert target.read_bytes()[:2] == b"\xff\xd8"
    assert not target.with_suffix(".tmp").exists(), "the staging file is moved, not left behind"


def test_the_live_frame_is_removed_when_the_session_ends(tmp_path) -> None:
    """A stale frame would keep looking like a running session."""
    import numpy as np

    from hashtag_robotics.sim_teleop import LiveFrames

    target = tmp_path / "live.jpg"
    live = LiveFrames(str(target), fps=1000)
    live.offer(np.zeros((32, 32, 3), dtype=np.uint8))

    live.clear()

    assert not target.exists()


def test_publishing_is_rate_limited(tmp_path) -> None:
    """Every frame would be wasted work; a viewer needs to see what is happening."""
    import numpy as np

    from hashtag_robotics.sim_teleop import LiveFrames

    target = tmp_path / "live.jpg"
    live = LiveFrames(str(target), fps=1.0)
    live.offer(np.zeros((32, 32, 3), dtype=np.uint8))
    first = target.stat().st_mtime_ns
    live.offer(np.full((32, 32, 3), 255, dtype=np.uint8))

    assert target.stat().st_mtime_ns == first, "the second frame was inside the interval"


def test_the_live_view_says_so_when_nothing_is_running(client) -> None:
    response = client.get("/api/simulation/live.mjpg")

    assert response.status_code == 409
    assert "No simulated session is running" in response.json()["detail"]


def test_the_live_view_waits_for_a_session_that_is_still_starting(client, monkeypatch) -> None:
    """A browser never retries an <img> that failed once.

    A session needs a few seconds to build its scene and open the leader --
    measured at six on this machine. Refusing during that window left the panel
    showing a broken box for the whole session, even though frames started
    flowing a moment later. So a running session is waited for; only the absence
    of one is refused.
    """
    from hashtag_robotics.models import JobRecord, JobState

    runtime = client.app.state.runtime
    runtime.repository.create_job(
        JobRecord(
            kind=JobKind.SIM_TELEOPERATION,
            target_mode=TargetMode.SIM,
            state=JobState.RUNNING,
            requested_by="test",
        )
    )
    monkeypatch.setattr("hashtag_robotics.api.SIM_LIVE_STARTUP_SECONDS", 0.4)

    response = client.get("/api/simulation/live.mjpg")

    assert response.status_code == 409
    assert "not produced a picture yet" in response.json()["detail"], (
        "a session that is starting gets a different answer from no session at all"
    )


def test_the_live_view_streams_once_a_frame_exists(client) -> None:
    runtime = client.app.state.runtime
    frame = runtime.settings.sim_live_frame_path
    frame.parent.mkdir(parents=True, exist_ok=True)
    frame.write_bytes(b"\xff\xd8\xff\xd9")

    with client.stream("GET", "/api/simulation/live.mjpg") as response:
        assert response.status_code == 200
        first = next(response.iter_bytes())

    assert b"--hashtagsimframe" in first


@requires_lerobot
def test_a_recording_stamps_its_name_like_lerobot_does(monkeypatch, tmp_path) -> None:
    """Two runs of the same task must not land in the same directory.

    `lerobot-record` stamps every dataset with `_YYYYMMDD_HHMMSS`; sim recording
    did not. The second run of a task would fail on an existing directory, and
    the salvage path would then re-register the FIRST run's episodes as the
    second run's output -- the silent-wrong-data shape `resolve_recorded` exists
    to prevent, reintroduced one layer down.
    """
    import re

    from hashtag_robotics import sim_teleop

    created: list[str] = []

    class FakeDataset:
        root = tmp_path

        def add_frame(self, frame: dict) -> None:
            pass

        def save_episode(self) -> None:
            pass

        def clear_episode_buffer(self) -> None:
            pass

        def finalize(self) -> None:
            created.append("finalized")

    def fake_create(*, repo_id: str, **_: object) -> FakeDataset:
        created.append(repo_id)
        return FakeDataset()

    import lerobot.datasets.lerobot_dataset as lerobot_dataset

    monkeypatch.setattr(lerobot_dataset.LeRobotDataset, "create", staticmethod(fake_create))

    class StillArm:
        physics_hz = 500
        cameras = {}  # noqa: RUF012 - a stub, not a model

        class scene:  # noqa: N801 - mirrors the real attribute
            camera_names = ()  # noqa: RUF012

        def apply(self, targets: list[float]) -> list[float]:
            # The real one clamps to each joint's range and reports back what
            # it accepted; the recording stores that, not the request.
            return list(targets)

        def step(self, substeps: int) -> None:
            pass

        def joint_positions(self) -> list[float]:
            return [0.0] * 6

        def frames(self) -> dict:
            return {}

        def reset(self) -> None:
            pass

        def body_position(self, name: str) -> None:
            return None

    class StillLeader:
        def get_action(self) -> dict:
            return dict.fromkeys(sim_teleop.LEADER_KEYS, 0.0)

    plan = sim_teleop.RecordingPlan(
        repo_id="mertkirgil/task",
        task="pick",
        episodes=1,
        episode_time_s=0.05,
        reset_time_s=0,
    )
    result = sim_teleop.record(plan, StillLeader(), StillArm(), sim_teleop.LeaderMapping())

    stamped = created[0]
    assert re.fullmatch(r"mertkirgil/task_\d{8}_\d{6}", stamped), stamped
    assert result["repo_id"] == stamped, "the job must be told the name that was written"
    assert "finalized" in created, (
        "LeRobot: without finalize() the parquet footers are missing and the dataset "
        "is invalid -- and this command exits with os._exit, which runs no finalisers"
    )


# -- a command the arm cannot take must not be recorded as one it took --------


class _Limited:
    """Two joints: one that stops at +-100 degrees, one with no limit at all."""

    nu = 2
    jnt_limited = (1, 0)
    jnt_range = ((-math.radians(100), math.radians(100)), (0.0, 0.0))
    actuator_trnid = ((0, -1), (1, -1))


def test_a_command_past_a_joints_limit_is_clamped() -> None:
    """MuJoCo neither refuses nor clamps it -- `actuator_ctrllimited` is off on
    this model -- it pushes the joint against its stop and the arm ends up
    somewhere other than where it was told."""
    arm = SimArm.__new__(SimArm)
    arm.model = _Limited()
    arm.data = SimpleNamespace(ctrl=[0.0, 0.0])

    accepted = arm.apply([math.radians(-140.0), math.radians(999.0)])

    assert accepted[0] == pytest.approx(math.radians(-100.0))
    assert arm.data.ctrl[0] == pytest.approx(math.radians(-100.0))


def test_an_unlimited_joint_is_left_alone() -> None:
    arm = SimArm.__new__(SimArm)
    arm.model = _Limited()
    arm.data = SimpleNamespace(ctrl=[0.0, 0.0])

    accepted = arm.apply([0.0, math.radians(999.0)])

    assert accepted[1] == pytest.approx(math.radians(999.0))


def test_a_reachable_command_passes_through_untouched() -> None:
    arm = SimArm.__new__(SimArm)
    arm.model = _Limited()
    arm.data = SimpleNamespace(ctrl=[0.0, 0.0])

    accepted = arm.apply([math.radians(42.0), 0.0])

    assert accepted[0] == pytest.approx(math.radians(42.0))
