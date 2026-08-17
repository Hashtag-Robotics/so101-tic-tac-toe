from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from typer.testing import CliRunner

from hashtag_robotics.api import create_app
from hashtag_robotics.cli import app as cli_app
from hashtag_robotics.config import Settings
from hashtag_robotics.security import SESSION_COOKIE, host_of


@pytest.fixture
def guarded(tmp_path: Path) -> Iterator[TestClient]:
    """A client with no token, so the guard can actually be observed."""
    settings = Settings(data_dir=tmp_path, open_browser=False, simulation_step_seconds=0.001)
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        yield client


def test_liveness_is_reachable_without_a_session(guarded: TestClient) -> None:
    assert guarded.get("/api/health").status_code == 200


def test_every_other_endpoint_needs_a_session(guarded: TestClient) -> None:
    refused = guarded.get("/api/summary")
    assert refused.status_code == 401
    assert "session token" in refused.json()["detail"]

    assert guarded.post("/api/devices/discover").status_code == 401


def test_a_session_unlocks_the_control_plane(guarded: TestClient) -> None:
    session = guarded.get("/api/session")
    assert session.status_code == 200
    token = session.json()["token"]
    assert len(token) >= 32
    assert guarded.cookies[SESSION_COOKIE] == token

    # The cookie now travels with the client, and the header works too.
    assert guarded.get("/api/summary").status_code == 200
    guarded.cookies.clear()
    assert guarded.get("/api/summary", headers={"X-Hashtag-Token": token}).status_code == 200
    assert guarded.get("/api/summary", headers={"X-Hashtag-Token": "guessed"}).status_code == 401


def test_each_run_mints_its_own_token(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, open_browser=False)
    first = create_app(settings).state.runtime.session_token
    second = create_app(settings).state.runtime.session_token

    assert first != second


def test_a_rebound_hostname_is_refused(client: TestClient) -> None:
    """A page resolving its own domain to 127.0.0.1 still sends its own Host."""
    refused = client.get("/api/summary", headers={"Host": "evil.example"})

    assert refused.status_code == 403
    assert "not an allowed local host" in refused.json()["detail"]


def test_a_cross_site_origin_is_refused(client: TestClient) -> None:
    refused = client.get("/api/summary", headers={"Origin": "https://evil.example"})

    assert refused.status_code == 403
    assert "may not call this control plane" in refused.json()["detail"]

    allowed = client.get("/api/summary", headers={"Origin": "http://127.0.0.1:8765"})
    assert allowed.status_code == 200


def test_the_configured_dev_origin_is_allowed(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        open_browser=False,
        frontend_dev_url="http://localhost:5173",
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        response = client.get("/api/summary", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200


# The test websocket client hardcodes its Host, so it is set explicitly here.
LOOPBACK = {"host": "127.0.0.1"}


def test_the_event_socket_refuses_an_unauthenticated_client(guarded: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as refusal,
        guarded.websocket_connect(
            "/api/events",
            headers=LOOPBACK,
        ),
    ):
        pass

    assert refusal.value.code == 4401


def test_the_event_socket_refuses_a_rebound_host(guarded: TestClient) -> None:
    token = guarded.get("/api/session").json()["token"]

    with (
        pytest.raises(WebSocketDisconnect) as refusal,
        guarded.websocket_connect(
            f"/api/events?token={token}",
            headers={"host": "evil.example"},
        ),
    ):
        pass

    assert refusal.value.code == 4403


def test_the_event_socket_accepts_the_token(guarded: TestClient) -> None:
    token = guarded.get("/api/session").json()["token"]

    with guarded.websocket_connect(f"/api/events?token={token}", headers=LOOPBACK) as socket:
        snapshot = socket.receive_json()

    assert snapshot["type"] == "job_snapshot"


def test_physical_control_refuses_a_non_loopback_bind(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HASHTAG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HASHTAG_ENABLE_PHYSICAL", "true")
    monkeypatch.setenv("HASHTAG_HOST", "0.0.0.0")
    monkeypatch.setenv("HASHTAG_OPEN_BROWSER", "false")
    from hashtag_robotics.config import get_settings

    get_settings.cache_clear()

    result = CliRunner().invoke(cli_app, ["serve"])

    assert result.exit_code == 2
    assert "Refusing to serve physical control" in result.output
    get_settings.cache_clear()


def test_host_parsing_handles_ports_and_ipv6() -> None:
    assert host_of("127.0.0.1:8765") == "127.0.0.1"
    assert host_of("http://localhost:5173") == "localhost"
    assert host_of("[::1]:8765") == "::1"
    assert host_of(None) == ""
