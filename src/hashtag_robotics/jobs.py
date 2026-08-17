from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from hashtag_robotics.calibration import CalibrationError, CalibrationStore
from hashtag_robotics.hardware import LeRobotCliAdapter, PhysicalExecutionError
from hashtag_robotics.models import (
    ApprovalStatus,
    AuditEvent,
    EpisodeAnnotation,
    JobCreateRequest,
    JobInputKey,
    JobKind,
    JobRecord,
    JobState,
    RobotProfile,
    TargetMode,
    utc_now,
)
from hashtag_robotics.process import reap_orphan
from hashtag_robotics.repository import Repository, ResourceBusyError
from hashtag_robotics.safety import SafetyService, parameter_hash
from hashtag_robotics.tic_tac_toe import (
    TicTacToePresetError,
    canonical_tic_tac_toe_parameters,
    is_tic_tac_toe_parameters,
)
from hashtag_robotics.workflows import WorkflowCancelled, WorkflowEngine

TERMINAL_STATES = {
    JobState.BLOCKED,
    JobState.COMPLETED,
    JobState.FAILED,
    JobState.ABORTED,
    JobState.INTERRUPTED,
}

EPISODE_KEYS = {
    JobInputKey.END_EPISODE,
    JobInputKey.RERECORD_EPISODE,
    JobInputKey.STOP_RECORDING,
}

ANNOTATABLE_JOB_KINDS = {JobKind.EVALUATION, JobKind.POLICY_ROLLOUT, JobKind.RECORDING}

# Jobs an emergency stop still has something to say to.
STOPPABLE_STATES = {
    JobState.QUEUED,
    JobState.STARTING,
    JobState.RUNNING,
    JobState.STOPPING,
    JobState.AWAITING_CONFIRMATION,
}

# Deliberately shorter than `ManagedProcess.stop`'s own default, and the
# difference is load-bearing rather than incidental.
#
# `terminate_group` escalates SIGINT -> SIGTERM -> SIGKILL. SIGINT raises
# KeyboardInterrupt inside LeRobot, whose `finally` disconnects the arm and
# disables torque; a plain cancel waits long enough for that to happen, which is
# why cancelling already left the arm limp. Measured on the bench, an emergency
# stop does not: the audit record read `SIGTERM`, meaning the half second
# elapsed with the process still alive and Python then terminated it without
# running `finally`. LeRobot's own teardown never ran, and the explicit torque
# cut in `safety.release_torque` was the only thing that de-energised the arm.
#
# Raise this value and the arm gets de-energised by LeRobot again, quietly
# making the torque cut look redundant -- until someone removes it. Lower it and
# nothing breaks; the cut does not depend on the grace at all.
ESTOP_GRACE_SECONDS = 0.5

JOB_INPUT_KEYS: dict[JobKind, set[JobInputKey]] = {
    JobKind.CALIBRATION: {
        JobInputKey.ENTER,
        JobInputKey.USE_EXISTING_CALIBRATION,
        JobInputKey.RECALIBRATE,
    },
    JobKind.MOTOR_SETUP: {JobInputKey.ENTER},
    JobKind.RECORDING: EPISODE_KEYS,
    # The simulated recorder listens for the same escape sequences, so one set
    # of buttons drives both. It was left out and a simulated session could
    # only be cancelled, which kills the process and loses the take in progress.
    JobKind.SIM_RECORDING: EPISODE_KEYS,
    JobKind.EVALUATION: EPISODE_KEYS,
    JobKind.POLICY_ROLLOUT: EPISODE_KEYS,
}


