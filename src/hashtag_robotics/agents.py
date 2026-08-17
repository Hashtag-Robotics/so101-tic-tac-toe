from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import DatasetError, DatasetStore, compare_selection
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.doctor import DoctorService
from hashtag_robotics.jobs import JobCoordinator
from hashtag_robotics.models import (
    BENCH_CLAIM_FIELDS,
    PROFILE_OWNED_ELSEWHERE,
    SIM_EQUIVALENT,
    AgentCommandRequest,
    AgentCommandResult,
    AgentSession,
    AuditEvent,
    CalibrationArtifact,
    CameraProfile,
    DatasetManifest,
    JobCreateRequest,
    JobKind,
    PolicyManifest,
    RobotProfile,
    TargetMode,
    new_id,
    preserve_fields,
)
from hashtag_robotics.repository import Repository
from hashtag_robotics.safety import PHYSICAL_JOB_KINDS, PUBLISHING_JOB_KINDS, SafetyService

ROLE_PERMISSIONS = {
    "lab_assistant": {
        "inspect_lab",
        "inspect_jobs",
        "inspect_devices",
        "inspect_robots",
        "inspect_cameras",
        "inspect_calibrations",
        "prepare_discovery",
        # The setup surface, which nothing could reach before. An assistant that
        # can enumerate devices and cannot write down what it found leaves the
        # operator to retype a serial number the assistant just read out.
        #
        # Neither of these moves anything. The fields that are a claim about the
        # bench are refused separately -- see BENCH_CLAIM_FIELDS.
        "save_robot_profile",
        "save_camera_mapping",
    },
    "dataset_curator": {
        "inspect_datasets",
        "inspect_dataset_episodes",
        "inspect_safety",
        "compare_datasets",
        "prepare_dataset_validation",
        "prepare_dataset_transform",
        "prepare_recording",
        "publish_dataset",
    },
    "training_advisor": {
        "inspect_datasets",
        "inspect_policies",
        # Whether two recordings can be trained together is the question that
        # decides what a training run is even possible on, and it was the one
        # thing this role could not find out without a person reading two
        # info.json files side by side.
        "compare_datasets",
        "prepare_training",
    },
    "evaluation_analyst": {
        "inspect_policies",
        "prepare_evaluation",
    },
    "robot_operator": {
        "inspect_lab",
        "inspect_safety",
        "inspect_devices",
        "inspect_robots",
        "inspect_cameras",
        "inspect_calibrations",
        "prepare_teleoperation",
        "prepare_recording",
        "prepare_replay",
        # Asking for a calibration is not performing one. The procedure is a
        # person moving each joint to its stops, and that is exactly why the
        # request is safe to plan: a human is at the bench for the whole of it,
        # and the approval gate is the same one every physical job passes.
        # Withheld at first on the grounds that an agent could not do the work,
        # which confused doing it with asking for it.
        "request_calibration",
        "request_rollout",
        "stop_job",
        # An agent that can start the arm must be able to stop it. There is no
        # matching permission to clear the latch anywhere: stopping is a
        # judgement a model can make, deciding it is over is not.
        "emergency_stop",
    },
}


# What each role is for, in the words of somebody choosing between them.
#
# The page listed five names and a green dot each, which made the most
# consequential choice on it a guess: nothing said what a Dataset Curator was
# for, or why you would pick it over a Lab Assistant. Kept beside the
# permissions rather than in the page, because the answer is "what it can do"
# and that lives here.
ROLE_DESCRIPTIONS = {
    "lab_assistant": (
        "Sets the bench up. Finds what is plugged in, writes down the arms and "
        "cameras, and reads the compatibility report. Touches no joint."
    ),
    "dataset_curator": (
        "Looks after recordings. Opens them take by take, says whether two can "
        "be trained together, joins them, drops the bad ones, and publishes."
    ),
    "training_advisor": (
        "Decides what a training run is possible on, and starts it. Reads "
        "recordings and policies; cannot record and cannot move an arm."
    ),
    "evaluation_analyst": (
        "Measures a trained policy. Reads what has been trained and runs evaluations against it."
    ),
    "robot_operator": (
        "The one that touches the arm. Teleoperation, recording, replay, "
        "calibration and rollouts -- each waiting for a person to approve it. "
        "Can latch the emergency stop; nobody can clear it."
    ),
}


AUDIT_VALUE_LIMIT = 200


def _short(value: Any) -> Any:
    """A parameter as the audit log should keep it.

    Bounded rather than filtered. A whole robot profile or a merge across eighty
    recordings would otherwise put a page into every line, and an audit log
    nobody scrolls is one nobody reads. What is kept is enough to answer which
    recording, which arm, which repository.
    """
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= AUDIT_VALUE_LIMIT else f"{text[:AUDIT_VALUE_LIMIT]}…"


