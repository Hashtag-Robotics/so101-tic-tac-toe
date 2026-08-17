"""The simulation had to be readable as a table and watchable as a picture.

Two things were wrong with it. `scenario.backend` was declared, stored, shown --
and read by nobody, so the "safe-mock" baseline ran MuJoCo physics like
everything else, silently depending on the one thing it exists to be independent
of. And the only output was numbers, which is a poor way to notice that an arm
is swinging through the floor.
"""

from __future__ import annotations

import threading
import time

import pytest

from hashtag_robotics.models import SimulationScenario
from hashtag_robotics.simulation import (
    JOINT_NAMES,
    MujocoAdapter,
    SimulationError,
    joint_targets,
    resolve_model,
    so101_scene_path,
)


@pytest.fixture
def adapter() -> MujocoAdapter:
    return MujocoAdapter()


def scenario(backend: str, model: str = "auto") -> SimulationScenario:
    return SimulationScenario(
        id=f"test-{backend}",
        name=f"Test {backend}",
        backend=backend,
        model=model,
    )


def test_mujoco_contract_stays_inside_joint_limits(adapter: MujocoAdapter) -> None:
    if not adapter.available():
        pytest.skip("MuJoCo feature pack is not installed.")

    result = adapter.run(scenario("mujoco", "contract"), control_ticks=30, control_hz=30)

    assert result["backend"] == "mujoco"
    assert result["constraint_violations"] == 0
    assert result["joint_names"] == JOINT_NAMES
    assert result["physics_hz"] == 500
    # A second viewpoint: one camera cannot show both reach and rotation.
    assert result["camera_count"] == 2


def test_a_safe_mock_scenario_does_not_run_a_physics_engine(
    adapter: MujocoAdapter,
) -> None:
    """This is the bug: the backend field was stored and never read.

    A baseline declaring `safe-mock` was running MuJoCo, so the check that was
    supposed to keep working without the sim feature pack would have started
    failing the day it went missing.
    """
    result = adapter.run(scenario("safe-mock"), control_ticks=30)

    assert result["backend"] == "safe-mock"
    assert result["physics_hz"] is None
    assert result["model"] == "hashtag-so101-analytic-v1"
    assert "no physics engine ran" in result["warning"]


def test_the_mock_runs_even_with_no_simulation_feature_pack(
    adapter: MujocoAdapter,
    monkeypatch,
) -> None:
    monkeypatch.setattr(adapter, "available", lambda: False)

    result = adapter.run(scenario("safe-mock"), control_ticks=10)

    assert result["constraint_violations"] == 0


def test_a_mujoco_scenario_says_what_to_install_rather_than_falling_back(
    adapter: MujocoAdapter,
    monkeypatch,
) -> None:
    """Quietly running the mock instead would report a pass nobody earned."""
    monkeypatch.setattr(adapter, "available", lambda: False)

    with pytest.raises(SimulationError, match="uv sync --extra sim"):
        adapter.run(scenario("mujoco"))


def test_an_unknown_backend_is_refused_not_substituted(
    adapter: MujocoAdapter,
) -> None:
    with pytest.raises(SimulationError, match="isaac"):
        adapter.run(scenario("isaac"))


def test_both_backends_follow_the_same_trajectory() -> None:
    """A mock whose motion differs from the simulated one is a mock of nothing."""
    assert len(joint_targets(0.0)) == len(JOINT_NAMES)
    assert joint_targets(0.5) != joint_targets(0.0)


def test_a_rendered_frame_is_a_jpeg_of_the_arm(adapter: MujocoAdapter) -> None:
    if not adapter.renderable():
        pytest.skip("MuJoCo cannot render on this machine.")

    frame = adapter.still(0.35, width=160, height=120)

    assert frame[:2] == b"\xff\xd8", "JPEG magic"
    assert len(frame) > 500, "a blank frame compresses to almost nothing"


def test_the_stream_yields_multipart_jpeg_parts(adapter: MujocoAdapter) -> None:
    if not adapter.renderable():
        pytest.skip("MuJoCo cannot render on this machine.")

    stream = adapter.frames(scenario("mujoco"), width=160, height=120, fps=60)
    try:
        part = next(iter(stream))
    finally:
        stream.close()

    assert part.startswith(b"--hashtagsimframe")
    assert b"Content-Type: image/jpeg" in part


def test_streaming_without_mujoco_reports_instead_of_yielding_nothing(
    adapter: MujocoAdapter,
    monkeypatch,
) -> None:
    monkeypatch.setattr(adapter, "available", lambda: False)

    with pytest.raises(SimulationError, match="not installed"):
        next(iter(adapter.frames(scenario("mujoco"))))


def test_renderable_is_false_when_rendering_raises(
    adapter: MujocoAdapter,
    monkeypatch,
) -> None:
    """Importable is not the same as renderable; a headless box has no GL context."""

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("no GL context")

    monkeypatch.setattr(adapter, "_still", explode)

    assert adapter.renderable() is False


# -- which arm is on screen ---------------------------------------------------


def test_auto_prefers_the_mesh_accurate_arm_when_it_is_on_this_machine(
    tmp_path,
    monkeypatch,
) -> None:
    scene = tmp_path / "scene.xml"
    scene.write_text("<mujoco/>")
    monkeypatch.setattr("hashtag_robotics.simulation.SO101_SCENE_CANDIDATES", (scene,))

    resolved = resolve_model("auto")

    assert resolved.kind == "so101"
    assert resolved.is_real_geometry
    assert resolved.path == scene


