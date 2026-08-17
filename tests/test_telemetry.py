from __future__ import annotations

from hashtag_robotics.models import JobInputKey, TelemetryKind
from hashtag_robotics.telemetry import TelemetryBuffer, TelemetryParser, strip_ansi

TELEOP_BLOCK = """
------------------------
NAME             |    NORM
shoulder_pan     |   12.34
shoulder_lift    |  -45.60
elbow_flex       |    0.00
wrist_flex       |    3.20
wrist_roll       |   -8.75
gripper          |   50.00
Teleop loop time: 12.34ms (81 Hz)
"""

CALIBRATION_BLOCK = """
-------------------------------------------
NAME            |    MIN |    POS |    MAX
shoulder_pan    |   1114 |   2000 |   3027
shoulder_lift   |    800 |   1600 |   3168
"""

MIDDLE_PROMPT = (
    "Move follower01 SOFollower to the middle of its range of motion and press ENTER...."
)
EXISTING_PROMPT = (
    "Press ENTER to use provided calibration file associated with the id follower01, "
    "or type 'c' and press ENTER to run calibration: "
)
MOTOR_PROMPT = "Connect the controller board to the 'gripper' motor only and press enter."


def collect(lines: list[str]) -> list:
    parser = TelemetryParser()
    samples = []
    for line in lines:
        samples.extend(parser.feed(line))
    samples.extend(parser.feed(""))
    return samples


def test_strip_ansi_removes_cursor_movement() -> None:
    assert strip_ansi("\x1b[9Ashoulder_pan | 1114") == "shoulder_pan | 1114"


def test_teleop_block_yields_joints_and_loop_timing() -> None:
    samples = collect(TELEOP_BLOCK.splitlines())
    joints = next(sample for sample in samples if sample.kind == TelemetryKind.JOINTS)
    loop = next(sample for sample in samples if sample.kind == TelemetryKind.LOOP)
    assert joints.joints["shoulder_pan"] == 12.34
    assert joints.joints["shoulder_lift"] == -45.6
    assert len(joints.joints) == 6
    assert loop.loop_ms == 12.34
    assert loop.hz == 81.0


def test_calibration_block_yields_live_ranges() -> None:
    samples = collect(CALIBRATION_BLOCK.splitlines())
    ranges = next(sample for sample in samples if sample.kind == TelemetryKind.CALIBRATION_RANGE)
    assert ranges.ranges["shoulder_pan"] == {"min": 1114, "pos": 2000, "max": 3027}
    assert ranges.ranges["shoulder_lift"]["max"] == 3168


def test_calibration_ranges_survive_cursor_up_escapes() -> None:
    lines = ["\x1b[9A" + line for line in CALIBRATION_BLOCK.splitlines()]
    samples = collect(lines)
    ranges = next(sample for sample in samples if sample.kind == TelemetryKind.CALIBRATION_RANGE)
    assert ranges.ranges["shoulder_pan"]["pos"] == 2000


def test_prompts_declare_the_expected_operator_key() -> None:
    samples = collect([MIDDLE_PROMPT, MOTOR_PROMPT, EXISTING_PROMPT])
    prompts = [sample for sample in samples if sample.kind == TelemetryKind.PROMPT]
    assert [sample.expects for sample in prompts] == [
        JobInputKey.ENTER,
        JobInputKey.ENTER,
        JobInputKey.RECALIBRATE,
    ]


def test_recording_phases_are_tracked() -> None:
    samples = collect(
        [
            "INFO 2026-07-29 22:00:00 lerobot_record.py:471 Recording episode 0",
            "INFO 2026-07-29 22:00:19 lerobot_record.py:492 Reset the environment",
            "INFO 2026-07-29 22:00:29 lerobot_record.py:471 Recording episode 1",
            "INFO 2026-07-29 22:00:48 lerobot_record.py:517 Stop recording",
        ]
    )
    episodes = [sample for sample in samples if sample.kind == TelemetryKind.EPISODE]
    assert [sample.phase for sample in episodes] == [
        "recording",
        "reset",
        "recording",
        "stopping",
    ]
    assert episodes[2].episode == 1


def test_episode_encoding_and_durable_save_are_tracked() -> None:
    samples = collect(
        [
            "Hashtag recorder: Encoding episode 7",
            "Hashtag recorder: Saved episode 7",
        ]
    )

    assert [(sample.phase, sample.episode) for sample in samples] == [
        ("encoding", 7),
        ("saved", 7),
    ]


