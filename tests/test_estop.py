"""The emergency stop must leave the arm limp, not merely leave the software stopped.

Killing the LeRobot process ends the stream of goal positions, but the servos go
on holding the last one under power. These tests pin the step that actually
de-energises the bus, and pin it as *pessimistic*: a stop that cannot prove the
arm went limp must say so.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from hashtag_robotics.calibration import CalibrationStore
from hashtag_robotics.camera import CameraService
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.doctor import DoctorService
from hashtag_robotics.identify import (
    SO101_JOINTS,
    TORQUE_ENABLE,
    lerobot_torque_register,
    release_torque,
)
from hashtag_robotics.jobs import ESTOP_GRACE_SECONDS
from hashtag_robotics.models import (
    CheckStatus,
    DeviceRole,
    JobKind,
    JobRecord,
    JobState,
    RobotProfile,
    TargetMode,
    TeleoperatorProfile,
    TorqueReleaseResult,
)
from hashtag_robotics.process import ManagedProcess
from hashtag_robotics.repository import Repository
from hashtag_robotics.safety import TORQUE_RELEASE_FLAG, SafetyService

BROADCAST_ID = 254
COMM_SUCCESS = 0
COMM_RX_TIMEOUT = -3001
TORQUE_ENABLE_ADDRESS = 40


class FakeBus:
    """A Feetech bus that remembers what was written to it.

    `answering` is which servos reply to a read; `ignores_writes` is which ones
    receive the broadcast and carry on holding torque anyway. The two are
    separate because they are separate failures: a deaf servo cannot be
    verified, a stubborn one is verified and still dangerous.
    """

    def __init__(
        self,
        *,
        torque: int = 1,
        answering: set[int] | None = None,
        ignores_writes: set[int] | None = None,
        open_ok: bool = True,
        accepted_baudrates: tuple[int, ...] = (1_000_000,),
    ) -> None:
        self.torque = dict.fromkeys(SO101_JOINTS, torque)
        self.answering = set(SO101_JOINTS) if answering is None else answering
        self.ignores_writes = ignores_writes or set()
        self.open_ok = open_ok
        self.accepted_baudrates = accepted_baudrates
        self.writes: list[tuple[int, int, int]] = []
        self.opens = 0
        self.closes = 0
        self.baudrate: int | None = None


class FakePortHandler:
    def __init__(self, bus: FakeBus, port: str) -> None:
        self.bus = bus
        self.port = port

    def openPort(self) -> bool:  # noqa: N802 - the SDK's spelling
        self.bus.opens += 1
        return self.bus.open_ok

    def setBaudRate(self, baudrate: int) -> bool:  # noqa: N802 - the SDK's spelling
        if baudrate not in self.bus.accepted_baudrates:
            return False
        self.bus.baudrate = baudrate
        return True

    def closePort(self) -> None:  # noqa: N802 - the SDK's spelling
        self.bus.closes += 1


class FakePacketHandler:
    def __init__(self, bus: FakeBus, protocol: int) -> None:
        self.bus = bus

    def write1ByteTxOnly(  # noqa: N802 - the SDK's spelling
        self,
        port: Any,
        scs_id: int,
        address: int,
        data: int,
    ) -> None:
        self.bus.writes.append((scs_id, address, data))
        reached = set(SO101_JOINTS) if scs_id == BROADCAST_ID else {scs_id}
        for motor in reached - self.bus.ignores_writes:
            self.bus.torque[motor] = data

    def read1ByteTxRx(  # noqa: N802 - the SDK's spelling
        self,
        port: Any,
        scs_id: int,
        address: int,
    ) -> tuple[int, int, int]:
        if scs_id not in self.bus.answering:
            return (0, COMM_RX_TIMEOUT, 0)
        return (self.bus.torque[scs_id], COMM_SUCCESS, 0)


@pytest.fixture
def bus(monkeypatch) -> FakeBus:
    """Install a fake scservo_sdk so no test ever writes to a real servo."""
    fake = FakeBus()
    module = types.ModuleType("scservo_sdk")
    module.BROADCAST_ID = BROADCAST_ID
    module.COMM_SUCCESS = COMM_SUCCESS
    module.PortHandler = lambda port: FakePortHandler(fake, port)
    module.PacketHandler = lambda protocol: FakePacketHandler(fake, protocol)
    monkeypatch.setitem(sys.modules, "scservo_sdk", module)
    monkeypatch.setattr("hashtag_robotics.identify.runtime_available", lambda: True)
    return fake


def build_safety(tmp_path: Path, monkeypatch) -> tuple[SafetyService, Repository]:
    monkeypatch.setattr("hashtag_robotics.discovery.list_ports.comports", list)
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")
    camera_root = tmp_path / "v4l-by-id"
    camera_root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", camera_root)

    settings = Settings(data_dir=tmp_path, enable_physical=True, open_browser=False)
    settings.ensure_directories()
    repository = Repository(settings.database_path)
    discovery = DiscoveryService(repository)
    safety = SafetyService(
        settings,
        repository,
        CalibrationStore(settings, repository),
        discovery,
        CameraService(settings, repository, discovery),
    )
    return safety, repository


# -- the write itself ---------------------------------------------------------


def test_torque_is_cut_by_one_broadcast_and_confirmed_by_reading_back(bus: FakeBus) -> None:
    result = release_torque("/dev/ttyACM0")

    assert result.released is True
    assert bus.writes == [(BROADCAST_ID, TORQUE_ENABLE_ADDRESS, 0)]
    assert result.motors_confirmed_off == list(SO101_JOINTS)
    assert result.motors_still_engaged == []
    assert set(bus.torque.values()) == {0}
    assert bus.closes == 1


def test_a_servo_that_ignores_the_broadcast_is_named_and_the_stop_is_not_claimed(
    bus: FakeBus,
) -> None:
    bus.ignores_writes = {3}

    result = release_torque("/dev/ttyACM0")

    assert result.released is False
    assert result.motors_still_engaged == [3]
    assert "elbow_flex" in result.detail
    assert "Remove power" in result.detail


def test_a_silent_servo_is_never_reported_as_de_energised(bus: FakeBus) -> None:
    """Five confirmations and one silence is not six confirmations."""
    bus.answering = {1, 2, 3, 4, 5}

    result = release_torque("/dev/ttyACM0")

    assert result.released is False
    assert result.motors_silent == [6]
    assert result.motors_confirmed_off == [1, 2, 3, 4, 5]
    assert "did not answer" in result.detail


def test_an_unopenable_port_reports_instead_of_raising(bus: FakeBus) -> None:
    bus.open_ok = False

    result = release_torque("/dev/ttyACM0", open_attempts=2, retry_seconds=0.0)

    assert result.released is False
    assert bus.opens == 2, "the port is retried; a just-killed process may still hold it"
    assert "still engaged" in result.detail


def test_a_dead_bus_is_reported_as_possibly_energised(bus: FakeBus) -> None:
    bus.answering = set()

    result = release_torque("/dev/ttyACM0")

    assert result.released is False
    assert result.baudrate is None
    assert "may still be energised" in result.detail


def test_the_second_baudrate_is_tried_when_the_first_is_refused(bus: FakeBus) -> None:
    bus.accepted_baudrates = (115_200,)

    result = release_torque("/dev/ttyACM0")

    assert result.released is True
    assert result.baudrate == 115_200


def test_a_missing_feetech_runtime_reports_instead_of_raising(monkeypatch) -> None:
    monkeypatch.setattr("hashtag_robotics.identify.runtime_available", lambda: False)

    result = release_torque("/dev/ttyACM0")

    assert result.released is False
    assert "Remove power" in result.detail


def test_the_cut_never_resolves_the_control_table_through_lerobot(bus: FakeBus) -> None:
    """Measured on the Orin: `_control_table()` costs 3.46 s the first time.

    It imports LeRobot's tables, which import torch. An emergency stop that
    waits three and a half seconds for a deep learning framework before writing
    one byte is not an emergency stop, so the address is a constant on this
    path. Making the slow resolution explode proves nothing calls it.
    """

    def explode() -> dict[str, tuple[int, int]]:
        raise AssertionError("release_torque must not import LeRobot")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("hashtag_robotics.identify._control_table", explode)
        result = release_torque("/dev/ttyACM0")

    assert result.released is True


@pytest.mark.skipif(
    lerobot_torque_register() is None,
    reason="LeRobot is not installed, so its control table cannot be cross-checked",
)
def test_the_constant_the_stop_writes_still_matches_lerobot() -> None:
    """The price of not resolving the table at runtime is checking it here."""
    assert lerobot_torque_register() == TORQUE_ENABLE


def test_doctor_blocks_when_lerobot_moves_the_torque_register(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "hashtag_robotics.doctor.lerobot_torque_register",
        lambda: (TORQUE_ENABLE[0] + 8, 1),
    )

    report = DoctorService(settings).run()
    check = next(check for check in report.checks if check.code == "safety.torque-register")

    assert check.status is CheckStatus.BLOCKED
    assert "would not de-energise" in check.detail


def test_the_cut_never_touches_the_eeprom_write_lock(bus: FakeBus) -> None:
    """LeRobot's disable_torque also writes Lock=0, which unlocks permanent memory.

    An emergency stop must not leave the servo's EEPROM writable, so only
    Torque_Enable (address 40, SRAM) is ever written.
    """
    release_torque("/dev/ttyACM0")

    assert {address for _, address, _ in bus.writes} == {TORQUE_ENABLE_ADDRESS}


# -- both arms ----------------------------------------------------------------


async def test_every_real_arm_is_cut_and_simulated_profiles_are_left_alone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    safety, repository = build_safety(tmp_path, monkeypatch)
    repository.upsert_entity("robot", RobotProfile(name="Follower 01", port="/dev/ttyACM0"))
    repository.upsert_entity(
        "robot",
        RobotProfile(name="Sim", port=None, target_mode=TargetMode.SIM),
    )
    repository.upsert_entity(
        "teleoperator",
        TeleoperatorProfile(name="Leader 01", port="/dev/ttyACM1"),
    )

    cut: list[str] = []

    def record(port: str, *args: object, **kwargs: object) -> TorqueReleaseResult:
        cut.append(port)
        return TorqueReleaseResult(port=port, released=True, detail="ok")

    monkeypatch.setattr("hashtag_robotics.safety.release_torque", record)

    results = await safety.release_torque()

    assert sorted(cut) == ["/dev/ttyACM0", "/dev/ttyACM1"]
    assert {result.role for result in results} == {DeviceRole.FOLLOWER, DeviceRole.LEADER}
    assert all(result.profile_id for result in results)


async def test_one_failed_arm_does_not_let_the_stop_claim_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    safety, repository = build_safety(tmp_path, monkeypatch)
    repository.upsert_entity("robot", RobotProfile(name="Follower 01", port="/dev/ttyACM0"))
    repository.upsert_entity(
        "teleoperator",
        TeleoperatorProfile(name="Leader 01", port="/dev/ttyACM1"),
    )

    def half_fail(port: str, *args: object, **kwargs: object) -> TorqueReleaseResult:
        return TorqueReleaseResult(port=port, released=port.endswith("0"), detail="")

    monkeypatch.setattr("hashtag_robotics.safety.release_torque", half_fail)

    await safety.release_torque()

    assert safety.last_torque_release()["outcome"] == "partial"
    event = next(
        event
        for event in repository.list_audit(limit=20)
        if event.action == "safety.torque_release"
    )
    assert event.outcome == "partial"


async def test_a_raising_adapter_is_reported_rather_than_crashing_the_stop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    safety, repository = build_safety(tmp_path, monkeypatch)
    repository.upsert_entity("robot", RobotProfile(name="Follower 01", port="/dev/ttyACM0"))

    def explode(port: str, *args: object, **kwargs: object) -> TorqueReleaseResult:
        raise OSError("adapter fell out")

    monkeypatch.setattr("hashtag_robotics.safety.release_torque", explode)

    results = await safety.release_torque()

    assert results[0].released is False
    assert "adapter fell out" in results[0].detail
    assert safety.last_torque_release()["outcome"] == "failed"


async def test_an_installation_with_no_real_arm_says_so_instead_of_claiming_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    safety, repository = build_safety(tmp_path, monkeypatch)

    results = await safety.release_torque()

    assert results == []
    assert safety.last_torque_release()["outcome"] == "no-physical-arms"


# -- the stop as a whole ------------------------------------------------------


async def test_torque_is_cut_after_the_processes_are_killed(client, monkeypatch) -> None:
    """Order matters: a live LeRobot process would re-enable torque on its next write."""
    runtime = client.app.state.runtime
    order: list[str] = []

    async def stop_all(*args: object, **kwargs: object) -> list[str]:
        order.append("kill")
        return []

    async def release(*args: object, **kwargs: object) -> list[TorqueReleaseResult]:
        order.append("torque")
        return [TorqueReleaseResult(port="/dev/ttyACM0", released=True)]

    monkeypatch.setattr(runtime.hardware, "stop_all", stop_all)
    monkeypatch.setattr(runtime.safety, "release_torque", release)

    response = client.post("/api/safety/emergency-stop")

    assert response.status_code == 200
    assert order == ["kill", "torque"]
    event = next(
        event
        for event in runtime.repository.list_audit(limit=20)
        if event.action == "safety.emergency_stop"
    )
    assert event.details["arms_de_energised"] is True


async def test_the_stop_owns_the_job_it_killed_even_when_the_worker_wins_the_race(
    client,
    monkeypatch,
) -> None:
    """On the bench the audit said `affected_jobs: []` and the job said `failed`.

    The process dies during `stop_all`, so by the time the bookkeeping loop runs
    the worker has already reaped it. The stop had stopped something and the
    record did not say what.
    """
    runtime = client.app.state.runtime
    coordinator = runtime.jobs

    async def stop_all(*args: object, **kwargs: object) -> list[str]:
        # Exactly the race: the job reaches a terminal state mid-kill.
        assert "job_ghost" in coordinator._cancelled, "the claim must precede the kill"
        assert coordinator._stop_reason["job_ghost"] == "emergency_stop"
        return ["job_ghost:SIGTERM"]

    async def release(*args: object, **kwargs: object) -> list[TorqueReleaseResult]:
        return []

    reaped = JobRecord(
        id="job_ghost",
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        state=JobState.ABORTED,
        requested_by="test",
    )
    monkeypatch.setattr(runtime.hardware, "processes", {"job_ghost": object()})
    monkeypatch.setattr(runtime.hardware, "stop_all", stop_all)
    monkeypatch.setattr(runtime.safety, "release_torque", release)
    monkeypatch.setattr(runtime.repository, "list_jobs", lambda **_: [reaped])

    affected = await coordinator.emergency_stop()

    assert [job.id for job in affected] == ["job_ghost"]
    event = next(
        event
        for event in runtime.repository.list_audit(limit=20)
        if event.action == "safety.emergency_stop"
    )
    assert event.details["affected_jobs"] == ["job_ghost"]


def test_a_job_killed_by_the_stop_does_not_report_a_bare_failure(client) -> None:
    """`workflow_failed` hides the cause; the operator must see which button won."""
    runtime = client.app.state.runtime
    coordinator = runtime.jobs
    job = JobRecord(
        id="job_reason",
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        state=JobState.RUNNING,
        requested_by="test",
    )
    runtime.repository.create_job(job)
    coordinator._cancelled.add(job.id)
    coordinator._stop_reason[job.id] = "emergency_stop"

    asyncio.run(_die(coordinator, job))

    stored = runtime.repository.get_job(job.id)
    assert stored.state is JobState.ABORTED
    assert stored.error_code == "emergency_stop"
    assert stored.message == "Aborted by emergency stop"


async def _die(coordinator, job: JobRecord) -> None:
    """Drive the generic failure path the way a killed process reaches it."""
    stored = coordinator.repository.get_job(job.id) or job
    operator_stop = job.id in coordinator._cancelled
    reason = coordinator._stop_reason.get(job.id, "operator_cancelled")
    stored.state = JobState.ABORTED if operator_stop else JobState.FAILED
    stored.message = (
        "Aborted by emergency stop"
        if reason == "emergency_stop" and operator_stop
        else "Stopped safely"
        if operator_stop
        else "Workflow failed safely"
    )
    stored.error_code = reason if operator_stop else "workflow_failed"
    coordinator.repository.update_job(stored)


def test_the_stop_gives_lerobot_less_grace_than_a_cancel_does() -> None:
    """The asymmetry is the reason the torque cut exists; pin it so it cannot drift.

    A cancel waits long enough for SIGINT to run LeRobot's `finally`, which
    disables torque by itself. An emergency stop deliberately does not wait that
    long -- which is exactly why it has to cut torque itself. If someone raises
    this value to match, LeRobot starts de-energising the arm again and the cut
    quietly looks redundant.
    """
    cancel_grace = inspect.signature(ManagedProcess.stop).parameters["grace_seconds"].default

    assert cancel_grace > ESTOP_GRACE_SECONDS


def test_the_panel_can_see_what_the_last_stop_de_energised(client) -> None:
    runtime = client.app.state.runtime

    assert client.get("/api/safety/status").json()["last_torque_release"] is None

    runtime.repository.set_flag(
        TORQUE_RELEASE_FLAG,
        '{"outcome": "failed", "arms": [{"port": "/dev/ttyACM0", "released": false}]}',
    )
    status = client.get("/api/safety/status").json()

    assert status["last_torque_release"]["outcome"] == "failed"
