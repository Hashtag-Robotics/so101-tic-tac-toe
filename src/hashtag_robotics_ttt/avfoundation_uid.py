from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np
from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import ColorMode, Cv2Rotation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from lerobot.utils.errors import DeviceNotConnectedError
from numpy.typing import NDArray

from hashtag_robotics_ttt.config_avfoundation_uid import AVFoundationUIDCameraConfig
from hashtag_robotics_ttt.macos_capture import MacOSCaptureError, read_raw_frame

logger = logging.getLogger(__name__)

# At 30 FPS a new frame should arrive every 33 ms.  After three missed frame
# periods, pause the control/recording loop instead of pairing repeated images
# with newer state and actions.  The bounded recovery below still absorbs short
# macOS/USB scheduling pauses and can restart only the affected camera helper.
DEFAULT_MAX_FRAME_AGE_MS = 100.0
STALE_FRAME_RECOVERY_TIMEOUT_MS = 2_000.0

# Monotonic, process-local incident generation.  The LeRobot compatibility
# wrapper snapshots this value at the start of every recorded take.  A camera
# helper restart can recover the live session, but it must never make a take
# containing a wall-clock gap look successful.
_camera_incident_lock = threading.Lock()
_camera_incident_generation = 0


def camera_incident_generation() -> int:
    with _camera_incident_lock:
        return _camera_incident_generation


def _publish_camera_incident(role: str, reason: str) -> int:
    global _camera_incident_generation
    with _camera_incident_lock:
        _camera_incident_generation += 1
        generation = _camera_incident_generation
    # This structured stdout line is parsed into the dashboard's durable
    # recording-event stream.  Keep it independent from logging formatting.
    print(
        f"Hashtag camera incident: generation={generation}; role={role}; reason={reason}",
        flush=True,
    )
    return generation


class _DashboardFrameRelay:
    """Publish a smooth JPEG relay without blocking the recorder camera thread."""

    def __init__(self, name: str | None, fps: float = 24.0) -> None:
        root = os.environ.get("HASHTAG_RECORDING_LIVE_DIR")
        self.path = Path(root) / f"{name}.jpg" if root and name else None
        self.interval = 1 / max(0.1, fps)
        self.lock = threading.Lock()
        self.frame_ready = threading.Event()
        self.stop = threading.Event()
        self.latest: tuple[NDArray[Any], ColorMode] | None = None
        self.thread: threading.Thread | None = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.thread = threading.Thread(
                target=self._publish_loop,
                name=f"dashboard-frame-relay-{name}",
                daemon=True,
            )
            self.thread.start()

    def offer(self, frame: NDArray[Any], color_mode: ColorMode) -> None:
        if self.path is None:
            return
        with self.lock:
            # Each AVFoundation read creates a new array, so the relay can hold
            # the reference without copying 640x480x3 bytes on the capture path.
            self.latest = (frame, color_mode)
        self.frame_ready.set()

    def _publish_loop(self) -> None:
        next_write = 0.0
        while not self.stop.is_set():
            self.frame_ready.wait(timeout=0.2)
            self.frame_ready.clear()
            if self.stop.is_set():
                return
            delay = next_write - time.monotonic()
            if delay > 0 and self.stop.wait(delay):
                return
            with self.lock:
                latest = self.latest
            if latest is not None:
                self._write(*latest)
                next_write = time.monotonic() + self.interval

    def _write(self, frame: NDArray[Any], color_mode: ColorMode) -> None:
        if self.path is None:
            return
        try:
            import cv2

            image = frame[:, :, ::-1] if color_mode == ColorMode.RGB else frame
            ok, buffer = cv2.imencode(
                ".jpg",
                image,
                [int(cv2.IMWRITE_JPEG_QUALITY), 75],
            )
            if not ok:
                return
            temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
            temporary.write_bytes(buffer.tobytes())
            temporary.replace(self.path)
        except Exception:  # noqa: BLE001 - a viewer must never fail a recording
            logger.debug("Could not publish dashboard frame for %s", self.path, exc_info=True)

    def close(self) -> None:
        self.stop.set()
        self.frame_ready.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None


