from __future__ import annotations

import re
from collections import deque
from statistics import median
from typing import Any

from hashtag_robotics.models import JobInputKey, TelemetryKind, TelemetrySample

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

LOOP_PATTERN = re.compile(r"Teleop loop time:\s*([0-9.]+)\s*ms\s*\(\s*([0-9.]+)\s*Hz\s*\)")
JOINT_HEADER = re.compile(r"^NAME\s*\|\s*NORM$")
RANGE_HEADER = re.compile(r"^NAME\s*\|\s*MIN\s*\|\s*POS\s*\|\s*MAX$")
JOINT_ROW = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*(-?[0-9]+\.[0-9]+)$")
RANGE_ROW = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)$")

EPISODE_PATTERN = re.compile(r"Recording episode\s+(\d+)")
ENCODING_PATTERN = re.compile(r"Hashtag recorder: Encoding episode\s+(\d+)")
DATASET_SAVED_PATTERN = re.compile(r"Hashtag recorder: Saved episode\s+(\d+)")
CAMERA_INCIDENT_PATTERN = re.compile(
    r"Hashtag camera incident:\s+generation=(\d+);\s+role=([^;]+);\s+reason=(.+)"
)
CAMERA_INVALIDATED_PATTERN = re.compile(
    r"Hashtag recorder: Camera incident invalidated episode\s+(\d+)"
)
MANUAL_TAKE_PATTERN = re.compile(r"Hashtag recorder: Manual take gate armed")
MANUAL_RESET_PATTERN = re.compile(r"Hashtag recorder: Manual reset gate armed")
TTT_HOMING_PATTERN = re.compile(r"Demo episode\s+(\d+) başlangıç pozuna")
TTT_HOME_READY_PATTERN = re.compile(r"Demo home hazır")
TTT_INFERENCE_PATTERN = re.compile(r"Tahta onaylandı; model inference başlıyor")
TTT_HOMING_FAILED_PATTERN = re.compile(r"Demo homing (?:başarısız|doğrulaması başarısız)")
RESET_PATTERN = re.compile(r"Reset the environment")
RERECORD_PATTERN = re.compile(r"Re-record episode")
STOP_PATTERN = re.compile(r"Stop recording")
SAVED_PATTERN = re.compile(r"Calibration saved to\s+(\S+)")

# These lines are emitted by LeRobot only after its listener decoded the byte
# and mutated the recording event flags.  They are therefore recorder ACKs,
# unlike a successful HTTP response which proves only that a byte was written.
CONTROL_ACK_PATTERNS = (
    (re.compile(r"Right arrow key pressed\. Exiting loop"), JobInputKey.END_EPISODE),
    (
        re.compile(r"Left arrow key pressed\. Exiting loop and rerecord"),
        JobInputKey.RERECORD_EPISODE,
    ),
    (re.compile(r"Escape key pressed\. Stopping data recording"), JobInputKey.STOP_RECORDING),
)

CHOICE_PROMPT = re.compile(r"type 'c' and press ENTER", re.IGNORECASE)
ENTER_PROMPT = re.compile(r"press ENTER", re.IGNORECASE)


class TelemetryError(RuntimeError):
    pass


def strip_ansi(value: str) -> str:
    return ANSI_PATTERN.sub("", value).replace("\r", "")


