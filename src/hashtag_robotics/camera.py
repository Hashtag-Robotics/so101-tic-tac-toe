from __future__ import annotations

import asyncio
import contextlib
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import AVFOUNDATION_SOURCE_PREFIX, DiscoveryService
from hashtag_robotics.macos_capture import (
    RAW_FRAME_HEADER,
    RAW_FRAME_MAGIC,
    ensure_avfoundation_uid_helper,
    read_raw_frame,
)
from hashtag_robotics.models import CameraProfile, DeviceRecord
from hashtag_robotics.repository import Repository

MJPEG_BOUNDARY = "hashtagframe"
MJPEG_CONTENT_TYPE = f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}"
MJPEG_QUALITY = 70
CAMERA_STALL_SECONDS = 5.0
CAMERA_JOIN_SECONDS = 2.0

# Formats worth trying on a UVC webcam: compressed first, raw as the fallback.
CANDIDATE_FOURCC = ("MJPG", "YUYV")

# Frames discarded before timing starts, so stream start-up is not charged to
# the format under test.
WARMUP_FRAMES = 5

# A format has to be meaningfully faster before it is worth recommending.
FORMAT_GAIN_THRESHOLD = 1.15

# Drivers rarely hit a requested rate exactly; this is the band we call "met".
FPS_TOLERANCE = 0.95


class CameraError(RuntimeError):
    pass


def load_cv2() -> Any:
    """Import OpenCV lazily so the control plane still starts without it."""
    try:
        import cv2
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise CameraError(
            "OpenCV is not installed. Install the [so101] extra to use camera features."
        ) from error
    return cv2


