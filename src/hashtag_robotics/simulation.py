from __future__ import annotations

import contextlib
import importlib.util
import math
import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hashtag_robotics.models import SimulationScenario

# What a scenario's `backend` field is allowed to say. It used to say anything
# and mean nothing: every scenario ran MuJoCo physics regardless, so the
# "safe-mock" baseline -- whose whole purpose is to need no physics engine --
# was quietly running one.
BACKEND_MUJOCO = "mujoco"
BACKEND_SAFE_MOCK = "safe-mock"
SUPPORTED_BACKENDS = (BACKEND_MUJOCO, BACKEND_SAFE_MOCK, "mock")

MJPEG_BOUNDARY = "hashtagsimframe"

# A renderer that has gone this long without a frame is not coming back; say so
# rather than leaving the viewer on a picture that has quietly stopped moving.
RENDER_STALL_SECONDS = 10.0
RENDER_JOIN_SECONDS = 5.0

# Which arm the simulation draws. The contract model is six capsules that keep
# the joint contract honest; it was never meant to look like an SO-101, and its
# own report says so. The real model is a generated, mesh-accurate SO-101 -- 16 MB
# of STL, which is why it is found on disk rather than shipped in the wheel.
MODEL_CONTRACT = "contract"
MODEL_SO101 = "so101"
MODEL_AUTO = "auto"
SUPPORTED_MODELS = (MODEL_AUTO, MODEL_SO101, MODEL_CONTRACT)

# Where `robot_descriptions` puts the SO-101 when something fetches it -- which
# is how it came to be on this machine, downloaded for the sim-lab examples.
SO101_SCENE_CANDIDATES = (
    Path.home() / ".cache/robot_descriptions/SO-ARM100/Simulation/SO101/scene.xml",
    Path("/usr/share/robot_descriptions/SO-ARM100/Simulation/SO101/scene.xml"),
)

# The generated model names its joints "1".."6" in the order LeRobot addresses
# them, so the mapping is positional. Stated rather than assumed, because a
# silently reordered gripper is the kind of bug a picture will not reveal.
SO101_JOINT_ORDER = ("1", "2", "3", "4", "5", "6")

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

SO101_CONTRACT_MJCF = """
<mujoco model="hashtag_so101_contract">
  <compiler angle="radian"/>
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <!-- The scene is rendered for a human now, not only stepped for numbers, so
       it needs enough ambient light to read shape from and cameras that keep
       the whole arm in frame. `mode="targetbody"` aims them at the elbow, which
       stays roughly at the arm's centre through the whole trajectory -- a fixed
       xyaxes drifted off the top of the picture as soon as a joint moved. -->
  <visual>
    <headlight ambient="0.45 0.45 0.45" diffuse="0.5 0.5 0.5" specular="0.1 0.1 0.1"/>
    <rgba haze="0.12 0.14 0.16 1"/>
  </visual>
  <default>
    <joint damping="1.5" armature="0.02"/>
    <geom type="capsule" size="0.018" rgba="0.42 0.58 0.22 1"/>
    <position kp="28" kv="3"/>
  </default>
  <worldbody>
    <light pos="0.6 -0.8 1.6" dir="-0.3 0.4 -1" diffuse="0.7 0.7 0.7"/>
    <light pos="-0.8 0.4 1.2" dir="0.5 -0.3 -1" diffuse="0.35 0.35 0.35"/>
    <geom name="floor" type="plane" size="1 1 0.05" rgba="0.16 0.18 0.2 1"/>
    <camera name="front" pos="0.95 -1.15 0.72" mode="targetbody" target="elbow_link"/>
    <camera name="side" pos="1.45 0.1 0.55" mode="targetbody" target="elbow_link"/>
    <body name="base" pos="0 0 0.035">
      <geom type="cylinder" size="0.07 0.035" rgba="0.15 0.2 0.14 1"/>
      <body name="shoulder_pan_link" pos="0 0 0.04">
        <joint name="shoulder_pan" axis="0 0 1" range="-1.9 1.9"/>
        <geom fromto="0 0 0 0 0 0.10"/>
        <body name="shoulder_lift_link" pos="0 0 0.10">
          <joint name="shoulder_lift" axis="0 1 0" range="-1.7 1.7"/>
          <geom fromto="0 0 0 0 0 0.16"/>
          <body name="elbow_link" pos="0 0 0.16">
            <joint name="elbow_flex" axis="0 1 0" range="-1.9 1.9"/>
            <geom fromto="0 0 0 0 0 0.15"/>
            <body name="wrist_flex_link" pos="0 0 0.15">
              <joint name="wrist_flex" axis="0 1 0" range="-1.8 1.8"/>
              <geom fromto="0 0 0 0 0 0.09"/>
              <body name="wrist_roll_link" pos="0 0 0.09">
                <joint name="wrist_roll" axis="0 0 1" range="-2.8 2.8"/>
                <geom fromto="0 0 0 0 0 0.06"/>
                <body name="gripper_link" pos="0 0 0.06">
                  <joint name="gripper" axis="0 1 0" range="0 1.2"/>
                  <geom fromto="0 0 0 0 0 0.045" size="0.012"/>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position joint="shoulder_pan" ctrlrange="-1.9 1.9"/>
    <position joint="shoulder_lift" ctrlrange="-1.7 1.7"/>
    <position joint="elbow_flex" ctrlrange="-1.9 1.9"/>
    <position joint="wrist_flex" ctrlrange="-1.8 1.8"/>
    <position joint="wrist_roll" ctrlrange="-2.8 2.8"/>
    <position joint="gripper" ctrlrange="0 1.2"/>
  </actuator>
</mujoco>
"""


