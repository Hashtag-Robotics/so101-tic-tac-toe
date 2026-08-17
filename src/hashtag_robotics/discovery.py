from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from serial.tools import list_ports

from hashtag_robotics.models import (
    DeviceKind,
    DeviceRecord,
    DeviceRole,
    RobotProfile,
    TeleoperatorProfile,
)
from hashtag_robotics.repository import Repository

SERIAL_BY_ID = Path("/dev/serial/by-id")
CAMERA_BY_ID = Path("/dev/v4l/by-id")
AVFOUNDATION_SOURCE_PREFIX = "avfoundation:"
MACOS_CAMERA_AUTO_REFRESH_SECONDS = 4.0

# FFmpeg only prints AVFoundation's transient index and display name. Two of
# this bench's cameras have the same display name, so joining FFmpeg's list to
# system_profiler by occurrence order can swap them after every reconnect.
# AVFoundation itself exposes the index and uniqueID from the same enumeration;
# use that as the primary source and keep the FFmpeg join only as a fallback on
# Macs without the Swift toolchain.
AVFOUNDATION_ENUMERATION_SWIFT = (
    "import AVFoundation; "
    "for (index, device) in AVCaptureDevice.devices(for: .video).enumerated() { "
    'print("\\(index)\\t\\(device.uniqueID)\\t\\(device.localizedName)") }'
)

# AVFoundation device enumeration is not passive while a camera is streaming:
# both system_profiler and FFmpeg touch the capture stack.  Re-running them on
# every dashboard GET can stall an active UVC stream for seconds, so ordinary
# reads share one immutable snapshot.  Operator-initiated discovery refreshes
# it when no camera lease is active.
_macos_camera_cache_lock = threading.Lock()
_macos_camera_cache: tuple[DeviceRecord, ...] | None = None
_macos_camera_cache_at: float | None = None

# A device the table remembers but cannot currently find. Distinct from
# "unknown": this one was here, and it is not here now.
DEVICE_ABSENT = "absent"


def _fingerprint(parts: Iterable[str | None]) -> str:
    material = "|".join(part or "" for part in parts)
    return hashlib.sha256(material.encode()).hexdigest()[:20]


def _avfoundation_camera_fingerprint(unique_id: str | None, name: str, model: str) -> str:
    """Keep an identical UVC camera stable when its hub moves between Mac ports.

    These inexpensive SO-101 cameras publish the product name as their USB
    serial number, so AVFoundation builds ``uniqueID`` from the USB location.
    The high byte is the Mac host/bus; the low 24 bits are the route below that
    host, including the camera's socket on the USB hub.  Moving the whole hub
    changed ``0x02110000`` to ``0x00110000`` on this bench even though the wrist
    camera stayed in the same hub socket.  Hashing the full value therefore
    created a new camera profile on every Mac-port change.

    Preserve the downstream route and the UVC vendor/product descriptor, but
    discard the host byte.  Built-in cameras and devices with an opaque UUID
    keep their complete AVFoundation ID.
    """
    if unique_id and ("UVC" in model.upper() or name.upper().startswith("USB")):
        match = re.fullmatch(r"0x([0-9a-fA-F]+)", unique_id)
        if match and len(match.group(1)) > 8:
            material = match.group(1)
            location_hex, usb_descriptor = material[:-8], material[-8:].lower()
            try:
                downstream_route = int(location_hex, 16) & 0x00FFFFFF
            except ValueError:
                downstream_route = 0
            if downstream_route:
                return _fingerprint(
                    [
                        "avfoundation-usb-route",
                        usb_descriptor,
                        f"{downstream_route:06x}",
                        model,
                    ]
                )
    return _fingerprint(["avfoundation", unique_id or name, model])


def _serial_identity(port: Any) -> tuple[str, bool]:
    """Identify a serial adapter by what it *is*, not by where it is plugged in.

    pyserial's `hwid` carries `LOCATION=<usb path>`, so folding it into the
    fingerprint makes the identity change the moment a cable moves to another
    port -- exactly what a stable fingerprint exists to survive. The adapter's
    own serial number is unique, so it carries the identity on its own.

    An adapter with no serial number is a different case: nothing but its
    position distinguishes it from an identical one, so location stays in the
    material and the record says the identity cannot survive a re-plug.
    """
    identity = [
        port.vid and f"{port.vid:04x}",
        port.pid and f"{port.pid:04x}",
        port.serial_number,
        port.manufacturer,
        port.product,
    ]
    if port.serial_number:
        return _fingerprint(identity), True
    return _fingerprint([*identity, port.hwid]), False


