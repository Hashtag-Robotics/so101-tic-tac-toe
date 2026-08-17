from __future__ import annotations

import asyncio
import importlib.util
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import requires_lerobot
from fastapi.testclient import TestClient

import hashtag_robotics.discovery as discovery_module
import hashtag_robotics.doctor as doctor_module
from hashtag_robotics.api import create_app
from hashtag_robotics.camera import (
    FORMAT_GAIN_THRESHOLD,
    WARMUP_FRAMES,
    CameraError,
    CameraService,
    _ffmpeg_avfoundation_command,
    _opencv_source,
    decode_fourcc,
    load_cv2,
)
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import (
    DiscoveryService,
    _parse_avfoundation_cameras,
    _parse_avfoundation_native_cameras,
    discover_macos_cameras,
)
from hashtag_robotics.doctor import DoctorService
from hashtag_robotics.models import CameraProfile, ResourceRequest
from hashtag_robotics.repository import Repository

if importlib.util.find_spec("lerobot") is not None:
    from lerobot.cameras.configs import ColorMode

    from hashtag_robotics.avfoundation_uid import AVFoundationUIDCamera, _DashboardFrameRelay
    from hashtag_robotics.config_avfoundation_uid import AVFoundationUIDCameraConfig

pytest.importorskip("cv2", reason="OpenCV ships with the [so101] extra.")

WIDTH, HEIGHT, FRAMES = 64, 48, 12


class RunningCaptureProcess:
    def poll(self) -> None:
        return None


class ExitedCaptureProcess:
    stderr = None

    def poll(self) -> int:
        return 9


def avfoundation_camera(tmp_path: Path) -> AVFoundationUIDCamera:
    camera = AVFoundationUIDCamera(
        AVFoundationUIDCameraConfig(
            unique_id="test-camera",
            helper_path=tmp_path / "capture-helper",
            fps=30,
            width=WIDTH,
            height=HEIGHT,
        )
    )
    camera.process = RunningCaptureProcess()  # type: ignore[assignment]
    return camera


def write_clip(path: Path) -> None:
    """A short clip stands in for a V4L2 node so no real webcam is opened."""
    cv2 = load_cv2()
    numpy = pytest.importorskip("numpy")
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        30,
        (WIDTH, HEIGHT),
    )
    try:
        for index in range(FRAMES):
            frame = numpy.full((HEIGHT, WIDTH, 3), index * 8 % 255, dtype=numpy.uint8)
            writer.write(frame)
    finally:
        writer.release()
    if not path.is_file():
        pytest.skip("OpenCV could not write a test clip on this machine.")


@pytest.fixture
def service(tmp_path: Path, monkeypatch) -> CameraService:
    root = tmp_path / "v4l-by-id"
    root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", root)
    settings = Settings(data_dir=tmp_path, open_browser=False)
    settings.ensure_directories()
    repository = Repository(settings.database_path)
    return CameraService(settings, repository, DiscoveryService(repository))


def connect(service: CameraService, tmp_path: Path, name: str) -> str:
    clip = tmp_path / "clip.avi"
    write_clip(clip)
    link = tmp_path / "v4l-by-id" / name
    link.symlink_to(clip)
    return str(link)


def profile_for(service: CameraService) -> CameraProfile:
    device = next(item for item in service.connected())
    return CameraProfile(
        name="Front",
        device_fingerprint=device.stable_fingerprint,
        semantic_name="front",
        width=WIDTH,
        height=HEIGHT,
        fps=30,
    )


def test_only_the_capture_node_is_discovered(service: CameraService, tmp_path: Path) -> None:
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    (tmp_path / "v4l-by-id" / "usb-SO101_Front_0001-video-index1").symlink_to(tmp_path / "clip.avi")

    devices = service.connected()

    assert len(devices) == 1
    assert devices[0].stable_path.endswith("index0")


def test_a_profile_resolves_to_its_stable_path(service: CameraService, tmp_path: Path) -> None:
    path = connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")

    assert service.resolve_path(profile_for(service)) == path


def test_an_unplugged_camera_cannot_be_resolved(service: CameraService, tmp_path: Path) -> None:
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    orphan = CameraProfile(
        name="Wrist",
        device_fingerprint="not-connected",
        semantic_name="wrist",
    )

    with pytest.raises(CameraError):
        service.resolve_path(orphan)