class AgentGateway:
    def __init__(
        self,
        repository: Repository,
        jobs: JobCoordinator,
        doctor: DoctorService,
        safety: SafetyService | None = None,
        settings: Settings | None = None,
        datasets: DatasetStore | None = None,
        discovery: DiscoveryService | None = None,
    ) -> None:
        self.repository = repository
        self.jobs = jobs
        self.doctor = doctor
        # An agent gated on the safety state has to be able to read it; refusing
        # to say whether the stop is latched only makes it guess.
        self.safety = safety if safety is not None else jobs.safety
        self.settings = settings
        # Listing a recording's episodes and asking whether two can be trained
        # together are reads of what is on disk, not of the manifest table, so
        # the store has to be here for the answer to be the current one.
        self.datasets = datasets
        # Same reason for devices: the stored table alone answers with every
        # identity these arms have ever had, all of them still claiming to be
        # plugged in.
        self.discovery = discovery

    def catalogue(self, role: str | None = None) -> list[dict[str, Any]]:
        """What an agent may do, with what, and what it would cost.

        Filtered by role when one is given, so an agent reads its own reach
        rather than the whole surface and then discovering half of it is denied.
        """
        allowed = ROLE_PERMISSIONS.get(role or "", set()) if role else None
        entries: list[dict[str, Any]] = []
        for action, entry in ACTION_CATALOGUE.items():
            if allowed is not None and action not in allowed:
                continue
            kind = entry.get("job_kind")
            entries.append(
                {
                    "action": action,
                    **entry,
                    "creates_job": kind is not None,
                    # The two things an agent most needs to predict: will a human
                    # have to approve this, and can it move a physical joint.
                    #
                    # Publishing counts. It moves no joint, and the preflight
                    # holds it for approval all the same -- something leaving
                    # this machine for a place other people can read is a
                    # decision, not an operation. Reading only PHYSICAL_JOB_KINDS
                    # here would promise an agent that publishing runs
                    # unattended, and it would then wait on a job it was told
                    # would not stop.
                    "needs_human_approval": bool(
                        kind and JobKind(kind) in PHYSICAL_JOB_KINDS | PUBLISHING_JOB_KINDS
                    ),
                    "required": required_parameters(entry),
                    "roles": sorted(
                        name for name, actions in ROLE_PERMISSIONS.items() if action in actions
                    ),
                }
            )
        return entries

    def brief(self, action: str) -> dict[str, Any]:
        """The server's own account of one action, for checking a plan against."""
        return next((item for item in self.catalogue() if item["action"] == action), {})

    async def execute(self, request: AgentCommandRequest) -> AgentCommandResult:
        """Run one command, and record that it ran.

        Job-creating actions left a trail already, because the job carries
        `requested_by`. Everything an agent only *read* left none at all: which
        recordings it listed, which arm it looked up, what it was refused. The
        roadmap asks for every tool call to be traceable, and half of them
        were invisible -- including the refusals, which are the half worth
        having when a plan does something surprising.
        """
        result = await self._execute(request)
        self._record(request, result)
        return result

    def _record(self, request: AgentCommandRequest, result: AgentCommandResult) -> None:
        self.repository.append_audit(
            AuditEvent(
                actor=f"agent:{request.session_id}",
                action=f"agent.{request.action}",
                target=result.job.id if result.job else request.action,
                # A command that made a job shares the job's thread. One that
                # did not gets its own: there is nothing else it belongs to,
                # and reusing the session id would collapse a month of reads
                # into one correlation.
                correlation_id=(result.job.correlation_id if result.job else new_id("agentcmd")),
                outcome="accepted" if result.accepted else "refused",
                details={
                    "parameters": {key: _short(value) for key, value in request.parameters.items()},
                    "message": result.message,
                },
            )
        )

    async def _execute(self, request: AgentCommandRequest) -> AgentCommandResult:
        session = self.repository.get_entity("agent_session", request.session_id, AgentSession)
        if session is None:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message="Agent session was not found.",
            )

        allowed = ROLE_PERMISSIONS.get(session.role, set())
        if request.action not in allowed:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"Role '{session.role}' cannot run '{request.action}'.",
            )

        if request.action == "inspect_lab":
            report = self.doctor.run()
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message="Lab inspection completed without physical access.",
                data=report.model_dump(mode="json"),
            )

        if request.action == "inspect_jobs":
            jobs = self.repository.list_jobs(limit=20)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(jobs)} recent jobs.",
                data={"jobs": [job.model_dump(mode="json") for job in jobs]},
            )

        if request.action == "inspect_safety":
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message="Read the safety state without changing it.",
                data={
                    "emergency_stop_engaged": self.safety.estop_engaged(),
                    "physical_enabled": self.settings.enable_physical,
                    "max_relative_target_ceiling": self.settings.max_relative_target_ceiling,
                    "last_torque_release": self.safety.last_torque_release(),
                },
            )

        if request.action == "emergency_stop":
            affected = await self.jobs.emergency_stop(actor=f"agent:{session.id}")
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=(
                    f"Emergency stop latched; {len(affected)} job(s) stopped and torque "
                    "cut. A human must clear the latch."
                ),
                data={"affected_jobs": [job.id for job in affected]},
            )

        if request.action == "inspect_datasets":
            datasets = self.repository.list_entities("dataset", DatasetManifest)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(datasets)} datasets.",
                data={"datasets": [item.model_dump(mode="json") for item in datasets]},
            )

        if request.action == "inspect_devices":
            if self.discovery is None:
                return AgentCommandResult(
                    accepted=False,
                    action=request.action,
                    message="This installation cannot enumerate devices.",
                )
            # The merged view, the same one the dashboard reads: what is plugged
            # in now, plus what is remembered and gone. Either half alone is
            # misleading -- an agent told only what is connected cannot explain
            # why a stored profile no longer resolves.
            devices = self.discovery.inventory()
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(devices)} device(s), connected or remembered.",
                data={"devices": [item.model_dump(mode="json") for item in devices]},
            )

        if request.action == "inspect_robots":
            robots = self.repository.list_entities("robot", RobotProfile)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(robots)} robot profile(s).",
                data={"robots": [item.model_dump(mode="json") for item in robots]},
            )

        if request.action == "inspect_cameras":
            cameras = self.repository.list_entities("camera", CameraProfile)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(cameras)} camera(s).",
                data={"cameras": [item.model_dump(mode="json") for item in cameras]},
            )

        if request.action == "inspect_calibrations":
            artifacts = self.repository.list_entities("calibration", CalibrationArtifact)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(artifacts)} calibration artifact(s).",
                data={"calibrations": [item.model_dump(mode="json") for item in artifacts]},
            )

        if request.action == "save_robot_profile":
            return self._save_robot(request)

        if request.action == "save_camera_mapping":
            return self._save_camera_mapping(request)

        if request.action == "inspect_dataset_episodes":
            return self._episodes(request)

        if request.action == "compare_datasets":
            return self._compare(request)

        if request.action == "inspect_policies":
            policies = self.repository.list_entities("policy", PolicyManifest)
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message=f"Found {len(policies)} policies.",
                data={"policies": [item.model_dump(mode="json") for item in policies]},
            )

        if request.action == "stop_job":
            job_id = str(request.parameters.get("job_id", ""))
            try:
                job = await self.jobs.cancel(job_id, actor=f"agent:{session.id}")
            except KeyError:
                return AgentCommandResult(
                    accepted=False,
                    action=request.action,
                    message=f"Job '{job_id}' was not found.",
                )
            return AgentCommandResult(
                accepted=True,
                action=request.action,
                message="Stop request passed to the deterministic job coordinator.",
                job=job,
            )

        job_request = self._job_request(session, request.action, request.parameters)
        if job_request is None:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message="The command has no registered deterministic workflow.",
            )
        job = await self.jobs.submit(job_request)
        return AgentCommandResult(
            accepted=job.state.value not in {"blocked", "failed"},
            action=request.action,
            message=(
                "The command was converted to a validated job."
                if job.state.value != "blocked"
                else "The deterministic preflight blocked the command."
            ),
            job=job,
        )

    def _save_robot(self, request: AgentCommandRequest) -> AgentCommandResult:
        """Write down a follower, without letting it vouch for one.

        Two sets of fields are taken back out of whatever the agent sends. The
        calibration binding, because it belongs to the calibration store and a
        profile that overwrites it silently unbinds an arm from the numbers that
        make it safe. And the bench claims -- `joint_limits_verified`,
        `emergency_stop_ready` -- because those are assertions about a room, and
        the agent is not in the room.

        The second set is not load-bearing yet: nothing reads either field. That
        is the argument for doing it now rather than later, when a preflight
        check reads one and inherits an opening nobody chose.
        """
        stored: RobotProfile | None = None
        parameters = dict(request.parameters)
        profile_id = str(parameters.get("id") or "").strip()
        if profile_id:
            stored = self.repository.get_entity("robot", profile_id, RobotProfile)
        merged = {**(stored.model_dump(mode="json") if stored else {}), **parameters}
        try:
            profile = RobotProfile.model_validate(merged)
        except ValidationError as error:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"That is not a usable robot profile: {error.error_count()} problem(s).",
                data={"problems": error.errors(include_url=False, include_input=False)},
            )
        effective = preserve_fields(
            profile, stored, (*PROFILE_OWNED_ELSEWHERE, *BENCH_CLAIM_FIELDS)
        )
        self.repository.upsert_entity("robot", effective)
        refused = sorted(
            name
            for name in (*PROFILE_OWNED_ELSEWHERE, *BENCH_CLAIM_FIELDS)
            if name in parameters and getattr(effective, name) != parameters[name]
        )
        return AgentCommandResult(
            accepted=True,
            action=request.action,
            message=(
                f"Saved robot profile '{effective.name}'."
                + (
                    f" Ignored {', '.join(refused)}: an agent cannot vouch for the bench."
                    if refused
                    else ""
                )
            ),
            data={"robot": effective.model_dump(mode="json"), "ignored_fields": refused},
        )

    def _save_camera_mapping(self, request: AgentCommandRequest) -> AgentCommandResult:
        """Say which camera is the wrist one, on a follower that already exists.

        Separate from saving the profile because it is the field an operator
        actually revisits, and because sending a whole profile to change one
        dictionary invites sending a stale copy of everything else with it.
        """
        profile_id = str(request.parameters.get("robot_profile_id", "")).strip()
        profile = self.repository.get_entity("robot", profile_id, RobotProfile)
        if profile is None:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"No robot profile is registered under id '{profile_id}'.",
            )
        mapping = request.parameters.get("camera_mapping")
        if not isinstance(mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in mapping.items()
        ):
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message="camera_mapping must be an object of {view name: camera id}.",
            )
        known = {camera.id for camera in self.repository.list_entities("camera", CameraProfile)}
        unknown = sorted(set(mapping.values()) - known)
        if unknown:
            # A mapping to a camera that does not exist reads as configured and
            # fails at the recording, by which point the demonstration is gone.
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"No camera is registered under id(s): {', '.join(unknown)}.",
                data={"known_camera_ids": sorted(known)},
            )
        effective = profile.model_copy(update={"camera_mapping": mapping})
        self.repository.upsert_entity("robot", effective)
        return AgentCommandResult(
            accepted=True,
            action=request.action,
            message=f"'{effective.name}' now maps {', '.join(sorted(mapping)) or 'no views'}.",
            data={"robot": effective.model_dump(mode="json")},
        )

    def _episodes(self, request: AgentCommandRequest) -> AgentCommandResult:
        """Which take was the bad one, rather than how many there were.

        An agent that can only read a total cannot act on a ruined episode: it
        knows something is wrong with the recording and has no way to name the
        part. The rows carry the frozen-joint and duplicate markers too, which
        is the whole reason the number matters.
        """
        dataset_id = str(request.parameters.get("dataset_id", "")).strip()
        manifest = self.repository.get_entity("dataset", dataset_id, DatasetManifest)
        if manifest is None:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"No dataset is registered under id '{dataset_id}'.",
            )
        if self.datasets is None or not manifest.repo_id:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message="This recording has no repo id to read from disk.",
            )
        episodes = self.datasets.episodes(manifest.repo_id, manifest.local_path or None)
        return AgentCommandResult(
            accepted=True,
            action=request.action,
            message=(
                f"Read {len(episodes)} episode(s) from disk."
                if episodes
                else (
                    "This recording carries no per-episode metadata, so its "
                    "episodes cannot be listed or removed individually."
                )
            ),
            data={"dataset_id": dataset_id, "episodes": episodes, "readable": bool(episodes)},
        )

    def _compare(self, request: AgentCommandRequest) -> AgentCommandResult:
        """Whether one policy can be trained on all of these at once.

        Not a boolean: LeRobot will not train on more than one dataset, so
        training on both means merging them, and the merge demands identical
        fps, robot_type and features. An agent told only 'no' would go on to
        request the merge anyway, so the answer names the field that differs.
        """
        dataset_ids = [str(item) for item in (request.parameters.get("dataset_ids") or [])]
        selected = [
            self.repository.get_entity("dataset", dataset_id, DatasetManifest)
            for dataset_id in dataset_ids
        ]
        missing = [
            dataset_id
            for dataset_id, manifest in zip(dataset_ids, selected, strict=True)
            if manifest is None
        ]
        if missing:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=f"Unknown dataset id(s): {', '.join(missing)}.",
            )
        if self.datasets is None:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message="This installation cannot read recordings from disk.",
            )
        try:
            report = compare_selection(
                [manifest for manifest in selected if manifest is not None],
                self.datasets,
                self.repository.list_entities("dataset", DatasetManifest),
            )
        except DatasetError as error:
            return AgentCommandResult(
                accepted=False,
                action=request.action,
                message=str(error),
            )
        return AgentCommandResult(
            accepted=True,
            action=request.action,
            message=str(report.get("summary", "")),
            data=report,
        )

    def _job_request(
        self,
        session: AgentSession,
        action: str,
        parameters: dict[str, Any],
    ) -> JobCreateRequest | None:
        parameters = dict(parameters)
        mapping = {
            "prepare_discovery": JobKind.HARDWARE_DISCOVERY,
            "prepare_dataset_validation": JobKind.DATASET_VALIDATE,
            "request_calibration": JobKind.CALIBRATION,
            "prepare_dataset_transform": JobKind.DATASET_TRANSFORM,
            "prepare_recording": JobKind.RECORDING,
            "prepare_replay": JobKind.REPLAY,
            "prepare_training": JobKind.TRAINING,
            "prepare_evaluation": JobKind.EVALUATION,
            "prepare_teleoperation": JobKind.TELEOPERATION,
            "publish_dataset": JobKind.HUB_SYNC,
            "request_rollout": JobKind.POLICY_ROLLOUT,
        }
        kind = mapping.get(action)
        if kind is None:
            return None
        # The default comes from the action's own declared modes rather than a
        # blanket 'sim'. Editing a recording is not simulated, and labelling it
        # that way puts a job in the log claiming a target it never had.
        declared = ACTION_CATALOGUE.get(action, {}).get("target_modes") or ["sim"]
        raw_mode = parameters.pop("target_mode", None) or declared[0]
        target_mode = TargetMode(raw_mode)
        return JobCreateRequest(
            kind=kind,
            target_mode=target_mode,
            parameters=parameters,
            requested_by=f"agent:{session.id}",
        )


