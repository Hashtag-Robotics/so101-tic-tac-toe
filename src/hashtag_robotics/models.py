from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def _reject_blank_id(self) -> StrictModel:
        """A blank id is worse than a missing one.

        Omitting `id` mints a fresh one; sending `""` sails past the default and
        stores a row that appears in every list and answers to no URL, because
        `/api/datasets//revalidate` is not a route. Nothing can then read, edit
        or delete it. Callers that leave the field out are already served; this
        only closes the door on the value that cannot work.
        """
        identifier = getattr(self, "id", None)
        if isinstance(identifier, str) and not identifier:
            raise ValueError("id may not be blank; leave it out to have one assigned")
        return self


class DeviceKind(StrEnum):
    SERIAL = "serial"
    CAMERA = "camera"
    GPU = "gpu"
    SIMULATOR = "simulator"


class TargetMode(StrEnum):
    READ_ONLY = "read_only"
    SIM = "sim"
    REAL = "real"


class JobKind(StrEnum):
    HARDWARE_DISCOVERY = "hardware_discovery"
    MOTOR_SETUP = "motor_setup"
    CALIBRATION = "calibration"
    CAMERA_PREVIEW = "camera_preview"
    TELEOPERATION = "teleoperation"
    RECORDING = "recording"
    REPLAY = "replay"
    DATASET_VALIDATE = "dataset_validate"
    DATASET_TRANSFORM = "dataset_transform"
    TRAINING = "training"
    POLICY_IMPORT = "policy_import"
    EVALUATION = "evaluation"
    POLICY_ROLLOUT = "policy_rollout"
    SIMULATION = "simulation"
    SIM_TELEOPERATION = "sim_teleoperation"
    SIM_RECORDING = "sim_recording"
    REMOTE_INFERENCE_PROBE = "remote_inference_probe"
    HUB_SYNC = "hub_sync"
    DIAGNOSTICS = "diagnostics"


class JobState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    BLOCKED = "blocked"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    INTERRUPTED = "interrupted"


class JobInputKey(StrEnum):
    ENTER = "enter"
    USE_EXISTING_CALIBRATION = "use_existing_calibration"
    RECALIBRATE = "recalibrate"
    END_EPISODE = "end_episode"
    RERECORD_EPISODE = "rerecord_episode"
    STOP_RECORDING = "stop_recording"


class TelemetryKind(StrEnum):
    LOOP = "loop"
    JOINTS = "joints"
    CALIBRATION_RANGE = "calibration_range"
    PROMPT = "prompt"
    EPISODE = "episode"
    NOTICE = "notice"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    REJECTED = "rejected"
    CONSUMED = "consumed"


class CheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DeviceRole(StrEnum):
    FOLLOWER = "follower"
    LEADER = "leader"
    CAMERA = "camera"
    UNASSIGNED = "unassigned"


class CalibrationSource(StrEnum):
    FACTORY = "factory"
    USER = "user"
    IMPORTED = "imported"
    BACKUP = "backup"


class DeviceRecord(StrictModel):
    id: str = Field(default_factory=lambda: new_id("dev"))
    kind: DeviceKind
    name: str
    stable_fingerprint: str
    # False when the only thing separating this device from an identical one is
    # which port it is in, so the identity cannot survive a re-plug.
    identity_stable: bool = True
    transient_path: str | None = None
    stable_path: str | None = None
    vendor: str | None = None
    product: str | None = None
    serial_number: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    health: str = "unknown"
    is_simulated: bool = False
    matched_profile_id: str | None = None
    matched_role: DeviceRole = DeviceRole.UNASSIGNED
    last_seen_at: datetime = Field(default_factory=utc_now)


class MotorReading(StrictModel):
    """What one servo answered during an active identification probe."""

    motor_id: int
    name: str
    responded: bool
    model_number: int | None = None
    position: int | None = None
    volts: float | None = None
    torque_enabled: bool | None = None


