from __future__ import annotations

import contextlib
import importlib.util
import time
from typing import Any

from hashtag_robotics.models import (
    DeviceIdentification,
    DeviceRole,
    MotorReading,
    TorqueReleaseResult,
)

# SO-101 joints in the order LeRobot addresses them.
SO101_JOINTS = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}

# Feetech STS/SMS control table entries. Reads resolve these through LeRobot's
# own table when it is installed, so a firmware revision stays in one place --
# except `TORQUE_ENABLE`, which the emergency stop writes from the constant.
# See `release_torque` for why, and `lerobot_torque_register` for the check that
# keeps the constant honest.
PRESENT_POSITION = (56, 2)
PRESENT_VOLTAGE = (62, 1)
TORQUE_ENABLE = (40, 1)

BAUDRATES = (1_000_000, 115_200)

TORQUE_DISABLED = 0

# The killed process may not have handed the file descriptor back yet.
PORT_OPEN_ATTEMPTS = 3
PORT_OPEN_RETRY_SECONDS = 0.2

# The Hashtag SO-101 kit powers the follower from a 12 V adapter and the leader
# from a 5 V one, so the bus voltage separates the two roles by a factor of two.
# This is a property of the shipped kit, not of SO-101 in general, which is why
# it is only ever a suggestion the operator confirms.
FOLLOWER_MIN_VOLTS = 9.0
LEADER_MAX_VOLTS = 7.5


class IdentificationError(RuntimeError):
    pass


def runtime_available() -> bool:
    return importlib.util.find_spec("scservo_sdk") is not None


def _control_table() -> dict[str, tuple[int, int]]:
    """Prefer LeRobot's own table so a firmware revision stays in one place."""
    try:
        from lerobot.motors.feetech.tables import STS_SMS_SERIES_CONTROL_TABLE as table
    except Exception:
        return {
            "Present_Position": PRESENT_POSITION,
            "Present_Voltage": PRESENT_VOLTAGE,
            "Torque_Enable": TORQUE_ENABLE,
        }
    return {
        name: table.get(name, default)
        for name, default in (
            ("Present_Position", PRESENT_POSITION),
            ("Present_Voltage", PRESENT_VOLTAGE),
            ("Torque_Enable", TORQUE_ENABLE),
        )
    }


def suggest_role(volts: float | None) -> tuple[DeviceRole, str, str]:
    """Map a measured bus voltage onto a role, a confidence and a reason."""
    if volts is None:
        return (
            DeviceRole.UNASSIGNED,
            "unknown",
            "Bus voltage could not be read, so the role cannot be suggested.",
        )
    if volts >= FOLLOWER_MIN_VOLTS:
        return (
            DeviceRole.FOLLOWER,
            "high",
            f"The bus reads {volts:.1f} V; the kit powers the follower from 12 V.",
        )
    if volts <= LEADER_MAX_VOLTS:
        return (
            DeviceRole.LEADER,
            "high",
            f"The bus reads {volts:.1f} V; the kit powers the leader from 5 V.",
        )
    return (
        DeviceRole.UNASSIGNED,
        "low",
        f"The bus reads {volts:.1f} V, which matches neither the 12 V follower "
        "nor the 5 V leader supply.",
    )


