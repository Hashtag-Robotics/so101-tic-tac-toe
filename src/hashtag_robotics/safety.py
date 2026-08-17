from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from hashtag_robotics.calibration import CalibrationError, CalibrationStore
from hashtag_robotics.camera import CameraError, CameraService
from hashtag_robotics.config import Settings
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.hardware import resolve_command
from hashtag_robotics.identify import release_torque
from hashtag_robotics.models import (
    ApprovalRecord,
    AuditEvent,
    CalibrationArtifact,
    CameraProfile,
    CheckStatus,
    DatasetManifest,
    DeviceRecord,
    DeviceRole,
    JobCreateRequest,
    JobKind,
    PolicyManifest,
    PreflightResult,
    ResolvedTargets,
    RobotProfile,
    SafetyCheck,
    TargetMode,
    TeleoperatorProfile,
    TorqueReleaseResult,
    utc_now,
)
from hashtag_robotics.repository import Repository
from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_MAX_RELATIVE_TARGET,
    TIC_TAC_TOE_POLICY_REPO,
    TIC_TAC_TOE_POLICY_REVISION,
    TicTacToePresetError,
    canonical_tic_tac_toe_parameters,
    is_tic_tac_toe_parameters,
)

ESTOP_FLAG = "estop_engaged"

# The last torque cut, kept where the panel can read it without walking the
# audit log. An operator asking "is the arm safe to touch?" needs one answer,
# not a search.
TORQUE_RELEASE_FLAG = "last_torque_release"

# A cut that has not landed in this long is not going to; report and move on
# rather than leaving the operator waiting on a hung adapter.
TORQUE_RELEASE_TIMEOUT_SECONDS = 8.0

PHYSICAL_JOB_KINDS = {
    JobKind.MOTOR_SETUP,
    JobKind.CALIBRATION,
    JobKind.TELEOPERATION,
    JobKind.RECORDING,
    JobKind.REPLAY,
    JobKind.EVALUATION,
    JobKind.POLICY_ROLLOUT,
}

# Jobs that produce a calibration instead of consuming one.
CALIBRATING_JOB_KINDS = {JobKind.MOTOR_SETUP, JobKind.CALIBRATION}

# Jobs that always drive a leader arm as well as the follower. Simulated
# sessions belong here too: the leader is the whole input, it is just the
# follower that is a model instead of a motor.
TELEOPERATED_JOB_KINDS = {
    JobKind.TELEOPERATION,
    JobKind.RECORDING,
    JobKind.SIM_TELEOPERATION,
    JobKind.SIM_RECORDING,
}

POLICY_JOB_KINDS = {JobKind.EVALUATION, JobKind.POLICY_ROLLOUT}

# Jobs whose effect leaves this machine. Nothing here can injure anyone, which
# is why they were never gated -- but an upload cannot be taken back either. A
# dataset carries video of the room it was recorded in, and a repository that
# was public for a minute has been read by whatever was watching.
PUBLISHING_JOB_KINDS = {JobKind.HUB_SYNC}


def _hub_token() -> str | None:
    """Whatever credential this process can actually use, or nothing.

    Read through `huggingface_hub` rather than the environment, because the
    token usually lives in a file the library knows about and an env-only check
    would report 'no credential' on a machine that is logged in.
    """
    try:
        from huggingface_hub import get_token
    except ImportError:  # pragma: no cover - huggingface_hub ships with lerobot
        return None
    try:
        return get_token()
    except Exception:  # noqa: BLE001 - a missing credential is an answer, not a fault
        return None


# Simulated sessions open the leader arm and nothing else. That is a read, not
# an actuation -- the follower is never connected, so no joint can move and the
# physical gate does not apply. The leader still has to be resolved, though:
# without its port and calibration the command has nothing to read.
SIM_JOB_KINDS = {JobKind.SIM_TELEOPERATION, JobKind.SIM_RECORDING}

COMMAND_NAMES = {
    JobKind.MOTOR_SETUP: "lerobot-setup-motors",
    JobKind.CALIBRATION: "lerobot-calibrate",
    JobKind.TELEOPERATION: "lerobot-teleoperate",
    JobKind.RECORDING: "lerobot-record",
    JobKind.REPLAY: "lerobot-replay",
    JobKind.EVALUATION: "lerobot-rollout",
    JobKind.POLICY_ROLLOUT: "lerobot-rollout",
}

EXPECTED_ACTION_JOINTS = 6

# Command parameters the server always re-derives; a client value is discarded.
SERVER_OWNED_PARAMETERS = (
    "robot_type",
    "robot_id",
    "robot_port",
    "robot_calibration_dir",
    "teleop_type",
    "teleop_id",
    "teleop_port",
    "teleop_calibration_dir",
    "max_relative_target",
    "policy_path",
    "rename_map",
)