class DeviceIdentification(StrictModel):
    """The result of talking to an arm instead of only reading its USB descriptor."""

    id: str = Field(default_factory=lambda: new_id("ident"))
    device_fingerprint: str | None = None
    port: str
    baudrate: int
    motors_expected: int
    motors_found: int
    bus_volts: float | None = None
    suggested_role: DeviceRole = DeviceRole.UNASSIGNED
    confidence: str = "unknown"
    reason: str = ""
    motor_ids_match: bool = False
    torque_engaged: bool = False
    readings: list[MotorReading] = Field(default_factory=list)
    identified_at: datetime = Field(default_factory=utc_now)

    @property
    def responsive(self) -> bool:
        return self.motors_found > 0


class TorqueReleaseResult(StrictModel):
    """What happened when an emergency stop tried to de-energise one arm.

    `released` is deliberately pessimistic: it is only True when a servo
    answered the read-back and answered zero. A silent bus cannot prove the arm
    went limp, and an emergency stop is the last place to report an unverified
    success.
    """

    port: str
    profile_id: str | None = None
    role: DeviceRole = DeviceRole.UNASSIGNED
    released: bool = False
    baudrate: int | None = None
    motors_confirmed_off: list[int] = Field(default_factory=list)
    motors_still_engaged: list[int] = Field(default_factory=list)
    motors_silent: list[int] = Field(default_factory=list)
    elapsed_ms: int = 0
    detail: str = ""
    released_at: datetime = Field(default_factory=utc_now)


class SetupStepState(StrEnum):
    DONE = "done"
    READY = "ready"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class SetupStep(StrictModel):
    """One step of the guided commissioning flow, with its reason spelled out."""

    id: str
    label: str
    state: SetupStepState
    summary: str
    detail: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    next_action: str | None = None


class SetupSlot(StrictModel):
    """One of the two arm slots. A device belongs to at most one slot."""

    role: DeviceRole
    label: str
    profile_id: str | None = None
    profile_name: str | None = None
    device_fingerprint: str | None = None
    device_serial: str | None = None
    port: str | None = None
    lerobot_id: str | None = None
    connected: bool = False
    calibration_revision: str | None = None
    calibration_source: str | None = None
    calibration_valid: bool | None = None
    calibration_warnings: list[str] = Field(default_factory=list)
    motor_count: int = 0
    max_relative_target: float | None = None


