"""A simulated session could only be cancelled, and cancelling kills the process.

A take that went wrong at second three still cost its full thirty, and the
episode in progress was lost with it. The real recorder has had end / re-record
/ stop since the beginning; the simulated one listens for the same escape
sequences, so one set of buttons drives both.
"""

from __future__ import annotations

import pytest

from hashtag_robotics.jobs import EPISODE_KEYS, JOB_INPUT_KEYS
from hashtag_robotics.models import JobCreateRequest, JobKind, TargetMode
from hashtag_robotics.process import KEY_BYTES
from hashtag_robotics.sim_teleop import (
    END_EPISODE,
    RERECORD_EPISODE,
    STOP_RECORDING,
    EpisodeKeyReader,
    decode_episode_keys,
)


def test_the_recorder_decodes_exactly_what_the_dashboard_sends() -> None:
    """Two copies of an escape sequence is how they drift apart."""
    for key, expected in (
        ("end_episode", END_EPISODE),
        ("rerecord_episode", RERECORD_EPISODE),
    ):
        raw = next(v for k, v in KEY_BYTES.items() if k.value == key)
        assert decode_episode_keys(raw) == ([expected], b"")


def test_a_lone_escape_stops_the_recording() -> None:
    raw = next(v for k, v in KEY_BYTES.items() if k.value == "stop_recording")

    assert decode_episode_keys(raw, flush=True) == ([STOP_RECORDING], b"")


def test_an_escape_is_not_read_as_stop_until_nothing_follows_it() -> None:
    """Guessing early turns "next episode" into "stop", which loses a take."""
    actions, remainder = decode_episode_keys(b"\x1b")

    assert actions == []
    assert remainder == b"\x1b"


def test_a_sequence_split_across_two_reads_still_arrives() -> None:
    first, remainder = decode_episode_keys(b"\x1b[")
    second, left = decode_episode_keys(remainder + b"C")

    assert first == []
    assert second == [END_EPISODE]
    assert left == b""


def test_several_requests_in_one_read_all_arrive() -> None:
    actions, _ = decode_episode_keys(b"\x1b[C\x1b[D\x1b[C")

    assert actions == [END_EPISODE, RERECORD_EPISODE, END_EPISODE]


def test_a_sequence_this_recorder_does_not_answer_to_is_dropped() -> None:
    actions, remainder = decode_episode_keys(b"\x1b[A\x1b[C")

    assert actions == [END_EPISODE]
    assert remainder == b""


def test_noise_between_sequences_is_ignored() -> None:
    # n/r/q are intentional one-byte controls, so noise must exclude them.
    actions, _ = decode_episode_keys(b"xyz\x1b[Cabc")

    assert actions == [END_EPISODE]


class _Stream:
    """A stream with no file descriptor, as a captured stdin has under pytest."""

    def fileno(self) -> int:
        raise OSError("no descriptor")


def test_a_stream_that_cannot_be_polled_reports_nothing_rather_than_raising() -> None:
    assert EpisodeKeyReader(_Stream()).poll() == []


def test_the_simulated_recorder_accepts_the_same_keys_as_the_real_one() -> None:
    assert JOB_INPUT_KEYS[JobKind.SIM_RECORDING] == EPISODE_KEYS
    assert JOB_INPUT_KEYS[JobKind.RECORDING] == EPISODE_KEYS


def test_the_simulated_recorder_is_given_a_terminal_to_read_them_from() -> None:
    """Without a PTY the server refuses the input before it reaches the process."""
    from hashtag_robotics.hardware import LeRobotCommandBuilder

    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_RECORDING,
            target_mode=TargetMode.SIM,
            requested_by="test",
            parameters={"repo_id": "u/x", "task": "t", "teleop_port": "/dev/ttyACM1"},
        )
    )

    assert plan.interactive is True


def test_a_rehearsal_is_not_given_one_because_it_writes_nothing() -> None:
    from hashtag_robotics.hardware import LeRobotCommandBuilder

    plan = LeRobotCommandBuilder().build(
        JobCreateRequest(
            kind=JobKind.SIM_TELEOPERATION,
            target_mode=TargetMode.SIM,
            requested_by="test",
            parameters={"repo_id": "u/x", "task": "t", "teleop_port": "/dev/ttyACM1"},
        )
    )

    assert plan.interactive is False


@pytest.mark.parametrize("key", ["end_episode", "rerecord_episode", "stop_recording"])
def test_the_panel_offers_every_key_the_server_accepts(key: str) -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx").read_text()
    block = source[source.index("  sim_recording: [") :][:400]

    assert f'key: "{key}"' in block