# What an agent is allowed to know about what it can do.
#
# Until now the only machine-readable thing was `AgentSession.permissions`: a
# list of bare action names. An agent could learn that it may `prepare_recording`
# and nothing else -- not that the server reads `repo_id`, `task` and `episodes`
# from the parameter bag, not that a real recording needs a human to approve it,
# not that asking in `sim` mode gets a different recorder. All of that lived in
# safety.py and hardware.py, so the only way to drive this dashboard correctly
# was to read its source.
#
# The parameter lists here are the keys the SERVER ACTUALLY READS. Anything else
# in the bag is silently ignored (`parameters` is dict[str, Any]), which is a
# quiet way to lose a whole recording, so they are written down rather than
# inferred.
ACTION_CATALOGUE: dict[str, dict[str, Any]] = {
    "inspect_lab": {
        "summary": "Read the compatibility and capability report for this machine.",
        "reads": True,
        "job_kind": None,
        "returns": "A DoctorReport: overall status, per-check detail, capability manifest.",
    },
    "inspect_jobs": {
        "summary": "List the most recent jobs and their states.",
        "reads": True,
        "job_kind": None,
        "returns": "The twenty most recent JobRecords.",
    },
    "inspect_datasets": {
        "summary": "List the recordings this installation knows about.",
        "reads": True,
        "job_kind": None,
        "returns": "Every DatasetManifest, with episode and frame counts read from disk.",
    },
    "inspect_devices": {
        "summary": "List the devices this machine can see, plus the ones it remembers.",
        "reads": True,
        "job_kind": None,
        "returns": (
            "One DeviceRecord per serial port, camera and simulator, each "
            "saying whether it is connected now or only remembered."
        ),
        "note": (
            "Both halves matter. What is connected alone cannot explain why a "
            "stored profile stopped resolving; what is remembered alone answers "
            "with every identity these arms have ever had, all of them still "
            "claiming to be plugged in."
        ),
    },
    "inspect_robots": {
        "summary": "List the follower arms this installation knows about.",
        "reads": True,
        "job_kind": None,
        "returns": (
            "Every RobotProfile: port, device fingerprint, camera mapping, "
            "safety profile and whether a calibration is bound to it."
        ),
    },
    "inspect_cameras": {
        "summary": "List the cameras this installation knows about.",
        "reads": True,
        "job_kind": None,
        "returns": "Every CameraProfile, with its semantic name and fingerprint.",
        "note": "Metadata, not pictures. There is no action that opens a video stream.",
    },
    "inspect_calibrations": {
        "summary": "List the calibrations on file and what they are bound to.",
        "reads": True,
        "job_kind": None,
        "returns": "Every CalibrationArtifact: role, device, revision and evidence.",
    },
    "save_robot_profile": {
        "summary": "Write down a follower arm, or correct one that is already there.",
        "job_kind": None,
        "parameters": {
            "id": (
                "the profile to update. Leave it out to create one; sending a "
                "blank string is refused rather than silently creating a row "
                "that answers to no URL."
            ),
            "name": "required — what to call this arm",
            "port": "the serial port it answers on",
            "device_fingerprint": "the stable identity, so a replug is not a new arm",
            "robot_type": "LeRobot follower type (default so101_follower)",
            "safety_profile": (
                "an object; the key the preflight reads is max_relative_target, "
                "which is bounded by the server's own ceiling"
            ),
            "camera_mapping": "use save_camera_mapping instead; it checks the ids",
        },
        "note": (
            "Nothing moves. Two sets of fields are taken back out of whatever "
            "is sent:\n"
            "The calibration binding (calibration_revision, motor_layout, "
            "calibration_verified) belongs to the calibration store. A profile "
            "that overwrote it would unbind an arm from the numbers that make "
            "it safe, silently.\n"
            "joint_limits_verified and emergency_stop_ready are claims about a "
            "bench, and an agent is not at the bench. The result says which "
            "fields were ignored rather than dropping them quietly."
        ),
    },
    "save_camera_mapping": {
        "summary": "Say which camera is the wrist view on a follower that already exists.",
        "job_kind": None,
        "parameters": {
            "robot_profile_id": "required — the follower to map",
            "camera_mapping": "required — an object of {view name: camera id}",
        },
        "note": (
            "Every camera id is checked against the registered cameras first. A "
            "mapping to a camera that does not exist reads as configured and "
            "fails at the recording, by which point the demonstration is gone."
        ),
    },
    "inspect_dataset_episodes": {
        "summary": "List the individual takes inside one recording.",
        "reads": True,
        "job_kind": None,
        "parameters": {"dataset_id": "required — the recording to open"},
        "returns": (
            "One row per episode with its frame count, the joints that never "
            "moved during it, and whether it duplicates another episode. Some "
            "recordings carry no per-episode metadata; those answer 'readable: "
            "false' and cannot be edited episode by episode."
        ),
        "note": (
            "The manifest only ever carried a total. An agent that knows a take "
            "was ruined needs to be able to say which take."
        ),
    },
    "compare_datasets": {
        "summary": "Ask whether one policy can be trained on all of these at once.",
        "reads": True,
        "job_kind": None,
        "parameters": {"dataset_ids": "required — two or more recording ids"},
        "returns": (
            "A verdict with reasons: blockers naming the exact field that "
            "differs, warnings that do not prevent a merge, and the combined "
            "episode and frame totals."
        ),
        "note": (
            "LeRobot will not train on more than one dataset, so training on "
            "several means merging them first, and the merge demands identical "
            "fps, robot_type and features. A recording and its simulated "
            "counterpart disagreed here on joint names, units and image axis "
            "order, and nothing raised -- the policy just learned less."
        ),
    },
    "inspect_policies": {
        "summary": "List the trained policies this installation knows about.",
        "reads": True,
        "job_kind": None,
        "returns": "Every PolicyManifest.",
    },
    "inspect_safety": {
        "summary": "Read the safety state every physical action is gated on.",
        "reads": True,
        "job_kind": None,
        "returns": (
            "Whether the emergency stop is latched, whether physical adapters are "
            "enabled, the relative-target ceiling, and what the last torque cut "
            "managed to de-energise."
        ),
    },
    "prepare_discovery": {
        "summary": "Enumerate connected devices without touching them.",
        "job_kind": "hardware_discovery",
        "target_modes": ["read_only", "sim"],
        "parameters": {},
    },
    "prepare_dataset_validation": {
        "summary": "Re-read a recording from disk and grade its integrity.",
        "job_kind": "dataset_validate",
        "target_modes": ["read_only"],
        "parameters": {"dataset_id": "required — the manifest to re-read"},
    },
    "prepare_dataset_transform": {
        "summary": "Join recordings into one, or write a copy without the bad takes.",
        "job_kind": "dataset_transform",
        "target_modes": ["read_only"],
        "parameters": {
            "operation": "required — 'merge' or 'remove_episodes'",
            "dataset_ids": (
                "required — the recordings to read. Merge takes two or more; "
                "remove_episodes reads the first and ignores the rest."
            ),
            "new_name": "required for a merge — what to call the result",
            "episodes": "remove_episodes only — the episode indices to drop",
        },
        "note": (
            "Always writes a new recording; nothing is edited in place and the "
            "originals stay where they were. Calling a take ruined is a "
            "judgement, and a judgement should be reversible.\n"
            "Merging re-encodes video and takes minutes on this board. It "
            "cannot be interrupted once the write starts -- the stop is checked "
            "before it begins, not during -- so a cancel that arrives late will "
            "not land.\n"
            "Merging a set with a recording it already contains does not fail: "
            "the frames are copied twice and the result still grades verified. "
            "Ask compare_datasets first; the overlap comes back as a warning."
        ),
    },
    "publish_dataset": {
        "summary": "Upload a recording to the Hub, where the machine that trains can reach it.",
        "job_kind": "hub_sync",
        "target_modes": ["read_only"],
        "parameters": {
            "dataset_id": "required — the recording to send",
            "repo_id": (
                "where to send it, as 'namespace/name'. Defaults to the "
                "recording's own repo id, which is often not namespaced and "
                "will be rejected before anything uploads."
            ),
            "private": "keep the repository private (default true)",
            "push_videos": "send the video files too (default true)",
            "dry_run": (
                "report what would be sent and send nothing. Measure first: an "
                "upload here is hundreds of megabytes over whatever this board "
                "is connected to."
            ),
        },
        "note": (
            "A human approves this unless dry_run is set. Nothing moves, but "
            "something leaving this machine for a place other people can read "
            "is a decision rather than an operation.\n"
            "The preflight refuses a recording that is not 'verified': "
            "publishing a broken one puts it somewhere others can take it."
        ),
    },
    "prepare_recording": {
        "summary": "Record demonstrations, on the real arm or in simulation.",
        "job_kind": "recording",
        "target_modes": ["sim", "real"],
        "parameters": {
            "repo_id": "required — dataset name, e.g. mertkirgil/so101_cube",
            "task": "required — the instruction the episodes demonstrate",
            "episodes": "how many episodes to record (default 1)",
            "episode_time_s": "seconds per episode",
            "robot_profile_id": "required in real mode — which follower",
            "teleoperator_profile_id": "required — which leader drives it",
            "workspace_confirmed": (
                "real mode only — a human's judgement that the workspace is clear. "
                "An agent asserting this about itself is asserting something it "
                "cannot see."
            ),
        },
        "note": (
            "In sim mode the server rewrites this to a simulated recording: the "
            "follower is never opened and the leader is only read, so nothing can "
            "move. In real mode the arm moves and a human must approve first."
        ),
    },
    "request_calibration": {
        "summary": "Ask for a guided calibration of a follower or leader arm.",
        "job_kind": "calibration",
        "target_modes": ["real"],
        "parameters": {
            "role": "'robot' (default) or 'teleoperator' — which arm to calibrate",
            "robot_profile_id": "required for a follower",
            "teleoperator_profile_id": "required for a leader",
            "workspace_confirmed": (
                "a human's judgement that the workspace is clear. An agent "
                "asserting this about itself is asserting something it cannot "
                "see."
            ),
        },
        "note": (
            "Asking is not performing. The procedure is a person moving each "
            "joint to its stops while the command prompts them, so a human is "
            "at the bench for the whole of it and approves it first.\n"
            "The result is written by the calibration store, not by this job's "
            "parameters. There is no action that marks an arm calibrated."
        ),
    },
    "prepare_replay": {
        "summary": "Play one recorded episode back onto the follower.",
        "job_kind": "replay",
        "target_modes": ["real"],
        "parameters": {
            "repo_id": "required — the recording to play back",
            "episode": "which episode (default 0)",
            "fps": "playback rate (default 30)",
            "dataset_root": "read the recording from here instead of the Hub cache",
            "robot_profile_id": "required — which follower",
            "workspace_confirmed": (
                "a human's judgement that the workspace is clear. An agent "
                "asserting this about itself is asserting something it cannot "
                "see."
            ),
        },
        "note": (
            "There is no simulated mode. Replay drives recorded joint targets "
            "at speed with no leader in the loop and no observation recorded, "
            "so the arm moves through a trajectory nobody is holding. A human "
            "approves it, as with any real actuation."
        ),
    },
    "prepare_teleoperation": {
        "summary": "Drive the follower (or the simulation) from the leader arm.",
        "job_kind": "teleoperation",
        "target_modes": ["sim", "real"],
        "parameters": {
            "robot_profile_id": "required in real mode",
            "teleoperator_profile_id": "required",
            "workspace_confirmed": "real mode only — a human judgement",
        },
    },
    "prepare_training": {
        "summary": "Train a policy from a recorded dataset.",
        "job_kind": "training",
        "target_modes": ["sim"],
        "parameters": {
            "repo_id": "required — the dataset to train on",
            "policy_type": "act | smolvla | ... (default act)",
            "steps": "training steps",
            "output_dir": "where checkpoints land",
        },
    },
    "prepare_evaluation": {
        "summary": "Run a trained policy and collect its result distribution.",
        "job_kind": "evaluation",
        "target_modes": ["sim", "real"],
        "parameters": {
            "policy_id": "required — the policy to evaluate",
            "episodes": "how many episodes",
            "robot_profile_id": "required in real mode",
        },
    },
    "request_rollout": {
        "summary": "Run a policy on the arm under the configured limits.",
        "job_kind": "policy_rollout",
        "target_modes": ["sim", "real"],
        "parameters": {
            "policy_id": "required",
            "robot_profile_id": "required in real mode",
            "workspace_confirmed": "real mode only — a human judgement",
        },
    },
    "stop_job": {
        "summary": "Stop a running job safely.",
        "job_kind": None,
        "parameters": {"job_id": "required"},
    },
    "emergency_stop": {
        "summary": "Latch the emergency stop, kill every running command and cut torque.",
        "job_kind": None,
        "parameters": {},
        "note": (
            "There is deliberately no matching action to clear it. An agent may "
            "stop the arm and may not decide the situation is over; a human has "
            "to look at the bench and release the latch."
        ),
    },
}