def release_torque(
    port: str,
    open_attempts: int = PORT_OPEN_ATTEMPTS,
    retry_seconds: float = PORT_OPEN_RETRY_SECONDS,
) -> TorqueReleaseResult:
    """Write `Torque_Enable = 0` to every servo on one bus and report what stuck.

    This is the step that actually makes an arm limp. Killing the LeRobot
    process ends the stream of goal positions, but the servos keep holding the
    last one under power: a jammed arm goes on pressing until it overloads, and
    a trapped one cannot be pushed away by hand. Only this write releases it.

    `Torque_Enable` is address 40, the first SRAM register, so the cut costs no
    EEPROM write cycles and changes nothing permanently -- the next `connect()`
    re-enables torque. LeRobot's own `disable_torque` also writes `Lock`, which
    unlocks EEPROM; that is deliberately not done here, because an emergency
    stop should not leave the servo's permanent memory writable.

    The broadcast goes out at every baudrate the adapter accepts, before
    anything is read back. Walking the bus first would mean discovering halfway
    through that motor 3 is deaf -- an emergency stop cannot afford to ask
    permission, so it writes first and reports second.

    Nothing on this path imports LeRobot. Resolving the address through
    `_control_table()` was measured on this machine at **3.46 s** the first time,
    because LeRobot's table module pulls in torch; an emergency stop cannot
    spend three and a half seconds loading a deep learning framework before it
    writes one byte. So the address is a constant here, and
    `lerobot_torque_register()` is the calm-moment check that it is still right.

    Never raises. A failed stop must still be reported, and the caller has
    nothing useful to do with an exception.
    """
    started = time.monotonic()
    result = TorqueReleaseResult(port=port)

    def finish(detail: str) -> TorqueReleaseResult:
        result.detail = detail
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        return result

    if not runtime_available():
        return finish(
            "The Feetech runtime is not installed, so torque cannot be cut in software. "
            "Remove power from the arm."
        )

    from scservo_sdk import BROADCAST_ID, COMM_SUCCESS, PacketHandler, PortHandler

    address, _ = TORQUE_ENABLE

    try:
        handler = PortHandler(port)
    except Exception as error:  # noqa: BLE001 - an emergency stop never raises
        return finish(f"Serial port '{port}' could not be prepared: {error}. Remove power.")

    opened = False
    for attempt in range(open_attempts):
        with contextlib.suppress(Exception):
            opened = bool(handler.openPort())
        if opened:
            break
        if attempt + 1 < open_attempts:
            time.sleep(retry_seconds)
    if not opened:
        return finish(
            f"Serial port '{port}' could not be opened, so torque is still engaged. "
            "Remove power from the arm."
        )

    try:
        for baudrate in BAUDRATES:
            if not handler.setBaudRate(baudrate):
                continue
            packet = PacketHandler(0)
            packet.write1ByteTxOnly(handler, BROADCAST_ID, address, TORQUE_DISABLED)
            off, engaged, silent = _scan_torque(packet, handler, address, COMM_SUCCESS)
            if not off and not engaged:
                continue

            result.baudrate = baudrate
            result.motors_confirmed_off = off
            result.motors_still_engaged = engaged
            result.motors_silent = silent
            result.released = not engaged and not silent

            if engaged:
                names = ", ".join(f"{SO101_JOINTS.get(m, m)}({m})" for m in engaged)
                return finish(f"Torque is STILL ENGAGED on {names}. Remove power from the arm.")
            if silent:
                return finish(
                    f"{len(off)}/{len(SO101_JOINTS)} servos confirm torque is off, but "
                    f"{len(silent)} did not answer. Check the arm before trusting it."
                )
            return finish(f"All {len(off)} servos confirm torque is off.")

        return finish(
            "The broadcast was sent but no servo answered at any baudrate, so the arm "
            "may still be energised. Remove power if it does not go limp."
        )
    except Exception as error:  # noqa: BLE001 - an emergency stop never raises
        return finish(f"Torque cut failed on '{port}': {error}. Remove power from the arm.")
    finally:
        with contextlib.suppress(Exception):
            handler.closePort()


def lerobot_torque_register() -> tuple[int, int] | None:
    """LeRobot's own `Torque_Enable` entry, or None when LeRobot is not installed.

    Slow -- importing LeRobot's tables pulls in torch. Never call this from the
    emergency path; it exists so `doctor` can prove, in a calm moment, that the
    constant `release_torque` writes still points at the right register. A
    firmware revision that moved it would otherwise be discovered during an
    emergency, by the arm not going limp.
    """
    try:
        from lerobot.motors.feetech.tables import STS_SMS_SERIES_CONTROL_TABLE as table
    except Exception:
        return None
    entry = table.get("Torque_Enable")
    return (int(entry[0]), int(entry[1])) if entry else None


def _scan_torque(
    packet: Any,
    handler: Any,
    address: int,
    success: int,
) -> tuple[list[int], list[int], list[int]]:
    """Read `Torque_Enable` back from every SO-101 joint: off, engaged, silent."""
    off: list[int] = []
    engaged: list[int] = []
    silent: list[int] = []
    for motor_id in SO101_JOINTS:
        try:
            value, comm, error = packet.read1ByteTxRx(handler, motor_id, address)
        except Exception:  # noqa: BLE001 - a deaf servo is data, not a failure
            silent.append(motor_id)
            continue
        if comm != success or error != 0:
            silent.append(motor_id)
        elif int(value):
            engaged.append(motor_id)
        else:
            off.append(motor_id)
    return off, engaged, silent