def test_the_lerobot_entry_carries_the_stable_path(service: CameraService, tmp_path: Path) -> None:
    path = connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    profile = profile_for(service)

    assert service.lerobot_config(profile, path) == {
        "type": "opencv",
        "index_or_path": path,
        "fps": 30,
        "width": WIDTH,
        "height": HEIGHT,
        "rotation": 0,
    }


def test_macos_camera_discovery_keeps_identity_separate_from_current_index() -> None:
    profile = """{
      "SPCameraDataType": [{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "UVC Camera VendorID_1443 ProductID_37424",
        "spcamera_unique-id": "test-camera-uid-a"
      }]
    }"""
    listing = """
[AVFoundation indev @ 0x1] AVFoundation video devices:
[AVFoundation indev @ 0x1] [0] MacBook Pro Camera
[AVFoundation indev @ 0x1] [1] USB2.0_CAM1
[AVFoundation indev @ 0x1] AVFoundation audio devices:
[AVFoundation indev @ 0x1] [0] MacBook Pro Microphone
"""

    devices = _parse_avfoundation_cameras(profile, listing)

    assert len(devices) == 1
    assert devices[0].name == "USB2.0_CAM1"
    assert devices[0].serial_number == "test-camera-uid-a"
    assert devices[0].identity_stable is True
    assert devices[0].transient_path == "avfoundation:1"
    assert "avfoundation" in devices[0].capabilities


def test_native_macos_discovery_does_not_swap_identical_camera_names() -> None:
    # system_profiler is deliberately in the opposite order. Joining by the
    # repeated display name would map wrist to top; the native enumeration's
    # index and uniqueID belong to the same AVCaptureDevice and cannot drift.
    profile = """{
      "SPCameraDataType": [{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "UVC Camera VendorID_1443 ProductID_37424",
        "spcamera_unique-id": "usb-top"
      }, {
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "UVC Camera VendorID_1443 ProductID_37424",
        "spcamera_unique-id": "usb-wrist"
      }]
    }"""
    native = "0\tusb-wrist\tUSB2.0_CAM1\n1\tusb-top\tUSB2.0_CAM1\n"

    devices = _parse_avfoundation_native_cameras(profile, native)

    assert [(item.serial_number, item.transient_path) for item in devices] == [
        ("usb-wrist", "avfoundation:0"),
        ("usb-top", "avfoundation:1"),
    ]


def test_uvc_identity_survives_moving_the_hub_to_another_mac_port() -> None:
    model = "UVC Camera VendorID_1443 ProductID_37424"
    old_profile = f'''{{
      "SPCameraDataType": [{{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "{model}",
        "spcamera_unique-id": "0xdeadbeef00abc123"
      }}]
    }}'''
    new_profile = f'''{{
      "SPCameraDataType": [{{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "{model}",
        "spcamera_unique-id": "0x00adbeef00abc123"
      }}]
    }}'''

    old = _parse_avfoundation_native_cameras(old_profile, "0\t0xdeadbeef00abc123\tUSB2.0_CAM1\n")[0]
    new = _parse_avfoundation_native_cameras(new_profile, "0\t0x00adbeef00abc123\tUSB2.0_CAM1\n")[0]

    assert old.stable_fingerprint == new.stable_fingerprint
    assert old.id == new.id
    assert old.serial_number != new.serial_number


def test_two_identical_uvc_cameras_in_different_hub_sockets_stay_distinct() -> None:
    profile = """{
      "SPCameraDataType": []
    }"""
    native = "0\t0x00adbeef00abc123\tUSB2.0_CAM1\n1\t0x00adbeee00abc123\tUSB2.0_CAM1\n"

    devices = _parse_avfoundation_native_cameras(profile, native)

    assert len({item.stable_fingerprint for item in devices}) == 2


def test_macos_camera_discovery_reuses_snapshot_until_forced(monkeypatch) -> None:
    profile = """{
      "SPCameraDataType": [{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "UVC Camera",
        "spcamera_unique-id": "usb-camera-1"
      }]
    }"""
    native = "0\tusb-camera-1\tUSB2.0_CAM1\n"
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        if command[0] == "system_profiler":
            return subprocess.CompletedProcess(command, 0, stdout=profile, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=native, stderr="")

    monkeypatch.setattr(discovery_module, "_macos_camera_cache", None)
    monkeypatch.setattr(discovery_module, "_macos_camera_cache_at", None)
    monkeypatch.setattr(discovery_module.subprocess, "run", fake_run)

    first = discover_macos_cameras()
    second = discover_macos_cameras()
    refreshed = discover_macos_cameras(force=True)

    assert [item.transient_path for item in first] == ["avfoundation:0"]
    assert [item.transient_path for item in second] == ["avfoundation:0"]
    assert [item.transient_path for item in refreshed] == ["avfoundation:0"]
    assert len(calls) == 4  # two subprocesses for the first scan, two for force