def apply_server_defaults(
    request: JobCreateRequest,
    repository: Repository,
) -> JobCreateRequest:
    """Fill in what the server decides, before anyone previews or runs it.

    Which cameras a simulated take renders is one of these. Simulated episodes
    exist here to be trained beside real ones and a merge needs identical
    features, so rendering a view the bench does not have produces
    demonstrations that are perfectly good and permanently unmergeable -- which
    is only discovered later, at the merge. The default therefore follows the
    arm: whatever the physical follower maps.

    This lives beside `submit` rather than in the HTTP layer because it was in
    the HTTP layer, and the agent gateway submits jobs without going through it.
    An agent recording in simulation got no cameras at all, which is the exact
    failure the default exists to prevent, arriving through the one door nobody
    was watching. `JobCreateRequest._resolve_simulated_kind` already made the
    argument: the correction belongs where every door passes, not at each door.

    The preview endpoint calls this too, and has to. It promises the command the
    server would actually run, and a default applied only on submission would
    make that promise false in exactly the case it matters -- the operator reads
    the command, sees no camera flag, and gets one anyway.
    """
    if request.kind == JobKind.POLICY_ROLLOUT and is_tic_tac_toe_parameters(request.parameters):
        try:
            parameters = canonical_tic_tac_toe_parameters(request.parameters)
        except TicTacToePresetError:
            # Preflight owns user-facing validation. Keeping the invalid move in
            # the request lets it produce a blocked check instead of turning a
            # preview or job submission into an unhandled server error.
            return request
        return request.model_copy(update={"parameters": parameters})

    if request.kind != JobKind.SIM_RECORDING or request.parameters.get("cameras"):
        return request
    mapped = [
        profile
        for profile in repository.list_entities("robot", RobotProfile)
        if profile.camera_mapping and profile.port and not profile.id.startswith("robot_sim")
    ]
    if not mapped:
        return request
    cameras = ",".join(sorted(mapped[0].camera_mapping))
    return request.model_copy(update={"parameters": {**request.parameters, "cameras": cameras}})