def _stable_paths(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    resolved: dict[str, str] = {}
    for link in sorted(root.iterdir()):
        try:
            resolved[str(link.resolve())] = str(link)
        except OSError:
            continue
    return resolved


def _parse_avfoundation_cameras(
    system_profile: str,
    ffmpeg_devices: str,
) -> list[DeviceRecord]:
    """Join macOS camera identities to their current AVFoundation indexes.

    AVFoundation opens cameras by a transient integer index.  The index alone
    is not an identity: it can change after a reconnect.  ``system_profiler``
    supplies the hardware identity while FFmpeg supplies the current index, so
    profiles remain bound to the camera rather than to yesterday's ordering.
    """
    try:
        cameras = json.loads(system_profile).get("SPCameraDataType", [])
    except (AttributeError, json.JSONDecodeError):
        return []
    if not isinstance(cameras, list):
        return []

    indexes_by_name: dict[str, list[int]] = {}
    in_video_section = False
    for line in ffmpeg_devices.splitlines():
        if "AVFoundation video devices:" in line:
            in_video_section = True
            continue
        if "AVFoundation audio devices:" in line:
            break
        if not in_video_section:
            continue
        match = re.search(r"\]\s+\[(\d+)\]\s+(.+?)\s*$", line)
        if match:
            indexes_by_name.setdefault(match.group(2), []).append(int(match.group(1)))

    records: list[DeviceRecord] = []
    for camera in cameras:
        if not isinstance(camera, dict):
            continue
        name = str(camera.get("_name") or "").strip()
        indexes = indexes_by_name.get(name, [])
        if not name or not indexes:
            continue
        index = indexes.pop(0)
        model = str(camera.get("spcamera_model-id") or name)
        unique_id = str(camera.get("spcamera_unique-id") or "") or None
        fingerprint = _avfoundation_camera_fingerprint(unique_id, name, model)
        records.append(
            DeviceRecord(
                id=f"camera_{fingerprint}",
                kind=DeviceKind.CAMERA,
                name=name,
                stable_fingerprint=fingerprint,
                identity_stable=unique_id is not None,
                transient_path=f"{AVFOUNDATION_SOURCE_PREFIX}{index}",
                vendor="AVFoundation",
                product=model,
                serial_number=unique_id,
                capabilities=["opencv", "avfoundation", "read-only-discovery"],
                health="available",
                matched_role=DeviceRole.CAMERA,
            )
        )
    return records


def _parse_avfoundation_native_cameras(
    system_profile: str,
    native_devices: str,
) -> list[DeviceRecord]:
    """Build camera records from one authoritative AVFoundation enumeration.

    ``native_devices`` carries ``index, uniqueID, name`` on each tab-separated
    line. Unlike the old name-based join, two identical UVC cameras cannot be
    exchanged merely because system_profiler returned them in another order.
    The model still comes from system_profiler so existing profile
    fingerprints remain valid across this discovery upgrade.
    """
    try:
        cameras = json.loads(system_profile).get("SPCameraDataType", [])
    except (AttributeError, json.JSONDecodeError):
        cameras = []
    metadata: dict[str, dict[str, Any]] = {}
    if isinstance(cameras, list):
        metadata = {
            str(camera.get("spcamera_unique-id")): camera
            for camera in cameras
            if isinstance(camera, dict) and camera.get("spcamera_unique-id")
        }

    records: list[DeviceRecord] = []
    for line in native_devices.splitlines():
        parts = line.rstrip().split("\t", 2)
        if len(parts) != 3:
            continue
        raw_index, unique_id, name = parts
        try:
            index = int(raw_index)
        except ValueError:
            continue
        unique_id = unique_id.strip()
        name = name.strip()
        if not unique_id or not name:
            continue
        camera = metadata.get(unique_id, {})
        model = str(camera.get("spcamera_model-id") or name)
        fingerprint = _avfoundation_camera_fingerprint(unique_id, name, model)
        records.append(
            DeviceRecord(
                id=f"camera_{fingerprint}",
                kind=DeviceKind.CAMERA,
                name=name,
                stable_fingerprint=fingerprint,
                identity_stable=True,
                transient_path=f"{AVFOUNDATION_SOURCE_PREFIX}{index}",
                vendor="AVFoundation",
                product=model,
                serial_number=unique_id,
                capabilities=["opencv", "avfoundation", "read-only-discovery"],
                health="available",
                matched_role=DeviceRole.CAMERA,
            )
        )
    return records


def discover_macos_cameras(
    *,
    force: bool = False,
    auto_refresh: bool = False,
) -> list[DeviceRecord]:
    """Return stable macOS camera identities without disturbing live capture.

    AVFoundation indexes only change after a device topology change, for which
    the UI already has an explicit scan action.  Normal callers therefore get
    the cached topology.  The lease-aware ``DiscoveryService`` opts into timed
    refreshes only while no camera is in use; a forced scan is reserved for an
    explicit operator action.
    """
    global _macos_camera_cache, _macos_camera_cache_at

    with _macos_camera_cache_lock:
        cache_expired = (
            auto_refresh
            and _macos_camera_cache_at is not None
            and time.monotonic() - _macos_camera_cache_at >= MACOS_CAMERA_AUTO_REFRESH_SECONDS
        )
        if _macos_camera_cache is not None and not force and not cache_expired:
            return [record.model_copy(deep=True) for record in _macos_camera_cache]

        try:
            profile = subprocess.run(
                ["system_profiler", "SPCameraDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # A transient enumeration failure must not make a live, already
            # resolved camera disappear from every dashboard response.
            if _macos_camera_cache is not None:
                return [record.model_copy(deep=True) for record in _macos_camera_cache]
            return []

        records: list[DeviceRecord] = []
        try:
            native = subprocess.run(
                ["xcrun", "swift", "-e", AVFOUNDATION_ENUMERATION_SWIFT],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if native.returncode == 0:
                records = _parse_avfoundation_native_cameras(profile.stdout, native.stdout)
        except (OSError, subprocess.TimeoutExpired):
            pass

        if not records:
            try:
                devices = subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-f",
                        "avfoundation",
                        "-list_devices",
                        "true",
                        "-i",
                        "",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                if _macos_camera_cache is not None:
                    return [record.model_copy(deep=True) for record in _macos_camera_cache]
                return []
            records = _parse_avfoundation_cameras(
                profile.stdout,
                f"{devices.stdout}\n{devices.stderr}",
            )
        _macos_camera_cache = tuple(record.model_copy(deep=True) for record in records)
        _macos_camera_cache_at = time.monotonic()
        return [record.model_copy(deep=True) for record in records]


class DiscoveryService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def discover(self, include_simulated: bool = True) -> list[DeviceRecord]:
        self.reconcile_fingerprints()
        devices = self.snapshot(include_simulated=include_simulated)
        for record in devices:
            self.repository.upsert_entity("device", record)
        self.retire_stale_devices(devices)
        return devices

    def retire_stale_devices(self, present: list[DeviceRecord]) -> dict[str, list[str]]:
        """Stop the device table from claiming that yesterday's rows are here now.

        Discovery only ever wrote what it saw, so nothing removed what it stopped
        seeing. Every fingerprint an arm has ever had -- one per cable position
        under the old scheme, one more when the scheme itself changed -- stayed
        in the table saying `health: available`. Two arms had grown into six rows,
        all six claiming to be plugged in.

        The rows split into two kinds, and they need opposite treatment:

        **Superseded** -- the serial number matches an arm that is present, but
        the fingerprint does not. That is not another device; it is this device
        under an identity it no longer uses. Keeping it would offer the operator
        a second copy of the same arm carrying a port path that is now wrong,
        which is how a job ends up addressed to the other arm. Deleted.

        **Absent** -- nothing connected shares its serial number. That is a real
        device that is simply unplugged, and the record is worth keeping; it just
        must not go on saying `available`.
        """
        live_fingerprints = {record.stable_fingerprint for record in present}
        live_serials = {record.serial_number for record in present if record.serial_number}

        retired: dict[str, list[str]] = {"superseded": [], "absent": []}
        for stored in self.repository.list_entities("device", DeviceRecord):
            if stored.stable_fingerprint in live_fingerprints or stored.is_simulated:
                continue
            if stored.serial_number and stored.serial_number in live_serials:
                self.repository.delete_entity("device", stored.id)
                retired["superseded"].append(stored.id)
            elif stored.health != DEVICE_ABSENT:
                stored.health = DEVICE_ABSENT
                stored.matched_profile_id = None
                stored.matched_role = DeviceRole.UNASSIGNED
                self.repository.upsert_entity("device", stored)
                retired["absent"].append(stored.id)
        return retired

    def inventory(self, include_simulated: bool = True) -> list[DeviceRecord]:
        """What is connected now, plus what is remembered but gone -- read-only.

        `snapshot` answers "what is here"; the stored table answers "what has
        been here". Neither alone is what an operator needs to see, and a GET
        must not write, so this merges them without touching the repository.
        """
        present = self.snapshot(include_simulated=include_simulated)
        live_fingerprints = {record.stable_fingerprint for record in present}
        live_serials = {record.serial_number for record in present if record.serial_number}

        records = list(present)
        for stored in self.repository.list_entities("device", DeviceRecord):
            if stored.stable_fingerprint in live_fingerprints or stored.is_simulated:
                continue
            if stored.serial_number and stored.serial_number in live_serials:
                continue  # the same arm under a retired identity
            stored.health = DEVICE_ABSENT
            records.append(stored)
        return records

    def reconcile_fingerprints(self) -> list[str]:
        """Re-attach a profile whose arm is present but fingerprinted differently.

        A profile stored under an older fingerprinting scheme, or written before
        a cable moved, points at an identity that no longer exists even though
        the arm is sitting right there. The adapter's serial number is the same
        physical fact in both records, so it is what reconnects them.
        """
        connected = {
            record.serial_number: record
            for record in self.snapshot(include_simulated=False)
            if record.kind == DeviceKind.SERIAL and record.serial_number
        }
        if not connected:
            return []

        healed: list[str] = []
        for kind, model in (("robot", RobotProfile), ("teleoperator", TeleoperatorProfile)):
            for profile in self.repository.list_entities(kind, model):
                device = connected.get(profile.serial_number or "")
                if device is None or profile.device_fingerprint == device.stable_fingerprint:
                    continue
                profile.device_fingerprint = device.stable_fingerprint
                profile.port = device.stable_path or device.transient_path
                self.repository.upsert_entity(kind, profile)
                healed.append(f"{kind}:{profile.id}")
        return healed

    def snapshot(self, include_simulated: bool = True) -> list[DeviceRecord]:
        """Enumerate what is connected right now without writing to the repository."""
        devices: list[DeviceRecord] = []
        robots = self.repository.list_entities("robot", RobotProfile)
        teleoperators = self.repository.list_entities("teleoperator", TeleoperatorProfile)

        serial_paths = _stable_paths(SERIAL_BY_ID)
        for port in list_ports.comports():
            if port.vid is None:
                continue
            fingerprint, identity_stable = _serial_identity(port)
            record = DeviceRecord(
                id=f"serial_{fingerprint}",
                kind=DeviceKind.SERIAL,
                name=port.product or port.description or port.device,
                stable_fingerprint=fingerprint,
                identity_stable=identity_stable,
                transient_path=port.device,
                stable_path=serial_paths.get(port.device),
                vendor=port.manufacturer,
                product=port.product,
                serial_number=port.serial_number,
                capabilities=["serial", "read-only-discovery"],
                health="available",
            )
            self._match_profile(record, robots, teleoperators)
            devices.append(record)

        devices.extend(self.cameras())

        if include_simulated:
            simulation = DeviceRecord(
                id="sim_so101",
                kind=DeviceKind.SIMULATOR,
                name="SO-101 Safe Simulator",
                stable_fingerprint="sim-so101-v1",
                vendor="Hashtag Robotics",
                product="SO-101",
                capabilities=["teleoperation", "recording", "training", "rollout"],
                health="ready",
                is_simulated=True,
            )
            devices.append(simulation)

            gpu = DeviceRecord(
                id="compute_local",
                kind=DeviceKind.GPU,
                name=f"Local compute · {platform.machine()}",
                stable_fingerprint=f"local-{platform.node()}-{platform.machine()}",
                vendor=platform.system(),
                product=platform.processor() or platform.machine(),
                capabilities=["training", "inference"],
                health="ready",
                is_simulated=True,
            )
            devices.append(gpu)

        return devices

    def cameras(self, *, refresh: bool = False) -> list[DeviceRecord]:
        """Return cameras, refreshing macOS topology only when capture is idle."""
        camera_in_use = any(
            lease.resource_type == "camera" for lease in self.repository.list_leases()
        )
        return self._cameras(
            refresh=refresh and not camera_in_use,
            auto_refresh=not camera_in_use,
        )

    def _cameras(
        self,
        *,
        refresh: bool = False,
        auto_refresh: bool = True,
    ) -> list[DeviceRecord]:
        records: list[DeviceRecord] = []
        if not CAMERA_BY_ID.is_dir():
            return (
                discover_macos_cameras(force=refresh, auto_refresh=auto_refresh)
                if platform.system() == "Darwin"
                else records
            )
        for link in sorted(CAMERA_BY_ID.iterdir()):
            if not link.name.endswith("index0"):
                continue
            fingerprint = _fingerprint([link.name])
            try:
                transient = str(link.resolve())
            except OSError:
                continue
            records.append(
                DeviceRecord(
                    id=f"camera_{fingerprint}",
                    kind=DeviceKind.CAMERA,
                    name=link.name.replace("usb-", "").replace("-video-index0", ""),
                    stable_fingerprint=fingerprint,
                    transient_path=transient,
                    stable_path=str(link),
                    capabilities=["opencv", "read-only-discovery"],
                    health="available",
                    matched_role=DeviceRole.CAMERA,
                )
            )
        return records

    def _match_profile(
        self,
        record: DeviceRecord,
        robots: list[RobotProfile],
        teleoperators: list[TeleoperatorProfile],
    ) -> None:
        for robot in robots:
            if robot.device_fingerprint == record.stable_fingerprint:
                record.matched_profile_id = robot.id
                record.matched_role = DeviceRole.FOLLOWER
                return
        for teleoperator in teleoperators:
            if teleoperator.device_fingerprint == record.stable_fingerprint:
                record.matched_profile_id = teleoperator.id
                record.matched_role = DeviceRole.LEADER
                return