class AVFoundationUIDCamera(Camera):
    """LeRobot camera backed by an AVCaptureDevice uniqueID, never an index."""

    def __init__(self, config: AVFoundationUIDCameraConfig) -> None:
        super().__init__(config)
        self.config = config
        self.process: subprocess.Popen[bytes] | None = None
        self.thread: threading.Thread | None = None
        self.stop_event: threading.Event | None = None
        self.new_frame_event = threading.Event()
        self.frame_lock = threading.Lock()
        self.latest_frame: NDArray[Any] | None = None
        self.latest_timestamp: float | None = None
        self.reader_error: Exception | None = None
        self.dashboard_relay: _DashboardFrameRelay | None = None
        # A stalled UVC/AVFoundation stream can be reopened without touching
        # the follower, leader, or the other camera.  Serialize that recovery
        # so concurrent consumers can never launch two helpers for one device.
        self.restart_lock = threading.Lock()

    def __str__(self) -> str:
        return f"AVFoundationUIDCamera({self.config.unique_id})"

    @property
    def is_connected(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        # Device discovery is performed before this adapter is constructed; the
        # resulting uniqueID is bound to the semantic top or wrist role.
        return []

    def _failure_detail(self) -> str:
        if self.process is None or self.process.stderr is None:
            return ""
        try:
            detail = self.process.stderr.read().decode(errors="replace").strip()
        except Exception:  # noqa: BLE001 - diagnostics must not hide the camera failure
            return ""
        return detail

    @check_if_already_connected
    def connect(self, warmup: bool = True) -> None:
        helper = self.config.helper_path
        if not helper.is_file():
            raise ConnectionError(f"AVFoundation uniqueID helper is missing: {helper}")
        self.process = subprocess.Popen(
            [
                str(helper),
                self.config.unique_id,
                str(self.config.width),
                str(self.config.height),
                str(self.config.fps),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        if self.process.stdout is None:
            self.process.kill()
            self.process.wait()
            self.process = None
            raise ConnectionError(f"{self} did not expose a frame stream.")

        self.reader_error = None
        self.stop_event = threading.Event()
        self.dashboard_relay = _DashboardFrameRelay(self.config.preview_name)
        self.thread = threading.Thread(
            target=self._read_loop,
            args=(self.process.stdout,),
            name=f"{self}_read_loop",
            daemon=True,
        )
        self.thread.start()

        timeout = max(5.0, self.config.warmup_s + 2.0) if warmup else 5.0
        if not self.new_frame_event.wait(timeout=timeout):
            detail = self._failure_detail() if self.process.poll() is not None else ""
            self.disconnect()
            raise ConnectionError(
                f"{self} produced no frame within {timeout:.1f}s"
                + (f": {detail}" if detail else ".")
            )
        if self.reader_error is not None:
            error = self.reader_error
            self.disconnect()
            raise ConnectionError(f"{self} failed during startup: {error}") from error
        logger.info("%s connected.", self)

    def _postprocess(self, payload: bytes, width: int, height: int, row: int) -> NDArray[Any]:
        image = np.frombuffer(payload, dtype=np.uint8).reshape(height, row)
        image = image[:, : width * 4].reshape(height, width, 4)[:, :, :3]
        if self.config.color_mode == ColorMode.RGB:
            image = image[:, :, ::-1]
        if self.config.rotation == Cv2Rotation.ROTATE_90:
            image = np.rot90(image, k=3)
        elif self.config.rotation == Cv2Rotation.ROTATE_180:
            image = np.rot90(image, k=2)
        elif self.config.rotation == Cv2Rotation.ROTATE_270:
            image = np.rot90(image, k=1)
        return np.ascontiguousarray(image)

    def _read_loop(self, stream: BinaryIO) -> None:
        try:
            while self.stop_event is not None and not self.stop_event.is_set():
                width, height, row, _timestamp_ns, payload = read_raw_frame(stream)
                if width != self.config.width or height != self.config.height:
                    raise MacOSCaptureError(
                        f"{self} returned {width}x{height}; expected "
                        f"{self.config.width}x{self.config.height}."
                    )
                frame = self._postprocess(payload, width, height, row)
                with self.frame_lock:
                    self.latest_frame = frame
                    self.latest_timestamp = time.perf_counter()
                if self.dashboard_relay is not None:
                    self.dashboard_relay.offer(frame, self.config.color_mode)
                self.new_frame_event.set()
        except EOFError as error:
            if self.stop_event is None or not self.stop_event.is_set():
                self.reader_error = error
                self.new_frame_event.set()
        except Exception as error:  # noqa: BLE001 - surfaced on the consumer thread
            self.reader_error = error
            self.new_frame_event.set()

    @check_if_not_connected
    def read(self, color_mode: ColorMode | None = None) -> NDArray[Any]:
        if color_mode is not None and ColorMode(color_mode) != self.config.color_mode:
            logger.warning("%s ignores deprecated per-read color_mode=%s.", self, color_mode)
        self.new_frame_event.clear()
        return self.async_read(timeout_ms=10_000)

    @check_if_not_connected
    def async_read(self, timeout_ms: float = 200) -> NDArray[Any]:
        if not self.new_frame_event.wait(timeout=timeout_ms / 1000):
            raise TimeoutError(f"Timed out waiting for a frame from {self} after {timeout_ms}ms.")
        if self.reader_error is not None:
            raise RuntimeError(f"{self} capture failed: {self.reader_error}") from self.reader_error
        with self.frame_lock:
            frame = self.latest_frame
            self.new_frame_event.clear()
        if frame is None:
            raise RuntimeError(f"{self} signalled a frame but stored none.")
        return frame

    @check_if_not_connected
    def _wait_for_newer_frame(
        self,
        previous_timestamp: float,
        timeout_ms: float,
    ) -> tuple[NDArray[Any], float] | None:
        """Wait for a frame captured after ``previous_timestamp``.

        Clearing the event while holding ``frame_lock`` closes the lost-wakeup
        race: the reader cannot update the timestamp until the event is ready
        to represent that update.  A timeout is intentionally bounded because
        a dead camera must still stop physical recording safely.
        """
        deadline = time.perf_counter() + timeout_ms / 1_000
        while True:
            with self.frame_lock:
                frame = self.latest_frame
                timestamp = self.latest_timestamp
                error = self.reader_error
                if frame is not None and timestamp is not None and timestamp > previous_timestamp:
                    return frame, timestamp
                self.new_frame_event.clear()

            if error is not None:
                raise RuntimeError(f"{self} capture failed: {error}") from error
            if self.process is not None and self.process.poll() is not None:
                detail = self._failure_detail()
                raise RuntimeError(
                    f"{self} capture process exited" + (f": {detail}" if detail else ".")
                )

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return None
            self.new_frame_event.wait(timeout=remaining)

    def _restart_capture_after_stall(
        self,
        previous_timestamp: float,
        reason: str,
    ) -> NDArray[Any]:
        """Reopen only this camera helper after a confirmed frame stall.

        The caller has already allowed a transient pause to recover.  This is
        therefore a single, bounded second-stage recovery: stop the affected
        helper, reconnect the same stable AVFoundation uniqueID, and require a
        newly captured frame.  Any reconnect failure still propagates so the
        physical workflow fails safely instead of consuming an old image.
        """
        with self.restart_lock:
            # Another consumer may have completed recovery while this caller
            # was waiting for the lock.  In that case, use its genuinely newer
            # frame and do not churn the camera again.
            with self.frame_lock:
                current_frame = self.latest_frame
                current_timestamp = self.latest_timestamp
            if (
                current_frame is not None
                and current_timestamp is not None
                and current_timestamp > previous_timestamp
                and self.is_connected
            ):
                return current_frame

            _publish_camera_incident(
                self.config.preview_name or self.config.unique_id,
                reason,
            )
            logger.error(
                "%s capture stalled (%s). Restarting only this camera; "
                "robot and teleoperation stay connected.",
                self,
                reason,
            )
            restart_started = time.perf_counter()
            try:
                self.disconnect()
                self.connect()
            except Exception as error:
                raise TimeoutError(
                    f"{self} did not recover after its capture helper was restarted: {error}"
                ) from error

            with self.frame_lock:
                fresh_frame = self.latest_frame
                fresh_timestamp = self.latest_timestamp
            if fresh_frame is None or fresh_timestamp is None:
                raise TimeoutError(f"{self} restarted but produced no fresh frame.")

            logger.warning(
                "%s capture helper recovered in %.1fms; recording session continues.",
                self,
                (time.perf_counter() - restart_started) * 1000,
            )
            return fresh_frame

    def read_latest(
        self,
        max_age_ms: float = DEFAULT_MAX_FRAME_AGE_MS,
        recovery_timeout_ms: float = STALE_FRAME_RECOVERY_TIMEOUT_MS,
    ) -> NDArray[Any]:
        if max_age_ms <= 0 or recovery_timeout_ms <= 0:
            raise ValueError("Frame age and recovery timeouts must be positive.")
        process = self.process
        if process is None:
            raise DeviceNotConnectedError(f"{self} not connected. Run `.connect()` first.")
        with self.frame_lock:
            frame = self.latest_frame
            timestamp = self.latest_timestamp
            reader_error = self.reader_error

        # The generic LeRobot connection decorator cannot distinguish a helper
        # crash from an intentionally disconnected camera.  A retained process
        # object means this camera was connected and its helper died, so recover
        # it through the same local restart path as a live-but-stalled helper.
        process_exit = process.poll()
        if process_exit is not None or reader_error is not None:
            detail = self._failure_detail() if process_exit is not None else ""
            reason = (
                f"capture process exited with code {process_exit}"
                + (f": {detail}" if detail else "")
                if process_exit is not None
                else f"capture reader failed: {reader_error}"
            )
            return self._restart_capture_after_stall(
                timestamp if timestamp is not None else float("-inf"),
                reason,
            )
        if frame is None or timestamp is None:
            raise RuntimeError(f"{self} has not captured a frame yet.")
        age_ms = (time.perf_counter() - timestamp) * 1000
        if age_ms <= max_age_ms:
            return frame

        logger.warning(
            "%s latest frame is %.1fms old; waiting up to %.0fms for a fresh frame.",
            self,
            age_ms,
            recovery_timeout_ms,
        )
        wait_started = time.perf_counter()
        wait_error: RuntimeError | None = None
        try:
            recovered = self._wait_for_newer_frame(timestamp, recovery_timeout_ms)
        except RuntimeError as error:
            # A helper exit and a live helper that stopped emitting frames have
            # the same safe recovery path: reopen this one stable uniqueID.
            recovered = None
            wait_error = error
        if recovered is None:
            with self.frame_lock:
                final_timestamp = self.latest_timestamp
            final_age_ms = (
                (time.perf_counter() - final_timestamp) * 1000
                if final_timestamp is not None
                else float("inf")
            )
            reason = (
                str(wait_error)
                if wait_error is not None
                else (
                    f"no fresh frame arrived within {recovery_timeout_ms:.0f}ms; "
                    f"latest frame age is {final_age_ms:.1f}ms"
                )
            )
            return self._restart_capture_after_stall(timestamp, reason)

        fresh_frame, _fresh_timestamp = recovered
        logger.warning(
            "%s recovered from a stale frame after %.1fms without reusing the old image.",
            self,
            (time.perf_counter() - wait_started) * 1000,
        )
        return fresh_frame

    def disconnect(self) -> None:
        if self.process is None and self.thread is None:
            raise DeviceNotConnectedError(f"{self} not connected.")
        if self.stop_event is not None:
            self.stop_event.set()
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if self.thread is not None:
            self.thread.join(timeout=2)
        if self.dashboard_relay is not None:
            self.dashboard_relay.close()
            self.dashboard_relay = None
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        self.process = None
        self.thread = None
        self.stop_event = None
        self.reader_error = None
        with self.frame_lock:
            self.latest_frame = None
            self.latest_timestamp = None
            self.new_frame_event.clear()
        logger.info("%s disconnected.", self)
