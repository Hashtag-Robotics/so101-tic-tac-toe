from __future__ import annotations

import asyncio
import os
import shutil
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import aclosing, asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from hashtag_robotics import __version__
from hashtag_robotics.agents import ROLE_DESCRIPTIONS, AgentGateway
from hashtag_robotics.calibration import CalibrationError, CalibrationStore
from hashtag_robotics.camera import MJPEG_CONTENT_TYPE, CameraError, CameraService
from hashtag_robotics.commissioning import CommissioningService
from hashtag_robotics.config import Settings, get_settings
from hashtag_robotics.dataset import (
    DatasetError,
    DatasetStore,
    compare_selection,
)
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.doctor import DoctorService, diagnostics_payload
from hashtag_robotics.hardware import (
    LeRobotCliAdapter,
    PhysicalExecutionError,
    resolve_command,
)
from hashtag_robotics.identify import IdentificationError, IdentificationService
from hashtag_robotics.jobs import JobCoordinator, apply_server_defaults
from hashtag_robotics.models import (
    PROFILE_OWNED_ELSEWHERE,
    AgentCommandRequest,
    AgentCommandResult,
    AgentPlanRequest,
    AgentPlanResult,
    AgentSession,
    AgentTurn,
    AuditEvent,
    CalibrationArtifact,
    CameraProfile,
    DashboardSummary,
    DatasetManifest,
    DeviceIdentification,
    DeviceKind,
    DeviceRecord,
    DeviceRole,
    EpisodeAnnotation,
    JobCreateRequest,
    JobInputRequest,
    JobKind,
    JobRecord,
    JobState,
    PhysicalGateRequest,
    PolicyManifest,
    RemoteEndpoint,
    ResourceRequest,
    RobotProfile,
    SafetyCheck,
    SetupStatus,
    SimulationScenario,
    TargetMode,
    TeleoperatorProfile,
    new_id,
    preserve_fields,
)
from hashtag_robotics.policy import PolicyStore
from hashtag_robotics.recording_plan import (
    RecordingPlanError,
    RecordingPlanParseRequest,
    RecordingRoadmap,
    parse_recording_roadmap,
)
from hashtag_robotics.repository import Repository, ResourceBusyError
from hashtag_robotics.safety import SafetyService
from hashtag_robotics.security import (
    SESSION_COOKIE,
    LocalAccessGuard,
    new_session_token,
)
from hashtag_robotics.seeding import seed_repository
from hashtag_robotics.simulation import MJPEG_BOUNDARY as SIM_MJPEG_BOUNDARY
from hashtag_robotics.simulation import (
    SUPPORTED_BACKENDS,
    SUPPORTED_MODELS,
    so101_scene_path,
)
from hashtag_robotics.strands_runtime import StrandsPlanner, StrandsRuntimeError
from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_POLICY_REPO,
    TIC_TAC_TOE_POLICY_REVISION,
    TIC_TAC_TOE_PROFILE,
    tic_tac_toe_catalogue,
)
from hashtag_robotics.workflows import WORKFLOW_STEPS, WorkflowEngine

# A session that has not published a frame in this long has ended; close the
# stream instead of leaving the viewer on a still that looks live.
SIM_LIVE_IDLE_SECONDS = 5.0
# How often the live stream asks whether a simulated session is still going.
# Cheap enough to be honest, rare enough not to poll the job table at 20 Hz.
SIM_LIVE_SESSION_POLL_SECONDS = 2.0
RECORDING_MJPEG_BOUNDARY = "hashtagrecordingframe"


def sim_live_should_close(idle_for: float, session_alive: bool) -> bool:
    """Whether a live view that has had no new frame for `idle_for` should end.

    Going quiet is not the same as being finished. Between episodes the recorder
    is inside `save_episode()` encoding video -- measured at 18.19 s for an
    876-frame take on this board -- and publishes nothing at all. Closing on a
    five second silence froze the panel on episode one's last frame for the rest
    of a five-episode session, while four more episodes recorded correctly.

    The timer still has a job: reaping a stream nobody is feeding. So silence
    only ends the stream once no session is running.
    """
    return idle_for > SIM_LIVE_IDLE_SECONDS and not session_alive


# How long a just-started session may take to build its scene, open the leader
# and render its first frame. Measured on this machine at about six seconds.
SIM_LIVE_STARTUP_SECONDS = 25.0