class CameraService:
    """Opens cameras through a stable discovered identity.

    Linux resolves that identity to ``/dev/v4l/by-id``. macOS resolves it to
    the camera's current AVFoundation index on every discovery. A camera can
    only be opened by one consumer at a time, so every
    preview and every recording takes an exclusive lease on the camera; the
    capture handle is released in a finally block on every path.
    """

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        discovery: DiscoveryService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.discovery = discovery

    def connected(self, *, refresh: bool = False) -> list[DeviceRecord]:
        return self.discovery.cameras(refresh=refresh)

    def discover(self) -> list[DeviceRecord]:
        records = self.connected(refresh=True)
        for record in records:
            self.repository.upsert_entity("device", record)
        return records

    def resolve_path(self, profile: CameraProfile) -> str:
        """Map a stored profile back to a live device path."""
        device = self.resolve_device(profile)
        path = device.stable_path or device.transient_path
        if path:
            return path
        raise CameraError(f"No connected camera matches profile '{profile.name}'.")

    def resolve_device(self, profile: CameraProfile) -> DeviceRecord:
        for device in self.connected():
            if device.stable_fingerprint == profile.device_fingerprint:
                return device
        raise CameraError(f"No connected camera matches profile '{profile.name}'.")

    def lerobot_config(
        self,
        profile: CameraProfile,
        path: str,
        preview_name: str | None = None,
    ) -> dict[str, Any]:
        """The entry LeRobot expects inside --robot.cameras."""
        if path.startswith(AVFOUNDATION_SOURCE_PREFIX):
            device = next(
                (
                    item
                    for item in self.connected()
                    if item.stable_fingerprint == profile.device_fingerprint
                ),
                None,
            )
            if device is not None and device.serial_number:
                helper = ensure_avfoundation_uid_helper(self.settings.data_dir)
                return {
                    "type": "avfoundation_uid",
                    "unique_id": device.serial_number,
                    "helper_path": str(helper),
                    "fps": profile.fps,
                    "width": profile.width,
                    "height": profile.height,
                    "rotation": profile.orientation_degrees,
                    **({"preview_name": preview_name} if preview_name else {}),
                }
        source, _, _ = _opencv_source(path)
        config: dict[str, Any] = {
            "type": "opencv",
            "index_or_path": source,
            "fps": profile.fps,
            "width": profile.width,
            "height": profile.height,
            "rotation": profile.orientation_degrees,
        }
        # Without this LeRobot lets the driver pick, which on a USB2 webcam means
        # raw YUYV and a frame rate well under the one the dataset claims.
        if profile.fourcc:
            config["fourcc"] = profile.fourcc
        return config

    @contextlib.contextmanager
    def _capture(
        self,
        profile: CameraProfile,
        fourcc: str | None = None,
    ) -> Iterator[Any]:
        cv2 = load_cv2()
        path = self.resolve_path(profile)
        source, _, backend_attribute = _opencv_source(path)
        backend = getattr(cv2, backend_attribute)
        capture = cv2.VideoCapture(source, backend)
        try:
            if not capture.isOpened():
                raise CameraError(f"Camera '{path}' could not be opened.")
            # FOURCC has to be negotiated before the geometry, or V4L2 keeps the
            # format it already picked and silently ignores the request.
            requested = fourcc or profile.fourcc
            if requested:
                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*requested))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, profile.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, profile.height)
            capture.set(cv2.CAP_PROP_FPS, profile.fps)
            yield capture
        finally:
            capture.release()

    def _measure(
        self,
        profile: CameraProfile,
        samples: int,
        fourcc: str | None = None,
    ) -> dict[str, Any]:
        cv2 = load_cv2()
        latencies: list[float] = []
        dropped = 0
        width = height = 0
        negotiated = 0

        with self._capture(profile, fourcc=fourcc) as capture:
            negotiated = int(capture.get(cv2.CAP_PROP_FOURCC))
            # The first frames carry the cost of starting the stream; measuring
            # them would blame the format for a warm-up it did not cause.
            for _ in range(WARMUP_FRAMES):
                capture.read()
            started = time.perf_counter()
            for _ in range(samples):
                frame_started = time.perf_counter()
                ok, frame = capture.read()
                if not ok or frame is None:
                    dropped += 1
                    continue
                latencies.append((time.perf_counter() - frame_started) * 1000)
                height, width = frame.shape[0], frame.shape[1]
            elapsed = time.perf_counter() - started

        captured = len(latencies)
        return {
            "fourcc": decode_fourcc(negotiated),
            "actual": {"width": width, "height": height},
            "measured_fps": round(captured / elapsed, 2) if elapsed > 0 and captured else 0.0,
            "p50_latency_ms": round(sorted(latencies)[captured // 2], 2) if captured else None,
            "frames_captured": captured,
            "frames_dropped": dropped,
        }

    def probe(
        self,
        profile: CameraProfile,
        samples: int = 15,
        compare_formats: bool = True,
    ) -> dict[str, Any]:
        """Measure what the camera actually delivers, not what was requested.

        When the profile pins no format the driver picks one, and on a USB2
        webcam that is raw YUYV, which cannot carry 640x480 at 30 fps. Measuring
        the alternatives here is what turns 'you asked for 30 and got 21' into a
        decision the operator can actually make.
        """
        device = self.resolve_device(profile)
        path = device.stable_path or device.transient_path
        if not path:
            raise CameraError(f"No connected camera matches profile '{profile.name}'.")
        if path.startswith(AVFOUNDATION_SOURCE_PREFIX) and device.serial_number:
            result = self._measure_avfoundation_uid(profile, device.serial_number, samples)
            return {
                "path": path,
                "backend": "avfoundation/unique-id",
                "requested": {
                    "width": profile.width,
                    "height": profile.height,
                    "fps": profile.fps,
                    "fourcc": profile.fourcc,
                },
                **result,
                "format_benchmark": {result["fourcc"]: result["measured_fps"]},
                "recommended_fourcc": None,
                "meets_requested_fps": result["measured_fps"] >= profile.fps * FPS_TOLERANCE,
            }
        result = self._measure(profile, samples)

        benchmark: dict[str, float] = {result["fourcc"]: result["measured_fps"]}
        if compare_formats and not profile.fourcc:
            for candidate in CANDIDATE_FOURCC:
                if candidate in benchmark:
                    continue
                try:
                    trial = self._measure(profile, samples, fourcc=candidate)
                except CameraError:
                    continue
                # A driver that ignores the request reports a format we already
                # measured; recording it under the requested name would lie.
                if trial["fourcc"] not in benchmark:
                    benchmark[trial["fourcc"]] = trial["measured_fps"]

        best = max(benchmark, key=lambda key: benchmark[key]) if benchmark else None
        recommended = (
            best
            if best
            and best != result["fourcc"]
            and benchmark[best] > result["measured_fps"] * FORMAT_GAIN_THRESHOLD
            else None
        )
        return {
            "path": path,
            "backend": _opencv_source(path)[1],
            "requested": {
                "width": profile.width,
                "height": profile.height,
                "fps": profile.fps,
                "fourcc": profile.fourcc,
            },
            **result,
            "format_benchmark": benchmark,
            "recommended_fourcc": recommended,
            "meets_requested_fps": result["measured_fps"] >= profile.fps * FPS_TOLERANCE,
        }

    def _uid_process(self, profile: CameraProfile, unique_id: str) -> subprocess.Popen[bytes]:
        helper = ensure_avfoundation_uid_helper(self.settings.data_dir)
        return subprocess.Popen(
            [
                str(helper),
                unique_id,
                str(profile.width),
                str(profile.height),
                str(profile.fps),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

    def _measure_avfoundation_uid(
        self,
        profile: CameraProfile,
        unique_id: str,
        samples: int,
    ) -> dict[str, Any]:
        process = self._uid_process(profile, unique_id)
        if process.stdout is None:
            process.kill()
            process.wait()
            raise CameraError("AVFoundation uniqueID capture exposed no frame stream.")
        latencies: list[float] = []
        dropped = 0
        width = height = 0
        try:
            for _ in range(WARMUP_FRAMES):
                read_raw_frame(process.stdout)
            started = time.perf_counter()
            for _ in range(samples):
                frame_started = time.perf_counter()
                try:
                    width, height, _row, _timestamp_ns, _payload = read_raw_frame(process.stdout)
                except EOFError:
                    dropped += 1
                    break
                latencies.append((time.perf_counter() - frame_started) * 1000)
            elapsed = time.perf_counter() - started
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
        captured = len(latencies)
        return {
            "fourcc": "BGRA",
            "actual": {"width": width, "height": height},
            "measured_fps": round(captured / elapsed, 2) if elapsed > 0 and captured else 0.0,
            "p50_latency_ms": round(sorted(latencies)[captured // 2], 2) if captured else None,
            "frames_captured": captured,
            "frames_dropped": dropped,
        }

    def frames(self, profile: CameraProfile) -> Iterator[bytes]:
        path = self.resolve_path(profile)
        device = next(
            (
                item
                for item in self.connected()
                if item.stable_fingerprint == profile.device_fingerprint
            ),
            None,
        )
        source, backend_name, _ = _opencv_source(path)
        if backend_name == "opencv/avfoundation" and device is not None and device.serial_number:
            yield from self._avfoundation_uid_frames(profile, device.serial_number)
            return
        if backend_name == "opencv/avfoundation" and shutil.which("ffmpeg"):
            yield from self._ffmpeg_avfoundation_frames(profile, int(source))
            return
        yield from self._opencv_frames(profile)

    async def async_frames(self, profile: CameraProfile) -> AsyncIterator[bytes]:
        """Stream without routing macOS camera I/O through worker threads."""
        path = self.resolve_path(profile)
        device = next(
            (
                item
                for item in self.connected()
                if item.stable_fingerprint == profile.device_fingerprint
            ),
            None,
        )
        source, backend_name, _ = _opencv_source(path)
        if backend_name == "opencv/avfoundation" and device is not None and device.serial_number:
            async with contextlib.aclosing(
                self._async_avfoundation_uid_frames(profile, device.serial_number)
            ) as chunks:
                async for chunk in chunks:
                    yield chunk
            return
        if backend_name == "opencv/avfoundation" and shutil.which("ffmpeg"):
            # Closing the outer response generator does not implicitly close a
            # nested async generator. Without an explicit aclose, FFmpeg keeps
            # the USB camera open after a browser tab or test client leaves.
            async with contextlib.aclosing(
                self._async_ffmpeg_avfoundation_frames(profile, int(source))
            ) as chunks:
                async for chunk in chunks:
                    yield chunk
            return

        iterator = iter(self._opencv_frames(profile))
        try:
            while True:
                chunk = await asyncio.to_thread(next, iterator, None)
                if chunk is None:
                    break
                yield chunk
        finally:
            close = getattr(iterator, "close", None)
            if close is not None:
                await asyncio.to_thread(close)

    @staticmethod
    def _mjpeg_chunk(payload: bytes) -> bytes:
        return (
            (
                f"--{MJPEG_BOUNDARY}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(payload)}\r\n\r\n"
            ).encode()
            + payload
            + b"\r\n"
        )

    @staticmethod
    def _encode_raw_frame(
        profile: CameraProfile,
        width: int,
        height: int,
        bytes_per_row: int,
        payload: bytes,
    ) -> bytes:
        cv2 = load_cv2()
        import numpy as np

        frame = np.frombuffer(payload, dtype=np.uint8).reshape(height, bytes_per_row)
        frame = frame[:, : width * 4].reshape(height, width, 4)[:, :, :3]
        if profile.orientation_degrees == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif profile.orientation_degrees == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif profile.orientation_degrees == -90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        encoded, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), MJPEG_QUALITY],
        )
        if not encoded:
            raise CameraError("Could not encode the AVFoundation frame as JPEG.")
        return CameraService._mjpeg_chunk(buffer.tobytes())

    def _avfoundation_uid_frames(
        self,
        profile: CameraProfile,
        unique_id: str,
    ) -> Iterator[bytes]:
        process = self._uid_process(profile, unique_id)
        if process.stdout is None:
            process.kill()
            process.wait()
            raise CameraError("AVFoundation uniqueID capture exposed no frame stream.")
        produced = False
        try:
            while True:
                try:
                    width, height, row, _timestamp_ns, payload = read_raw_frame(process.stdout)
                except EOFError:
                    break
                produced = True
                yield self._encode_raw_frame(profile, width, height, row, payload)
            if not produced:
                raise CameraError(f"AVFoundation camera '{unique_id}' produced no frames.")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)

    async def _async_avfoundation_uid_frames(
        self,
        profile: CameraProfile,
        unique_id: str,
    ) -> AsyncIterator[bytes]:
        helper = ensure_avfoundation_uid_helper(self.settings.data_dir)
        process = await asyncio.create_subprocess_exec(
            str(helper),
            unique_id,
            str(profile.width),
            str(profile.height),
            str(profile.fps),
            stdout=asyncio.subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if process.stdout is None:
            process.kill()
            await process.wait()
            raise CameraError("AVFoundation uniqueID capture exposed no frame stream.")
        produced = False
        try:
            while True:
                try:
                    header = await process.stdout.readexactly(RAW_FRAME_HEADER.size)
                except asyncio.IncompleteReadError:
                    break
                magic, width, height, row, payload_size, _timestamp_ns = RAW_FRAME_HEADER.unpack(
                    header
                )
                if magic != RAW_FRAME_MAGIC or payload_size != row * height:
                    raise CameraError("AVFoundation helper emitted an invalid frame header.")
                payload = await process.stdout.readexactly(payload_size)
                produced = True
                yield self._encode_raw_frame(profile, width, height, row, payload)
            if not produced:
                raise CameraError(f"AVFoundation camera '{unique_id}' produced no frames.")
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await asyncio.shield(process.wait())

    async def _async_ffmpeg_avfoundation_frames(
        self,
        profile: CameraProfile,
        index: int,
    ) -> AsyncIterator[bytes]:
        process = await asyncio.create_subprocess_exec(
            *_ffmpeg_avfoundation_command(profile, index),
            stdout=asyncio.subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if process.stdout is None:  # pragma: no cover - subprocess contract guard
            process.kill()
            await process.wait()
            raise CameraError("FFmpeg camera stream did not expose stdout.")
        produced = False
        try:
            while chunk := await process.stdout.read(64 * 1024):
                produced = True
                yield chunk
            if not produced:
                raise CameraError(f"FFmpeg could not open AVFoundation camera {index}.")
        finally:
            if process.returncode is None:
                # HTTP disconnect cancels the response task. A graceful TERM
                # followed by an awaited timeout can itself be cancelled before
                # the KILL branch runs, which leaves FFmpeg holding the UVC
                # camera with no corresponding lease. Kill is appropriate here:
                # this child owns no durable output and must release hardware
                # synchronously when its viewer disappears.
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                # shield keeps the child reap alive even if Starlette cancels
                # this cleanup await along with the disconnected response.
                await asyncio.shield(process.wait())

    def _ffmpeg_avfoundation_frames(
        self,
        profile: CameraProfile,
        index: int,
    ) -> Iterator[bytes]:
        """Let FFmpeg own macOS capture and MJPEG encoding end to end.

        OpenCV reaches 30 FPS when read on the Python main thread, but macOS
        AVFoundation drops sharply in a web server worker. FFmpeg's native
        capture loop holds 30 FPS on the same camera and already emits the
        multipart format the browser expects, so no decode/re-encode is needed.
        """
        process = subprocess.Popen(
            _ffmpeg_avfoundation_command(profile, index),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if process.stdout is None:  # pragma: no cover - Popen contract guard
            process.kill()
            raise CameraError("FFmpeg camera stream did not expose stdout.")
        read = getattr(process.stdout, "read1", process.stdout.read)
        produced = False
        try:
            while True:
                chunk = read(64 * 1024)
                if not chunk:
                    if process.poll() is not None:
                        if not produced:
                            raise CameraError(f"FFmpeg could not open AVFoundation camera {index}.")
                        break
                    continue
                produced = True
                yield chunk
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)

    def _opencv_frames(self, profile: CameraProfile) -> Iterator[bytes]:
        """Yield a paced low-latency MJPEG stream until the client disconnects.

        Camera reads already block until the next hardware frame. Sleeping a
        full frame interval *after* every read therefore cut a 30 FPS camera to
        roughly 15 FPS. This deadline only sleeps when the backend delivers
        faster than the requested rate (for example, a video-file test source).

        AVFoundation also requires capture creation, reads and release to stay
        on one thread. Starlette may advance a sync response generator on a
        different worker for every chunk, which reduced this camera to one
        frame every few seconds. The capture thread owns the whole OpenCV
        lifecycle and publishes only the newest encoded frame through a queue.
        """
        interval = 1 / max(1, profile.fps)
        outbox: queue.Queue[bytes | Exception | None] = queue.Queue(maxsize=1)
        stop = threading.Event()

        def publish(item: bytes | Exception | None) -> None:
            while not stop.is_set():
                try:
                    outbox.put(item, timeout=interval)
                    return
                except queue.Full:
                    # Latency matters more than completeness for a live view.
                    # Discard the old JPEG instead of showing the robot's past.
                    with contextlib.suppress(queue.Empty):
                        outbox.get_nowait()

        def capture_loop() -> None:
            next_frame_at = time.perf_counter()
            terminal: Exception | None = None
            try:
                cv2 = load_cv2()
                with self._capture(profile) as capture:
                    while not stop.is_set():
                        ok, frame = capture.read()
                        if not ok or frame is None:
                            break
                        encoded, buffer = cv2.imencode(
                            ".jpg",
                            frame,
                            [int(cv2.IMWRITE_JPEG_QUALITY), MJPEG_QUALITY],
                        )
                        if encoded:
                            payload = buffer.tobytes()
                            publish(
                                (
                                    f"--{MJPEG_BOUNDARY}\r\n"
                                    f"Content-Type: image/jpeg\r\n"
                                    f"Content-Length: {len(payload)}\r\n\r\n"
                                ).encode()
                                + payload
                                + b"\r\n"
                            )
                        next_frame_at += interval
                        now = time.perf_counter()
                        if next_frame_at > now:
                            stop.wait(next_frame_at - now)
                        elif now - next_frame_at > interval:
                            # A long stall must not create a burst of stale
                            # frames while the deadline catches up.
                            next_frame_at = now
            except Exception as error:  # surfaced to the response consumer
                terminal = error
            finally:
                publish(terminal)

        worker = threading.Thread(
            target=capture_loop,
            name=f"hashtag-camera-{profile.id}",
            daemon=True,
        )
        worker.start()
        try:
            while True:
                try:
                    item = outbox.get(timeout=CAMERA_STALL_SECONDS)
                except queue.Empty as error:
                    raise CameraError(
                        f"Camera '{profile.name}' stopped producing frames."
                    ) from error
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            stop.set()
            with contextlib.suppress(queue.Empty):
                outbox.get_nowait()
            worker.join(timeout=CAMERA_JOIN_SECONDS)


def decode_fourcc(value: int) -> str:
    """Turn the OpenCV FOURCC integer into the pixel format the driver negotiated."""
    if value <= 0:
        return "unknown"
    return "".join(chr((value >> shift) & 0xFF) for shift in (0, 8, 16, 24)).strip()


def _opencv_source(path: str) -> tuple[str | int, str, str]:
    """Translate a discovered source into OpenCV and LeRobot input values."""
    if path.startswith(AVFOUNDATION_SOURCE_PREFIX):
        raw_index = path.removeprefix(AVFOUNDATION_SOURCE_PREFIX)
        try:
            return int(raw_index), "opencv/avfoundation", "CAP_AVFOUNDATION"
        except ValueError as error:
            raise CameraError(f"Invalid AVFoundation camera source '{path}'.") from error
    if Path(path).resolve().is_char_device():
        return path, "opencv/v4l2", "CAP_V4L2"
    return path, "opencv/auto", "CAP_ANY"


def _ffmpeg_avfoundation_command(profile: CameraProfile, index: int) -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "avfoundation",
        "-pixel_format",
        "nv12",
        "-framerate",
        str(profile.fps),
        "-video_size",
        f"{profile.width}x{profile.height}",
        "-i",
        f"{index}:none",
        "-an",
        "-c:v",
        "mjpeg",
        "-q:v",
        "8",
        "-threads",
        "2",
        "-flush_packets",
        "1",
        "-f",
        "mpjpeg",
        "-boundary_tag",
        MJPEG_BOUNDARY,
        "pipe:1",
    ]