def joint_targets(phase: float) -> list[float]:
    """The bounded six-joint trajectory both backends follow.

    Shared on purpose: a mock whose motion differs from the simulated one is a
    mock of nothing. The only difference between the backends is whether a
    physics engine is asked to follow it.
    """
    return [
        0.35 * math.sin(phase * math.tau),
        0.25 * math.sin(phase * math.tau + 0.4),
        -0.3 * math.sin(phase * math.tau + 0.8),
        0.2 * math.sin(phase * math.tau + 1.2),
        0.4 * math.sin(phase * math.tau + 1.6),
        0.5 + 0.2 * math.sin(phase * math.tau),
    ]


class SimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedModel:
    """Which arm is on screen, and where it came from.

    Reported with every run and every stream. A picture of an arm is persuasive
    in a way a table of numbers is not, so it has to say out loud whether it is
    the real geometry or the six-capsule stand-in -- otherwise the stand-in gets
    believed.
    """

    kind: str
    name: str
    path: Path | None = None
    fell_back_from: str | None = None

    @property
    def is_real_geometry(self) -> bool:
        return self.kind == MODEL_SO101


def so101_scene_path(override: Path | None = None) -> Path | None:
    """Find the mesh-accurate SO-101 on this machine, or None.

    Not vendored: the meshes are 16 MB and belong to the upstream description
    package, so the wheel would carry a copy that goes stale. Found at runtime
    instead, which also means an installation without it degrades to the
    contract model rather than failing.
    """
    candidates = (override, *SO101_SCENE_CANDIDATES) if override else SO101_SCENE_CANDIDATES
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def resolve_model(preference: str = MODEL_AUTO, override: Path | None = None) -> ResolvedModel:
    """Pick the model to simulate, and say plainly if it is not the one asked for."""
    wanted = (preference or MODEL_AUTO).strip().lower()
    if wanted not in SUPPORTED_MODELS:
        raise SimulationError(
            f"Unknown simulation model '{preference}'; expected one of "
            f"{', '.join(SUPPORTED_MODELS)}."
        )

    contract = ResolvedModel(kind=MODEL_CONTRACT, name="hashtag-so101-contract-v1")
    if wanted == MODEL_CONTRACT:
        return contract

    scene = so101_scene_path(override)
    if scene is not None:
        return ResolvedModel(kind=MODEL_SO101, name="so101-new-calib", path=scene)
    if wanted == MODEL_SO101:
        looked_in = ", ".join(str(path) for path in SO101_SCENE_CANDIDATES) or "nowhere"
        raise SimulationError(
            "The mesh-accurate SO-101 model was not found. Looked in "
            f"{looked_in}; fetch it with the robot_descriptions package, or ask "
            "for the 'contract' model."
        )
    return ResolvedModel(
        kind=contract.kind,
        name=contract.name,
        fell_back_from=MODEL_SO101,
    )