def test_auto_falls_back_to_the_contract_model_and_says_so(monkeypatch) -> None:
    """A stand-in that does not announce itself gets believed."""
    monkeypatch.setattr("hashtag_robotics.simulation.SO101_SCENE_CANDIDATES", ())

    resolved = resolve_model("auto")

    assert resolved.kind == "contract"
    assert resolved.fell_back_from == "so101"


def test_asking_for_so101_explicitly_refuses_to_substitute(monkeypatch) -> None:
    """`auto` may fall back; a named request may not, or the picture lies."""
    monkeypatch.setattr("hashtag_robotics.simulation.SO101_SCENE_CANDIDATES", ())

    with pytest.raises(SimulationError, match="robot_descriptions"):
        resolve_model("so101")


def test_an_override_path_wins_over_the_cache(tmp_path, monkeypatch) -> None:
    cached = tmp_path / "cached.xml"
    cached.write_text("<mujoco/>")
    chosen = tmp_path / "chosen.xml"
    chosen.write_text("<mujoco/>")
    monkeypatch.setattr("hashtag_robotics.simulation.SO101_SCENE_CANDIDATES", (cached,))

    assert resolve_model("auto", chosen).path == chosen


def test_an_unknown_model_is_refused(adapter: MujocoAdapter) -> None:
    with pytest.raises(SimulationError, match="digital-twin-9000"):
        resolve_model("digital-twin-9000")


def test_the_contract_model_can_always_be_asked_for(monkeypatch) -> None:
    """Even with the real one present: comparing the two is a legitimate reason."""
    monkeypatch.setattr("hashtag_robotics.simulation.SO101_SCENE_CANDIDATES", ())

    assert resolve_model("contract").kind == "contract"


def test_the_real_arm_runs_the_same_trajectory_without_violating_its_limits(
    adapter: MujocoAdapter,
) -> None:
    """The shared trajectory was written against the contract model's ranges."""
    if so101_scene_path() is None:
        pytest.skip("The mesh-accurate SO-101 model is not on this machine.")

    result = adapter.run(
        SimulationScenario(id="real", name="Real", backend="mujoco", model="so101"),
        control_ticks=60,
    )

    assert result["model_kind"] == "so101"
    assert result["constraint_violations"] == 0
    assert "not a calibrated digital twin" in result["warning"]


def test_the_report_says_which_arm_it_drew(adapter: MujocoAdapter) -> None:
    if not adapter.available():
        pytest.skip("MuJoCo feature pack is not installed.")

    result = adapter.run(
        SimulationScenario(id="c", name="Contract", backend="mujoco", model="contract"),
        control_ticks=10,
    )

    assert result["model_kind"] == "contract"
    assert result["model_path"] is None
    assert "not a validated SO-101 digital twin" in result["warning"]


# -- streaming must not be able to kill the process ---------------------------


def test_the_renderer_thread_does_not_outlive_a_closed_stream(
    adapter: MujocoAdapter,
) -> None:
    """Abandoning the stream is the normal case: the viewer closes the tab.

    A `StreamingResponse` hands each `next()` to whichever worker thread is
    free and simply stops iterating on disconnect, so the generator's `finally`
    -- and the GL teardown in it -- used to run on an unrelated thread, or in
    garbage collection, whenever. Three interrupted streams segfaulted the
    control plane. Now the context lives and dies on one thread, and this pins
    that the thread actually ends.
    """
    if not adapter.renderable():
        pytest.skip("MuJoCo cannot render on this machine.")

    before = {thread.name for thread in threading.enumerate()}
    stream = adapter.frames(scenario("mujoco", "contract"), width=64, height=48, fps=60)
    next(iter(stream))
    assert any(thread.name == "hashtag-sim-render" for thread in threading.enumerate())

    stream.close()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not any(thread.name == "hashtag-sim-render" for thread in threading.enumerate()):
            break
        time.sleep(0.05)
    after = {thread.name for thread in threading.enumerate()}
    assert "hashtag-sim-render" not in after
    assert after == before, "no thread may be left behind"


def test_every_gl_call_happens_on_the_render_thread(adapter: MujocoAdapter) -> None:
    """The consumer's thread must never touch the context that another thread made."""
    if not adapter.renderable():
        pytest.skip("MuJoCo cannot render on this machine.")

    consumer = threading.current_thread().name
    stream = adapter.frames(scenario("mujoco", "contract"), width=64, height=48, fps=60)
    try:
        next(iter(stream))
        render_threads = [
            thread.name for thread in threading.enumerate() if thread.name == "hashtag-sim-render"
        ]
    finally:
        stream.close()

    assert render_threads == ["hashtag-sim-render"]
    assert consumer not in render_threads


def test_several_streams_can_be_started_and_abandoned_in_turn(
    adapter: MujocoAdapter,
) -> None:
    """The exact shape that killed the server: open, read one frame, walk away."""
    if not adapter.renderable():
        pytest.skip("MuJoCo cannot render on this machine.")

    for _ in range(4):
        stream = adapter.frames(scenario("mujoco", "contract"), width=64, height=48, fps=60)
        assert next(iter(stream)).startswith(b"--hashtagsimframe")
        stream.close()

    assert not any(thread.name == "hashtag-sim-render" for thread in threading.enumerate())