def test_camera_incident_and_automatic_take_rejection_are_visible() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer()
    for line in (
        "Recording episode 34",
        "Hashtag camera incident: generation=2; role=wrist; reason=no fresh frame",
        "Hashtag recorder: Camera incident invalidated episode 34; "
        "take will be discarded and re-recorded",
    ):
        for sample in parser.feed(line):
            buffer.append(sample)

    events = buffer.summary()["events"]
    assert [event["phase"] for event in events][-2:] == [
        "camera:incident_during_take",
        "camera:take_invalidated",
    ]
    assert events[-2]["message"].startswith("wrist camera stream stopped")
    assert events[-1]["episode"] == 34


def test_a_camera_restart_during_reset_does_not_claim_the_take_was_invalid() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer()
    for line in (
        "Recording episode 34",
        "Reset the environment",
        "Hashtag camera incident: generation=3; role=wrist; reason=no fresh frame",
    ):
        for sample in parser.feed(line):
            buffer.append(sample)

    assert buffer.summary()["events"][-1]["phase"] == "camera:incident_during_reset"


def test_manual_take_and_reset_gates_are_visible() -> None:
    samples = collect(
        [
            "Hashtag recorder: Manual take gate armed; press SPACE to end this take",
            "Hashtag recorder: Manual reset gate armed; press SPACE to save and continue",
        ]
    )

    assert [sample.phase for sample in samples] == ["manual:take", "manual:reset"]


def test_reset_phase_keeps_the_episode_number_for_the_operator_ui() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer()
    for line in ("Recording episode 13", "Reset the environment"):
        for sample in parser.feed(line):
            buffer.append(sample)

    assert buffer.summary()["episode"]["episode"] == 13
    assert buffer.summary()["episode"]["phase"] == "reset"


def test_calibration_saved_path_is_reported() -> None:
    samples = collect(["Calibration saved to /tmp/hashtag/calibration/follower01.json"])
    notice = next(sample for sample in samples if sample.kind == TelemetryKind.NOTICE)
    assert notice.message == "/tmp/hashtag/calibration/follower01.json"


def test_recording_controls_are_reported_only_after_lerobot_acknowledges_them() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer()
    for line in (
        "Right arrow key pressed. Exiting loop...",
        "Left arrow key pressed. Exiting loop and rerecord the last episode...",
        "Escape key pressed. Stopping data recording...",
    ):
        for sample in parser.feed(line):
            buffer.append(sample)

    control = buffer.summary()["control"]
    assert control["phase"] == "control:stop_recording"
    assert "Stopping data recording" in control["message"]


def test_tic_tac_toe_homing_and_inference_phases_are_visible_to_the_dashboard() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer()
    for line in (
        "Demo episode 45 başlangıç pozuna 5 saniyede gidiliyor...",
        "Demo home hazır (maksimum eklem hatası 0.8°).",
        "Tahta onaylandı; model inference başlıyor.",
    ):
        for sample in parser.feed(line):
            buffer.append(sample)

    phases = [event["phase"] for event in buffer.summary()["events"]]
    assert phases == ["ttt:homing", "ttt:home_ready", "ttt:inference"]


def test_recording_event_history_survives_high_frequency_samples() -> None:
    parser = TelemetryParser()
    buffer = TelemetryBuffer(capacity=3)
    for line in (
        "Recording episode 2",
        "Right arrow key pressed. Exiting loop...",
        "Reset the environment",
    ):
        for sample in parser.feed(line):
            buffer.append(sample)
    for loop_ms in range(20):
        for sample in parser.feed(f"Teleop loop time: {loop_ms + 1}.0ms (30 Hz)"):
            buffer.append(sample)

    assert [event["phase"] for event in buffer.summary()["events"]] == [
        "recording",
        "control:end_episode",
        "reset",
    ]


def test_buffer_summary_reports_latency_percentiles_and_latest_state() -> None:
    buffer = TelemetryBuffer()
    parser = TelemetryParser()
    for line in TELEOP_BLOCK.splitlines():
        for sample in parser.feed(line):
            buffer.append(sample)
    for loop_ms in (10.0, 20.0, 30.0, 40.0):
        for sample in parser.feed(f"Teleop loop time: {loop_ms}ms (30 Hz)"):
            buffer.append(sample)

    summary = buffer.summary()
    assert summary["p50_loop_ms"] is not None
    assert summary["p95_loop_ms"] >= summary["p50_loop_ms"]
    assert summary["joints"]["gripper"] == 50.0
    assert summary["prompt"] is None