def load_model(resolved: ResolvedModel) -> Any:
    import mujoco

    if resolved.path is not None:
        return mujoco.MjModel.from_xml_path(str(resolved.path))
    return mujoco.MjModel.from_xml_string(SO101_CONTRACT_MJCF)


def default_camera(model: Any, resolved: ResolvedModel) -> Any:
    """A viewpoint that keeps the whole arm in frame.

    The contract model carries its own aimed cameras. The generated SO-101
    carries none at all (`ncam == 0`), so one is built here rather than letting
    MuJoCo's default free camera point wherever it likes.
    """
    import mujoco

    if not resolved.is_real_geometry:
        return "front"
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    camera.distance = 0.75
    camera.azimuth = 135
    camera.elevation = -20
    camera.lookat[:] = [0.0, -0.1, 0.18]
    return camera


class MujocoAdapter:
    def __init__(self, model_override: Path | None = None) -> None:
        self.model_override = model_override

    def available(self) -> bool:
        return importlib.util.find_spec("mujoco") is not None

    def renderable(self) -> bool:
        """Whether frames can actually be produced on this machine.

        MuJoCo being importable does not mean it can render: offscreen rendering
        needs a GL context, and a headless box may have none. Asked before
        offering the operator a live view, so the answer is 'not here' rather
        than a stream that never starts.
        """
        if not self.available():
            return False
        try:
            self._still(0.0, width=64, height=48)
        except Exception:
            return False
        return True

    def run(
        self,
        scenario: SimulationScenario,
        control_ticks: int = 180,
        control_hz: int = 30,
    ) -> dict[str, Any]:
        """Run a scenario on the backend it actually asks for.

        `scenario.backend` was read by nobody, so a scenario declaring
        `safe-mock` ran MuJoCo anyway. That is the wrong direction for a field
        whose purpose is to say "this one must not need a physics engine": the
        baseline silently depended on the thing it was there to be independent
        of, and would have started failing the day MuJoCo did.
        """
        backend = (scenario.backend or "").strip().lower()
        if backend not in SUPPORTED_BACKENDS:
            raise SimulationError(
                f"Scenario '{scenario.name}' asks for backend '{scenario.backend}', which is "
                f"not one of {', '.join(SUPPORTED_BACKENDS)}."
            )
        if backend != BACKEND_MUJOCO:
            return self._run_mock(scenario, backend, control_ticks, control_hz)
        return self._run_mujoco(scenario, control_ticks, control_hz)

    def _run_mock(
        self,
        scenario: SimulationScenario,
        backend: str,
        control_ticks: int,
        control_hz: int,
    ) -> dict[str, Any]:
        """Follow the same trajectory analytically, with no physics engine involved.

        This is what a safe-mock scenario is for: a baseline that keeps working
        when the simulation feature pack is missing, and that cannot report a
        constraint violation because it never leaves the commanded path.
        """
        previous = [0.0] * 6
        max_joint_delta = 0.0
        for tick in range(control_ticks):
            current = joint_targets(tick / max(1, control_ticks - 1))
            max_joint_delta = max(
                max_joint_delta,
                max(abs(value - previous[index]) for index, value in enumerate(current)),
            )
            previous = current
        return {
            "scenario_id": scenario.id,
            "backend": backend,
            "model": "hashtag-so101-analytic-v1",
            "control_ticks": control_ticks,
            "control_hz": control_hz,
            "physics_hz": None,
            "max_joint_delta": round(max_joint_delta, 6),
            "constraint_violations": 0,
            "camera_count": 0,
            "joint_names": JOINT_NAMES,
            "warning": (
                "Analytic mock: no physics engine ran, so this proves timing and "
                "bookkeeping only. Nothing here says the motion is achievable."
            ),
        }

    def _run_mujoco(
        self,
        scenario: SimulationScenario,
        control_ticks: int,
        control_hz: int,
    ) -> dict[str, Any]:
        if not self.available():
            raise SimulationError(
                f"Scenario '{scenario.name}' asks for MuJoCo, but the sim feature pack "
                "is not installed. Install it with: uv sync --extra sim"
            )

        import mujoco

        resolved = resolve_model(scenario.model, self.model_override)
        model = load_model(resolved)
        data = mujoco.MjData(model)
        physics_hz = round(1 / model.opt.timestep)
        substeps = max(1, round(physics_hz / control_hz))
        previous = [float(value) for value in data.qpos]
        max_joint_delta = 0.0
        constraint_violations = 0

        for tick in range(control_ticks):
            targets = joint_targets(tick / max(1, control_ticks - 1))
            for index, target in enumerate(targets):
                data.ctrl[index] = target
            for _ in range(substeps):
                mujoco.mj_step(model, data)

            current = [float(value) for value in data.qpos]
            max_joint_delta = max(
                max_joint_delta,
                max(abs(value - previous[index]) for index, value in enumerate(current)),
            )
            previous = current
            for joint_index, value in enumerate(current):
                low, high = model.jnt_range[joint_index]
                if value < low - 1e-5 or value > high + 1e-5:
                    constraint_violations += 1

        return {
            "scenario_id": scenario.id,
            "backend": "mujoco",
            "model": resolved.name,
            "model_kind": resolved.kind,
            "model_path": str(resolved.path) if resolved.path else None,
            "model_fell_back_from": resolved.fell_back_from,
            "control_ticks": control_ticks,
            "control_hz": control_hz,
            "physics_hz": physics_hz,
            "max_joint_delta": round(max_joint_delta, 6),
            "constraint_violations": constraint_violations,
            "camera_count": model.ncam,
            "joint_names": JOINT_NAMES,
            "warning": (
                "Mesh-accurate SO-101 geometry. Still not a calibrated digital twin: "
                "masses, friction and motor response come from the published model, "
                "not from this arm."
                if resolved.is_real_geometry
                else "Contract model only; it is not a validated SO-101 digital twin."
            ),
        }

    # -- watching it ----------------------------------------------------------

    def frames(
        self,
        scenario: SimulationScenario,
        width: int = 640,
        height: int = 480,
        fps: int = 20,
    ) -> Iterator[bytes]:
        """Stream the simulated arm as MJPEG, the same shape a real camera does.

        Until now the simulation could only be read as a table of numbers, which
        is a poor way to notice that an arm is swinging through the floor. The
        renderer is offscreen, so this needs no window and no desktop session --
        measured on this machine at 4.4 ms a frame at 640x480, far cheaper than
        the 20 fps it is asked for.

        Deliberately reuses the camera's multipart contract so the dashboard can
        show a simulated arm anywhere it can show a real one.

        Every OpenGL call happens on one thread that is born and dies with the
        stream, and frames leave it through a queue. That is not tidiness: a
        Starlette `StreamingResponse` advances a sync generator by handing each
        `next()` to whichever worker thread is free, and when the viewer closes
        the tab the generator is abandoned mid-yield, so its `finally` -- and the
        GL teardown inside it -- ran on some unrelated thread, or during garbage
        collection, whenever. Streaming this three times segfaulted the control
        plane. An operator must not be able to kill the process that holds the
        emergency stop by watching a simulation.
        """
        if not self.available():
            raise SimulationError("MuJoCo feature pack is not installed.")

        resolved = resolve_model(scenario.model, self.model_override)
        interval = 1 / max(1, fps)
        # Two frames of slack: enough that a momentarily slow consumer does not
        # stall the renderer, small enough that nobody watches the past.
        outbox: queue.Queue[bytes | None] = queue.Queue(maxsize=2)
        stop = threading.Event()

        def render_loop() -> None:
            import mujoco

            model = load_model(resolved)
            data = mujoco.MjData(model)
            camera = default_camera(model, resolved)
            substeps = max(1, round((1 / model.opt.timestep) / max(1, fps)))
            renderer = mujoco.Renderer(model, height=height, width=width)
            tick = 0
            try:
                while not stop.is_set():
                    # A loop rather than a fixed run: the operator watches until
                    # they have seen enough, and a scenario that ends mid-swing
                    # tells them less than one that keeps cycling.
                    for index, target in enumerate(joint_targets((tick % 180) / 179)):
                        data.ctrl[index] = target
                    for _ in range(substeps):
                        mujoco.mj_step(model, data)
                    renderer.update_scene(data, camera=camera)
                    part = _jpeg_part(renderer.render())
                    while not stop.is_set():
                        try:
                            outbox.put(part, timeout=interval)
                            break
                        except queue.Full:
                            continue
                    tick += 1
                    time.sleep(interval)
            finally:
                # Same thread that created it, always, and before the thread ends.
                renderer.close()
                with contextlib.suppress(queue.Full):
                    outbox.put_nowait(None)

        worker = threading.Thread(target=render_loop, name="hashtag-sim-render", daemon=True)
        worker.start()
        try:
            while True:
                try:
                    part = outbox.get(timeout=RENDER_STALL_SECONDS)
                except queue.Empty as error:
                    raise SimulationError(
                        "The simulation renderer stopped producing frames."
                    ) from error
                if part is None:
                    break
                yield part
        finally:
            stop.set()
            # Unblock a renderer parked on a full queue so it can reach its own
            # teardown; joining without this would wait out the timeout.
            with contextlib.suppress(queue.Empty):
                outbox.get_nowait()
            worker.join(timeout=RENDER_JOIN_SECONDS)

    def still(
        self,
        phase: float = 0.0,
        width: int = 320,
        height: int = 240,
        model: str = MODEL_AUTO,
    ) -> bytes:
        """One JPEG of the arm at a point in the trajectory."""
        if not self.available():
            raise SimulationError("MuJoCo feature pack is not installed.")
        return _encode_jpeg(self._still(phase, width=width, height=height, model=model))

    def _still(
        self,
        phase: float,
        width: int,
        height: int,
        model: str = MODEL_AUTO,
    ) -> Any:
        import mujoco

        resolved = resolve_model(model, self.model_override)
        loaded = load_model(resolved)
        data = mujoco.MjData(loaded)
        for index, target in enumerate(joint_targets(phase)):
            data.ctrl[index] = target
        for _ in range(200):
            mujoco.mj_step(loaded, data)
        renderer = mujoco.Renderer(loaded, height=height, width=width)
        try:
            renderer.update_scene(data, camera=default_camera(loaded, resolved))
            return renderer.render()
        finally:
            renderer.close()