# Everything this server can run that no agent may ask for, and why not.
#
# The catalogue is written by hand, so it only ever describes the actions
# somebody remembered to add. Nine job kinds accumulated on the other side of
# it -- publishing to the Hub, merging recordings, calibration -- and no test
# noticed, because the only guarantee was that granted permissions are
# *documented*, never that the server's capabilities are *accounted for*.
#
# So every JobKind now has to appear on one side or the other. Adding a kind
# without deciding whether an agent may reach it fails the coverage test, and
# the decision is written here rather than inferred from an absence. A reason
# of "not offered yet" is a legitimate answer; silence is not.
UNEXPOSED_JOB_KINDS: dict[JobKind, str] = {
    JobKind.POLICY_IMPORT: (
        "Withheld. Imports may download large remote checkpoints and require "
        "private Hub credentials, so an operator must choose the repository "
        "and revision explicitly through the local policy surface."
    ),
    JobKind.MOTOR_SETUP: (
        "Withheld. Writes servo ids and baud rates onto a live bus, where a "
        "wrong id leaves an arm that no longer answers and the recovery is "
        "physical."
    ),
    JobKind.CAMERA_PREVIEW: (
        "Withheld. Produces a video stream for somebody to look at, not a "
        "result an agent can read. inspect_cameras answers what an agent can "
        "act on, which is the metadata."
    ),
    JobKind.SIMULATION: (
        "Withheld. A deterministic contract mock that touches no bench. What "
        "an agent needs from simulation is the sim target of teleoperation and "
        "recording, which it has."
    ),
    JobKind.REMOTE_INFERENCE_PROBE: (
        "Withheld while it is a mock. The workflow validates the URL scheme and "
        "then returns fixed latencies with network_access_performed false, so "
        "an agent offered this would be handed invented numbers and no way to "
        "tell. Expose it when it measures something."
    ),
    JobKind.DIAGNOSTICS: (
        "Withheld as redundant. inspect_lab already returns the doctor report "
        "this produces, without creating a job to do it."
    ),
}