def test_macos_camera_snapshot_auto_refreshes_after_hotplug_interval(monkeypatch) -> None:
    profile = """{
      "SPCameraDataType": [{
        "_name": "USB2.0_CAM1",
        "spcamera_model-id": "UVC Camera",
        "spcamera_unique-id": "test-camera-uid-c"
      }]
    }"""
    native = "0\ttest-camera-uid-c\tUSB2.0_CAM1\n"
    calls: list[tuple[str, ...]] = []
    now = [0.0]

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        if command[0] == "system_profiler":
            return subprocess.CompletedProcess(command, 0, stdout=profile, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=native, stderr="")

    monkeypatch.setattr(discovery_module, "_macos_camera_cache", None)
    monkeypatch.setattr(discovery_module, "_macos_camera_cache_at", None)
    monkeypatch.setattr(discovery_module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(discovery_module.subprocess, "run", fake_run)

    discover_macos_cameras(auto_refresh=True)
    now[0] = 1.0
    discover_macos_cameras(auto_refresh=True)
    now[0] = 5.0
    discover_macos_cameras(auto_refresh=True)

    assert len(calls) == 4  # first scan plus one automatic refresh


def test_doctor_camera_check_never_refreshes_macos_capture_topology(
    tmp_path: Path,
    monkeypatch,
) -> None:
    requests: list[tuple[bool, bool]] = []

    def fake_discover(*, force: bool = False, auto_refresh: bool = False):
        requests.append((force, auto_refresh))
        return []

    monkeypatch.setattr(doctor_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor_module, "discover_macos_cameras", fake_discover)

    DoctorService(Settings(data_dir=tmp_path, open_browser=False))._camera_device_check()

    assert requests == [(False, False)]


def test_camera_refresh_does_not_enumerate_while_capture_is_leased(
    service: CameraService,
    monkeypatch,
) -> None:
    refresh_requests: list[bool] = []
    service.repository.acquire_leases(
        "preview_test",
        [ResourceRequest(resource_id="camera_test", resource_type="camera")],
    )

    def fake_cameras(*, refresh: bool = False, auto_refresh: bool = True):
        refresh_requests.append(refresh or auto_refresh)
        return []

    monkeypatch.setattr(service.discovery, "_cameras", fake_cameras)

    assert service.connected(refresh=True) == []
    assert refresh_requests == [False]


def test_macos_source_uses_integer_index_for_opencv_and_lerobot(
    service: CameraService,
) -> None:
    profile = CameraProfile(name="USB", device_fingerprint="camera-id", semantic_name="front")

    assert _opencv_source("avfoundation:1") == (
        1,
        "opencv/avfoundation",
        "CAP_AVFOUNDATION",
    )
    assert service.lerobot_config(profile, "avfoundation:1")["index_or_path"] == 1

    command = _ffmpeg_avfoundation_command(profile, 1)
    assert command[command.index("-i") + 1] == "1:none"
    assert command[command.index("-video_size") + 1] == "640x480"
    assert command[command.index("-framerate") + 1] == "30"
    assert command[command.index("-boundary_tag") + 1] == "hashtagframe"


def test_an_invalid_macos_source_is_rejected() -> None:
    with pytest.raises(CameraError, match="Invalid AVFoundation"):
        _opencv_source("avfoundation:not-an-index")


def test_closing_async_stream_closes_nested_ffmpeg_generator(
    service: CameraService,
    monkeypatch,
) -> None:
    profile = CameraProfile(name="USB", device_fingerprint="camera-id", semantic_name="wrist")
    closed = False

    async def fake_ffmpeg_stream(_profile: CameraProfile, _index: int):
        nonlocal closed
        try:
            yield b"frame"
        finally:
            closed = True

    monkeypatch.setattr(service, "resolve_path", lambda _profile: "avfoundation:0")
    monkeypatch.setattr(service, "_async_ffmpeg_avfoundation_frames", fake_ffmpeg_stream)
    monkeypatch.setattr("hashtag_robotics.camera.shutil.which", lambda _name: "/usr/bin/ffmpeg")

    async def consume_one_frame() -> None:
        stream = service.async_frames(profile)
        assert await anext(stream) == b"frame"
        await stream.aclose()

    asyncio.run(consume_one_frame())

    assert closed is True


@requires_lerobot
def test_avfoundation_stale_frame_waits_for_a_fresh_capture(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    numpy = pytest.importorskip("numpy")
    camera = avfoundation_camera(tmp_path)
    stale = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    fresh = numpy.full((HEIGHT, WIDTH, 3), 211, dtype=numpy.uint8)
    camera.latest_frame = stale
    camera.latest_timestamp = time.perf_counter() - 0.12

    def publish_fresh_frame() -> None:
        time.sleep(0.02)
        with camera.frame_lock:
            camera.latest_frame = fresh
            camera.latest_timestamp = time.perf_counter()
        camera.new_frame_event.set()

    publisher = threading.Thread(target=publish_fresh_frame)
    publisher.start()
    with caplog.at_level("WARNING"):
        result = camera.read_latest(recovery_timeout_ms=250)
    publisher.join(timeout=1)

    assert result is fresh
    assert "recovered from a stale frame" in caplog.text


@requires_lerobot
def test_avfoundation_genuine_frame_stall_restarts_only_its_capture_helper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    numpy = pytest.importorskip("numpy")
    camera = avfoundation_camera(tmp_path)
    stale = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    fresh = numpy.full((HEIGHT, WIDTH, 3), 127, dtype=numpy.uint8)
    camera.latest_frame = stale
    camera.latest_timestamp = time.perf_counter() - 0.54
    recoveries: list[tuple[float, str]] = []

    def recover(previous_timestamp: float, reason: str):
        recoveries.append((previous_timestamp, reason))
        return fresh

    monkeypatch.setattr(camera, "_restart_capture_after_stall", recover)

    result = camera.read_latest(max_age_ms=500, recovery_timeout_ms=20)

    assert result is fresh
    assert len(recoveries) == 1
    assert "no fresh frame arrived" in recoveries[0][1]


@requires_lerobot
def test_avfoundation_capture_restart_requires_a_new_frame(
    tmp_path: Path,
    monkeypatch,
) -> None:
    numpy = pytest.importorskip("numpy")
    camera = avfoundation_camera(tmp_path)
    camera.latest_frame = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    camera.latest_timestamp = time.perf_counter() - 0.54

    def disconnect() -> None:
        camera.process = None
        camera.latest_frame = None
        camera.latest_timestamp = None

    def connect() -> None:
        camera.process = RunningCaptureProcess()  # type: ignore[assignment]

    monkeypatch.setattr(camera, "disconnect", disconnect)
    monkeypatch.setattr(camera, "connect", connect)

    with pytest.raises(TimeoutError, match="restarted but produced no fresh frame"):
        camera.read_latest(max_age_ms=500, recovery_timeout_ms=20)


@requires_lerobot
def test_avfoundation_capture_restart_returns_the_reopened_helpers_frame(
    tmp_path: Path,
    monkeypatch,
) -> None:
    numpy = pytest.importorskip("numpy")
    camera = avfoundation_camera(tmp_path)
    stale = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    fresh = numpy.full((HEIGHT, WIDTH, 3), 63, dtype=numpy.uint8)
    camera.latest_frame = stale
    camera.latest_timestamp = time.perf_counter() - 0.54
    calls: list[str] = []

    def disconnect() -> None:
        calls.append("disconnect")
        camera.process = None
        camera.latest_frame = None
        camera.latest_timestamp = None

    def connect() -> None:
        calls.append("connect")
        camera.process = RunningCaptureProcess()  # type: ignore[assignment]
        camera.latest_frame = fresh
        camera.latest_timestamp = time.perf_counter()

    monkeypatch.setattr(camera, "disconnect", disconnect)
    monkeypatch.setattr(camera, "connect", connect)

    result = camera.read_latest(max_age_ms=500, recovery_timeout_ms=20)

    assert result is fresh
    assert calls == ["disconnect", "connect"]


@requires_lerobot
def test_avfoundation_exited_helper_uses_the_local_restart_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    numpy = pytest.importorskip("numpy")
    camera = avfoundation_camera(tmp_path)
    fresh = numpy.full((HEIGHT, WIDTH, 3), 31, dtype=numpy.uint8)
    camera.process = ExitedCaptureProcess()  # type: ignore[assignment]
    recoveries: list[str] = []

    def recover(_previous_timestamp: float, reason: str):
        recoveries.append(reason)
        return fresh

    monkeypatch.setattr(camera, "_restart_capture_after_stall", recover)

    assert camera.read_latest() is fresh
    assert recoveries == ["capture process exited with code 9"]


def test_probe_reports_measured_timing_not_the_request(
    service: CameraService,
    tmp_path: Path,
) -> None:
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")

    result = service.probe(profile_for(service), samples=FRAMES)

    assert result["frames_captured"] > 0
    assert result["actual"] == {"width": WIDTH, "height": HEIGHT}
    assert result["requested"]["fps"] == 30
    assert result["measured_fps"] > 0
    assert result["p50_latency_ms"] is not None


def test_frames_yield_multipart_jpeg_and_release_the_device(
    service: CameraService,
    tmp_path: Path,
) -> None:
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    profile = profile_for(service)

    chunks = list(service.frames(profile))

    assert chunks, "the clip should produce at least one frame"
    assert chunks[0].startswith(b"--hashtagframe")
    assert b"Content-Type: image/jpeg" in chunks[0]
    assert b"\xff\xd8" in chunks[0]
    # The generator ran to completion, so the capture was released and can reopen.
    assert service.probe(profile, samples=2)["frames_captured"] > 0
    assert not any(thread.name.startswith("hashtag-camera-") for thread in threading.enumerate())


def test_fourcc_is_reported_as_text() -> None:
    cv2 = load_cv2()
    assert decode_fourcc(int(cv2.VideoWriter_fourcc(*"MJPG"))) == "MJPG"
    assert decode_fourcc(0) == "unknown"


@pytest.fixture
def camera_client(tmp_path: Path, monkeypatch) -> Iterator[TestClient]:
    root = tmp_path / "v4l-by-id"
    root.mkdir()
    monkeypatch.setattr("hashtag_robotics.discovery.CAMERA_BY_ID", root)
    clip = tmp_path / "clip.avi"
    write_clip(clip)
    (root / "usb-SO101_Front_0001-video-index0").symlink_to(clip)

    settings = Settings(
        data_dir=tmp_path / "state",
        open_browser=False,
        simulation_step_seconds=0.001,
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        client.headers["X-Hashtag-Token"] = client.app.state.runtime.session_token
        yield client


def register_camera(client: TestClient) -> str:
    devices = client.post("/api/cameras/discover").json()
    assert len(devices) == 1
    profile = client.post(
        "/api/cameras",
        json={
            "name": "Front",
            "device_fingerprint": devices[0]["stable_fingerprint"],
            "semantic_name": "front",
            "width": WIDTH,
            "height": HEIGHT,
            "fps": 30,
        },
    )
    assert profile.status_code == 200
    return str(profile.json()["id"])


def test_saving_the_same_camera_twice_reuses_its_profile(camera_client: TestClient) -> None:
    devices = camera_client.post("/api/cameras/discover").json()
    fingerprint = devices[0]["stable_fingerprint"]
    payload = {
        "name": "Wrist",
        "device_fingerprint": fingerprint,
        "semantic_name": "wrist",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": 30,
    }

    first = camera_client.post("/api/cameras", json=payload).json()
    second = camera_client.post("/api/cameras", json={**payload, "name": "Wrist renamed"}).json()

    assert second["id"] == first["id"]
    assert second["name"] == "Wrist renamed"
    physical = [
        item
        for item in camera_client.get("/api/cameras").json()
        if item["device_fingerprint"] == fingerprint
    ]
    assert len(physical) == 1


def camera_leases(client: TestClient, camera_id: str) -> list[str]:
    repository = client.app.state.runtime.repository
    return [
        lease.owner_job_id for lease in repository.list_leases() if lease.resource_id == camera_id
    ]


def test_the_preview_stream_serves_jpeg_and_releases_the_camera(
    camera_client: TestClient,
) -> None:
    camera_id = register_camera(camera_client)

    with camera_client.stream("GET", f"/api/cameras/{camera_id}/preview.mjpg") as stream:
        assert stream.status_code == 200
        assert "multipart/x-mixed-replace" in stream.headers["content-type"]
        assert "no-store" in stream.headers["cache-control"]
        assert stream.headers["x-accel-buffering"] == "no"
        body = b"".join(stream.iter_bytes())

    assert body.count(b"Content-Type: image/jpeg") > 0
    assert b"\xff\xd8" in body
    # The clip ran out, so the finally block must have handed the device back.
    assert camera_leases(camera_client, camera_id) == []


def test_a_camera_held_by_another_job_refuses_a_preview(camera_client: TestClient) -> None:
    camera_id = register_camera(camera_client)
    repository = camera_client.app.state.runtime.repository
    repository.acquire_leases(
        "job_recording",
        [ResourceRequest(resource_id=camera_id, resource_type="camera", mode="exclusive")],
    )

    busy = camera_client.get(f"/api/cameras/{camera_id}/preview.mjpg")
    assert busy.status_code == 409
    assert "job_recording" in busy.json()["detail"]

    repository.release_leases("job_recording")
    assert camera_client.get(f"/api/cameras/{camera_id}/preview.mjpg").status_code == 200


def test_a_camera_preview_job_reports_measured_timing(camera_client: TestClient) -> None:
    camera_id = register_camera(camera_client)
    response = camera_client.post(
        "/api/jobs",
        json={
            "kind": "camera_preview",
            "target_mode": "sim",
            "parameters": {"camera_id": camera_id, "samples": FRAMES},
            "resources": [],
            "requested_by": "test",
        },
    )
    job_id = response.json()["id"]
    for _ in range(200):
        job = camera_client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in {"completed", "failed", "aborted", "blocked"}:
            break
        time.sleep(0.05)

    assert job["state"] == "completed"
    assert job["result"]["frames_captured"] > 0
    assert job["result"]["actual"] == {"width": WIDTH, "height": HEIGHT}
    assert job["result"]["path"].endswith("index0")

    stored = camera_client.get("/api/cameras").json()
    front = next(item for item in stored if item["id"] == camera_id)
    assert front["latency_baseline_ms"] is not None


def test_probe_discards_the_stream_warmup_before_timing(
    service: CameraService,
    tmp_path: Path,
) -> None:
    """Timing from the first frame charges stream start-up to the format.

    On a real webcam that alone made every camera look about a quarter slower
    than it is, which is enough for an operator to blame hardware that is fine.
    """
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    camera = profile_for(service)

    assert WARMUP_FRAMES > 0
    samples = FRAMES - WARMUP_FRAMES - 1
    result = service.probe(camera, samples=samples, compare_formats=False)

    # Every timed frame is a real frame; the warm-up ones never enter the stats.
    assert result["frames_captured"] == samples
    assert result["measured_fps"] > 0


def test_the_pixel_format_reaches_the_lerobot_config(
    service: CameraService,
    tmp_path: Path,
) -> None:
    """Without this the driver picks, so a dataset's format is not reproducible."""
    connect(service, tmp_path, "usb-SO101_Front_0001-video-index0")
    camera = profile_for(service)
    assert "fourcc" not in service.lerobot_config(camera, "/dev/video0")

    camera.fourcc = "MJPG"
    config = service.lerobot_config(camera, "/dev/video0")
    assert config["fourcc"] == "MJPG"


@requires_lerobot
def test_the_recording_relay_encodes_the_recorder_owned_rgb_frame(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The dashboard copy comes from LeRobot's frame, not a second capture."""
    numpy = pytest.importorskip("numpy")
    monkeypatch.setenv("HASHTAG_RECORDING_LIVE_DIR", str(tmp_path))
    relay = _DashboardFrameRelay("wrist", fps=30)
    rgb = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    rgb[:, :, 0] = 255

    relay.offer(rgb, ColorMode.RGB)

    deadline = time.monotonic() + 2
    output = tmp_path / "wrist.jpg"
    while not output.is_file() and time.monotonic() < deadline:
        time.sleep(0.01)
    relay.close()
    payload = output.read_bytes()
    decoded = load_cv2().imdecode(numpy.frombuffer(payload, dtype=numpy.uint8), 1)
    assert decoded is not None
    # OpenCV decodes BGR. A red RGB source must therefore land in channel 2.
    assert int(decoded[HEIGHT // 2, WIDTH // 2, 2]) > 240
    assert int(decoded[HEIGHT // 2, WIDTH // 2, 0]) < 10


def test_a_format_is_only_recommended_when_the_gain_is_real() -> None:
    """A few percent is measurement noise, not a reason to change the format."""
    assert FORMAT_GAIN_THRESHOLD > 1.0
    measured, alternative = 28.6, 30.0
    assert alternative <= measured * FORMAT_GAIN_THRESHOLD