class IdentificationService:
    """Actively probes an arm to report what is really on the bus.

    Discovery only enumerates USB descriptors, which cannot tell a follower from
    a leader and cannot tell a powered arm from an unpowered one. This service
    pings the servos instead. A ping and a register read cannot move a joint and
    never change torque, but they do open the port and put packets on the bus,
    so this is an explicit operator action rather than part of passive scanning.
    """

    def identify(self, port: str) -> DeviceIdentification:
        if not runtime_available():
            raise IdentificationError(
                "The Feetech runtime is not installed. Install the [so101] extra to identify arms."
            )
        from scservo_sdk import COMM_SUCCESS, PacketHandler, PortHandler

        table = _control_table()
        handler = PortHandler(port)
        try:
            if not handler.openPort():
                raise IdentificationError(f"Serial port '{port}' could not be opened.")
        except OSError as error:
            raise IdentificationError(f"Serial port '{port}' could not be opened.") from error

        try:
            for baudrate in BAUDRATES:
                if not handler.setBaudRate(baudrate):
                    continue
                packet = PacketHandler(0)
                readings = self._read_all(packet, handler, table, COMM_SUCCESS)
                if any(reading.responded for reading in readings):
                    return self._summarise(port, baudrate, readings)
            return self._summarise(port, BAUDRATES[0], self._empty())
        finally:
            handler.closePort()

    def _empty(self) -> list[MotorReading]:
        return [
            MotorReading(motor_id=motor_id, name=name, responded=False)
            for motor_id, name in SO101_JOINTS.items()
        ]

    def _read_all(
        self,
        packet: Any,
        handler: Any,
        table: dict[str, tuple[int, int]],
        success: int,
    ) -> list[MotorReading]:
        readings: list[MotorReading] = []
        for motor_id, name in SO101_JOINTS.items():
            model, comm, error = packet.ping(handler, motor_id)
            if comm != success or error != 0:
                readings.append(MotorReading(motor_id=motor_id, name=name, responded=False))
                continue
            position = self._read(packet, handler, motor_id, table["Present_Position"], success)
            volts = self._read(packet, handler, motor_id, table["Present_Voltage"], success)
            torque = self._read(packet, handler, motor_id, table["Torque_Enable"], success)
            readings.append(
                MotorReading(
                    motor_id=motor_id,
                    name=name,
                    responded=True,
                    model_number=model,
                    position=position,
                    volts=self._volts(volts),
                    torque_enabled=self._torque(torque),
                )
            )
        return readings

    def _read(
        self,
        packet: Any,
        handler: Any,
        motor_id: int,
        entry: tuple[int, int],
        success: int,
    ) -> int | None:
        address, length = entry
        reader = packet.read1ByteTxRx if length == 1 else packet.read2ByteTxRx
        value, comm, error = reader(handler, motor_id, address)
        return None if comm != success or error != 0 else int(value)

    def _volts(self, raw: int | None) -> float | None:
        # Feetech reports the bus voltage in tenths of a volt.
        return None if raw is None else round(raw / 10, 1)

    def _torque(self, raw: int | None) -> bool | None:
        return None if raw is None else bool(raw)

    def _summarise(
        self,
        port: str,
        baudrate: int,
        readings: list[MotorReading],
    ) -> DeviceIdentification:
        answered = [reading for reading in readings if reading.responded]
        volts = [reading.volts for reading in answered if reading.volts is not None]
        average = round(sum(volts) / len(volts), 1) if volts else None
        role, confidence, reason = suggest_role(average)

        if not answered:
            reason = (
                "No servo answered on this port. The arm is either unpowered or "
                "the controller board is not connected."
            )
        elif len(answered) < len(SO101_JOINTS):
            missing = ", ".join(reading.name for reading in readings if not reading.responded)
            reason = f"{reason} Only {len(answered)}/6 servos answered; missing: {missing}."

        return DeviceIdentification(
            port=port,
            baudrate=baudrate,
            motors_expected=len(SO101_JOINTS),
            motors_found=len(answered),
            bus_volts=average,
            suggested_role=role,
            confidence=confidence,
            reason=reason,
            motor_ids_match=[reading.motor_id for reading in answered] == sorted(SO101_JOINTS),
            torque_engaged=any(reading.torque_enabled for reading in answered),
            readings=readings,
        )
