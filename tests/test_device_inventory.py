"""The device table must not claim that yesterday's rows are plugged in today.

Discovery only ever wrote what it saw, so nothing removed what it stopped
seeing. On the test bench two arms had grown into six rows -- one per cable
position, one more when the fingerprinting scheme itself changed -- and all six
said `health: available`.

The rows are not all the same kind of wrong, and the difference is the whole
fix: a row whose serial number matches a connected arm is *that arm under a
retired identity* and must go, while a row nothing connected shares is a real
device that is merely unplugged and must stay, correctly labelled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hashtag_robotics.calibration import CalibrationStore
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import DEVICE_ABSENT, DiscoveryService
from hashtag_robotics.models import CheckStatus, DeviceRecord, RobotProfile
from hashtag_robotics.repository import Repository


class FakePort:
    """The pyserial ListPortInfo surface discovery reads."""

    def __init__(self, device: str, serial_number: str) -> None:
        self.device = device
        self.vid = 0x1A86
        self.pid = 0x7523
        self.serial_number = serial_number
        self.manufacturer = "QinHeng Electronics"
        self.product = "USB Single Serial"
        self.description = self.product
        self.hwid = f"USB VID:PID=1A86:7523 SER={serial_number} LOCATION=1-2.1"


class Bench:
    def __init__(self, repository: Repository, discovery: DiscoveryService) -> None:
        self.repository = repository
        self.discovery = discovery
        self.ports: list[FakePort] = []

    def plug(self, device: str, serial_number: str) -> None:
        self.ports.append(FakePort(device, serial_number))

    def unplug_all(self) -> None:
        self.ports.clear()

    def serial_rows(self) -> list[DeviceRecord]:
        return [
            record
            for record in self.repository.list_entities("device", DeviceRecord)
            if record.kind.value == "serial"
        ]


@pytest.fixture
def bench(tmp_path: Path, monkeypatch) -> Bench:
    settings = Settings(data_dir=tmp_path, open_browser=False)
    settings.ensure_directories()
    repository = Repository(settings.database_path)
    discovery = DiscoveryService(repository)
    fixture = Bench(repository, discovery)

    monkeypatch.setattr(
        "hashtag_robotics.discovery.list_ports.comports",
        lambda: list(fixture.ports),
    )
    monkeypatch.setattr("hashtag_robotics.discovery.SERIAL_BY_ID", tmp_path / "serial-by-id")
    camera_root = tmp_path / "v4l-by-id"
    camera_root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", camera_root)
    return fixture


def ghost(repository: Repository, serial_number: str, port: str, fingerprint: str) -> None:
    """Persist a row the way an older fingerprinting scheme would have."""
    repository.upsert_entity(
        "device",
        DeviceRecord(
            id=f"serial_{fingerprint}",
            kind="serial",
            name="USB Single Serial",
            stable_fingerprint=fingerprint,
            transient_path=port,
            serial_number=serial_number,
            health="available",
        ),
    )


def test_an_arm_under_a_retired_identity_is_removed_not_kept(bench: Bench) -> None:
    """This is the bench state: two arms, six rows, all claiming to be present."""
    bench.plug("/dev/ttyACM1", "5A7C121358")
    bench.plug("/dev/ttyACM0", "5AB0182238")
    ghost(bench.repository, "5A7C121358", "/dev/ttyACM0", "old_scheme_follower")
    ghost(bench.repository, "5AB0182238", "/dev/ttyACM1", "old_scheme_leader")
    ghost(bench.repository, "5A7C121358", "/dev/ttyACM0", "older_still_follower")
    ghost(bench.repository, "5AB0182238", "/dev/ttyACM1", "older_still_leader")

    assert len(bench.serial_rows()) == 4

    bench.discovery.discover()

    rows = bench.serial_rows()
    assert len(rows) == 2, "two arms must leave two rows, not six"
    assert {row.serial_number for row in rows} == {"5A7C121358", "5AB0182238"}
    assert all(row.health == "available" for row in rows)


def test_a_retired_identity_cannot_survive_carrying_a_stale_port(bench: Bench) -> None:
    """The ghost's port was right yesterday and points at the *other* arm today."""
    bench.plug("/dev/ttyACM1", "5A7C121358")
    ghost(bench.repository, "5A7C121358", "/dev/ttyACM0", "yesterdays_identity")

    bench.discovery.discover()

    assert [row.transient_path for row in bench.serial_rows()] == ["/dev/ttyACM1"]