def required_parameters(entry: dict[str, Any]) -> list[str]:
    """The parameters an action needs whatever mode it runs in.

    Read off the hints rather than kept in a list beside them. A second list is
    a second thing to forget, and this file spent months proving that a
    hand-maintained copy of something drifts from it silently. The prose is what
    a person reads and what an agent is shown, so the prose is the source.

    Three prefixes and they mean different things:
      'required — '          always, so a plan without it will block
      'required in real mode' only when a joint would move
      'required for a merge'  only for one value of another parameter
    Only the first is returned. The conditional ones cannot be checked without
    knowing the request, and reporting them as missing would teach an agent to
    ignore the warning.
    """
    return sorted(
        key
        for key, hint in (entry.get("parameters") or {}).items()
        if hint.startswith("required") and not hint.startswith(("required in", "required for"))
    )


def reachable_job_kinds() -> set[JobKind]:
    """Every job kind some role can actually cause, sim rewrites included.

    An action nobody is granted is not reach, and a catalogue entry is not the
    whole story either: asking to record in `sim` becomes a `sim_recording`
    inside `JobCreateRequest`, so the kind an agent names is not always the
    kind that runs.
    """
    granted = {action for actions in ROLE_PERMISSIONS.values() for action in actions}
    kinds: set[JobKind] = set()
    for action, entry in ACTION_CATALOGUE.items():
        raw = entry.get("job_kind")
        if raw is None or action not in granted:
            continue
        kind = JobKind(raw)
        kinds.add(kind)
        if "sim" in entry.get("target_modes", ()) and kind in SIM_EQUIVALENT:
            kinds.add(SIM_EQUIVALENT[kind])
    return kinds
