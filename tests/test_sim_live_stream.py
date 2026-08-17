"""A quiet stream is not a finished one.

Between episodes the recorder sits inside `save_episode()` encoding video --
measured at 18.19 s for an 876-frame take on this board -- and publishes no
frames at all. The live view closed on a five second silence, so a five-episode
session showed episode one's last frame and then nothing, while the arm kept
moving and four more episodes were recorded correctly.
"""

from __future__ import annotations

import re
from pathlib import Path

from hashtag_robotics.api import (
    SIM_LIVE_IDLE_SECONDS,
    SIM_LIVE_SESSION_POLL_SECONDS,
    sim_live_should_close,
)

APP_TSX = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx"
API = Path(__file__).resolve().parents[1] / "src" / "hashtag_robotics" / "api.py"

# What the encoder actually cost, from the run that exposed this.
ENCODE_SECONDS = 18.19


def test_encoding_a_take_does_not_end_the_live_view() -> None:
    assert ENCODE_SECONDS > SIM_LIVE_IDLE_SECONDS  # the silence that broke it

    assert sim_live_should_close(ENCODE_SECONDS, session_alive=True) is False


def test_a_stream_nobody_is_feeding_is_still_reaped() -> None:
    """The timer keeps its original job once the session is over."""
    assert sim_live_should_close(ENCODE_SECONDS, session_alive=False) is True


def test_a_brief_gap_never_closes_anything() -> None:
    assert sim_live_should_close(0.1, session_alive=False) is False
    assert sim_live_should_close(0.1, session_alive=True) is False


def test_the_running_check_is_not_run_at_stream_speed() -> None:
    """The job table is read from SQLite; polling it 20 times a second is not free."""
    assert SIM_LIVE_SESSION_POLL_SECONDS >= 1.0


def test_the_stream_asks_the_shared_question() -> None:
    """A second copy of the rule inside the loop is how the two drift apart."""
    source = API.read_text()
    stream = source[source.index("def stream() -> Iterator[bytes]:") :]

    assert "sim_live_should_close(idle_for, alive)" in stream


def test_the_panel_reconnects_between_episodes() -> None:
    """`onError` never fires for a stream that ends cleanly; the picture freezes."""
    source = APP_TSX.read_text()

    assert re.search(r"liveEpisode\b", source)
    assert "setLiveAttempt((n) => n + 1);" in source


def test_a_stream_with_no_session_and_no_frame_is_refused(client) -> None:
    response = client.get("/api/simulation/live.mjpg")

    assert response.status_code == 409
    assert "No simulated session is running" in response.json()["detail"]