def test_an_unplugged_arm_is_kept_but_stops_claiming_to_be_available(bench: Bench) -> None:
    bench.plug("/dev/ttyACM0", "5A7C121358")
    bench.discovery.discover()
    assert bench.serial_rows()[0].health == "available"

    bench.unplug_all()
    bench.discovery.discover()

    rows = bench.serial_rows()
    assert len(rows) == 1, "an unplugged arm is worth remembering"
    assert rows[0].health == DEVICE_ABSENT
    assert rows[0].serial_number == "5A7C121358"


def test_an_absent_arm_does_not_keep_pointing_at_a_profile(bench: Bench) -> None:
    """A stale binding would offer the operator a target that is not there."""
    bench.plug("/dev/ttyACM0", "5A7C121358")
    device = bench.discovery.discover()[0]
    bench.repository.upsert_entity(
        "robot",
        RobotProfile(name="Follower 01", device_fingerprint=device.stable_fingerprint),
    )
    bench.discovery.discover()
    assert bench.serial_rows()[0].matched_profile_id is not None

    bench.unplug_all()
    bench.discovery.discover()

    assert bench.serial_rows()[0].matched_profile_id is None


def test_inventory_reports_both_kinds_without_writing(bench: Bench) -> None:
    """A GET must not mutate; the merge happens in memory."""
    bench.plug("/dev/ttyACM0", "5A7C121358")
    bench.discovery.discover()
    ghost(bench.repository, "GONE-ARM-99", "/dev/ttyACM7", "long_gone")
    before = len(bench.serial_rows())

    inventory = [item for item in bench.discovery.inventory() if item.kind.value == "serial"]

    assert len(bench.serial_rows()) == before, "inventory() must not write"
    health = {item.serial_number: item.health for item in inventory}
    assert health == {"5A7C121358": "available", "GONE-ARM-99": DEVICE_ABSENT}


def test_inventory_hides_a_retired_identity_of_a_connected_arm(bench: Bench) -> None:
    """Showing the same arm twice, once as 'absent', is worse than not showing it."""
    bench.plug("/dev/ttyACM1", "5A7C121358")
    ghost(bench.repository, "5A7C121358", "/dev/ttyACM0", "yesterdays_identity")

    inventory = [item for item in bench.discovery.inventory() if item.kind.value == "serial"]

    assert len(inventory) == 1
    assert inventory[0].transient_path == "/dev/ttyACM1"


def test_validate_robot_reports_an_unplugged_arm_as_unresolved(bench: Bench) -> None:
    """`Resolved device` claims the arm is connected, so it must ask what is connected."""
    settings = Settings(data_dir=bench.repository.database_path.parent, open_browser=False)
    calibration = CalibrationStore(settings, bench.repository)
    bench.plug("/dev/ttyACM0", "5A7C121358")
    device = bench.discovery.discover()[0]
    profile = RobotProfile(name="Follower 01", device_fingerprint=device.stable_fingerprint)

    present = calibration.validate_robot(profile, bench.discovery.snapshot(False))
    assert _status(present, "target.device_fingerprint") is CheckStatus.PASS

    bench.unplug_all()
    absent = calibration.validate_robot(profile, bench.discovery.snapshot(False))

    assert _status(absent, "target.device_fingerprint") is CheckStatus.BLOCKED


def test_the_stored_table_alone_would_have_said_the_arm_was_still_there(bench: Bench) -> None:
    """Pins the old behaviour so the endpoint cannot quietly go back to it."""
    settings = Settings(data_dir=bench.repository.database_path.parent, open_browser=False)
    calibration = CalibrationStore(settings, bench.repository)
    bench.plug("/dev/ttyACM0", "5A7C121358")
    device = bench.discovery.discover()[0]
    profile = RobotProfile(name="Follower 01", device_fingerprint=device.stable_fingerprint)
    bench.unplug_all()

    stored = bench.repository.list_entities("device", DeviceRecord)
    checks = calibration.validate_robot(profile, stored)

    assert _status(checks, "target.device_fingerprint") is CheckStatus.PASS, (
        "the stored table still resolves the fingerprint -- which is exactly why "
        "the endpoint must not use it"
    )


def _status(checks: list, code: str) -> CheckStatus:
    return next(check.status for check in checks if check.code == code)