class JobCoordinator:
    def __init__(
        self,
        repository: Repository,
        safety: SafetyService,
        workflows: WorkflowEngine,
        hardware: LeRobotCliAdapter,
        calibration: CalibrationStore,
    ) -> None:
        self.repository = repository
        self.safety = safety
        self.workflows = workflows
        self.hardware = hardware
        self.calibration = calibration
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._cancelled: set[str] = set()
        self._stop_reason: dict[str, str] = {}
        self._last_input: dict[str, float] = {}

    async def start(self) -> None:
        await self._reap_orphans()
        self.repository.recover_incomplete_jobs()
        self._worker = asyncio.create_task(self._worker_loop(), name="hashtag-job-worker")

    async def _reap_orphans(self) -> None:
        for job in self.repository.list_jobs(limit=10_000):
            if job.process is None:
                continue
            details = {"pid": job.process.pid, "pgid": job.process.pgid}
            outcome = await reap_orphan(job.process)
            job.process = None
            self.repository.update_job(job)
            self.repository.append_audit(
                AuditEvent(
                    actor="control-plane",
                    action="job.reap",
                    target=job.id,
                    correlation_id=job.correlation_id,
                    outcome=outcome,
                    details=details,
                )
            )

    async def stop(self) -> None:
        for job in self.repository.list_jobs(limit=500):
            if job.state == JobState.RUNNING:
                self._cancelled.add(job.id)
        await self.hardware.stop_all()
        await self._queue.put(None)
        if self._worker is not None:
            try:
                await asyncio.wait_for(self._worker, timeout=20)
            except TimeoutError:
                self._worker.cancel()
            self._worker = None

    async def submit(self, request: JobCreateRequest) -> JobRecord:
        request = apply_server_defaults(request, self.repository)
        preflight = self.safety.preflight(request)
        effective = self.safety.apply_resolution(request, preflight.resolved)
        job = JobRecord(
            kind=effective.kind,
            target_mode=effective.target_mode,
            parameters=effective.parameters,
            resources=effective.resources,
            requested_by=effective.requested_by,
            resolved_targets=preflight.resolved,
            state=JobState.VALIDATING,
            message="Running deterministic preflight",
        )
        self.repository.create_job(job)
        job.result["preflight"] = preflight.model_dump(mode="json")

        if not preflight.allowed:
            job.state = JobState.BLOCKED
            job.message = "Blocked by deterministic preflight"
            job.error_code = "preflight_blocked"
            job.error_message = "; ".join(
                check.message for check in preflight.checks if check.status.value == "blocked"
            )
        elif preflight.requires_approval:
            approval = self.safety.create_approval(job.id, effective, preflight.resolved)
            self.repository.create_approval(approval)
            job.approval_id = approval.id
            job.state = JobState.AWAITING_CONFIRMATION
            job.message = "Waiting for explicit physical actuation approval"
        else:
            job.state = JobState.QUEUED
            job.message = "Queued"

        self.repository.update_job(job)
        self._audit(job, "job.submit", job.state.value)
        if job.state == JobState.QUEUED:
            await self._queue.put(job.id)
        return job

    async def confirm(self, job_id: str, approval_id: str) -> JobRecord:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state != JobState.AWAITING_CONFIRMATION or job.approval_id != approval_id:
            raise ValueError("The job is not waiting for this approval.")

        approval = self.repository.get_approval(approval_id)
        if approval is None:
            raise ValueError("Approval was not found.")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is '{approval.status.value}'.")
        if approval.expires_at <= datetime.now(UTC):
            self.repository.expire_approval(approval)
            raise ValueError("Approval expired.")

        request = JobCreateRequest(
            kind=job.kind,
            target_mode=job.target_mode,
            parameters=job.parameters,
            resources=job.resources,
            requested_by=job.requested_by,
        )
        if approval.parameters_hash != parameter_hash(request):
            raise ValueError("Job parameters changed after approval was created.")

        preflight = self.safety.preflight(request)
        current_targets = preflight.resolved.digest() if preflight.resolved else None
        if not preflight.allowed:
            job.state = JobState.BLOCKED
            job.error_code = "preflight_changed"
            job.error_message = "The safety preflight no longer permits this job."
            job.message = "Blocked after approval revalidation"
        elif approval.targets_hash != current_targets:
            job.state = JobState.BLOCKED
            job.error_code = "targets_changed"
            job.error_message = (
                "The resolved physical targets changed after the approval was created."
            )
            job.message = "Blocked because the approved targets no longer match"
            job.resolved_targets = preflight.resolved
        else:
            approval.status = ApprovalStatus.CONFIRMED
            approval.confirmed_at = utc_now()
            self.repository.update_approval(approval)
            job.state = JobState.QUEUED
            job.message = "Approved and queued"
            await self._queue.put(job.id)

        self.repository.update_job(job)
        self._audit(job, "job.confirm", job.state.value)
        return job

    async def cancel(
        self,
        job_id: str,
        actor: str = "local-user",
        reason: str = "operator_cancelled",
    ) -> JobRecord:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state in TERMINAL_STATES:
            return job

        self._cancelled.add(job_id)
        self._stop_reason[job_id] = reason
        emergency = reason == "emergency_stop"
        if job.state in {
            JobState.CREATED,
            JobState.VALIDATING,
            JobState.AWAITING_CONFIRMATION,
            JobState.QUEUED,
        }:
            job.state = JobState.ABORTED
            job.error_code = reason
            job.message = "Aborted by emergency stop" if emergency else "Cancelled before execution"
            self.repository.release_leases(job.id)
        else:
            job.state = JobState.STOPPING
            job.message = "Stopping under emergency stop" if emergency else "Stopping safely"
        self.repository.update_job(job)
        self._audit(job, "job.estop" if emergency else "job.cancel", job.state.value, actor=actor)
        return job

    async def send_input(
        self,
        job_id: str,
        key: JobInputKey,
        actor: str = "local-user",
    ) -> JobRecord:
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state != JobState.RUNNING:
            raise ValueError(f"Job is '{job.state.value}'; operator input needs a running job.")
        if job.process is None or not job.process.pty:
            raise ValueError("This command does not accept operator input.")
        if key not in JOB_INPUT_KEYS.get(job.kind, set()):
            raise ValueError(f"'{key.value}' is not accepted by a '{job.kind.value}' job.")
        if job.approval_id is not None:
            approval = self.repository.get_approval(job.approval_id)
            active = {ApprovalStatus.CONFIRMED, ApprovalStatus.CONSUMED}
            if approval is None or approval.status not in active:
                raise ValueError("The physical approval for this job is not active.")

        now = asyncio.get_running_loop().time()
        minimum = self.hardware.settings.input_min_interval_ms / 1000
        if now - self._last_input.get(job_id, 0.0) < minimum:
            raise ValueError("Operator input is arriving faster than the safe interval.")
        self._last_input[job_id] = now

        previous_control = self.hardware.latest_control_ack(job_id)
        try:
            self.hardware.send_input(job_id, key)
        except PhysicalExecutionError as error:
            raise ValueError(str(error)) from error

        if key in EPISODE_KEYS:
            acknowledged = await self.hardware.wait_for_control_ack(
                job_id,
                key,
                str(previous_control.get("at")) if previous_control else None,
            )
            if acknowledged is None:
                self._audit(job, "job.input_unacknowledged", key.value, actor=actor)
                raise ValueError(
                    f"'{key.value}' recorder kanalına iletildi ancak recorder 2 saniye "
                    "içinde uyguladığını doğrulamadı. Körlemesine tekrar göndermeyin; "
                    "kayıt durumunu kontrol edin."
                )
        self._audit(job, "job.input", key.value, actor=actor)
        return job

    async def annotate(
        self,
        job_id: str,
        annotation: EpisodeAnnotation,
        actor: str = "local-user",
    ) -> JobRecord:
        """Record the operator's verdict for one episode and recompute the rate."""
        job = self.repository.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.kind not in ANNOTATABLE_JOB_KINDS:
            raise ValueError(f"A '{job.kind.value}' job has no episodes to annotate.")

        outcomes = [
            item
            for item in job.result.get("episode_outcomes", [])
            if item.get("episode") != annotation.episode
        ]
        outcomes.append(annotation.model_dump(mode="json"))
        outcomes.sort(key=lambda item: item["episode"])

        successes = len([item for item in outcomes if item["outcome"] == "success"])
        job.result["episode_outcomes"] = outcomes
        job.result["evaluation"] = {
            "annotated": len(outcomes),
            "successes": successes,
            "failures": len(outcomes) - successes,
            "success_rate": round(successes / len(outcomes), 4) if outcomes else None,
            "source": "operator-annotation",
        }
        self.repository.update_job(job)
        self._audit(
            job, "job.annotate", f"{annotation.episode}:{annotation.outcome.value}", actor=actor
        )
        return job

    async def emergency_stop(self, actor: str = "local-user") -> list[JobRecord]:
        """Latch the stop, kill every process group, cut torque, then abort the jobs.

        The latch is persisted first so a crash between the kill and the abort
        still leaves physical work blocked on the next start.

        Torque is cut after the kill and before the bookkeeping, in that order
        for a reason. Before the kill, a live LeRobot process still owns the
        serial port and would re-enable torque on its next write; after the
        bookkeeping, the operator would have waited for database work while the
        arm was still holding its last commanded position.
        """
        self.safety.engage_estop(actor)
        claimed = self._claim_running_jobs()
        stopped = await self.hardware.stop_all(grace_seconds=ESTOP_GRACE_SECONDS)
        released = await self.safety.release_torque(actor)

        affected: list[JobRecord] = []
        seen: set[str] = set()
        for job in self.repository.list_jobs(limit=500):
            if job.id in seen:
                continue
            if job.state in STOPPABLE_STATES:
                seen.add(job.id)
                affected.append(await self.cancel(job.id, actor=actor, reason="emergency_stop"))
            elif job.id in claimed:
                # Already finished dying while the torque was being cut. It is
                # still a job this stop stopped, and leaving it out of the record
                # is how an emergency stop ends up with nothing attributed to it.
                seen.add(job.id)
                affected.append(job)
        event = AuditEvent(
            actor=actor,
            action="safety.emergency_stop",
            target="all-active-jobs",
            correlation_id="emergency-stop",
            outcome="triggered",
            details={
                "affected_jobs": [job.id for job in affected],
                "stopped_processes": stopped,
                "torque_released": [result.model_dump(mode="json") for result in released],
                # None, not True, when there was no physical arm to de-energise:
                # "nothing to cut" and "everything cut" are different answers.
                "arms_de_energised": (
                    all(result.released for result in released) if released else None
                ),
            },
        )
        self.repository.append_audit(event)
        return affected

    def _claim_running_jobs(self) -> set[str]:
        """Name the jobs this stop is about to kill, before it kills them.

        `_run_job` tells "aborted by emergency stop" apart from "workflow failed"
        by asking whether the job is in `_cancelled` when its process dies. The
        process dies during `stop_all`, well before the bookkeeping loop below
        can reach it -- so on the bench the operator got a bare `failed` job and
        an audit record whose `affected_jobs` was empty. The stop had stopped
        something and the trail did not say what.

        Claiming from the live process table costs two in-memory writes and no
        database read, so nothing is delayed by it.
        """
        claimed = set(self.hardware.processes)
        for job_id in claimed:
            self._cancelled.add(job_id)
            self._stop_reason[job_id] = "emergency_stop"
        return claimed

    async def clear_emergency_stop(self, actor: str = "local-user") -> bool:
        """Release the latch. Cancelled jobs are never resumed by this."""
        was_engaged = self.safety.estop_engaged()
        self.safety.clear_estop()
        self.repository.append_audit(
            AuditEvent(
                actor=actor,
                action="safety.clear_emergency_stop",
                target="emergency-stop-latch",
                correlation_id="emergency-stop",
                outcome="cleared" if was_engaged else "already-clear",
                details={},
            )
        )
        return was_engaged

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            if job_id is None:
                self._queue.task_done()
                break
            try:
                await self._run_job(job_id)
            finally:
                self._queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if job is None or job.state != JobState.QUEUED:
            return

        try:
            job.state = JobState.STARTING
            job.message = "Acquiring resource leases"
            self.repository.update_job(job)
            self.repository.acquire_leases(job.id, job.resources)

            backup_id = self._backup_calibration(job)
            if backup_id:
                job.result["calibration_backup_id"] = backup_id
                self._audit(job, "calibration.backup", backup_id)

            if job.approval_id:
                approval = self.repository.get_approval(job.approval_id)
                if approval and approval.status == ApprovalStatus.CONFIRMED:
                    approval.status = ApprovalStatus.CONSUMED
                    self.repository.update_approval(approval)

            job.state = JobState.RUNNING
            job.message = "Running"
            self.repository.update_job(job)
            self._audit(job, "job.start", "running")

            async def progress(value: float, message: str) -> None:
                current = self.repository.get_job(job.id)
                if current is None:
                    return
                current.progress = value
                current.message = message
                self.repository.update_job(current)
                self.repository.heartbeat_leases(job.id)

            result = await self.workflows.execute(
                job,
                progress=progress,
                cancelled=lambda: job.id in self._cancelled,
            )
            job = self.repository.get_job(job.id) or job
            job.state = JobState.COMPLETED
            job.progress = 1.0
            job.message = "Completed"
            job.result.update(result)
            self.repository.update_job(job)
            self._audit(job, "job.complete", "completed")
        except WorkflowCancelled as error:
            job = self.repository.get_job(job.id) or job
            job.state = JobState.ABORTED
            job.message = "Stopped safely"
            job.error_code = "operator_cancelled"
            job.error_message = str(error)
            job.result.update(self.workflows.salvage_recording(job))
            self.repository.update_job(job)
            self._audit(job, "job.abort", "aborted")
        except ResourceBusyError as error:
            job.state = JobState.BLOCKED
            job.message = "Required resource is busy"
            job.error_code = "resource_busy"
            job.error_message = str(error)
            self.repository.update_job(job)
            self._audit(job, "job.block", "resource_busy")
        except CalibrationError as error:
            job.state = JobState.BLOCKED
            job.message = "The calibration backup failed, so nothing was started"
            job.error_code = "calibration_backup_failed"
            job.error_message = str(error)
            self.repository.update_job(job)
            self._audit(job, "job.block", "calibration_backup_failed")
        except Exception as error:
            job = self.repository.get_job(job.id) or job
            operator_stop = job.id in self._cancelled
            reason = self._stop_reason.get(job.id, "operator_cancelled")
            job.state = JobState.ABORTED if operator_stop else JobState.FAILED
            # "Stopped safely" reads as a clean shutdown; an emergency stop is
            # not one, and the operator needs to see which of the two happened.
            job.message = (
                "Aborted by emergency stop"
                if reason == "emergency_stop" and operator_stop
                else "Stopped safely"
                if operator_stop
                else "Workflow failed safely"
            )
            job.error_code = reason if operator_stop else "workflow_failed"
            job.error_message = str(error)
            # Whatever the run wrote before it stopped is on disk either way;
            # without this it stays there unregistered and unreachable from the
            # panel, which is the same as losing it.
            job.result.update(self.workflows.salvage_recording(job))
            self.repository.update_job(job)
            self._audit(job, "job.abort" if operator_stop else "job.fail", job.state.value)
        finally:
            self.repository.release_leases(job.id)
            self._cancelled.discard(job.id)
            self._stop_reason.pop(job.id, None)

    def _backup_calibration(self, job: JobRecord) -> str | None:
        """Archive the live calibration before a real calibration overwrites it."""
        if job.target_mode != TargetMode.REAL or job.kind != JobKind.CALIBRATION:
            return None
        targets = job.resolved_targets
        if targets is None:
            return None
        if str(job.parameters.get("role", "robot")) == "teleoperator":
            device_type, device_id = targets.teleop_type, targets.teleop_id
            profile_id = targets.teleoperator_profile_id
        else:
            device_type, device_id = targets.robot_type, targets.robot_id
            profile_id = targets.robot_profile_id
        if not device_type or not device_id:
            return None
        artifact = self.calibration.backup(device_type, device_id, target_profile_id=profile_id)
        return artifact.id if artifact else None

    def _audit(
        self,
        job: JobRecord,
        action: str,
        outcome: str,
        actor: str | None = None,
    ) -> None:
        self.repository.append_audit(
            AuditEvent(
                actor=actor or job.requested_by,
                action=action,
                target=job.id,
                correlation_id=job.correlation_id,
                outcome=outcome,
                details={
                    "kind": job.kind.value,
                    "target_mode": job.target_mode.value,
                },
            )
        )