def launch_viewer(
    model_preference: str = MODEL_AUTO,
    override: Path | None = None,
    seconds: float | None = None,
) -> ResolvedModel:
    """Open MuJoCo's window on the workspace so it can be looked at.

    Nothing drives the arm here, and that is the point. This window used to run
    a canned trajectory, so opening it showed a robot dancing by itself -- which
    is exactly what it looks like when a feature is fake. A session's window is
    opened by the session (`sim_teleop.open_session_viewer`) onto the model the
    leader is actually moving; this one is for looking at the scene before one
    starts: where the bin is, how far the cube sits, whether the arm can reach.

    Physics still runs, so the scene settles and ctrl-clicking a body pushes it.
    It simply is not commanded anywhere.

    Blocks until the window is closed, so it belongs in a process of its own; it
    needs a desktop session, which a server has no business assuming it has.
    """
    if importlib.util.find_spec("mujoco") is None:
        raise SimulationError(
            "The sim feature pack is not installed. Install it with: uv sync --extra sim"
        )
    import mujoco
    import mujoco.viewer

    resolved = resolve_model(model_preference, override)
    model = load_model(resolved)
    data = mujoco.MjData(model)
    # Hold the arm where it starts rather than letting gravity fold it into the
    # floor while somebody is trying to judge the workspace.
    data.ctrl[: model.nu] = data.qpos[: model.nu]
    started = time.monotonic()
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            if seconds is not None and time.monotonic() - started >= seconds:
                break
            step_start = time.monotonic()
            mujoco.mj_step(model, data)
            viewer.sync()
            # Real time, so a nudge falls at the speed a nudge should.
            remaining = model.opt.timestep - (time.monotonic() - step_start)
            if remaining > 0:
                time.sleep(remaining)
    return resolved


def _encode_jpeg(pixels: Any) -> bytes:
    """RGB array to JPEG bytes.

    MuJoCo renders RGB and OpenCV writes BGR, so the channels are reversed on
    the way out; skipping that is the classic blue-robot bug.
    """
    import cv2

    ok, buffer = cv2.imencode(".jpg", pixels[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise SimulationError("The rendered frame could not be encoded as JPEG.")
    return bytes(buffer.tobytes())


def _jpeg_part(pixels: Any) -> bytes:
    payload = _encode_jpeg(pixels)
    return (
        (
            f"--{MJPEG_BOUNDARY}\r\n"
            f"Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
        ).encode()
        + payload
        + b"\r\n"
    )