class TelemetryParser:
    def __init__(self) -> None:
        self._mode: str | None = None
        self._joints: dict[str, float] = {}
        self._ranges: dict[str, dict[str, int]] = {}

    def feed(self, line: str) -> list[TelemetrySample]:
        text = strip_ansi(line).strip()
        if JOINT_HEADER.match(text):
            samples = self._flush()
            self._mode = "joints"
            self._joints = {}
            return samples
        if RANGE_HEADER.match(text):
            samples = self._flush()
            self._mode = "ranges"
            self._ranges = {}
            return samples

        if self._mode == "joints":
            row = JOINT_ROW.match(text)
            if row:
                self._joints[row.group(1)] = float(row.group(2))
                return []
        if self._mode == "ranges":
            row = RANGE_ROW.match(text)
            if row:
                self._ranges[row.group(1)] = {
                    "min": int(row.group(2)),
                    "pos": int(row.group(3)),
                    "max": int(row.group(4)),
                }
                return []

        samples = self._flush()
        event = self._event(text)
        if event is not None:
            samples.append(event)
        return samples

    def _flush(self) -> list[TelemetrySample]:
        samples: list[TelemetrySample] = []
        if self._mode == "joints" and self._joints:
            samples.append(TelemetrySample(kind=TelemetryKind.JOINTS, joints=dict(self._joints)))
        if self._mode == "ranges" and self._ranges:
            samples.append(
                TelemetrySample(
                    kind=TelemetryKind.CALIBRATION_RANGE,
                    ranges={motor: dict(values) for motor, values in self._ranges.items()},
                )
            )
        self._mode = None
        return samples

    def _event(self, text: str) -> TelemetrySample | None:
        if not text:
            return None

        loop = LOOP_PATTERN.search(text)
        if loop:
            return TelemetrySample(
                kind=TelemetryKind.LOOP,
                loop_ms=float(loop.group(1)),
                hz=float(loop.group(2)),
            )

        if CHOICE_PROMPT.search(text):
            return TelemetrySample(
                kind=TelemetryKind.PROMPT,
                prompt=text,
                expects=JobInputKey.RECALIBRATE,
            )
        if ENTER_PROMPT.search(text):
            return TelemetrySample(
                kind=TelemetryKind.PROMPT,
                prompt=text,
                expects=JobInputKey.ENTER,
            )

        for pattern, control in CONTROL_ACK_PATTERNS:
            if pattern.search(text):
                return TelemetrySample(
                    kind=TelemetryKind.NOTICE,
                    phase=f"control:{control.value}",
                    message=text,
                )

        ttt_homing = TTT_HOMING_PATTERN.search(text)
        if ttt_homing:
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                episode=int(ttt_homing.group(1)),
                phase="ttt:homing",
                message=text,
            )
        if TTT_HOMING_FAILED_PATTERN.search(text):
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="ttt:homing_failed",
                message=text,
            )
        if TTT_HOME_READY_PATTERN.search(text):
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="ttt:home_ready",
                message=text,
            )
        if TTT_INFERENCE_PATTERN.search(text):
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="ttt:inference",
                message=text,
            )

        camera_incident = CAMERA_INCIDENT_PATTERN.search(text)
        if camera_incident:
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="camera:incident",
                message=(
                    f"{camera_incident.group(2).strip()} camera stream stopped; "
                    "the active take is invalid"
                ),
            )
        camera_invalidated = CAMERA_INVALIDATED_PATTERN.search(text)
        if camera_invalidated:
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                episode=int(camera_invalidated.group(1)),
                phase="camera:take_invalidated",
                message=text,
            )
        if MANUAL_TAKE_PATTERN.search(text):
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="manual:take",
                message=text,
            )
        if MANUAL_RESET_PATTERN.search(text):
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="manual:reset",
                message=text,
            )

        episode = EPISODE_PATTERN.search(text)
        if episode:
            return TelemetrySample(
                kind=TelemetryKind.EPISODE,
                episode=int(episode.group(1)),
                phase="recording",
                message=text,
            )
        for pattern, phase in (
            (ENCODING_PATTERN, "encoding"),
            (DATASET_SAVED_PATTERN, "saved"),
        ):
            match = pattern.search(text)
            if match:
                return TelemetrySample(
                    kind=TelemetryKind.EPISODE,
                    episode=int(match.group(1)),
                    phase=phase,
                    message=text,
                )
        for pattern, phase in (
            (RERECORD_PATTERN, "rerecord"),
            (RESET_PATTERN, "reset"),
            (STOP_PATTERN, "stopping"),
        ):
            if pattern.search(text):
                return TelemetrySample(kind=TelemetryKind.EPISODE, phase=phase, message=text)

        saved = SAVED_PATTERN.search(text)
        if saved:
            return TelemetrySample(
                kind=TelemetryKind.NOTICE,
                phase="calibration_saved",
                message=saved.group(1),
            )
        return None


class TelemetryBuffer:
    def __init__(self, capacity: int = 240) -> None:
        self._samples: deque[TelemetrySample] = deque(maxlen=capacity)
        self._loop_ms: deque[float] = deque(maxlen=capacity)
        # Lifecycle events must survive high-frequency joint/loop samples so
        # the operator can audit the whole recording session in the dashboard.
        self._events: deque[TelemetrySample] = deque(maxlen=64)

    def append(self, sample: TelemetrySample) -> None:
        if sample.phase == "camera:incident":
            current_episode = self.latest(TelemetryKind.EPISODE)
            current_phase = current_episode.phase if current_episode is not None else None
            if current_phase == "recording":
                sample = sample.model_copy(update={"phase": "camera:incident_during_take"})
            elif current_phase == "reset":
                sample = sample.model_copy(update={"phase": "camera:incident_during_reset"})
        self._samples.append(sample)
        if sample.loop_ms is not None:
            self._loop_ms.append(sample.loop_ms)
        if sample.kind == TelemetryKind.EPISODE or (
            sample.kind == TelemetryKind.NOTICE
            and (sample.phase or "").startswith(("control:", "camera:", "manual:", "ttt:"))
        ):
            self._events.append(sample)

    def latest(self, kind: TelemetryKind) -> TelemetrySample | None:
        for sample in reversed(self._samples):
            if sample.kind == kind:
                return sample
        return None

    def summary(self) -> dict[str, Any]:
        joints = self.latest(TelemetryKind.JOINTS)
        ranges = self.latest(TelemetryKind.CALIBRATION_RANGE)
        prompt = self.latest(TelemetryKind.PROMPT)
        episode = self.latest(TelemetryKind.EPISODE)
        control = next(
            (
                sample
                for sample in reversed(self._samples)
                if sample.kind == TelemetryKind.NOTICE
                and (sample.phase or "").startswith("control:")
            ),
            None,
        )
        if episode is not None and episode.episode is None:
            numbered = next(
                (
                    sample
                    for sample in reversed(self._samples)
                    if sample.kind == TelemetryKind.EPISODE and sample.episode is not None
                ),
                None,
            )
            if numbered is not None:
                episode = episode.model_copy(update={"episode": numbered.episode})
        return {
            "samples": len(self._samples),
            "p50_loop_ms": _percentile(self._loop_ms, 0.5),
            "p95_loop_ms": _percentile(self._loop_ms, 0.95),
            "joints": joints.joints if joints else {},
            "ranges": ranges.ranges if ranges else {},
            "prompt": prompt.model_dump(mode="json") if prompt else None,
            "episode": episode.model_dump(mode="json") if episode else None,
            "control": control.model_dump(mode="json") if control else None,
            "events": [sample.model_dump(mode="json") for sample in self._events],
        }


def _percentile(values: deque[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if fraction <= 0.5:
        return round(median(ordered), 3)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return round(ordered[index], 3)