def parameter_hash(request: JobCreateRequest) -> str:
    encoded = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _check(
    code: str,
    label: str,
    passed: bool,
    passed_message: str,
    failed_message: str,
    failed_status: CheckStatus = CheckStatus.BLOCKED,
) -> SafetyCheck:
    return SafetyCheck(
        code=code,
        label=label,
        status=CheckStatus.PASS if passed else failed_status,
        message=passed_message if passed else failed_message,
    )


def _not_applicable(code: str, label: str, message: str) -> SafetyCheck:
    return SafetyCheck(
        code=code,
        label=label,
        status=CheckStatus.NOT_APPLICABLE,
        message=message,
    )


class SafetyService:
    """Resolves every physical target on the server and gates actuation on it.

    The only judgement the client is allowed to make is whether the physical
    workspace is clear; ports, calibrations and limits are always re-derived
    here from the repository and the live device inventory.
    """

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        calibration: CalibrationStore,
        discovery: DiscoveryService,
        cameras: CameraService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.calibration = calibration
        self.discovery = discovery
        self.cameras = cameras

    # -- emergency stop latch -------------------------------------------------

    def estop_engaged(self) -> bool:
        return self.repository.get_flag(ESTOP_FLAG) is not None

    def engage_estop(self, actor: str) -> None:
        self.repository.set_flag(ESTOP_FLAG, f"{actor}@{utc_now().isoformat()}")

    def clear_estop(self) -> None:
        self.repository.set_flag(ESTOP_FLAG, None)

    # -- torque release -------------------------------------------------------

    async def release_torque(self, actor: str = "local-user") -> list[TorqueReleaseResult]:
        """De-energise every physical arm this installation knows about.

        Latching the stop and killing the process groups stops *new* commands.
        It does not stop the *last* one: the servos keep holding their final
        goal position under power. Until this runs, "emergency stop" means
        "the software stopped", not "the arm is safe to reach into".

        Both arms are cut in parallel because they are separate buses, and one
        adapter that has stopped answering must not delay the other.

        Never raises: the caller is an emergency stop.
        """
        targets = self._torque_targets()
        if not targets:
            self._record_torque_release(actor, [], "no-physical-arms")
            return []

        results = await asyncio.gather(
            *(self._release_one(port, profile_id, role) for port, profile_id, role in targets)
        )
        outcome = (
            "released"
            if all(result.released for result in results)
            else "partial"
            if any(result.released for result in results)
            else "failed"
        )
        self._record_torque_release(actor, list(results), outcome)
        return list(results)

    def last_torque_release(self) -> dict[str, Any] | None:
        """What the most recent cut reported, or None if none has run."""
        stored = self.repository.get_flag(TORQUE_RELEASE_FLAG)
        if not stored:
            return None
        try:
            parsed = json.loads(stored)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _torque_targets(self) -> list[tuple[str, str, DeviceRole]]:
        """Every distinct serial port a real arm profile points at."""
        targets: list[tuple[str, str, DeviceRole]] = []
        seen: set[str] = set()
        for kind, model, role in (
            ("robot", RobotProfile, DeviceRole.FOLLOWER),
            ("teleoperator", TeleoperatorProfile, DeviceRole.LEADER),
        ):
            for profile in self.repository.list_entities(kind, model):
                port = profile.port
                if not port or profile.target_mode != TargetMode.REAL or port in seen:
                    continue
                seen.add(port)
                targets.append((port, profile.id, role))
        return targets

    async def _release_one(
        self,
        port: str,
        profile_id: str,
        role: DeviceRole,
    ) -> TorqueReleaseResult:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(release_torque, port),
                timeout=TORQUE_RELEASE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            result = TorqueReleaseResult(
                port=port,
                detail=(
                    f"The torque cut did not finish within "
                    f"{TORQUE_RELEASE_TIMEOUT_SECONDS:.0f} s. Remove power from the arm."
                ),
                elapsed_ms=int(TORQUE_RELEASE_TIMEOUT_SECONDS * 1000),
            )
        except Exception as error:  # noqa: BLE001 - an emergency stop never raises
            result = TorqueReleaseResult(
                port=port,
                detail=f"The torque cut failed: {error}. Remove power from the arm.",
            )
        result.profile_id = profile_id
        result.role = role
        return result

    def _record_torque_release(
        self,
        actor: str,
        results: list[TorqueReleaseResult],
        outcome: str,
    ) -> None:
        payload = {
            "outcome": outcome,
            "recorded_at": utc_now().isoformat(),
            "arms": [result.model_dump(mode="json") for result in results],
        }
        self.repository.set_flag(TORQUE_RELEASE_FLAG, json.dumps(payload))
        self.repository.append_audit(
            AuditEvent(
                actor=actor,
                action="safety.torque_release",
                target="all-physical-arms",
                correlation_id="emergency-stop",
                outcome=outcome,
                details=payload,
            )
        )

    # -- preflight ------------------------------------------------------------

    def preflight(self, request: JobCreateRequest) -> PreflightResult:
        checks: list[SafetyCheck] = [
            SafetyCheck(
                code="target.explicit",
                label="Resolved target mode",
                status=CheckStatus.PASS,
                message=f"Target mode is explicitly '{request.target_mode.value}'.",
            )
        ]
        is_real_actuation = (
            request.target_mode == TargetMode.REAL and request.kind in PHYSICAL_JOB_KINDS
        )
        # A dry run reports what it would send and sends nothing, so it needs no
        # more permission than reading the folder does.
        publishes = request.kind in PUBLISHING_JOB_KINDS and not request.parameters.get(
            "dry_run", False
        )
        resolved: ResolvedTargets | None = (
            ResolvedTargets() if request.kind in POLICY_JOB_KINDS else None
        )

        if request.kind in POLICY_JOB_KINDS:
            checks.extend(self._policy_checks(request, resolved))

        if request.kind == JobKind.TRAINING:
            checks.extend(self._training_checks(request))

        if request.kind in PUBLISHING_JOB_KINDS:
            checks.extend(self._publishing_checks(request))

        if is_real_actuation:
            resolved = resolved or ResolvedTargets()
            connected = self._connected()
            checks.extend(self._runtime_checks(request))
            checks.extend(self._robot_checks(request, resolved, connected))
            checks.extend(self._teleoperator_checks(request, resolved, connected))
            checks.extend(self._operator_checks(request, resolved))
        elif request.kind in SIM_JOB_KINDS:
            resolved = ResolvedTargets()
            checks.extend(self._teleoperator_checks(request, resolved, self._connected()))
            # A latched stop has to hold here too. The follower is not opened,
            # but the leader is -- and the leader is one of the two arms the stop
            # just de-energised. Letting a simulated session start on it while
            # the latch is down would mean the stop stopped less than it says.
            checks.append(
                _check(
                    "estop.armed",
                    "Emergency stop",
                    not self.estop_engaged(),
                    "The emergency stop is armed and not latched.",
                    "The emergency stop is latched; clear it before opening the leader arm.",
                )
            )
            checks.append(
                SafetyCheck(
                    code="target.simulated_only",
                    label="Nothing physical moves",
                    status=CheckStatus.PASS,
                    message=(
                        "The follower is never opened and the leader is only read, so this "
                        "session cannot move a joint."
                    ),
                )
            )

        if request.kind == JobKind.POLICY_ROLLOUT and is_tic_tac_toe_parameters(request.parameters):
            checks.extend(self._tic_tac_toe_checks(request, resolved))

        blocked = any(check.status == CheckStatus.BLOCKED for check in checks)
        return PreflightResult(
            allowed=not blocked,
            requires_approval=is_real_actuation or publishes,
            checks=checks,
            resolved=resolved,
        )

    def _tic_tac_toe_checks(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets | None,
    ) -> list[SafetyCheck]:
        """Pin the dashboard profile to the exact bench-validated contract."""
        try:
            canonical = canonical_tic_tac_toe_parameters(request.parameters)
        except TicTacToePresetError as error:
            return [
                _check(
                    "ttt.move_resolved",
                    "Tic-tac-toe move",
                    False,
                    "",
                    str(error),
                )
            ]

        pinned_keys = (
            "move_id",
            "task",
            "ttt_preset",
            "strategy",
            "fps",
            "inference_type",
            "inference_queue_threshold",
            "inference_rtc_enabled",
            "repo_id",
            "episodes",
            "episode_time_s",
            "reset_time_s",
            "dataset_video",
            "return_to_initial_position",
            "disable_torque_on_disconnect",
        )
        contract_pinned = all(
            request.parameters.get(key) == canonical.get(key) for key in pinned_keys
        )

        policy_id = str(request.parameters.get("policy_id", "")).strip()
        policy = (
            self.repository.get_entity("policy", policy_id, PolicyManifest) if policy_id else None
        )
        policy_matches = bool(
            policy
            and policy.model_repo_id == TIC_TAC_TOE_POLICY_REPO
            and policy.model_revision == TIC_TAC_TOE_POLICY_REVISION
        )
        correct_robot = bool(resolved and resolved.robot_id and resolved.robot_calibration_revision)
        correct_limit = bool(
            resolved
            and resolved.max_relative_target is not None
            and abs(resolved.max_relative_target - TIC_TAC_TOE_MAX_RELATIVE_TARGET) < 1e-9
        )
        wrapper_ready = resolve_command("hashtag-lerobot-rollout") is not None

        return [
            _check(
                "ttt.move_resolved",
                "Tic-tac-toe move",
                contract_pinned,
                (
                    f"{canonical['move_id']} is pinned to training episode "
                    f"{canonical['ttt_preset']['episode_index']} and an exact board/start pose."
                ),
                "The move does not match the server-owned tic-tac-toe rollout contract.",
            ),
            _check(
                "ttt.policy_revision",
                "Bench-validated policy revision",
                policy_matches,
                f"Policy is pinned to {TIC_TAC_TOE_POLICY_REVISION[:12]}.",
                "This profile only accepts the pinned Games 1-15 120K revision.",
            ),
            _check(
                "ttt.robot_calibration",
                "Demo-pose calibration",
                correct_robot,
                "Follower identity and calibration revision are resolved by the server.",
                "Select a connected follower with an imported, verified calibration revision.",
            ),
            _check(
                "ttt.relative_limit",
                "Bench-validated motion limit",
                correct_limit,
                f"Relative target clamp remains {TIC_TAC_TOE_MAX_RELATIVE_TARGET} degrees.",
                "The tic-tac-toe profile requires an exact 5 degree relative target clamp.",
            ),
            _check(
                "ttt.wrapper_runtime",
                "Dashboard rollout wrapper",
                wrapper_ready,
                "The homing and operator-control wrapper is installed.",
                "'hashtag-lerobot-rollout' is unavailable; the generic command "
                "cannot run this profile.",
            ),
            _check(
                "ttt.real_target",
                "Physical target",
                request.target_mode == TargetMode.REAL,
                "The profile targets the explicitly approved physical follower.",
                "The trained tabletop profile is not exposed as a simulated success path.",
            ),
        ]

    def create_approval(
        self,
        job_id: str,
        request: JobCreateRequest,
        resolved: ResolvedTargets | None = None,
    ) -> ApprovalRecord:
        return ApprovalRecord(
            job_id=job_id,
            parameters_hash=parameter_hash(request),
            targets_hash=resolved.digest() if resolved else None,
            expires_at=utc_now() + timedelta(minutes=5),
        )

    # -- checks ---------------------------------------------------------------

    def _runtime_checks(self, request: JobCreateRequest) -> list[SafetyCheck]:
        command_name = COMMAND_NAMES[request.kind]
        return [
            _check(
                "physical.enabled",
                "Physical adapter gate",
                self.settings.enable_physical,
                "Physical adapters are enabled.",
                "Physical adapters remain locked until HIL testing.",
            ),
            _check(
                "physical.runtime",
                "LeRobot physical runtime",
                resolve_command(command_name) is not None,
                f"Resolved '{command_name}'.",
                f"Required command '{command_name}' is not installed.",
            ),
            _check(
                "estop.armed",
                "Emergency stop",
                not self.estop_engaged(),
                "The emergency stop is armed and not latched.",
                "The emergency stop is latched; clear it before starting physical work.",
            ),
        ]

    def _robot_checks(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets,
        connected: list[DeviceRecord],
    ) -> list[SafetyCheck]:
        if not self._needs_robot(request):
            return [
                _not_applicable(
                    "target.robot_resolved",
                    "Resolved follower",
                    "This job targets the leader arm only.",
                )
            ]

        profile = self._robot_profile(request)
        checks = [
            _check(
                "target.robot_resolved",
                "Resolved follower",
                profile is not None,
                f"Follower profile '{profile.name}' resolved from the repository."
                if profile
                else "",
                "Real actuation needs a 'robot_profile_id' that resolves to a stored profile.",
            )
        ]
        if profile is None:
            return checks

        resolved.robot_profile_id = profile.id
        resolved.robot_type = profile.robot_type
        resolved.robot_id = profile.calibration_id

        checks.append(
            _check(
                "target.robot_identity",
                "Follower device id",
                bool(profile.calibration_id),
                f"The follower is addressed as '{profile.calibration_id}'.",
                "The follower profile carries no LeRobot device id; name the arm first.",
            )
        )
        checks.append(
            self._device_check("robot", profile.device_fingerprint, resolved, "robot", connected)
        )
        checks.extend(self._calibration_checks("robot", request, profile, resolved))
        checks.extend(self._limit_checks(request, profile, resolved))
        checks.append(self._camera_check(profile, resolved))
        return checks

    def _teleoperator_checks(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets,
        connected: list[DeviceRecord],
    ) -> list[SafetyCheck]:
        if not self._needs_teleoperator(request):
            return [
                _not_applicable(
                    "target.teleoperator_resolved",
                    "Resolved leader",
                    "This job does not drive a leader arm.",
                )
            ]

        profile = self._teleoperator_profile(request)
        checks = [
            _check(
                "target.teleoperator_resolved",
                "Resolved leader",
                profile is not None,
                f"Leader profile '{profile.name}' resolved from the repository." if profile else "",
                "This job needs a 'teleoperator_profile_id' that resolves to a stored profile.",
            )
        ]
        if profile is None:
            return checks

        resolved.teleoperator_profile_id = profile.id
        resolved.teleop_type = profile.teleoperator_type
        resolved.teleop_id = profile.calibration_id

        checks.append(
            _check(
                "target.teleoperator_identity",
                "Leader device id",
                bool(profile.calibration_id),
                f"The leader is addressed as '{profile.calibration_id}'.",
                "The leader profile carries no LeRobot device id; name the arm first.",
            )
        )
        checks.append(
            self._device_check(
                "teleop", profile.device_fingerprint, resolved, "teleoperator", connected
            )
        )
        checks.extend(self._calibration_checks("teleoperator", request, profile, resolved))
        checks.append(self._role_distinct_check(request, profile, resolved))
        return checks

    def _operator_checks(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets,
    ) -> list[SafetyCheck]:
        leases = resolved.resource_requests(request.kind)
        exclusive = leases and all(lease.mode == "exclusive" for lease in leases)
        return [
            _check(
                "resources.exclusive_pair",
                "Exclusive resources",
                bool(exclusive),
                "Server-derived exclusive leases: "
                + ", ".join(f"{lease.resource_type}:{lease.resource_id}" for lease in leases),
                "No physical target could be locked exclusively.",
            ),
            _check(
                "workspace.confirmed",
                "Workspace confirmation",
                bool(request.parameters.get("workspace_confirmed")),
                "The operator confirmed the workspace is clear.",
                "The operator has not confirmed that the workspace is clear.",
            ),
        ]

    def _publishing_checks(self, request: JobCreateRequest) -> list[SafetyCheck]:
        """What has to be true before a dataset leaves this machine.

        The kind existed as three progress strings that walked and returned a
        hash: a job that pretended to sync. Making it real means answering the
        questions an operator would have asked it -- is there a credential, does
        the recording exist, is it whole, and is the repository private -- before
        anything is uploaded rather than after.
        """
        dataset_id = str(request.parameters.get("dataset_id", "")).strip()
        manifest = (
            self.repository.get_entity("dataset", dataset_id, DatasetManifest)
            if dataset_id
            else None
        )
        repo_id = str(request.parameters.get("repo_id") or (manifest.repo_id if manifest else ""))
        checks = [
            _check(
                "hub.dataset_resolved",
                "Dataset",
                manifest is not None,
                f"'{manifest.name}' has {manifest.episodes} episode(s)." if manifest else "",
                f"No dataset is registered under id '{dataset_id}'.",
            ),
            _check(
                "hub.repo_namespaced",
                "Repository id",
                bool(repo_id) and "/" in repo_id,
                f"Will publish to '{repo_id}'.",
                "A Hub repository id needs a namespace, as in 'user/dataset'.",
            ),
        ]
        if manifest is not None:
            checks.append(
                _check(
                    "hub.integrity",
                    "Recording integrity",
                    manifest.integrity_status == "verified",
                    "The recording verified against what is on disk.",
                    f"The recording is '{manifest.integrity_status}'; publishing it "
                    "would put a broken dataset somewhere other people can take it.",
                )
            )
        token = _hub_token()
        checks.append(
            _check(
                "hub.credential",
                "Hub credential",
                bool(token),
                "A Hugging Face token is available to this process.",
                "No Hugging Face token was found. Run 'hf auth login' as the user "
                "that runs this server.",
            )
        )
        # Not a blocker: a public dataset can be exactly what is wanted. It is
        # said out loud because the default here is private and the difference
        # cannot be undone by deleting the repository afterwards.
        public = request.parameters.get("private") is False
        checks.append(
            SafetyCheck(
                code="hub.visibility",
                label="Visibility",
                status=CheckStatus.WARNING if public else CheckStatus.PASS,
                message=(
                    "This will be PUBLIC. Anyone can read the video and the "
                    "workspace it was recorded in."
                    if public
                    else "This will be a private repository."
                ),
            )
        )
        return checks

    def _training_checks(self, request: JobCreateRequest) -> list[SafetyCheck]:
        repo_id = str(request.parameters.get("repo_id", "")).strip()
        checks = [
            _check(
                "dataset.resolved",
                "Training dataset",
                bool(repo_id),
                f"Training reads dataset '{repo_id}'.",
                "Training needs a 'repo_id'; LeRobot cannot train without --dataset.repo_id.",
            )
        ]

        dataset_id = str(request.parameters.get("dataset_id", "")).strip()
        dataset = (
            self.repository.get_entity("dataset", dataset_id, DatasetManifest)
            if dataset_id
            else None
        )
        if dataset is not None:
            verified = dataset.integrity_status == "verified"
            checks.append(
                _check(
                    "dataset.integrity",
                    "Dataset integrity",
                    verified,
                    f"'{dataset.name}' is verified: {dataset.episodes} episode(s), "
                    f"{dataset.total_frames} frame(s).",
                    f"'{dataset.name}' is '{dataset.integrity_status}'; validate or re-record "
                    "it before spending compute on it.",
                    failed_status=CheckStatus.WARNING,
                )
            )
        return checks

    @staticmethod
    def _camera_feature(name: str) -> str:
        stripped = str(name).strip()
        return (
            stripped
            if stripped.startswith("observation.images.")
            else f"observation.images.{stripped}"
        )

    def _policy_checks(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets | None,
    ) -> list[SafetyCheck]:
        policy_id = str(request.parameters.get("policy_id", "")).strip()
        policy = (
            self.repository.get_entity("policy", policy_id, PolicyManifest) if policy_id else None
        )
        checks = [
            _check(
                "policy.resolved",
                "Resolved policy",
                policy is not None,
                f"Policy '{policy.name}' resolved from the registry." if policy else "",
                "Evaluation and rollout need a 'policy_id' that resolves to a stored manifest.",
            )
        ]
        if policy is None:
            return checks

        if resolved is not None:
            resolved.policy_id = policy.id
            resolved.policy_checkpoint = policy.checkpoint
            resolved.policy_revision = policy.model_revision
            resolved.rename_map = {
                self._camera_feature(source): self._camera_feature(target)
                for source, target in policy.camera_mapping.items()
            }

        expected = list(policy.action_shape)
        matches = expected == [EXPECTED_ACTION_JOINTS]
        checks.append(
            _check(
                "policy.feature_mapping",
                "Policy feature mapping",
                matches and bool(policy.expected_features),
                f"Action shape {expected} and {len(policy.expected_features)} expected features "
                "match the SO-101 contract.",
                f"Action shape {expected} or the expected feature list does not match the "
                "SO-101 contract.",
            )
        )

        if request.target_mode != TargetMode.REAL:
            return checks

        checkpoint = Path(policy.checkpoint).expanduser() if policy.checkpoint else None
        checkpoint_ready = bool(
            checkpoint
            and checkpoint.is_dir()
            and (checkpoint / "config.json").is_file()
            and (
                (checkpoint / "model.safetensors").is_file()
                or any(checkpoint.glob("model-*.safetensors"))
            )
        )
        checks.append(
            _check(
                "policy.checkpoint_present",
                "Local policy checkpoint",
                checkpoint_ready,
                f"Pinned policy files are present under '{checkpoint}'.",
                "The selected policy has no complete local checkpoint. "
                "Import it from the Hub first.",
            )
        )

        profile = self._robot_profile(request)
        robot_roles = set(profile.camera_mapping) if profile else set()
        expected_visuals = {
            feature
            for feature in policy.expected_features
            if feature.startswith("observation.images.")
        }
        rename_map = resolved.rename_map if resolved else {}
        mapped_sources = {source.removeprefix("observation.images.") for source in rename_map}
        mapped_targets = set(rename_map.values())
        mapping_valid = (
            bool(rename_map)
            and mapped_sources.issubset(robot_roles)
            and mapped_targets.issubset(expected_visuals)
            and len(mapped_targets) == len(rename_map)
            and len(expected_visuals - mapped_targets) <= policy.empty_cameras
        )
        checks.append(
            _check(
                "policy.camera_mapping",
                "Policy camera mapping",
                mapping_valid,
                (
                    f"Robot cameras {sorted(mapped_sources)} map to policy features "
                    f"{sorted(mapped_targets)}; {policy.empty_cameras} empty camera(s) allowed."
                ),
                (
                    f"Camera mapping is incompatible. Robot roles: {sorted(robot_roles)}; "
                    f"policy visuals: {sorted(expected_visuals)}; mapping: {rename_map}; "
                    f"empty cameras allowed: {policy.empty_cameras}."
                ),
            )
        )
        return checks

    # -- resolution -----------------------------------------------------------

    def _needs_robot(self, request: JobCreateRequest) -> bool:
        if request.kind in CALIBRATING_JOB_KINDS:
            return str(request.parameters.get("role", "robot")) != "teleoperator"
        return True

    def _needs_teleoperator(self, request: JobCreateRequest) -> bool:
        if request.kind in TELEOPERATED_JOB_KINDS:
            return True
        if request.kind in CALIBRATING_JOB_KINDS:
            return str(request.parameters.get("role", "robot")) == "teleoperator"
        return False

    def _robot_profile(self, request: JobCreateRequest) -> RobotProfile | None:
        profile_id = str(request.parameters.get("robot_profile_id", "")).strip()
        if not profile_id:
            return None
        return self.repository.get_entity("robot", profile_id, RobotProfile)

    def _teleoperator_profile(self, request: JobCreateRequest) -> TeleoperatorProfile | None:
        profile_id = str(request.parameters.get("teleoperator_profile_id", "")).strip()
        if not profile_id:
            return None
        return self.repository.get_entity("teleoperator", profile_id, TeleoperatorProfile)

    def _connected(self) -> list[DeviceRecord]:
        return self.discovery.snapshot(include_simulated=False)

    def _device_check(
        self,
        prefix: str,
        fingerprint: str | None,
        resolved: ResolvedTargets,
        label_role: str,
        connected: list[DeviceRecord],
    ) -> SafetyCheck:
        device = next(
            (item for item in connected if fingerprint and item.stable_fingerprint == fingerprint),
            None,
        )
        if device is not None:
            port = device.stable_path or device.transient_path
            setattr(resolved, f"{prefix}_port", port)
        return _check(
            f"device.{prefix}_fingerprint_match",
            f"Connected {label_role}",
            device is not None,
            f"Fingerprint resolves to {getattr(resolved, f'{prefix}_port', None)}.",
            f"No connected device matches the {label_role} profile fingerprint.",
        )

    def _calibration_checks(
        self,
        role: str,
        request: JobCreateRequest,
        profile: RobotProfile | TeleoperatorProfile,
        resolved: ResolvedTargets,
    ) -> list[SafetyCheck]:
        prefix = "robot" if role == "robot" else "teleop"
        device_type = (
            profile.robot_type if isinstance(profile, RobotProfile) else profile.teleoperator_type
        )
        try:
            # Only the directory is needed here; LeRobot appends '<device id>.json' itself.
            directory = self.calibration.live_path(
                device_type, profile.calibration_id or "unnamed"
            ).parent
            setattr(resolved, f"{prefix}_calibration_dir", str(directory))
        except CalibrationError:
            return [
                _check(
                    f"calibration.{role}.artifact_present",
                    f"{role.capitalize()} calibration artifact",
                    False,
                    "",
                    f"LeRobot device type '{device_type}' has no known calibration directory.",
                )
            ]

        if request.kind in CALIBRATING_JOB_KINDS:
            reason = "This job creates the calibration, so no existing revision is required."
            return [
                _not_applicable(
                    f"calibration.{role}.artifact_present", "Calibration artifact", reason
                ),
                _not_applicable(
                    f"calibration.{role}.revision_match", "Calibration revision", reason
                ),
                _not_applicable(
                    f"calibration.{role}.checksum_match", "Calibration checksum", reason
                ),
            ]

        artifact = (
            self.repository.get_entity(
                "calibration", profile.calibration_revision, CalibrationArtifact
            )
            if profile.calibration_revision
            else None
        )
        checks = [
            _check(
                f"calibration.{role}.artifact_present",
                f"{role.capitalize()} calibration artifact",
                artifact is not None,
                f"Bound to revision {artifact.id} ({artifact.source.value})." if artifact else "",
                f"The {role} profile has no bound calibration revision.",
            )
        ]
        if artifact is None:
            return checks

        setattr(resolved, f"{prefix}_calibration_revision", artifact.id)
        belongs = (
            artifact.device_type == device_type and artifact.device_id == profile.calibration_id
        )
        checks.append(
            _check(
                f"calibration.{role}.revision_match",
                f"{role.capitalize()} calibration revision",
                belongs,
                f"Revision {artifact.id} belongs to {device_type}/{profile.calibration_id}.",
                f"Revision {artifact.id} was recorded for "
                f"{artifact.device_type}/{artifact.device_id}, not "
                f"{device_type}/{profile.calibration_id}.",
            )
        )
        checks.append(
            _check(
                f"calibration.{role}.checksum_match",
                f"{role.capitalize()} calibration checksum",
                self.calibration.matches_disk(artifact),
                "The live calibration file matches the bound revision.",
                "The live calibration file drifted from the bound revision.",
            )
        )
        return checks

    def _limit_checks(
        self,
        request: JobCreateRequest,
        profile: RobotProfile,
        resolved: ResolvedTargets,
    ) -> list[SafetyCheck]:
        if request.kind in CALIBRATING_JOB_KINDS:
            reason = "Setup and calibration commands do not accept motion limits."
            return [
                _not_applicable("limits.max_relative_target", "Relative target limit", reason),
                _not_applicable("limits.action_shape", "Action shape", reason),
            ]

        ceiling = self.settings.max_relative_target_ceiling
        raw = profile.safety_profile.get("max_relative_target")
        limit = float(raw) if isinstance(raw, int | float) else None
        within = limit is not None and 0 < limit <= ceiling
        if within and limit is not None:
            resolved.max_relative_target = limit

        joints = len(profile.motor_layout)
        if joints == EXPECTED_ACTION_JOINTS:
            resolved.action_shape = [joints]

        return [
            _check(
                "limits.max_relative_target",
                "Relative target limit",
                within,
                f"Each step is capped at {limit} (server ceiling {ceiling}).",
                f"The safety profile must define 0 < max_relative_target <= {ceiling}; "
                f"it is {raw!r}.",
            ),
            _check(
                "limits.action_shape",
                "Action shape",
                joints == EXPECTED_ACTION_JOINTS,
                f"The bound motor map has {joints} joints.",
                f"The bound motor map has {joints} joints instead of "
                f"{EXPECTED_ACTION_JOINTS}; bind a valid calibration first.",
            ),
        ]

    def _camera_check(self, profile: RobotProfile, resolved: ResolvedTargets) -> SafetyCheck:
        mapping = dict(profile.camera_mapping)
        if not mapping:
            return _not_applicable(
                "camera.mapping_resolved",
                "Camera mapping",
                "The profile maps no cameras; this runs as a no-camera workflow.",
            )

        missing: list[str] = []
        cameras: dict[str, dict[str, Any]] = {}
        for name, camera_id in mapping.items():
            camera = self.repository.get_entity("camera", camera_id, CameraProfile)
            if camera is None:
                missing.append(f"{name} (no profile)")
                continue
            try:
                path = self.cameras.resolve_path(camera)
            except CameraError:
                missing.append(f"{name} (not connected)")
                continue
            cameras[name] = self.cameras.lerobot_config(camera, path, preview_name=name)

        if not missing:
            resolved.camera_profile_ids = mapping
            resolved.cameras = cameras
        return _check(
            "camera.mapping_resolved",
            "Camera mapping",
            not missing,
            f"{len(cameras)} camera role(s) resolved to a live device: "
            + ", ".join(
                f"{name}={config.get('unique_id', config.get('index_or_path', 'unknown'))}"
                for name, config in cameras.items()
            ),
            f"Unresolved camera role(s): {', '.join(missing)}.",
        )

    def _role_distinct_check(
        self,
        request: JobCreateRequest,
        teleoperator: TeleoperatorProfile,
        resolved: ResolvedTargets,
    ) -> SafetyCheck:
        robot = self._robot_profile(request)
        if robot is None:
            return _not_applicable(
                "target.role_distinct",
                "Distinct leader and follower",
                "No follower profile is resolved for this job.",
            )
        distinct = (
            robot.id != teleoperator.id
            and robot.device_fingerprint is not None
            and robot.device_fingerprint != teleoperator.device_fingerprint
        )
        ports_distinct = (
            resolved.robot_port is None
            or resolved.teleop_port is None
            or resolved.robot_port != resolved.teleop_port
        )
        return _check(
            "target.role_distinct",
            "Distinct leader and follower",
            distinct and ports_distinct,
            "The leader and the follower resolve to different devices.",
            "The leader and the follower resolve to the same device.",
        )

    def apply_resolution(
        self,
        request: JobCreateRequest,
        resolved: ResolvedTargets | None,
    ) -> JobCreateRequest:
        """Replace client-supplied command parameters with the resolved ones."""
        if resolved is None:
            return request
        parameters: dict[str, Any] = {
            key: value
            for key, value in request.parameters.items()
            if key not in SERVER_OWNED_PARAMETERS
        }
        parameters.update(resolved.command_parameters())
        return request.model_copy(
            update={
                "parameters": parameters,
                "resources": resolved.resource_requests(request.kind) or request.resources,
            }
        )