class SetupStatus(StrictModel):
    commissioned: bool
    physical_enabled: bool
    slots: list[SetupSlot]
    steps: list[SetupStep]
    unassigned_devices: list[DeviceRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class RobotProfile(StrictModel):
    id: str = Field(default_factory=lambda: new_id("robot"))
    name: str
    product_sku: str = "SO-101"
    robot_type: str = "so101_follower"
    serial_number: str | None = None
    hardware_revision: str | None = None
    device_fingerprint: str | None = None
    port: str | None = None
    calibration_id: str | None = None
    motor_layout: dict[str, int] = Field(default_factory=dict)
    calibration_revision: str | None = None
    camera_mapping: dict[str, str] = Field(default_factory=dict)
    safety_profile: dict[str, Any] = Field(default_factory=dict)
    supported_features: list[str] = Field(default_factory=list)
    joint_limits_verified: bool = False
    calibration_verified: bool = False
    emergency_stop_ready: bool = False
    target_mode: TargetMode = TargetMode.REAL
    compatibility_channel: str = "stable"
    created_at: datetime = Field(default_factory=utc_now)


# Fields on a profile that whoever posts it does not own.
#
# Calibration binding belongs to the calibration store; otherwise renaming an
# arm silently unbinds its calibration.
PROFILE_OWNED_ELSEWHERE = ("calibration_revision", "motor_layout", "calibration_verified")

# Fields that are a claim about a bench.
#
# A person setting `joint_limits_verified` is recording that they checked. An
# agent setting it is asserting something about a room it cannot see, which is
# the `workspace_confirmed` mistake wearing a different name. Nothing reads
# these two yet, which is exactly why the rule belongs here now: a check added
# later would inherit the hole rather than open it.
BENCH_CLAIM_FIELDS = ("joint_limits_verified", "emergency_stop_ready")


def preserve_fields[M: BaseModel](incoming: M, stored: M | None, names: Sequence[str]) -> M:
    """`incoming`, with `names` taken from the stored row or the field default."""
    update: dict[str, Any] = {}
    for name in names:
        field = type(incoming).model_fields.get(name)
        if field is None:
            continue
        update[name] = (
            getattr(stored, name)
            if stored is not None
            else field.get_default(call_default_factory=True)
        )
    return incoming.model_copy(update=update)


class TeleoperatorProfile(StrictModel):
    id: str = Field(default_factory=lambda: new_id("teleop"))
    name: str
    product_sku: str = "SO-101"
    teleoperator_type: str = "so101_leader"
    serial_number: str | None = None
    hardware_revision: str | None = None
    device_fingerprint: str | None = None
    port: str | None = None
    calibration_id: str | None = None
    calibration_revision: str | None = None
    target_robot_types: list[str] = Field(default_factory=lambda: ["so101_follower"])
    feature_mapping: dict[str, str] = Field(default_factory=dict)
    target_mode: TargetMode = TargetMode.REAL
    created_at: datetime = Field(default_factory=utc_now)


class CalibrationArtifact(StrictModel):
    id: str = Field(default_factory=lambda: new_id("calib"))
    role: DeviceRole
    device_type: str
    device_id: str
    target_profile_id: str | None = None
    source: CalibrationSource
    schema_version: str = "lerobot-motor-calibration-v1"
    checksum: str
    live_path: str
    stored_path: str
    motors: dict[str, dict[str, int]] = Field(default_factory=dict)
    validation_result: dict[str, Any] = Field(default_factory=dict)
    supersedes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CameraProfile(StrictModel):
    id: str = Field(default_factory=lambda: new_id("camera"))
    name: str
    device_fingerprint: str
    backend: str = "opencv"
    semantic_name: str
    width: int = 640
    height: int = 480
    fps: int = 30
    # A USB2 webcam negotiates raw YUYV unless asked otherwise, and raw frames
    # do not fit in the bus budget at 30 fps. Leaving this unset is what made a
    # 30 fps recording silently run at 21.
    fourcc: str | None = Field(default=None, min_length=4, max_length=4)
    supports_depth: bool = False
    orientation_degrees: int = 0
    latency_baseline_ms: float | None = None
    measured_fps: float | None = None
    format_benchmark: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class DatasetManifest(StrictModel):
    id: str = Field(default_factory=lambda: new_id("dataset"))
    name: str
    repo_id: str | None = None
    local_path: str | None = None
    task: str
    robot_profile_id: str | None = None
    teleoperator_profile_id: str | None = None
    calibration_revision: str | None = None
    features: list[str] = Field(default_factory=list)
    camera_mapping: dict[str, str] = Field(default_factory=dict)
    fps: int = 30
    episodes: int = 0
    total_frames: int = 0
    codebase_version: str | None = None
    robot_type: str | None = None
    action_shape: list[int] = Field(default_factory=list)
    integrity_status: str = "unverified"
    integrity_report: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class PolicyManifest(StrictModel):
    id: str = Field(default_factory=lambda: new_id("policy"))
    name: str
    policy_type: str
    checkpoint: str | None = None
    checkpoint_step: int | None = None
    model_repo_id: str | None = None
    model_revision: str | None = None
    source_dataset_id: str | None = None
    source_repo_id: str | None = None
    expected_features: list[str] = Field(default_factory=list)
    processor_chain: list[str] = Field(default_factory=list)
    action_shape: list[int] = Field(default_factory=lambda: [6])
    camera_mapping: dict[str, str] = Field(default_factory=dict)
    empty_cameras: int = Field(default=0, ge=0)
    runtime: str = "local"
    training_steps: int | None = None
    compatibility_status: str = "unverified"
    evaluation_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class AgentSession(StrictModel):
    id: str = Field(default_factory=lambda: new_id("agent"))
    role: str
    name: str
    model_provider: str = "deterministic"
    permissions: list[str] = Field(default_factory=list)
    status: str = "ready"
    created_at: datetime = Field(default_factory=utc_now)


class RemoteEndpoint(StrictModel):
    id: str = Field(default_factory=lambda: new_id("remote"))
    name: str
    url: str
    transport: str = "grpc"
    tls_required: bool = True
    expected_policy_id: str | None = None
    status: str = "unverified"
    created_at: datetime = Field(default_factory=utc_now)


class SimulationScenario(StrictModel):
    id: str = Field(default_factory=lambda: new_id("scenario"))
    name: str
    robot_type: str = "so101"
    backend: str = "mock"
    # Which arm to draw: the six-capsule contract stand-in, the mesh-accurate
    # SO-101, or whichever of the two this machine actually has.
    model: str = "auto"
    scene: str = "tabletop"
    task: str = "Reach a safe target"
    camera_mapping: dict[str, str] = Field(
        default_factory=lambda: {"front": "observation.images.front"}
    )
    created_at: datetime = Field(default_factory=utc_now)


# Jobs whose *output* depends on the camera stream. Teleoperation is not one of
# them: it records nothing, and with `display_data=false` LeRobot reads every
# frame and throws it away. Holding the camera there costs USB bandwidth on the
# bus that already broke a recording, delays the start by seconds of probing,
# and locks out the live preview for no gain.
CAMERA_JOB_KINDS = {
    JobKind.RECORDING,
    JobKind.EVALUATION,
    JobKind.POLICY_ROLLOUT,
    JobKind.CAMERA_PREVIEW,
}


class ResourceRequest(StrictModel):
    resource_id: str
    resource_type: str
    mode: str = "exclusive"


# Simulation is a target, not a separate activity. Asking to record in
# simulation and asking to record on the arm are the same request with a
# different follower, so the request says which follower and the server picks
# the recorder.
SIM_EQUIVALENT = {
    JobKind.RECORDING: JobKind.SIM_RECORDING,
    JobKind.TELEOPERATION: JobKind.SIM_TELEOPERATION,
}


class JobCreateRequest(StrictModel):
    kind: JobKind
    target_mode: TargetMode = TargetMode.SIM
    parameters: dict[str, Any] = Field(default_factory=dict)
    resources: list[ResourceRequest] = Field(default_factory=list)
    requested_by: str = "local-user"

    @model_validator(mode="after")
    def _resolve_simulated_kind(self) -> JobCreateRequest:
        """Turn 'record, in simulation' into the job that actually records.

        Asking for `recording` with `target_mode='sim'` used to produce a job
        that reached no command at all: it walked five cosmetic progress strings
        and finished green having written nothing. The dashboard's own button
        did exactly that, and so would any agent or curl call that reasoned the
        obvious way.

        Canonicalised here rather than at the call site so every door -- browser,
        agent gateway, command preview, curl -- goes through it. The kinds stay
        separate underneath because the lease rules, the camera rules and the
        approval rules genuinely differ; it is only the *request* that should
        not have to know that.
        """
        if self.target_mode == TargetMode.SIM and self.kind in SIM_EQUIVALENT:
            object.__setattr__(self, "kind", SIM_EQUIVALENT[self.kind])
        return self


class JobProcess(StrictModel):
    pid: int
    pgid: int
    executable: str
    arguments: list[str] = Field(default_factory=list)
    pty: bool = False
    boot_id: str | None = None
    started_at: datetime = Field(default_factory=utc_now)


class TelemetrySample(StrictModel):
    kind: TelemetryKind
    at: datetime = Field(default_factory=utc_now)
    loop_ms: float | None = None
    hz: float | None = None
    joints: dict[str, float] = Field(default_factory=dict)
    ranges: dict[str, dict[str, int]] = Field(default_factory=dict)
    prompt: str | None = None
    expects: JobInputKey | None = None
    episode: int | None = None
    phase: str | None = None
    message: str | None = None


class JobInputRequest(StrictModel):
    key: JobInputKey


class EpisodeOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class EpisodeAnnotation(StrictModel):
    """An operator's judgement about one episode. Nothing infers this."""

    episode: int = Field(ge=0)
    outcome: EpisodeOutcome
    note: str | None = Field(default=None, max_length=500)
    annotated_at: datetime = Field(default_factory=utc_now)


class ResolvedTargets(StrictModel):
    """Server-resolved physical targets. Clients never supply these values."""

    robot_profile_id: str | None = None
    robot_type: str | None = None
    robot_id: str | None = None
    robot_port: str | None = None
    robot_calibration_dir: str | None = None
    robot_calibration_revision: str | None = None
    teleoperator_profile_id: str | None = None
    teleop_type: str | None = None
    teleop_id: str | None = None
    teleop_port: str | None = None
    teleop_calibration_dir: str | None = None
    teleop_calibration_revision: str | None = None
    camera_profile_ids: dict[str, str] = Field(default_factory=dict)
    cameras: dict[str, dict[str, Any]] = Field(default_factory=dict)
    policy_id: str | None = None
    policy_checkpoint: str | None = None
    policy_revision: str | None = None
    rename_map: dict[str, str] = Field(default_factory=dict)
    max_relative_target: float | None = None
    action_shape: list[int] = Field(default_factory=list)

    def command_parameters(self) -> dict[str, Any]:
        """The subset the LeRobot command builder is allowed to read."""
        keys = (
            "robot_type",
            "robot_id",
            "robot_port",
            "robot_calibration_dir",
            "teleop_type",
            "teleop_id",
            "teleop_port",
            "teleop_calibration_dir",
            "max_relative_target",
        )
        parameters = {key: getattr(self, key) for key in keys if getattr(self, key) is not None}
        if self.cameras:
            parameters["cameras"] = self.cameras
        if self.policy_checkpoint:
            parameters["policy_path"] = self.policy_checkpoint
        if self.rename_map:
            parameters["rename_map"] = self.rename_map
        return parameters

    def resource_requests(self, kind: JobKind | None = None) -> list[ResourceRequest]:
        """The devices this job must hold alone while it runs.

        `kind` decides whether the camera is among them. Without it every
        resolved job claimed every mapped camera, so starting a teleoperation
        locked out the live preview -- while LeRobot read the frames and
        discarded them.
        """
        requests: list[ResourceRequest] = []
        if self.robot_profile_id:
            requests.append(
                ResourceRequest(
                    resource_id=self.robot_profile_id,
                    resource_type="robot",
                    mode="exclusive",
                )
            )
        if self.teleoperator_profile_id:
            requests.append(
                ResourceRequest(
                    resource_id=self.teleoperator_profile_id,
                    resource_type="teleoperator",
                    mode="exclusive",
                )
            )
        # A V4L2 device serves one consumer at a time, so a preview and a
        # recording must not hold the same camera together.
        if kind is not None and kind not in CAMERA_JOB_KINDS:
            return requests
        for camera_id in sorted(set(self.camera_profile_ids.values())):
            requests.append(
                ResourceRequest(
                    resource_id=camera_id,
                    resource_type="camera",
                    mode="exclusive",
                )
            )
        return requests

    def digest(self) -> str:
        encoded = self.model_dump_json()
        return hashlib.sha256(encoded.encode()).hexdigest()


class JobRecord(StrictModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    kind: JobKind
    state: JobState = JobState.CREATED
    target_mode: TargetMode
    parameters: dict[str, Any] = Field(default_factory=dict)
    resources: list[ResourceRequest] = Field(default_factory=list)
    requested_by: str
    resolved_targets: ResolvedTargets | None = None
    process: JobProcess | None = None
    progress: float = 0.0
    message: str = "Created"
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    correlation_id: str = Field(default_factory=lambda: new_id("corr"))
    approval_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ResourceLease(StrictModel):
    resource_id: str
    resource_type: str
    owner_job_id: str
    mode: str = "exclusive"
    acquired_at: datetime = Field(default_factory=utc_now)
    heartbeat_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class ApprovalRecord(StrictModel):
    id: str = Field(default_factory=lambda: new_id("approval"))
    job_id: str
    parameters_hash: str
    targets_hash: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    confirmed_at: datetime | None = None


class SafetyCheck(StrictModel):
    code: str
    label: str
    status: CheckStatus
    message: str


class PhysicalGateRequest(StrictModel):
    """An explicit, session-scoped operator decision about real actuation."""

    enabled: bool
    confirmed: bool = False


class PreflightResult(StrictModel):
    allowed: bool
    requires_approval: bool = False
    checks: list[SafetyCheck] = Field(default_factory=list)
    resolved: ResolvedTargets | None = None


class DoctorCheck(StrictModel):
    code: str
    label: str
    status: CheckStatus
    detail: str
    remediation: str | None = None


class CapabilityManifest(StrictModel):
    platform_version: str
    python_version: str
    os: str
    architecture: str
    packages: dict[str, str | None]
    accelerator: str
    ffmpeg: str | None = None
    camera_backends: list[str]
    robot_adapters: list[str]
    teleoperator_adapters: list[str] = Field(default_factory=list)
    policy_adapters: list[str]
    simulation_backends: list[str]
    contract_test_results: dict[str, str] = Field(default_factory=dict)
    physical_enabled: bool
    generated_at: datetime = Field(default_factory=utc_now)


class DoctorReport(StrictModel):
    overall: CheckStatus
    checks: list[DoctorCheck]
    capabilities: CapabilityManifest
    generated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(StrictModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    timestamp: datetime = Field(default_factory=utc_now)
    actor: str
    action: str
    target: str
    correlation_id: str
    outcome: str
    details: dict[str, Any] = Field(default_factory=dict)


class AgentCommandRequest(StrictModel):
    session_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentCommandResult(StrictModel):
    accepted: bool
    action: str
    message: str
    job: JobRecord | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AgentPlanRequest(StrictModel):
    session_id: str
    prompt: str = Field(min_length=3, max_length=8_000)
    execute: bool = False


class AgentPlanStep(StrictModel):
    action: str
    rationale: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentPlan(StrictModel):
    """An ordered answer, because one action is rarely the whole answer.

    The plan used to be a single action, which meant the honest response to
    "can I train on what I recorded yesterday" was one third of an answer: list
    the recordings, and stop before finding out whether they go together. The
    roadmap's own examples are chains -- inspect, validate, report, decide --
    and a planner that can only take the first step of one leaves the operator
    to carry the result to the next step by hand, which is the work they asked
    the planner to do.

    Capped at eight. A model that wants more than eight steps has misunderstood
    the request, and running an unbounded list it invented is not a plan, it is
    a loop.
    """

    # `min_length` rather than a validator, because the bound has to reach the
    # model. Ollama constrains decoding to the JSON schema, so `minItems: 1` is
    # something it cannot violate -- while a validator runs afterwards and only
    # turns an empty plan into an error. Measured: the second turn of a
    # conversation came back with no steps at all, the model apparently reading
    # the history as the answer already given.
    steps: list[AgentPlanStep] = Field(min_length=1, max_length=8)
    rationale: str = ""
    risks: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False

    @property
    def action(self) -> str:
        """The first step's action, for anything that only wants the headline."""
        return self.steps[0].action


class AgentStepResult(StrictModel):
    index: int
    action: str
    # completed | blocked | failed | awaiting_human | skipped
    state: str
    message: str
    command_result: AgentCommandResult | None = None
    # What the server says about this action. The plan's `risks` are the
    # model's own account of itself and cannot be checked; this is the part
    # that can, sitting beside it so the two can be read together.
    brief: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class AgentPlanResult(StrictModel):
    plan: AgentPlan
    executed: bool = False
    steps: list[AgentStepResult] = Field(default_factory=list)
    # Why the run stopped short, when it did. A plan that ends at step two
    # because step three moves an arm is the normal case, not a failure.
    stopped_because: str | None = None
    warnings: list[str] = Field(default_factory=list)


class AgentTurn(StrictModel):
    """One exchange, kept so the next one can refer to it.

    Planning was stateless: every request started from nothing, so the model
    could not be asked a follow-up. "Which of these can be trained together"
    had to name the recordings again, because the model had never seen the
    answer to "what do I have" -- it had produced the step that asked, and then
    the process forgot both the question and the result.

    Stored server-side rather than sent back and forth, because what makes a
    follow-up work is the *result* of the earlier steps, and those run to
    thousands of lines.
    """

    id: str = Field(default_factory=lambda: new_id("turn"))
    session_id: str
    prompt: str
    result: AgentPlanResult
    created_at: datetime = Field(default_factory=utc_now)


class DashboardSummary(StrictModel):
    system_status: CheckStatus
    physical_enabled: bool
    devices: int
    robots: int
    datasets: int
    policies: int
    active_jobs: int
    blocked_jobs: int
    recent_jobs: list[JobRecord]