class Runtime:
    def __init__(self, settings: Settings) -> None:
        settings.ensure_directories()
        self.settings = settings
        self.repository = Repository(settings.database_path)
        self.doctor = DoctorService(settings)
        self.discovery = DiscoveryService(self.repository)
        self.calibration = CalibrationStore(settings, self.repository)
        self.cameras = CameraService(settings, self.repository, self.discovery)
        self.datasets = DatasetStore(settings, self.repository)
        self.policies = PolicyStore(settings, self.repository)
        self.hardware = LeRobotCliAdapter(settings, self.repository)
        self.safety = SafetyService(
            settings,
            self.repository,
            self.calibration,
            self.discovery,
            self.cameras,
        )
        self.workflows = WorkflowEngine(
            self.repository,
            self.discovery,
            settings,
            self.hardware,
            self.cameras,
            self.datasets,
            self.policies,
            self.calibration,
        )
        self.identification = IdentificationService()
        self.commissioning = CommissioningService(
            settings,
            self.repository,
            self.discovery,
            self.calibration,
            self.safety,
        )
        self.jobs = JobCoordinator(
            self.repository,
            self.safety,
            self.workflows,
            self.hardware,
            self.calibration,
        )
        self.agents = AgentGateway(
            self.repository,
            self.jobs,
            self.doctor,
            self.safety,
            settings,
            self.datasets,
            self.discovery,
        )
        self.strands = StrandsPlanner(settings, self.repository, self.agents)
        # A new token per run; closing the control plane ends every session.
        self.session_token = new_session_token()
        self.guard = LocalAccessGuard(settings, self.session_token)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = Runtime(settings or get_settings())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        seed_repository(runtime.repository)
        # Cables move while the control plane is down, so startup is exactly when
        # the stored picture is most likely to be wrong. Waiting for the operator
        # to press refresh is how six rows for two arms survived three sessions.
        runtime.discovery.discover()
        await runtime.jobs.start()
        yield
        await runtime.jobs.stop()

    app = FastAPI(
        title="Hashtag Robotics Control Plane",
        version=__version__,
        description="Local-first, agent-safe SO-101 control plane",
        lifespan=lifespan,
    )
    app.state.runtime = runtime

    if runtime.settings.frontend_dev_url:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[runtime.settings.frontend_dev_url],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def local_access_guard(request: Request, call_next: Any) -> Response:
        refusal = runtime.guard.check(request)
        return refusal if refusal is not None else await call_next(request)

    @app.get("/api/session")
    async def session(response: Response) -> dict[str, Any]:
        """Hand the dashboard its token; a cross-origin page cannot read this."""
        response.set_cookie(
            SESSION_COOKIE,
            runtime.session_token,
            httponly=False,
            samesite="strict",
            path="/",
        )
        return {"token": runtime.session_token, "expires": "process-lifetime"}

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "physical_enabled": runtime.settings.enable_physical,
            "mode": "software-only" if not runtime.settings.enable_physical else "hil",
        }

    @app.get("/api/summary", response_model=DashboardSummary)
    async def summary() -> DashboardSummary:
        jobs = runtime.repository.list_jobs(limit=30)
        active_states = {
            JobState.CREATED,
            JobState.VALIDATING,
            JobState.AWAITING_CONFIRMATION,
            JobState.QUEUED,
            JobState.STARTING,
            JobState.RUNNING,
            JobState.STOPPING,
        }
        report = runtime.doctor.run()
        return DashboardSummary(
            system_status=report.overall,
            physical_enabled=runtime.settings.enable_physical,
            # What is plugged in now, not every identity ever recorded.
            devices=len(runtime.discovery.snapshot()),
            robots=len(runtime.repository.list_entities("robot", RobotProfile)),
            datasets=len(runtime.repository.list_entities("dataset", DatasetManifest)),
            policies=len(runtime.repository.list_entities("policy", PolicyManifest)),
            active_jobs=len([job for job in jobs if job.state in active_states]),
            blocked_jobs=len([job for job in jobs if job.state == JobState.BLOCKED]),
            recent_jobs=jobs[:8],
        )

    @app.get("/api/system/doctor")
    async def doctor() -> dict[str, Any]:
        return runtime.doctor.run().model_dump(mode="json")

    @app.get("/api/system/capabilities")
    async def capabilities() -> dict[str, Any]:
        return runtime.doctor.capabilities().model_dump(mode="json")

    @app.get("/api/system/diagnostics")
    async def diagnostics() -> dict[str, Any]:
        return {
            **diagnostics_payload(runtime.settings),
            "jobs": [job.model_dump(mode="json") for job in runtime.repository.list_jobs(limit=20)],
            "audit": [
                event.model_dump(mode="json") for event in runtime.repository.list_audit(limit=30)
            ],
        }

    @app.get("/api/system/hil-checklist")
    async def hil_checklist() -> dict[str, Any]:
        checks = [
            {
                "id": "workspace",
                "label": "Robot workspace is clear and collision-free",
                "status": "manual",
            },
            {
                "id": "identity",
                "label": "Leader and follower identities are verified",
                "status": "pending",
            },
            {
                "id": "calibration",
                "label": "Calibration backup and revision are verified",
                "status": "pending",
            },
            {
                "id": "limits",
                "label": "Joint and relative target limits are verified",
                "status": "pending",
            },
            {
                "id": "estop",
                "label": "Emergency stop path is tested",
                "status": "pending",
            },
            {
                "id": "power",
                "label": "Power, torque and safe pose are verified",
                "status": "manual",
            },
        ]
        return {
            "physical_enabled": runtime.settings.enable_physical,
            "software_gate": (
                "ready-for-hil" if not runtime.settings.enable_physical else "hil-active"
            ),
            "checks": checks,
        }

    @app.get("/api/workflows")
    async def workflows() -> list[dict[str, Any]]:
        return [
            {
                "kind": kind.value,
                "steps": steps,
                "physical_capable": kind.value
                in {"motor_setup", "calibration", "teleoperation", "replay", "policy_rollout"},
            }
            for kind, steps in WORKFLOW_STEPS.items()
        ]

    @app.post("/api/hardware/command-preview")
    async def hardware_command_preview(request: JobCreateRequest) -> dict[str, Any]:
        """Preview the command the server would actually run, not the requested one."""
        request = apply_server_defaults(request, runtime.repository)
        preflight = runtime.safety.preflight(request)
        effective = runtime.safety.apply_resolution(request, preflight.resolved)
        try:
            preview = runtime.hardware.preview(effective)
        except PhysicalExecutionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {**preview, "preflight": preflight.model_dump(mode="json")}

    @app.post("/api/devices/discover", response_model=list[DeviceRecord])
    async def discover_devices(
        include_simulated: Annotated[bool, Query()] = True,
    ) -> list[DeviceRecord]:
        return runtime.discovery.discover(include_simulated=include_simulated)

    @app.get("/api/devices", response_model=list[DeviceRecord])
    async def devices() -> list[DeviceRecord]:
        # The stored table alone would answer with every identity these arms
        # have ever had, all of them still claiming to be plugged in.
        return runtime.discovery.inventory()

    # Calibration binding is owned by the calibration store, never by whoever
    # posts a profile; otherwise renaming an arm silently unbinds its calibration.
    def _preserve_calibration(kind: str, profile: Any) -> Any:
        model = RobotProfile if kind == "robot" else TeleoperatorProfile
        stored = runtime.repository.get_entity(kind, profile.id, model)
        return preserve_fields(profile, stored, PROFILE_OWNED_ELSEWHERE)

    def _reject_role_conflict(kind: str, profile: Any) -> None:
        """One arm, one role. The safety layer catches this at job time; the
        setup surface has to catch it while the operator can still fix it."""
        if not profile.device_fingerprint:
            return
        other_kind = "teleoperator" if kind == "robot" else "robot"
        other_model = TeleoperatorProfile if kind == "robot" else RobotProfile
        clash = next(
            (
                item
                for item in runtime.repository.list_entities(other_kind, other_model)
                if item.device_fingerprint == profile.device_fingerprint
                and item.target_mode != TargetMode.SIM
            ),
            None,
        )
        if clash is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This device is already assigned to the {other_kind} profile "
                    f"'{clash.name}'. One arm can only hold one role; release that "
                    "profile first."
                ),
            )

    @app.get("/api/robots", response_model=list[RobotProfile])
    async def robots() -> list[RobotProfile]:
        return runtime.repository.list_entities("robot", RobotProfile)

    @app.post("/api/robots", response_model=RobotProfile)
    async def save_robot(profile: RobotProfile) -> RobotProfile:
        _reject_role_conflict("robot", profile)
        effective = _preserve_calibration("robot", profile)
        runtime.repository.upsert_entity("robot", effective)
        return effective

    @app.delete("/api/robots/{robot_id}")
    async def delete_robot(robot_id: str) -> dict[str, Any]:
        removed = runtime.repository.delete_entity("robot", robot_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Robot profile not found")
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="profile.delete",
                target=robot_id,
                correlation_id="setup",
                outcome="deleted",
                details={"kind": "robot"},
            )
        )
        return {"deleted": robot_id}

    @app.get("/api/teleoperators", response_model=list[TeleoperatorProfile])
    async def teleoperators() -> list[TeleoperatorProfile]:
        return runtime.repository.list_entities("teleoperator", TeleoperatorProfile)

    @app.post("/api/teleoperators", response_model=TeleoperatorProfile)
    async def save_teleoperator(profile: TeleoperatorProfile) -> TeleoperatorProfile:
        _reject_role_conflict("teleoperator", profile)
        effective = _preserve_calibration("teleoperator", profile)
        runtime.repository.upsert_entity("teleoperator", effective)
        return effective

    @app.delete("/api/teleoperators/{teleoperator_id}")
    async def delete_teleoperator(teleoperator_id: str) -> dict[str, Any]:
        removed = runtime.repository.delete_entity("teleoperator", teleoperator_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Teleoperator profile not found")
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="profile.delete",
                target=teleoperator_id,
                correlation_id="setup",
                outcome="deleted",
                details={"kind": "teleoperator"},
            )
        )
        return {"deleted": teleoperator_id}

    @app.get("/api/setup/status", response_model=SetupStatus)
    async def setup_status() -> SetupStatus:
        return runtime.commissioning.status()

    @app.post("/api/setup/identify", response_model=DeviceIdentification)
    async def identify_device(device_id: Annotated[str, Body(embed=True)]) -> DeviceIdentification:
        """Ask an arm what it is. Pings and register reads only; nothing moves."""
        device = next(
            (
                item
                for item in runtime.discovery.snapshot(include_simulated=False)
                if item.id == device_id and item.kind == DeviceKind.SERIAL
            ),
            None,
        )
        if device is None:
            raise HTTPException(status_code=404, detail="Serial device not found")
        port = device.stable_path or device.transient_path
        if not port:
            raise HTTPException(status_code=422, detail="Device has no serial path")
        try:
            identification = runtime.identification.identify(port)
        except IdentificationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        identification.id = f"ident_{device.stable_fingerprint}"
        identification.device_fingerprint = device.stable_fingerprint
        runtime.repository.upsert_entity("identification", identification)
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="device.identify",
                target=device.id,
                correlation_id="setup",
                outcome=f"{identification.motors_found}/{identification.motors_expected}",
                details={
                    "bus_volts": identification.bus_volts,
                    "suggested_role": identification.suggested_role.value,
                },
            )
        )
        return identification

    @app.post("/api/setup/slots", response_model=SetupStatus)
    async def assign_slot(
        role: Annotated[DeviceRole, Body()],
        device_id: Annotated[str | None, Body()] = None,
        name: Annotated[str | None, Body()] = None,
        max_relative_target: Annotated[float | None, Body()] = None,
    ) -> SetupStatus:
        """Put one device in one slot, or empty the slot when device_id is null.

        There are exactly two slots, so a device cannot end up holding both roles
        and a third profile cannot be created by accident.
        """
        if role not in {DeviceRole.FOLLOWER, DeviceRole.LEADER}:
            raise HTTPException(status_code=422, detail="Slots exist for follower and leader only")

        if max_relative_target is not None and not (
            0 < max_relative_target <= runtime.settings.max_relative_target_ceiling
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "max_relative_target must be greater than 0 and no greater than "
                    f"{runtime.settings.max_relative_target_ceiling}."
                ),
            )

        kind = "robot" if role == DeviceRole.FOLLOWER else "teleoperator"
        model = RobotProfile if role == DeviceRole.FOLLOWER else TeleoperatorProfile
        existing = (
            runtime.commissioning.robot_profile()
            if role == DeviceRole.FOLLOWER
            else runtime.commissioning.teleoperator_profile()
        )

        if device_id is None:
            if existing is not None:
                runtime.repository.delete_entity(kind, existing.id)
            return runtime.commissioning.status()

        device = next(
            (
                item
                for item in runtime.discovery.snapshot(include_simulated=False)
                if item.id == device_id and item.kind == DeviceKind.SERIAL
            ),
            None,
        )
        if device is None:
            raise HTTPException(status_code=404, detail="Serial device not found")

        other = (
            runtime.commissioning.teleoperator_profile()
            if role == DeviceRole.FOLLOWER
            else runtime.commissioning.robot_profile()
        )
        if other is not None and other.device_fingerprint == device.stable_fingerprint:
            other_role = "leader" if role == DeviceRole.FOLLOWER else "follower"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"That arm already fills the {other_role} slot. "
                    "Release it there before assigning it here."
                ),
            )

        lerobot_id = runtime.commissioning.default_lerobot_id(role)
        device_type = runtime.commissioning.device_type(role)
        keep = existing is not None and existing.device_fingerprint == device.stable_fingerprint
        payload: dict[str, Any] = {
            "id": existing.id if existing is not None else new_id(kind),
            "name": name or (existing.name if existing else f"{role.value.capitalize()} 01"),
            "device_fingerprint": device.stable_fingerprint,
            "serial_number": device.serial_number,
            "port": device.stable_path or device.transient_path,
            "calibration_id": lerobot_id,
            "target_mode": TargetMode.REAL,
        }
        if role == DeviceRole.FOLLOWER:
            payload["robot_type"] = device_type
            payload["safety_profile"] = {
                "max_relative_target": max_relative_target
                if max_relative_target is not None
                else (
                    existing.safety_profile.get(
                        "max_relative_target", runtime.settings.default_max_relative_target
                    )
                    if existing
                    else runtime.settings.default_max_relative_target
                )
            }
        else:
            payload["teleoperator_type"] = device_type

        # A slot that keeps the same arm keeps its calibration; a slot that
        # changes arms must be calibrated again, so the binding is dropped.
        if keep and existing is not None:
            payload["calibration_revision"] = existing.calibration_revision
            if role == DeviceRole.FOLLOWER:
                payload["motor_layout"] = existing.motor_layout
                payload["calibration_verified"] = existing.calibration_verified

        runtime.repository.upsert_entity(kind, model(**payload))
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="setup.assign_slot",
                target=payload["id"],
                correlation_id="setup",
                outcome=role.value,
                details={"serial": device.serial_number, "kept_calibration": keep},
            )
        )
        return runtime.commissioning.status()

    @app.post("/api/setup/follower-limit", response_model=SetupStatus)
    async def update_follower_limit(
        max_relative_target: Annotated[float, Body(embed=True)],
    ) -> SetupStatus:
        """Update only the follower tracking-error cap; preserve every other binding."""
        ceiling = runtime.settings.max_relative_target_ceiling
        if not 0 < max_relative_target <= ceiling:
            raise HTTPException(
                status_code=422,
                detail=f"max_relative_target must be greater than 0 and no greater than {ceiling}.",
            )

        profile = runtime.commissioning.robot_profile()
        if profile is None:
            raise HTTPException(status_code=409, detail="Follower slot is empty")

        safety_profile = dict(profile.safety_profile)
        safety_profile["max_relative_target"] = float(max_relative_target)
        runtime.repository.upsert_entity(
            "robot", profile.model_copy(update={"safety_profile": safety_profile})
        )
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="setup.follower_limit",
                target=profile.id,
                correlation_id="setup",
                outcome=str(float(max_relative_target)),
                details={"max_relative_target": float(max_relative_target)},
            )
        )
        return runtime.commissioning.status()

    @app.post("/api/robots/{robot_id}/validate", response_model=list[SafetyCheck])
    async def validate_robot(robot_id: str) -> list[SafetyCheck]:
        profile = runtime.repository.get_entity("robot", robot_id, RobotProfile)
        if profile is None:
            raise HTTPException(status_code=404, detail="Robot profile not found")
        # This check reports whether the arm is *connected*, so it has to look at
        # what is connected. Reading the stored table instead made it pass for an
        # arm that had been unplugged since the last discovery.
        connected = runtime.discovery.snapshot(include_simulated=False)
        return runtime.calibration.validate_robot(profile, connected)

    @app.get("/api/calibrations", response_model=list[CalibrationArtifact])
    async def calibrations() -> list[CalibrationArtifact]:
        return runtime.repository.list_entities("calibration", CalibrationArtifact)

    @app.post("/api/calibrations/import", response_model=list[CalibrationArtifact])
    async def import_calibrations(
        directory: Annotated[str, Body(embed=True)],
    ) -> list[CalibrationArtifact]:
        try:
            return runtime.calibration.import_directory(Path(directory).expanduser())
        except CalibrationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/setup/calibrations/bind", response_model=SetupStatus)
    async def bind_existing_calibration(
        role: Annotated[DeviceRole, Body()],
        artifact_id: Annotated[str, Body()],
    ) -> SetupStatus:
        """Restore one known revision and bind it to the matching setup slot.

        Imported LeRobot ids do not have to be ``follower01`` / ``leader01``.
        Binding therefore belongs on the server: it changes the profile id and
        the revision together after checking that the artifact is valid and is
        for the requested role.
        """
        if role not in {DeviceRole.FOLLOWER, DeviceRole.LEADER}:
            raise HTTPException(status_code=422, detail="Calibration slots exist for arms only")

        artifact = runtime.repository.get_entity("calibration", artifact_id, CalibrationArtifact)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Calibration artifact not found")
        if artifact.role != role:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Calibration '{artifact.device_id}' belongs to {artifact.role.value}, "
                    f"not {role.value}."
                ),
            )
        if not artifact.validation_result.get("valid"):
            problems = artifact.validation_result.get("problems", [])
            detail = "; ".join(problems) or "The calibration contents are invalid."
            raise HTTPException(status_code=422, detail=detail)

        profile = (
            runtime.commissioning.robot_profile()
            if role == DeviceRole.FOLLOWER
            else runtime.commissioning.teleoperator_profile()
        )
        if profile is None:
            raise HTTPException(
                status_code=409,
                detail=f"Fill the {role.value} slot before binding a calibration.",
            )

        try:
            restored = runtime.calibration.restore(artifact.id)
        except CalibrationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        if isinstance(profile, RobotProfile):
            runtime.calibration.bind_robot(profile, restored)
        else:
            runtime.calibration.bind_teleoperator(profile, restored)
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="calibration.bind_existing",
                target=profile.id,
                correlation_id="setup",
                outcome=restored.id,
                details={
                    "role": role.value,
                    "device_type": restored.device_type,
                    "device_id": restored.device_id,
                },
            )
        )
        return runtime.commissioning.status()

    @app.post("/api/calibrations/{artifact_id}/restore", response_model=CalibrationArtifact)
    async def restore_calibration(artifact_id: str) -> CalibrationArtifact:
        try:
            return runtime.calibration.restore(artifact_id)
        except CalibrationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/cameras", response_model=list[CameraProfile])
    async def cameras() -> list[CameraProfile]:
        return runtime.repository.list_entities("camera", CameraProfile)

    @app.post("/api/cameras", response_model=CameraProfile)
    async def save_camera(profile: CameraProfile) -> CameraProfile:
        duplicate = next(
            (
                item
                for item in runtime.repository.list_entities("camera", CameraProfile)
                if item.id != profile.id
                and item.device_fingerprint == profile.device_fingerprint
                and item.id != "camera_sim_front"
            ),
            None,
        )
        if duplicate is not None:
            profile = profile.model_copy(
                update={"id": duplicate.id, "created_at": duplicate.created_at}
            )
        runtime.repository.upsert_entity("camera", profile)
        return profile

    @app.post("/api/cameras/discover", response_model=list[DeviceRecord])
    async def discover_cameras() -> list[DeviceRecord]:
        return runtime.cameras.discover()

    @app.get("/api/cameras/{camera_id}/availability")
    async def camera_availability(camera_id: str) -> dict[str, Any]:
        """Whether the live view can be opened, and if not, what is holding it.

        A V4L2 node serves one consumer at a time, so the answer is sometimes
        no. An operator who is told 'no' without being told 'because the
        recording you started owns it' will go looking for a broken camera.
        """
        profile = runtime.repository.get_entity("camera", camera_id, CameraProfile)
        if profile is None:
            raise HTTPException(status_code=404, detail="Camera profile not found")

        owner = runtime.repository.lease_owner(camera_id)
        if owner is None:
            return {"camera_id": camera_id, "available": True, "held_by": None, "reason": ""}

        job = runtime.repository.get_job(owner)
        if job is None:
            return {
                "camera_id": camera_id,
                "available": False,
                "held_by": owner,
                "held_by_kind": None,
                "reason": "Another viewer is holding the camera.",
            }
        return {
            "camera_id": camera_id,
            "available": False,
            "held_by": owner,
            "held_by_kind": job.kind.value,
            "reason": (
                f"The {job.kind.value.replace('_', ' ')} job running now owns this camera. "
                "A camera can only be read by one program at a time, so the live view "
                "resumes when the job ends."
            ),
        }

    @app.get("/api/cameras/{camera_id}/preview.mjpg")
    async def camera_preview_stream(camera_id: str, request: Request) -> StreamingResponse:
        """Stream MJPEG while holding the camera exclusively for this client."""
        profile = runtime.repository.get_entity("camera", camera_id, CameraProfile)
        if profile is None:
            raise HTTPException(status_code=404, detail="Camera profile not found")

        # One owner per connection, so a second viewer collides instead of
        # silently refreshing the first viewer's lease.
        owner = new_id("preview")
        lease_request = ResourceRequest(
            resource_id=camera_id,
            resource_type="camera",
            mode="exclusive",
        )
        try:
            runtime.repository.acquire_leases(owner, [lease_request])
        except ResourceBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        async def stream() -> AsyncIterator[bytes]:
            beat = time.monotonic()
            try:
                # An async-for consumer does not own or automatically close a
                # nested async generator when the HTTP client disconnects.
                # Explicit ownership is what reaches CameraService's FFmpeg
                # cleanup instead of leaving the UVC device open.
                async with aclosing(runtime.cameras.async_frames(profile)) as frames:
                    async for chunk in frames:
                        if await request.is_disconnected():
                            break
                        now = time.monotonic()
                        if now - beat > 5:
                            beat = now
                            runtime.repository.heartbeat_leases(owner)
                        yield chunk
            finally:
                runtime.repository.release_leases(owner)

        try:
            return StreamingResponse(
                stream(),
                media_type=MJPEG_CONTENT_TYPE,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        except CameraError as error:
            runtime.repository.release_leases(owner)
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/recordings/{job_id}/cameras/{camera_role}.mjpg")
    async def recording_camera_stream(
        job_id: str,
        camera_role: str,
        request: Request,
    ) -> StreamingResponse:
        """Relay frames already read by LeRobot; never open the camera twice."""
        job = runtime.repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Recording job not found")
        if job.kind not in {JobKind.RECORDING, JobKind.EVALUATION, JobKind.POLICY_ROLLOUT}:
            raise HTTPException(status_code=409, detail="This job has no physical camera relay")
        roles = set(job.resolved_targets.camera_profile_ids) if job.resolved_targets else set()
        if camera_role not in roles:
            raise HTTPException(status_code=404, detail="Camera role is not mapped for this job")
        try:
            frame_path = runtime.settings.recording_live_frame_path(job_id, camera_role)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        active_states = {
            JobState.QUEUED,
            JobState.STARTING,
            JobState.RUNNING,
            JobState.STOPPING,
        }

        def session_running() -> bool:
            current = runtime.repository.get_job(job_id)
            return current is not None and current.state in active_states

        waited = 0.0
        while session_running() and not frame_path.is_file() and waited < SIM_LIVE_STARTUP_SECONDS:
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="Viewer disconnected")
            await asyncio.sleep(0.2)
            waited += 0.2
        if not frame_path.is_file():
            raise HTTPException(
                status_code=409,
                detail="The recorder has not published this camera yet.",
            )

        def stream() -> Iterator[bytes]:
            last = 0.0
            idle_since = time.monotonic()
            checked_at = 0.0
            alive = True
            while True:
                try:
                    stamp = frame_path.stat().st_mtime
                except OSError:
                    return
                if stamp != last:
                    last = stamp
                    idle_since = time.monotonic()
                    payload = frame_path.read_bytes()
                    if payload:
                        yield (
                            (
                                f"--{RECORDING_MJPEG_BOUNDARY}\r\n"
                                f"Content-Type: image/jpeg\r\n"
                                f"Content-Length: {len(payload)}\r\n\r\n"
                            ).encode()
                            + payload
                            + b"\r\n"
                        )
                else:
                    now = time.monotonic()
                    idle_for = now - idle_since
                    if idle_for > SIM_LIVE_IDLE_SECONDS:
                        if now - checked_at > SIM_LIVE_SESSION_POLL_SECONDS:
                            checked_at = now
                            alive = session_running()
                        if sim_live_should_close(idle_for, alive):
                            return
                        idle_since = now
                time.sleep(0.05)

        return StreamingResponse(
            stream(),
            media_type=f"multipart/x-mixed-replace; boundary={RECORDING_MJPEG_BOUNDARY}",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/recording-plans/parse", response_model=RecordingRoadmap)
    async def parse_recording_plan(request: RecordingPlanParseRequest) -> RecordingRoadmap:
        """Validate a local roadmap upload and return its executable game queue."""
        try:
            return parse_recording_roadmap(request.source_name, request.content)
        except RecordingPlanError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/recordings/{job_id}/status")
    async def recording_status(job_id: str) -> dict[str, Any]:
        """Expose what is already durable instead of guessing from job progress."""
        job = runtime.repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Recording job not found")
        if job.kind not in {JobKind.RECORDING, JobKind.SIM_RECORDING}:
            raise HTTPException(status_code=409, detail="This job does not write a dataset")
        repo_id = str(job.parameters.get("repo_id", "")).strip()
        if not repo_id:
            raise HTTPException(status_code=409, detail="Recording job has no dataset repo id")
        started_at = job.process.started_at if job.process is not None else job.created_at
        status = runtime.datasets.recording_status(
            repo_id,
            job.parameters.get("dataset_root"),
            started_at=started_at,
        )
        status.update(
            {
                "job_id": job.id,
                "job_state": job.state.value,
                "planned_episodes": int(job.parameters.get("episodes", 0) or 0),
                "dataset_episode_start": int(job.parameters.get("dataset_episode_start", 0) or 0),
                "finalized": job.state
                not in {
                    JobState.CREATED,
                    JobState.VALIDATING,
                    JobState.AWAITING_CONFIRMATION,
                    JobState.QUEUED,
                    JobState.STARTING,
                    JobState.RUNNING,
                    JobState.STOPPING,
                },
            }
        )
        return status

    @app.get("/api/datasets", response_model=list[DatasetManifest])
    async def datasets() -> list[DatasetManifest]:
        return runtime.repository.list_entities("dataset", DatasetManifest)

    @app.post("/api/datasets", response_model=DatasetManifest)
    async def save_dataset(manifest: DatasetManifest) -> DatasetManifest:
        runtime.repository.upsert_entity("dataset", manifest)
        return manifest

    def _resolve_dataset(dataset_id: str) -> DatasetManifest:
        manifest = runtime.repository.get_entity("dataset", dataset_id, DatasetManifest)
        if manifest is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return manifest

    @app.post("/api/datasets/{dataset_id}/revalidate", response_model=DatasetManifest)
    async def revalidate_dataset(dataset_id: str) -> DatasetManifest:
        """Re-read what is on disk now, rather than what was true when it was recorded.

        A manifest is a snapshot; files get deleted, moved and half-written
        between then and training.
        """
        try:
            return runtime.datasets.revalidate(_resolve_dataset(dataset_id))
        except DatasetError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/datasets/compare")
    async def compare_dataset_selection(
        dataset_ids: Annotated[list[str], Body(embed=True)],
    ) -> dict[str, Any]:
        """Can one policy be trained on all of these at once?

        Worth an endpoint of its own because the answer was previously only
        available by opening two `info.json` files side by side and noticing.
        On this machine a real recording and a simulated one disagreed on joint
        names, units and image axis order, and nothing raised: the policy just
        learned less.
        """
        if len(dataset_ids) < 2:
            raise HTTPException(status_code=422, detail="Choose at least two datasets.")
        selected = [_resolve_dataset(dataset_id) for dataset_id in dataset_ids]
        try:
            return compare_selection(
                selected,
                runtime.datasets,
                runtime.repository.list_entities("dataset", DatasetManifest),
            )
        except DatasetError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/datasets/merge", response_model=JobRecord)
    async def merge_datasets(
        dataset_ids: Annotated[list[str], Body(embed=True)],
        new_name: Annotated[str, Body(embed=True)],
    ) -> JobRecord:
        """Join recordings into one, which is the only way to train on both.

        Returns a job rather than the result. Merging eighty episodes re-encodes
        video and takes minutes; holding an HTTP request open for that gives the
        operator no progress, no way to stop, and nothing in the log afterwards.
        """
        if len(dataset_ids) < 2:
            raise HTTPException(status_code=422, detail="Choose at least two datasets.")
        for dataset_id in dataset_ids:
            _resolve_dataset(dataset_id)
        return await runtime.jobs.submit(
            JobCreateRequest(
                kind=JobKind.DATASET_TRANSFORM,
                target_mode=TargetMode.READ_ONLY,
                parameters={
                    "operation": "merge",
                    "dataset_ids": dataset_ids,
                    "new_name": new_name,
                },
                requested_by="local-user",
            )
        )

    @app.get("/api/datasets/{dataset_id}/episodes")
    async def dataset_episodes(dataset_id: str) -> dict[str, Any]:
        """Every episode in a recording, so a bad one can be pointed at.

        The dashboard only ever showed a total. An operator who knew the third
        take was ruined had no way to say which take that was.
        """
        manifest = _resolve_dataset(dataset_id)
        if not manifest.repo_id:
            raise HTTPException(status_code=409, detail="This dataset has no repo id to read.")
        episodes = runtime.datasets.episodes(manifest.repo_id, manifest.local_path or None)
        return {
            "dataset_id": dataset_id,
            "episodes": episodes,
            "readable": bool(episodes),
            "note": (
                ""
                if episodes
                else (
                    "This recording carries no per-episode metadata, so its episodes "
                    "cannot be listed or removed individually."
                )
            ),
        }

    @app.get("/api/datasets/{dataset_id}/episodes/{episode_index}/videos/{camera}.mp4")
    async def dataset_episode_video(
        dataset_id: str,
        episode_index: int,
        camera: str,
    ) -> FileResponse:
        """Serve the MP4 containing one episode's camera segment with range support."""
        manifest = _resolve_dataset(dataset_id)
        if not manifest.repo_id:
            raise HTTPException(status_code=409, detail="This dataset has no repo id to read.")
        episodes = runtime.datasets.episodes(manifest.repo_id, manifest.local_path or None)
        episode = next((item for item in episodes if item["index"] == episode_index), None)
        if episode is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        video = next((item for item in episode.get("videos", []) if item["camera"] == camera), None)
        if video is None:
            raise HTTPException(status_code=404, detail="Episode camera video not found")

        root = runtime.datasets.root_for(manifest.repo_id, manifest.local_path or None)
        path = (
            root
            / "videos"
            / str(video["feature"])
            / f"chunk-{int(video['chunk_index']):03d}"
            / f"file-{int(video['file_index']):03d}.mp4"
        )
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Episode video file is missing")
        return FileResponse(
            path,
            media_type="video/mp4",
            filename=f"episode-{episode_index}-{camera}.mp4",
            content_disposition_type="inline",
            headers={"Cache-Control": "private, max-age=60"},
        )

    @app.post("/api/datasets/{dataset_id}/episodes/remove", response_model=JobRecord)
    async def remove_dataset_episodes(
        dataset_id: str,
        episodes: Annotated[list[int], Body(embed=True)],
        new_name: Annotated[str | None, Body(embed=True)] = None,
    ) -> JobRecord:
        """Write a copy of a recording without the episodes that were no good.

        A new dataset, never an edit in place: a ruined take is a judgement, and
        a judgement should be reversible. The original is left where it was and
        both appear in the list afterwards.

        Returns a job: any video segment mixing kept and removed episodes is
        re-encoded, which is fast for two episodes and not for eighty.
        """
        _resolve_dataset(dataset_id)
        if not episodes:
            raise HTTPException(status_code=422, detail="No episodes were selected.")
        return await runtime.jobs.submit(
            JobCreateRequest(
                kind=JobKind.DATASET_TRANSFORM,
                target_mode=TargetMode.READ_ONLY,
                parameters={
                    "operation": "remove_episodes",
                    "dataset_ids": [dataset_id],
                    "episodes": episodes,
                    "new_name": new_name,
                },
                requested_by="local-user",
            )
        )

    @app.post("/api/datasets/{dataset_id}/publish", response_model=JobRecord)
    async def publish_dataset(
        dataset_id: str,
        repo_id: Annotated[str | None, Body(embed=True)] = None,
        private: Annotated[bool, Body(embed=True)] = True,
        push_videos: Annotated[bool, Body(embed=True)] = True,
        dry_run: Annotated[bool, Body(embed=True)] = False,
    ) -> JobRecord:
        """Send a recording to the Hub, which is how it reaches a machine that can train.

        A job rather than a request: this board uploads hundreds of megabytes
        over whatever it is connected to, and the operator needs progress, a
        stop button and a line in the log afterwards.

        Publishing needs a human to confirm it even though nothing moves. An
        upload cannot be taken back, and a recording carries video of the room
        it was made in. `dry_run` reports what would be sent and sends nothing,
        so it needs no confirmation.
        """
        manifest = _resolve_dataset(dataset_id)
        return await runtime.jobs.submit(
            JobCreateRequest(
                kind=JobKind.HUB_SYNC,
                target_mode=TargetMode.READ_ONLY,
                parameters={
                    "dataset_id": dataset_id,
                    "repo_id": (repo_id or manifest.repo_id or "").strip(),
                    "private": private,
                    "push_videos": push_videos,
                    "dry_run": dry_run,
                },
                requested_by="local-user",
            )
        )

    @app.delete("/api/datasets/{dataset_id}")
    async def forget_dataset(
        dataset_id: str,
        delete_files: Annotated[bool, Query()] = False,
    ) -> dict[str, Any]:
        """Drop a dataset from the dashboard, and optionally from the disk.

        Two separate things on purpose. Forgetting a manifest is cheap and
        reversible by re-importing; deleting the recording is neither, so it
        never happens unless it is asked for by name.
        """
        manifest = _resolve_dataset(dataset_id)
        removed_path: str | None = None
        if delete_files and manifest.local_path:
            directory = Path(manifest.local_path)
            library = runtime.settings.lerobot_home.resolve()
            resolved = directory.resolve()
            # Only ever inside the dataset library: a manifest's `local_path` is
            # operator-supplied, and 'delete this directory' is the wrong thing
            # to take on trust.
            if not resolved.is_relative_to(library):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"'{resolved}' is outside the dataset library, so it will not be "
                        "deleted from here. Remove it by hand if that is what you want."
                    ),
                )
            if resolved.is_dir():
                shutil.rmtree(resolved)
                removed_path = str(resolved)
        runtime.repository.delete_entity("dataset", dataset_id)
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="dataset.forget",
                target=dataset_id,
                correlation_id=dataset_id,
                outcome="deleted" if removed_path else "forgotten",
                details={"repo_id": manifest.repo_id, "removed_path": removed_path},
            )
        )
        return {"dataset_id": dataset_id, "removed_path": removed_path}

    @app.get("/api/policies", response_model=list[PolicyManifest])
    async def policies() -> list[PolicyManifest]:
        return runtime.repository.list_entities("policy", PolicyManifest)

    @app.get("/api/policy-rollouts/tic-tac-toe")
    async def tic_tac_toe_rollout_catalogue() -> dict[str, Any]:
        """The finite set of physical moves the dashboard may request."""
        return {
            "profile": TIC_TAC_TOE_PROFILE,
            "policy_repo_id": TIC_TAC_TOE_POLICY_REPO,
            "policy_revision": TIC_TAC_TOE_POLICY_REVISION,
            "moves": tic_tac_toe_catalogue(),
        }

    @app.post("/api/policies", response_model=PolicyManifest)
    async def save_policy(manifest: PolicyManifest) -> PolicyManifest:
        runtime.repository.upsert_entity("policy", manifest)
        return manifest

    @app.get("/api/simulation/scenarios", response_model=list[SimulationScenario])
    async def scenarios() -> list[SimulationScenario]:
        return runtime.repository.list_entities("scenario", SimulationScenario)

    @app.post("/api/simulation/scenarios", response_model=SimulationScenario)
    async def save_scenario(scenario: SimulationScenario) -> SimulationScenario:
        runtime.repository.upsert_entity("scenario", scenario)
        return scenario

    @app.get("/api/simulation/backends")
    async def simulation_backends() -> dict[str, Any]:
        """What the simulation can actually do on this machine.

        MuJoCo being installed does not mean it can render: offscreen rendering
        needs a GL context. Asked before the panel offers a live view, so a
        headless box says 'not here' instead of showing a stream that never
        starts.
        """
        adapter = runtime.workflows.simulation
        scene = so101_scene_path(runtime.settings.simulation_model_path)
        return {
            "mujoco_installed": adapter.available(),
            "mujoco_renderable": adapter.renderable(),
            "supported": list(SUPPORTED_BACKENDS),
            "models": list(SUPPORTED_MODELS),
            # The mesh-accurate arm is 16 MB of upstream STL, found on disk
            # rather than shipped, so whether it is here is a per-machine fact.
            "so101_model_available": scene is not None,
            "so101_model_path": str(scene) if scene else None,
            # A window needs a desktop session; the browser stream does not.
            "viewer_available": bool(
                os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            ),
        }

    @app.post("/api/simulation/viewer")
    async def launch_simulation_viewer(
        model: Annotated[str, Body(embed=True)] = "auto",
    ) -> dict[str, Any]:
        """Open MuJoCo's own interactive window on the machine running the server.

        The browser stream is enough to watch the simulation and not enough to
        poke it: no orbiting the camera, no ctrl-clicking a body, no pause and
        step. This opens the real viewer for that.

        A separate process on purpose. A GUI loop inside the server would block
        the event loop that the emergency stop travels on, and the window opens
        on the server's screen -- which is worth saying plainly, because someone
        connected from a laptop will see nothing appear.
        """
        display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        if not display:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The control plane has no desktop session, so it cannot open a "
                    "window. The live view in this page needs none."
                ),
            )
        executable = resolve_command("hashtag-robotics")
        if executable is None:
            raise HTTPException(status_code=503, detail="The hashtag-robotics command is missing.")
        process = await asyncio.create_subprocess_exec(
            executable,
            "sim-viewer",
            f"--model={model}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="simulation.viewer_launched",
                target=model,
                outcome="launched",
                details={"pid": process.pid, "display": display},
            )
        )
        return {
            "pid": process.pid,
            "model": model,
            "note": "The window opens on the machine running the control plane.",
        }

    @app.get("/api/simulation/scenarios/{scenario_id}/still.jpg")
    async def simulation_still(scenario_id: str) -> Response:
        """One frame of the workspace at rest, for choosing a task.

        This used to be a stream, and the stream ran its own simulation driving a
        canned trajectory. That was worse than showing nothing: during a
        recording the operator watched an arm swinging by itself while their
        leader drove a different, invisible one, which looks exactly like the
        whole thing being fake. Motion now only ever comes from a real session.
        """
        scenario = runtime.repository.get_entity("scenario", scenario_id, SimulationScenario)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        adapter = runtime.workflows.simulation
        if not adapter.renderable():
            raise HTTPException(
                status_code=503,
                detail="MuJoCo cannot render on this machine, so there is no picture to show.",
            )
        return Response(
            content=adapter.still(0.0, width=640, height=480, model=scenario.model),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/simulation/live.mjpg")
    async def simulation_live() -> StreamingResponse:
        """Watch the simulation the leader arm is driving right now.

        The frames come from the recording process itself -- the same render it
        writes into the dataset -- rather than from a second simulation here.
        Anything else would be showing the operator a different arm than the one
        they are moving.
        """
        frame_path = runtime.settings.sim_live_frame_path
        running = any(
            job.kind in {JobKind.SIM_TELEOPERATION, JobKind.SIM_RECORDING}
            and job.state
            in {JobState.QUEUED, JobState.STARTING, JobState.RUNNING, JobState.STOPPING}
            for job in runtime.repository.list_jobs(limit=50)
        )
        if not frame_path.is_file() and not running:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No simulated session is running. Start a rehearsal or a recording "
                    "and the live view appears here."
                ),
            )

        # A session takes a few seconds to build its scene and open the leader
        # before it can publish anything -- measured at six. Refusing during that
        # window is worse than waiting: a browser never retries an <img> that
        # failed once, so the panel showed a broken box for the whole session
        # even though frames started flowing a moment later.
        waited = 0.0
        while running and not frame_path.is_file() and waited < SIM_LIVE_STARTUP_SECONDS:
            await asyncio.sleep(0.2)
            waited += 0.2
        if not frame_path.is_file():
            raise HTTPException(
                status_code=409,
                detail=(
                    "The simulated session has not produced a picture yet. If it just "
                    "started, try again in a moment."
                ),
            )

        def session_running() -> bool:
            return any(
                job.kind in {JobKind.SIM_TELEOPERATION, JobKind.SIM_RECORDING}
                and job.state
                in {JobState.QUEUED, JobState.STARTING, JobState.RUNNING, JobState.STOPPING}
                for job in runtime.repository.list_jobs(limit=50)
            )

        def stream() -> Iterator[bytes]:
            last = 0.0
            idle_since = time.monotonic()
            checked_at = 0.0
            alive = True
            while True:
                try:
                    stamp = frame_path.stat().st_mtime
                except OSError:
                    return  # the session ended and took its frame with it
                if stamp != last:
                    last = stamp
                    idle_since = time.monotonic()
                    payload = frame_path.read_bytes()
                    if payload:
                        yield (
                            (
                                f"--{SIM_MJPEG_BOUNDARY}\r\n"
                                f"Content-Type: image/jpeg\r\n"
                                f"Content-Length: {len(payload)}\r\n\r\n"
                            ).encode()
                            + payload
                            + b"\r\n"
                        )
                else:
                    now = time.monotonic()
                    idle_for = now - idle_since
                    if idle_for > SIM_LIVE_IDLE_SECONDS:
                        if now - checked_at > SIM_LIVE_SESSION_POLL_SECONDS:
                            checked_at = now
                            alive = session_running()
                        if sim_live_should_close(idle_for, alive):
                            return
                        idle_since = now
                time.sleep(0.05)

        return StreamingResponse(
            stream(),
            media_type=f"multipart/x-mixed-replace; boundary={SIM_MJPEG_BOUNDARY}",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/remote/endpoints", response_model=list[RemoteEndpoint])
    async def remote_endpoints() -> list[RemoteEndpoint]:
        return runtime.repository.list_entities("remote_endpoint", RemoteEndpoint)

    @app.post("/api/remote/endpoints", response_model=RemoteEndpoint)
    async def save_remote_endpoint(endpoint: RemoteEndpoint) -> RemoteEndpoint:
        runtime.repository.upsert_entity("remote_endpoint", endpoint)
        return endpoint

    @app.get("/api/agents/sessions", response_model=list[AgentSession])
    async def agent_sessions() -> list[AgentSession]:
        return runtime.repository.list_entities("agent_session", AgentSession)

    @app.get("/api/agents/catalogue")
    async def agent_catalogue(
        role: Annotated[str | None, Query()] = None,
        session_id: Annotated[str | None, Query()] = None,
    ) -> dict[str, Any]:
        """What an agent may do here, without having to read the source.

        Until this existed the only machine-readable thing was a list of bare
        action names. Which parameters the server actually reads, which of them
        are a human's judgement rather than a fact, and whether an action needs
        someone to approve it, all lived in safety.py and hardware.py.
        """
        if session_id:
            session = runtime.repository.get_entity("agent_session", session_id, AgentSession)
            if session is None:
                raise HTTPException(status_code=404, detail="Agent session was not found")
            role = session.role
        return {
            "role": role,
            "description": ROLE_DESCRIPTIONS.get(role or "", ""),
            "actions": runtime.agents.catalogue(role),
            "note": (
                "Parameters not listed here are ignored by the server. A real-mode "
                "action moves a physical arm and needs a human to approve it."
            ),
        }

    @app.get("/api/agents/runtime")
    async def agent_runtime() -> dict[str, object]:
        return runtime.strands.status()

    @app.post("/api/agents/commands", response_model=AgentCommandResult)
    async def agent_command(command: AgentCommandRequest) -> AgentCommandResult:
        return await runtime.agents.execute(command)

    @app.post("/api/agents/plan", response_model=AgentPlanResult)
    async def agent_plan(request: AgentPlanRequest) -> AgentPlanResult:
        try:
            return await runtime.strands.plan(request)
        except StrandsRuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/agents/sessions/{session_id}/turns", response_model=list[AgentTurn])
    async def agent_turns(session_id: str) -> list[AgentTurn]:
        """The conversation so far, oldest first.

        Kept here rather than in the page because what makes a follow-up work is
        the *result* of the earlier steps, and a browser reload should not be
        the thing that makes the model forget what it found.
        """
        if runtime.repository.get_entity("agent_session", session_id, AgentSession) is None:
            raise HTTPException(status_code=404, detail="Agent session was not found")
        return runtime.strands.turns(session_id)

    @app.delete("/api/agents/sessions/{session_id}/turns")
    async def clear_agent_turns(session_id: str) -> dict[str, Any]:
        """Start again.

        A conversation that has gone somewhere unhelpful is easier to abandon
        than to argue out of, and there is no other way to tell the model that
        the last four exchanges no longer apply.
        """
        return {"cleared": runtime.strands.forget(session_id)}

    @app.get("/api/jobs", response_model=list[JobRecord])
    async def jobs(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[JobRecord]:
        return runtime.repository.list_jobs(limit=limit)

    @app.get("/api/jobs/{job_id}", response_model=JobRecord)
    async def job(job_id: str) -> JobRecord:
        result = runtime.repository.get_job(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return result

    @app.post("/api/jobs", response_model=JobRecord)
    async def create_job(request: JobCreateRequest) -> JobRecord:
        # The defaults are applied inside `submit`, so this door and the agent
        # gateway's door get the same request.
        return await runtime.jobs.submit(request)

    @app.post("/api/jobs/{job_id}/confirm", response_model=JobRecord)
    async def confirm_job(
        job_id: str,
        approval_id: Annotated[str, Body(embed=True)],
    ) -> JobRecord:
        try:
            return await runtime.jobs.confirm(job_id, approval_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/jobs/{job_id}/cancel", response_model=JobRecord)
    async def cancel_job(job_id: str) -> JobRecord:
        try:
            return await runtime.jobs.cancel(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error

    @app.post("/api/jobs/{job_id}/input", response_model=JobRecord)
    async def send_job_input(job_id: str, request: JobInputRequest) -> JobRecord:
        try:
            return await runtime.jobs.send_input(job_id, request.key)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/jobs/{job_id}/annotate", response_model=JobRecord)
    async def annotate_job(job_id: str, annotation: EpisodeAnnotation) -> JobRecord:
        try:
            return await runtime.jobs.annotate(job_id, annotation)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/jobs/{job_id}/telemetry")
    async def job_telemetry(job_id: str) -> dict[str, Any]:
        if runtime.repository.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return runtime.hardware.telemetry_summary(job_id)

    @app.post("/api/safety/emergency-stop", response_model=list[JobRecord])
    async def emergency_stop() -> list[JobRecord]:
        return await runtime.jobs.emergency_stop()

    @app.post("/api/safety/clear-estop")
    async def clear_emergency_stop() -> dict[str, Any]:
        was_engaged = await runtime.jobs.clear_emergency_stop()
        return {"was_engaged": was_engaged, "engaged": runtime.safety.estop_engaged()}

    def _safety_status() -> dict[str, Any]:
        return {
            "emergency_stop_engaged": runtime.safety.estop_engaged(),
            "physical_enabled": runtime.settings.enable_physical,
            "default_max_relative_target": runtime.settings.default_max_relative_target,
            "max_relative_target_ceiling": runtime.settings.max_relative_target_ceiling,
            "runtime_available": runtime.hardware.runtime_available(),
            # What the last emergency stop managed to de-energise. A latched
            # stop whose torque cut failed is the one state the operator must
            # not have to read the audit log to discover.
            "last_torque_release": runtime.safety.last_torque_release(),
        }

    @app.get("/api/safety/status")
    async def safety_status() -> dict[str, Any]:
        return _safety_status()

    @app.post("/api/safety/physical-gate")
    async def set_physical_gate(request: PhysicalGateRequest) -> dict[str, Any]:
        """Open or close real actuation for this local process only.

        Opening the gate never starts a job or moves an arm. It is deliberately
        ephemeral: restarting the control plane returns to the configured safe
        default. Closing the gate while real hardware is active first applies
        the existing emergency-stop path so a running child process cannot keep
        issuing commands after the UI says the gate is closed.
        """
        if request.enabled:
            if not request.confirmed:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Fiziksel kapıyı açmak için çalışma alanını ve E-STOP erişimini "
                        "doğruladığını onaylamalısın."
                    ),
                )
            if not runtime.settings.binds_to_loopback:
                raise HTTPException(
                    status_code=403,
                    detail="Fiziksel kontrol yalnızca loopback üzerinde açılabilir.",
                )
            if runtime.safety.estop_engaged():
                raise HTTPException(
                    status_code=409,
                    detail="E-STOP mandalı açıkken fiziksel kapı açılamaz.",
                )

        active_real_jobs = [
            job
            for job in runtime.repository.list_jobs(limit=500)
            if job.target_mode == TargetMode.REAL
            and job.state
            in {
                JobState.QUEUED,
                JobState.STARTING,
                JobState.RUNNING,
                JobState.STOPPING,
            }
        ]
        auto_estop = bool(active_real_jobs) and not request.enabled
        if auto_estop:
            await runtime.jobs.emergency_stop(actor="physical-gate")

        previous = runtime.settings.enable_physical
        runtime.settings.enable_physical = request.enabled
        runtime.repository.append_audit(
            AuditEvent(
                actor="local-user",
                action="safety.physical_gate",
                target="physical-actuation",
                correlation_id="physical-gate",
                outcome="enabled" if request.enabled else "disabled",
                details={
                    "previous": previous,
                    "current": request.enabled,
                    "scope": "process-lifetime",
                    "auto_estop": auto_estop,
                    "active_real_jobs": [job.id for job in active_real_jobs],
                },
            )
        )
        return _safety_status()

    @app.get("/api/audit", response_model=list[AuditEvent])
    async def audit(limit: Annotated[int, Query(ge=1, le=1000)] = 200) -> list[AuditEvent]:
        return runtime.repository.list_audit(limit=limit)

    @app.get("/api/fleet")
    async def fleet() -> dict[str, Any]:
        robots = runtime.repository.list_entities("robot", RobotProfile)
        return {
            "mode": "local-only",
            "cloud_connected": False,
            "robots": [robot.model_dump(mode="json") for robot in robots],
        }

    @app.get("/api/update/status")
    async def update_status() -> dict[str, Any]:
        return {
            "current_version": __version__,
            "channel": "development",
            "update_available": False,
            "network_checked": False,
        }

    @app.websocket("/api/events")
    async def events(websocket: WebSocket) -> None:
        # HTTP middleware never sees a websocket handshake, so it is checked here.
        if not runtime.guard.allowed_host(websocket.headers.get("host")):
            await websocket.close(code=4403)
            return
        if not runtime.guard.allowed_origin(websocket.headers.get("origin")):
            await websocket.close(code=4403)
            return
        if not runtime.guard.authorised(
            websocket.query_params.get("token"),
            websocket.cookies.get(SESSION_COOKIE),
        ):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        try:
            while True:
                jobs = runtime.repository.list_jobs(limit=30)
                telemetry = {
                    job.id: runtime.hardware.telemetry_summary(job.id)
                    for job in jobs
                    if job.state == JobState.RUNNING
                }
                await websocket.send_json(
                    {
                        "type": "job_snapshot",
                        "jobs": [item.model_dump(mode="json") for item in jobs],
                        "leases": [
                            item.model_dump(mode="json")
                            for item in runtime.repository.list_leases()
                        ],
                        "telemetry": telemetry,
                    }
                )
                await asyncio.sleep(0.25 if telemetry else 0.75)
        except WebSocketDisconnect:
            return

    web_root = Path(__file__).parent / "web"
    index_file = web_root / "index.html"
    if index_file.exists():
        assets_dir = web_root / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        async def frontend_index() -> FileResponse:
            # The JS/CSS filenames are content-hashed and may be cached for a
            # long time; the small HTML shell must not be. Otherwise a tab
            # reopened after a dashboard rebuild can keep booting yesterday's
            # asset names and make newly added controls appear to be missing.
            return FileResponse(index_file, headers={"Cache-Control": "no-store"})

        @app.get("/{route:path}", include_in_schema=False)
        async def frontend_fallback(route: str) -> FileResponse:
            if route.startswith("api/"):
                raise HTTPException(status_code=404)
            return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    else:

        @app.get("/", include_in_schema=False)
        async def no_frontend() -> dict[str, str]:
            return {
                "name": "Hashtag Robotics Control Plane",
                "message": "Frontend assets are not built. Use the API at /docs.",
            }

    return app
