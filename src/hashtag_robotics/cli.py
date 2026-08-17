from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import typer
import uvicorn

from hashtag_robotics import __version__, sim_scene, sim_teleop
from hashtag_robotics.calibration import CalibrationError, CalibrationStore
from hashtag_robotics.config import get_settings
from hashtag_robotics.doctor import DoctorService
from hashtag_robotics.models import AuditEvent
from hashtag_robotics.repository import Repository
from hashtag_robotics.safety import ESTOP_FLAG
from hashtag_robotics.simulation import SimulationError, launch_viewer

app = typer.Typer(
    name="hashtag-robotics",
    help="Hashtag Robotics local SO-101 control plane.",
    no_args_is_help=False,
)


def _build_dashboard_from_checkout(project_root: Path | None = None) -> bool:
    """Build the React dashboard when serving directly from a source checkout.

    Wheels carry prebuilt assets and do not carry ``frontend/``. A checkout
    carries both, which creates a dangerous third state: Python can be current
    while an older ignored ``web/assets`` directory is still being served. In
    that state controls appear to vanish even though their source exists.

    Node is intentionally optional for deployed robot hosts. If it is absent,
    keep the packaged/prebuilt dashboard; if it is present in a checkout, a
    failed build must stop startup rather than silently serve stale controls.
    """
    root = project_root or Path(__file__).resolve().parents[2]
    frontend = root / "frontend"
    if not (frontend / "package.json").is_file():
        return False
    npm = shutil.which("npm")
    if npm is None:
        typer.echo(
            "Frontend source found but npm is unavailable; serving the existing dashboard build.",
            err=True,
        )
        return False
    typer.echo("Building the dashboard from the current frontend source...")
    result = subprocess.run(
        [npm, "--prefix", str(frontend), "run", "build"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        typer.echo(
            "Dashboard build failed; refusing to serve stale frontend assets. "
            "Run 'npm install --prefix frontend' and retry.",
            err=True,
        )
        raise typer.Exit(code=2)
    return True


def _serve() -> None:
    settings = get_settings()
    if settings.enable_physical and not settings.binds_to_loopback:
        typer.echo(
            f"Refusing to serve physical control on '{settings.host}'.\n"
            "A control plane that can move a robot must stay on loopback; "
            "use an SSH tunnel to reach it from another machine.",
            err=True,
        )
        raise typer.Exit(code=2)
    _build_dashboard_from_checkout()
    if settings.open_browser:
        threading.Timer(
            0.9,
            lambda: webbrowser.open(f"http://{settings.host}:{settings.port}"),
        ).start()
    uvicorn.run(
        "hashtag_robotics.api:create_app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        factory=True,
    )


@app.callback(invoke_without_command=True)
def main(context: typer.Context) -> None:
    """Start the local dashboard when no subcommand is supplied."""
    if context.invoked_subcommand is None:
        _serve()


@app.command()
def serve() -> None:
    """Start the local control plane and dashboard."""
    _serve()


@app.command()
def doctor() -> None:
    """Print a read-only compatibility and safety report."""
    settings = get_settings()
    report = DoctorService(settings).run()
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
    if report.overall.value == "blocked":
        raise typer.Exit(code=2)


@app.command()
def capabilities() -> None:
    """Print the detected runtime capability manifest."""
    settings = get_settings()
    manifest = DoctorService(settings).capabilities()
    typer.echo(json.dumps(manifest.model_dump(mode="json"), indent=2))


@app.command("import-calibration")
def import_calibration(directory: str) -> None:
    """Copy existing LeRobot calibration files into the app-managed root."""
    settings = get_settings()
    store = CalibrationStore(settings, Repository(settings.database_path))
    try:
        artifacts = store.import_directory(Path(directory))
    except CalibrationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    for artifact in artifacts:
        state = "valid" if artifact.validation_result.get("valid") else "invalid"
        typer.echo(
            f"{artifact.device_type}/{artifact.device_id} -> {artifact.id} "
            f"[{state}] sha256:{artifact.checksum[:12]}"
        )
    typer.echo(f"{len(artifacts)} calibration artifact(s) imported into {settings.calibration_dir}")


@app.command("clear-estop")
def clear_estop() -> None:
    """Release a latched emergency stop when the dashboard is unreachable."""
    settings = get_settings()
    repository = Repository(settings.database_path)
    latched_by = repository.get_flag(ESTOP_FLAG)
    repository.set_flag(ESTOP_FLAG, None)
    repository.append_audit(
        AuditEvent(
            actor="cli",
            action="safety.clear_emergency_stop",
            target="emergency-stop-latch",
            correlation_id="emergency-stop",
            outcome="cleared" if latched_by else "already-clear",
            details={"latched_by": latched_by},
        )
    )
    if latched_by:
        typer.echo(f"Emergency stop cleared; it was latched by {latched_by}.")
    else:
        typer.echo("No emergency stop was latched.")


@app.command("hil-checklist")
def hil_checklist() -> None:
    """Print the physical hardware-in-the-loop gate."""
    typer.echo(
        "\n".join(
            [
                "SO-101 HIL gate",
                "[ ] Workspace is clear and collision-free",
                "[ ] Leader and follower identities are verified",
                "[ ] Calibration backup and revision are verified",
                "[ ] Joint and relative target limits are verified",
                "[ ] Emergency stop is tested",
                "[ ] Power, torque and safe pose are verified",
                "",
                "Physical actuation remains disabled until this gate is completed.",
            ]
        )
    )


@app.command()
def version() -> None:
    """Print the application version."""
    typer.echo(__version__)


@app.command("sim-viewer")
def sim_viewer(
    model: str = typer.Option(
        "auto",
        help="Which arm to open: auto, so101 (mesh-accurate) or contract (six capsules).",
    ),
    seconds: float | None = typer.Option(
        None,
        help="Close the window after this many seconds; omit to leave it open.",
    ),
) -> None:
    """Open MuJoCo's interactive window on this machine's screen.

    The dashboard streams the same simulation into the browser, which is enough
    to watch it but not to poke it. This is the window with the mouse in it:
    orbit the camera, ctrl-click a body to push it, pause and step, switch on
    contact forces. It needs a desktop session, so it runs here rather than
    inside the server.
    """
    settings = get_settings()
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        typer.echo(
            "No desktop session found (DISPLAY and WAYLAND_DISPLAY are both unset), so "
            "there is nowhere to open a window. The dashboard's live view works without "
            "one.",
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        resolved = launch_viewer(model, settings.simulation_model_path, seconds)
    except SimulationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    if resolved.fell_back_from:
        typer.echo(
            f"The {resolved.fell_back_from} model was not on this machine, so the "
            f"{resolved.kind} model was opened instead."
        )
    typer.echo(f"Viewer closed ({resolved.name}).")

    # Leave without unwinding the interpreter.
    #
    # On this Tegra board, tearing down the window's GL context segfaults *after*
    # the viewer has closed cleanly -- reproduced with ten lines of nothing but
    # MuJoCo, so it is the driver's teardown path and not this program's. The
    # work is finished by the time we get here and there is nothing left to
    # flush but the two lines above, so the process is ended before the crash
    # has anything to crash in. Without this the command exits 139 and every
    # caller has to learn that 139 means success.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


@app.command("sim-record")
def sim_record(
    repo_id: str = typer.Option(..., help="Dataset repo id, e.g. mertkirgil/so101_sim_cube."),
    task: str = typer.Option("pick up the red cube and drop it in the bin"),
    leader_port: str = typer.Option(..., help="Serial port of the leader arm."),
    leader_id: str = typer.Option("leader01"),
    leader_calibration_dir: str | None = typer.Option(None),
    root: str | None = typer.Option(None, help="Dataset directory; LeRobot's root, not a parent."),
    episodes: int = typer.Option(1, min=1),
    episode_time_s: float = typer.Option(30.0),
    reset_time_s: float = typer.Option(3.0),
    fps: int = typer.Option(30, min=1),
    width: int = typer.Option(640),
    height: int = typer.Option(480),
    cameras: str = typer.Option(
        "front,wrist",
        help="Which simulated cameras to record, comma separated. Match the real "
        "bench: a merge needs identical features, so a simulated take with a "
        "camera the arm does not have can never be trained beside a real one.",
    ),
    keep_only_successes: bool = typer.Option(False),
    teleop_only: bool = typer.Option(False, help="Drive the simulation without recording."),
    live_frame_path: str | None = typer.Option(
        None, help="Publish the driven simulation here so the dashboard can show it."
    ),
    viewer: bool = typer.Option(
        False, help="Open MuJoCo's window onto the simulation this session is driving."
    ),
) -> None:
    """Record demonstrations in simulation, driven by the real leader arm.

    A separate process on purpose, exactly like `lerobot-record`. MuJoCo's
    renderer has already been seen to take a process down on this board, and
    this one also opens a serial port; neither belongs inside the server that
    holds the emergency stop. The dashboard runs this, reads its output and
    registers what it produced.

    Nothing physical moves. The follower is never opened and the leader is only
    read -- the same read identification performs -- so a simulated session
    cannot injure anyone or overload a servo.
    """
    settings = get_settings()
    episode_tasks: list[str] | None = None
    raw_episode_tasks = os.environ.get("HASHTAG_EPISODE_TASKS_JSON")
    if raw_episode_tasks:
        parsed_tasks = json.loads(raw_episode_tasks)
        if not isinstance(parsed_tasks, list) or len(parsed_tasks) != episodes:
            raise typer.BadParameter(
                "HASHTAG_EPISODE_TASKS_JSON must contain one task per requested episode."
            )
        episode_tasks = [str(item).strip() for item in parsed_tasks]
        if any(not item for item in episode_tasks):
            raise typer.BadParameter("Every planned episode needs a non-empty task.")
    try:
        wanted = tuple(name.strip() for name in cameras.split(",") if name.strip())
        scene = sim_scene.build(
            sim_scene.SceneSpec(cameras=wanted), scene_path=settings.simulation_model_path
        )
        arm = sim_teleop.SimArm(scene, width=width, height=height)
    except SimulationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    mapping = sim_teleop.LeaderMapping()
    live = sim_teleop.LiveFrames(live_frame_path)
    leader = None
    window = None
    try:
        leader = sim_teleop.open_leader(leader_port, leader_id, leader_calibration_dir)
        if viewer:
            window = sim_teleop.open_session_viewer(arm)
        if teleop_only:
            result = sim_teleop.run_teleop(
                leader,
                arm,
                mapping,
                None if episode_time_s <= 0 else episode_time_s,
                fps,
                live=live,
                viewer=window,
            )
        else:
            result = sim_teleop.record(
                sim_teleop.RecordingPlan(
                    repo_id=repo_id,
                    task=task,
                    tasks=episode_tasks,
                    root=root,
                    episodes=episodes,
                    episode_time_s=episode_time_s,
                    reset_time_s=reset_time_s,
                    fps=fps,
                    width=width,
                    height=height,
                    keep_only_successes=keep_only_successes,
                ),
                leader,
                arm,
                mapping,
                live=live,
                viewer=window,
            )
    except SimulationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    finally:
        if window is not None:
            with contextlib.suppress(Exception):
                window.close()
        if leader is not None:
            with contextlib.suppress(Exception):
                leader.disconnect()
        arm.close()
        live.clear()

    typer.echo(json.dumps(result))
    # The same Tegra GL teardown crash that ends `sim-viewer` with 139; the work
    # is done and the result is printed, so leave before it can happen.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
