from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from hashtag_robotics.calibration import CalibrationError, CalibrationStore, compare_motors
from hashtag_robotics.camera import CameraService
from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import (
    STATUS_INCOMPLETE,
    STATUS_MISSING,
    STATUS_VERIFIED,
    DatasetError,
    DatasetStore,
    lineage_overlaps,
)
from hashtag_robotics.discovery import DiscoveryService
from hashtag_robotics.doctor import diagnostics_payload
from hashtag_robotics.hardware import LeRobotCliAdapter
from hashtag_robotics.models import (
    CalibrationSource,
    CameraProfile,
    DatasetManifest,
    JobCreateRequest,
    JobKind,
    JobRecord,
    RobotProfile,
    SimulationScenario,
    TeleoperatorProfile,
)
from hashtag_robotics.policy import PolicyError, PolicyStore
from hashtag_robotics.repository import Repository
from hashtag_robotics.simulation import MujocoAdapter

# What a dataset transform is allowed to be. Both write a NEW recording and
# leave the sources untouched, which is why they can be one job kind: the
# operator is never editing something they might still need.
DATASET_OPERATIONS = {"merge", "remove_episodes"}

# What a manifest calls the thing that produced its frames. Two recorders write
# the same schema on purpose, so this string is the only place left that says
# whether they came from a motor or a model -- and the dashboard colours a tag
# from it, which is why it lives in one named place instead of two literals.
RECORDING_SOURCE = {
    JobKind.SIM_RECORDING: "simulation",
    JobKind.RECORDING: "real-arm",
}

ProgressCallback = Callable[[float, str], Awaitable[None]]
CancelCheck = Callable[[], bool]


WORKFLOW_STEPS: dict[JobKind, list[str]] = {
    JobKind.HARDWARE_DISCOVERY: [
        "Inspecting serial devices",
        "Resolving stable fingerprints",
        "Publishing capability inventory",
    ],
    JobKind.MOTOR_SETUP: [
        "Validating target profile",
        "Preparing motor setup plan",
        "Verifying resulting motor map",
    ],
    JobKind.CALIBRATION: [
        "Backing up the active calibration",
        "Preparing calibration ranges",
        "Validating the calibration artifact",
    ],
    JobKind.CAMERA_PREVIEW: [
        "Resolving the camera profile",
        "Checking frame timing",
        "Publishing preview metadata",
    ],
    JobKind.TELEOPERATION: [
        "Acquiring robot and teleoperator leases",
        "Starting the safe control loop",
        "Checking latency and watchdog",
        "Stopping the control loop safely",
    ],
    JobKind.RECORDING: [
        "Validating recording schema",
        "Preparing episode storage",
        "Capturing simulated episode data",
        "Writing the dataset manifest",
        "Running integrity checks",
    ],
    JobKind.REPLAY: [
        "Validating episode action shape",
        "Preparing replay limits",
        "Replaying in the selected target mode",
        "Stopping safely",
    ],
    JobKind.DATASET_VALIDATE: [
        "Reading dataset metadata",
        "Checking feature and camera schema",
        "Checking episode integrity",
        "Updating the dataset manifest",
    ],
    JobKind.DATASET_TRANSFORM: [
        "Creating an immutable source revision",
        "Applying the requested transform",
        "Validating the transformed dataset",
    ],
    JobKind.TRAINING: [
        "Resolving dataset and policy preset",
        "Checking compute capabilities",
        "Preparing a reproducible training configuration",
        "Running the safe mock trainer",
        "Registering the resulting policy",
    ],
    JobKind.POLICY_IMPORT: [
        "Resolving the pinned Hugging Face revision",
        "Downloading the model snapshot",
        "Inspecting weights and feature contracts",
        "Registering the runnable policy",
    ],
    JobKind.EVALUATION: [
        "Checking policy compatibility",
        "Preparing evaluation episodes",
        "Running the safe evaluation",
        "Computing result distribution",
    ],
    JobKind.POLICY_ROLLOUT: [
        "Resolving policy and target robot",
        "Validating processors and feature mapping",
        "Starting the guarded rollout",
        "Collecting telemetry",
        "Stopping the rollout safely",
    ],
    JobKind.SIMULATION: [
        "Loading the simulation contract",
        "Resolving robot and camera mappings",
        "Running the deterministic mock scenario",
        "Collecting simulation telemetry",
    ],
    JobKind.SIM_TELEOPERATION: [
        "Loading the simulated workspace",
        "Opening the leader arm",
        "Driving the simulation",
        "Closing the leader arm",
    ],
    JobKind.SIM_RECORDING: [
        "Loading the simulated workspace",
        "Opening the leader arm",
        "Recording episodes",
        "Writing the dataset manifest",
        "Running integrity checks",
    ],
    JobKind.REMOTE_INFERENCE_PROBE: [
        "Validating endpoint security",
        "Checking protocol compatibility",
        "Measuring the mocked latency budget",
    ],
    JobKind.HUB_SYNC: [
        "Validating local artifact",
        "Preparing the sync plan",
        "Recording the safe dry-run result",
    ],
    JobKind.DIAGNOSTICS: [
        "Running system checks",
        "Redacting sensitive values",
        "Preparing the diagnostics payload",
    ],
}


def _push_dataset(
    *,
    repo_id: str,
    source_repo_id: str,
    root: str,
    private: bool,
    push_videos: bool,
) -> None:
    """Upload one recording, in a worker thread because it blocks for minutes."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    dataset = LeRobotDataset(source_repo_id, root=root)
    # The repository it lands in is not always the one it was recorded under --
    # a merge names itself, and a local name is not always the name it should
    # carry on the Hub.
    dataset.repo_id = repo_id
    dataset.meta.repo_id = repo_id
    dataset.push_to_hub(private=private, push_videos=push_videos)


def _launched_at(job: JobRecord) -> datetime:
    """When the command that would have written this dataset actually started.

    `job.process.started_at` is the precise answer. `created_at` is the fallback
    for a job whose command never launched, and it errs the only direction a
    freshness filter may err -- earlier, so a real recording is never discarded
    for looking too old.
    """
    if job.process is not None:
        return job.process.started_at
    return job.created_at


class WorkflowCancelled(RuntimeError):
    pass


class WorkflowEngine:
    def __init__(
        self,
        repository: Repository,
        discovery: DiscoveryService,
        settings: Settings,
        hardware: LeRobotCliAdapter,
        cameras: CameraService,
        datasets: DatasetStore,
        policies: PolicyStore,
        calibration: CalibrationStore,
    ) -> None:
        self.repository = repository
        self.discovery = discovery
        self.settings = settings
        self.hardware = hardware
        self.cameras = cameras
        self.datasets = datasets
        self.policies = policies
        self.calibration = calibration
        self.simulation = MujocoAdapter(settings.simulation_model_path)

    async def execute(
        self,
        job: JobRecord,
        progress: ProgressCallback,
        cancelled: CancelCheck,
    ) -> dict[str, Any]:
        # A camera probe reads frames; it has no LeRobot command and moves nothing.
        # A simulated session is not physical, but it is still a command run in
        # its own process -- see the command builder for why.
        simulated_command = job.kind in {JobKind.SIM_TELEOPERATION, JobKind.SIM_RECORDING}
        physical = job.target_mode.value == "real" and job.kind != JobKind.CAMERA_PREVIEW
        local_training = (
            job.kind == JobKind.TRAINING and str(job.parameters.get("runtime")) == "lerobot-local"
        )
        if physical or local_training or simulated_command:
            result = await self.hardware.execute(job, progress, cancelled)
            return {**result, **self._collect_artifacts(job)}

        if job.kind == JobKind.DATASET_TRANSFORM:
            return await self._transform_dataset(job, progress, cancelled)

        if job.kind == JobKind.HUB_SYNC:
            return await self._sync_to_hub(job, progress, cancelled)

        if job.kind == JobKind.POLICY_IMPORT:
            return await self._import_policy(job, progress, cancelled)

        steps = WORKFLOW_STEPS[job.kind]
        for index, message in enumerate(steps, start=1):
            if cancelled():
                raise WorkflowCancelled("The job was stopped by the operator.")
            await progress((index - 1) / len(steps), message)
            await asyncio.sleep(self.settings.simulation_step_seconds)
        result = self._finalize(job)
        await progress(1.0, "Completed")
        return result

    async def _import_policy(
        self,
        job: JobRecord,
        progress: ProgressCallback,
        cancelled: CancelCheck,
    ) -> dict[str, Any]:
        """Download and inspect a model without ever exposing the Hub token."""
        repo_id = str(job.parameters.get("repo_id", "")).strip()
        revision = str(job.parameters.get("revision", "")).strip() or None
        name = str(job.parameters.get("name", "")).strip() or None
        raw_mapping = job.parameters.get("camera_mapping")
        camera_mapping = (
            {str(key): str(value) for key, value in raw_mapping.items()}
            if isinstance(raw_mapping, dict)
            else None
        )
        if cancelled():
            raise WorkflowCancelled("The job was stopped before the download started.")
        await progress(0.05, f"Resolving pinned revision for {repo_id}")
        try:
            manifest = await asyncio.to_thread(
                self.policies.import_from_hub,
                repo_id,
                revision=revision,
                name=name,
                camera_mapping=camera_mapping,
            )
        except PolicyError as error:
            return {"artifact_error": str(error), "policy_id": None, "repo_id": repo_id}
        await progress(1.0, "Completed")
        return {
            "policy_id": manifest.id,
            "repo_id": manifest.model_repo_id,
            "revision": manifest.model_revision,
            "checkpoint": manifest.checkpoint,
            "policy_type": manifest.policy_type,
            "action_shape": manifest.action_shape,
            "camera_mapping": manifest.camera_mapping,
            "empty_cameras": manifest.empty_cameras,
            "compatibility_status": manifest.compatibility_status,
        }

    def _request_for(self, job: JobRecord) -> JobCreateRequest:
        return JobCreateRequest(
            kind=job.kind,
            target_mode=job.target_mode,
            parameters=job.parameters,
            resources=job.resources,
            requested_by=job.requested_by,
        )

    def _contract_run(self, job: JobRecord) -> dict[str, Any]:
        """Step the MuJoCo contract model; never invent numbers when it is absent."""
        scenario_id = job.parameters.get("scenario_id")
        scenario = (
            self.repository.get_entity("scenario", str(scenario_id), SimulationScenario)
            if scenario_id
            else None
        )
        scenario = scenario or SimulationScenario(
            id="scenario_contract",
            name="SO-101 contract model",
            backend="mujoco",
            task=str(job.parameters.get("task", "Contract trajectory")),
        )
        if not self.simulation.available():
            return {
                "scenario_id": scenario.id,
                "backend": "unavailable",
                "simulated": False,
                "problems": ["The MuJoCo feature pack is not installed."],
            }
        return {
            **self.simulation.run(
                scenario,
                control_ticks=int(job.parameters.get("control_ticks", 180)),
                control_hz=int(job.parameters.get("control_hz", 30)),
            ),
            "simulated": True,
        }

    def _collect_artifacts(self, job: JobRecord) -> dict[str, Any]:
        """Read what the command actually wrote once it exits."""
        if job.kind == JobKind.CALIBRATION:
            return self._register_calibration(job)
        if job.kind in {JobKind.RECORDING, JobKind.SIM_RECORDING}:
            return self._record_dataset(job)
        if job.kind == JobKind.TRAINING:
            return self._register_policy(job)
        if job.kind in {JobKind.EVALUATION, JobKind.POLICY_ROLLOUT}:
            return self._rollout_summary(job)
        return {}

    def _register_calibration(self, job: JobRecord) -> dict[str, Any]:
        """Capture the file the calibration just wrote and bind it to its profile.

        Without this a successful calibration leaves nothing behind: no revision,
        no checksum and a profile that still reports it has never been calibrated.
        """
        targets = job.resolved_targets
        if targets is None:
            return {"artifact_error": "The calibration job carried no resolved targets."}

        leader = str(job.parameters.get("role", "robot")) == "teleoperator"
        if leader:
            device_type, device_id = targets.teleop_type, targets.teleop_id
            profile_id = targets.teleoperator_profile_id
        else:
            device_type, device_id = targets.robot_type, targets.robot_id
            profile_id = targets.robot_profile_id
        if not device_type or not device_id:
            return {"artifact_error": "The calibration job resolved no device identity."}

        previous = self.calibration.latest(device_type, device_id)
        try:
            artifact = self.calibration.capture(
                device_type,
                device_id,
                CalibrationSource.USER,
                target_profile_id=profile_id,
            )
        except CalibrationError as error:
            return {"artifact_error": str(error)}

        bound = False
        if profile_id:
            if leader:
                profile = self.repository.get_entity(
                    "teleoperator", profile_id, TeleoperatorProfile
                )
                if profile is not None:
                    self.calibration.bind_teleoperator(profile, artifact)
                    bound = True
            else:
                profile = self.repository.get_entity("robot", profile_id, RobotProfile)
                if profile is not None:
                    self.calibration.bind_robot(profile, artifact)
                    bound = True

        validation = artifact.validation_result
        return {
            "calibration_revision": artifact.id,
            "calibration_source": artifact.source.value,
            "calibration_checksum": artifact.checksum,
            "calibration_valid": bool(validation.get("valid")),
            "calibration_warnings": validation.get("warnings", []),
            "calibration_problems": validation.get("problems", []),
            "calibration_comparison": compare_motors(
                previous.motors if previous else None, artifact.motors
            ),
            "bound_to_profile": bound,
            "supersedes": artifact.supersedes,
        }

    async def _sync_to_hub(
        self,
        job: JobRecord,
        progress: ProgressCallback,
        cancelled: CancelCheck,
    ) -> dict[str, Any]:
        """Put a recording somewhere the machine that trains on it can reach.

        This kind was declared, given three progress strings and never
        implemented: it walked them, returned a hash and reported success having
        sent nothing. Training happens on a different machine here, so the last
        step of the pipeline was the one that pretended.

        `dry_run` reports what would be sent and sends nothing, which is what
        the operator wants before committing an upload measured in hundreds of
        megabytes over whatever this board is connected to.

        The upload itself cannot be interrupted mid-file, so the cancel check
        happens before it starts. Saying otherwise would be a stop button that
        does not stop.
        """
        dataset_id = str(job.parameters.get("dataset_id", "")).strip()
        manifest = self.repository.get_entity("dataset", dataset_id, DatasetManifest)
        if manifest is None:
            return {"artifact_error": f"No dataset is registered under id '{dataset_id}'."}

        repo_id = str(job.parameters.get("repo_id") or manifest.repo_id or "").strip()
        if "/" not in repo_id:
            return {
                "artifact_error": (
                    f"'{repo_id}' is not a Hub repository id; it needs a namespace, "
                    "as in 'user/dataset'."
                )
            }

        root = manifest.local_path or str(self.datasets.root_for(manifest.repo_id or repo_id))
        directory = Path(root)
        if not (directory / "meta" / "info.json").is_file():
            return {"artifact_error": f"Nothing is on disk at '{root}' to publish."}

        await progress(0.05, "Measuring what would be sent")
        files = [item for item in directory.rglob("*") if item.is_file()]
        total_bytes = sum(item.stat().st_size for item in files)
        plan = {
            "repo_id": repo_id,
            "source_repo_id": manifest.repo_id,
            "root": str(directory),
            "episodes": manifest.episodes,
            "frames": manifest.total_frames,
            "files": len(files),
            "bytes": total_bytes,
            "megabytes": round(total_bytes / 1e6, 1),
            "private": bool(job.parameters.get("private", True)),
            "push_videos": bool(job.parameters.get("push_videos", True)),
        }

        if job.parameters.get("dry_run", False):
            await progress(1.0, "Completed")
            return {**plan, "uploaded": False, "note": "Dry run: nothing was sent."}

        # The approval may have been created from an older manifest. Re-read
        # disk at the irreversible boundary so a later task/video mismatch can
        # never ride a stale green badge to the Hub.
        manifest = self.datasets.revalidate(manifest)
        if manifest.integrity_status != STATUS_VERIFIED:
            problems = manifest.integrity_report.get("problems", [])
            return {
                **plan,
                "uploaded": False,
                "artifact_error": (
                    "The dataset failed its current on-disk integrity audit and was not "
                    f"uploaded: {'; '.join(str(problem) for problem in problems)}"
                ),
            }

        if cancelled():
            raise WorkflowCancelled("The job was stopped by the operator.")

        await progress(0.2, f"Uploading {plan['megabytes']} MB to {repo_id}")
        try:
            await asyncio.to_thread(
                _push_dataset,
                repo_id=repo_id,
                source_repo_id=manifest.repo_id or repo_id,
                root=str(directory),
                private=plan["private"],
                push_videos=plan["push_videos"],
            )
        except Exception as error:  # noqa: BLE001 - surfaced as a job result, not a traceback
            return {**plan, "uploaded": False, "artifact_error": f"The upload failed: {error}"}

        await progress(1.0, "Completed")
        self.repository.upsert_entity(
            "dataset",
            manifest.model_copy(
                update={
                    "provenance": {
                        **manifest.provenance,
                        "published_to": repo_id,
                        "published_by_job": job.id,
                    }
                }
            ),
        )
        return {**plan, "uploaded": True, "url": f"https://huggingface.co/datasets/{repo_id}"}

    async def _transform_dataset(
        self,
        job: JobRecord,
        progress: ProgressCallback,
        cancelled: CancelCheck,
    ) -> dict[str, Any]:
        """Edit a recording: drop the takes that were no good, or join several into one.

        This kind was declared, given three progress strings and never
        implemented, so it walked them and returned a hash -- the shape of a job
        that pretends. Editing lived on an endpoint instead, which meant a merge
        of eighty episodes held an HTTP request open for minutes with no
        progress, no way to stop it, no job in the log, and no way for an agent
        to ask for it.

        The write itself cannot be interrupted -- `aggregate_datasets` and
        `delete_episodes` re-encode video and have no checkpoint -- so the
        cancel check happens before it starts and not during. Saying otherwise
        would be a stop button that does not stop.
        """
        operation = str(job.parameters.get("operation", "")).strip()
        if operation not in DATASET_OPERATIONS:
            return {
                "artifact_error": (
                    f"Unknown dataset operation '{operation}'; expected one of "
                    f"{', '.join(sorted(DATASET_OPERATIONS))}."
                )
            }

        await progress(0.05, "Resolving the recordings")
        dataset_ids = [str(item) for item in (job.parameters.get("dataset_ids") or [])]
        manifests = [
            manifest
            for manifest in (
                self.repository.get_entity("dataset", dataset_id, DatasetManifest)
                for dataset_id in dataset_ids
            )
            if manifest is not None
        ]
        if len(manifests) != len(dataset_ids) or not manifests:
            return {"artifact_error": "One of the selected datasets no longer exists."}

        if cancelled():
            raise WorkflowCancelled("The job was stopped by the operator.")

        new_name = str(job.parameters.get("new_name") or "").strip() or None
        try:
            if operation == "merge":
                await progress(0.2, f"Merging {len(manifests)} recordings")
                if not new_name:
                    return {"artifact_error": "A merge needs a name for the result."}
                # Aggregation happily copies the same recording in twice and
                # grades the result verified, so the duplication is invisible
                # afterwards. Recorded rather than refused: doing it on purpose
                # is a real thing to want, and the result should say so.
                overlaps = lineage_overlaps(
                    manifests,
                    self.repository.list_entities("dataset", DatasetManifest),
                )
                shared = sorted({name for item in overlaps for name in item["shared"]})
                duplicated = sum(item.get("duplicated_frames", 0) for item in overlaps)
                report = await asyncio.to_thread(self.datasets.merge, manifests, new_name)
                produced = report["repo_id"]
                label = new_name.split("/")[-1]
                # Where a merge came from is whatever its inputs agree on. A
                # literal "merged" here would be read as a source by the tag
                # that colours anything non-simulation green, so joining sim
                # takes to real ones would print "real arm" over both. When
                # they disagree the honest answer is that they disagree --
                # which is the normal state of a co-training set, not a fault.
                #
                # An input that never recorded its source cannot join a
                # consensus. Skipping the blanks made a real recording merged
                # with a simulated one come out labelled "simulation", because
                # the real one predates provenance being written at all.
                sources = [str(item.provenance.get("source") or "") for item in manifests]
                distinct = set(sources)
                provenance = {
                    "adapter": "aggregate_datasets",
                    "merged_from": report["sources"],
                }
                if shared:
                    provenance["shared_recordings"] = shared
                    provenance["duplicated_frames"] = duplicated
                if len(distinct) == 1 and "" not in distinct:
                    provenance["source"] = distinct.pop()
                elif len(distinct) > 1:
                    provenance["source"] = "mixed"
                    provenance["mixed_sources"] = sorted(name for name in distinct if name)
            else:
                episodes = [int(item) for item in (job.parameters.get("episodes") or [])]
                await progress(0.2, f"Removing {len(episodes)} episode(s)")
                report = await asyncio.to_thread(
                    self.datasets.remove_episodes, manifests[0], episodes, new_name
                )
                produced = report["repo_id"]
                label = f"{manifests[0].name} (kırpılmış)"
                provenance = {
                    **manifests[0].provenance,
                    # The source's own provenance says `lerobot-record` made it.
                    # Carrying that forward unchanged would claim this file came
                    # off a robot, when what it came off is an edit.
                    "adapter": "delete_episodes",
                    "trimmed_from": manifests[0].repo_id,
                    "removed_episodes": report["removed"],
                }
        except DatasetError as error:
            return {"artifact_error": str(error), "operation": operation}

        await progress(0.85, "Reading what was written")
        source = manifests[0]
        manifest = self.datasets.manifest(
            self.datasets.inspect(produced),
            name=label,
            task=source.task,
            robot_profile_id=source.robot_profile_id,
            teleoperator_profile_id=source.teleoperator_profile_id,
            calibration_revision=source.calibration_revision,
            camera_mapping=source.camera_mapping,
            provenance={**provenance, "job_id": job.id},
        )
        await progress(1.0, "Completed")
        return {
            "operation": operation,
            "dataset_id": manifest.id,
            "repo_id": manifest.repo_id,
            "episodes": manifest.episodes,
            "total_frames": manifest.total_frames,
            "integrity_status": manifest.integrity_status,
            **report,
        }

    def salvage_recording(self, job: JobRecord) -> dict[str, Any]:  # noqa: D401
        """Register whatever a stopped recording managed to write.

        `_finalize` only runs when the command exits cleanly, so a recording that
        crashed on episode nine left the first eight registered nowhere. They
        were on disk the whole time; the dashboard simply never looked, and from
        the panel there was no way to reach them. Data that exists and cannot be
        found is lost in every way that matters to the operator.

        Never raises, and never grades above `incomplete`: a run that did not
        finish has not earned `verified`, whatever the file count says.
        """
        if job.kind not in {JobKind.RECORDING, JobKind.SIM_RECORDING}:
            return {}
        try:
            return self._record_dataset(job, salvaged=True)
        except Exception as error:  # noqa: BLE001 - salvage must not mask the real failure
            return {"artifact_error": f"Could not salvage the recording: {error}"}

    def _record_dataset(self, job: JobRecord, salvaged: bool = False) -> dict[str, Any]:
        repo_id = str(job.parameters.get("repo_id", "")).strip()
        if not repo_id:
            return {"artifact_error": "The recording job carried no repo id."}
        root = job.parameters.get("dataset_root")
        # LeRobot renames the dataset it creates, so ask for what landed on disk
        # rather than for what the job requested -- and bound the search by when
        # this job started, so an earlier run's directory cannot be adopted as
        # this one's output.
        recorded = self.datasets.resolve_recorded(repo_id, root, started_at=_launched_at(job))
        report = self.datasets.inspect(recorded, root)
        if salvaged and report["integrity_status"] == STATUS_MISSING:
            return {
                "requested_repo_id": repo_id,
                "recorded_repo_id": None,
                "artifact_error": "The recording stopped before writing anything to disk.",
            }
        targets = job.resolved_targets
        episode_plan = job.parameters.get("episode_plan")
        plan_sidecar: str | None = None
        dataset_episode_start = int(job.parameters.get("dataset_episode_start", 0))
        durable_episode_count = max(
            0,
            int(report.get("total_episodes", 0) or 0) - dataset_episode_start,
        )
        durable_episode_plan = (
            episode_plan[:durable_episode_count]
            if isinstance(episode_plan, list) and durable_episode_count > 0
            else []
        )
        if durable_episode_plan:
            try:
                sidecar = self.datasets.write_episode_plan(
                    report["root"],
                    durable_episode_plan,
                    dataset_episode_start,
                )
                plan_sidecar = sidecar.relative_to(Path(report["root"])).as_posix()
            except (DatasetError, OSError, TypeError, ValueError) as error:
                return {
                    "artifact_error": f"Dataset was written but its episode plan was not: {error}"
                }

            # The first inspection happened before the intended plan existed on
            # disk. Re-read now so task labels and video windows participate in
            # the same integrity result that is registered and later uploaded.
            report = self.datasets.inspect(recorded, root)

        if salvaged:
            report["problems"].append(
                "The recording did not finish, so this dataset holds only the episodes "
                "written before it stopped."
            )
            report["integrity_status"] = STATUS_INCOMPLETE

        existing = next(
            (
                item
                for item in self.repository.list_entities("dataset", DatasetManifest)
                if item.local_path
                and Path(item.local_path).resolve() == Path(report["root"]).resolve()
            ),
            None,
        )
        recording_plan = job.parameters.get("recording_plan")
        recording_plan = recording_plan if isinstance(recording_plan, dict) else {}
        recording_session = {
            **recording_plan,
            "job_id": job.id,
            "dataset_episode_start": dataset_episode_start,
            "episodes": durable_episode_count,
        }
        stored_sessions = (existing.provenance if existing else {}).get("recording_sessions", [])
        previous_sessions = list(stored_sessions) if isinstance(stored_sessions, list) else []
        if recording_plan:
            previous_sessions.append(recording_session)
        manifest = self.datasets.manifest(
            report,
            name=existing.name if existing else str(job.parameters.get("name", repo_id)),
            task=(existing.task if existing else str(job.parameters.get("task", ""))),
            robot_profile_id=targets.robot_profile_id if targets else None,
            teleoperator_profile_id=targets.teleoperator_profile_id if targets else None,
            calibration_revision=targets.robot_calibration_revision if targets else None,
            camera_mapping={
                name: f"observation.images.{name}" for name in (targets.cameras if targets else {})
            },
            provenance={
                **(existing.provenance if existing else {}),
                "job_id": job.id,
                "target_mode": job.target_mode.value,
                "source": RECORDING_SOURCE.get(job.kind, "real-arm"),
                "adapter": (
                    "hashtag-robotics sim-record"
                    if job.kind == JobKind.SIM_RECORDING
                    else "lerobot-record"
                ),
                "scenario_id": job.parameters.get("scenario_id"),
                **({"recording_sessions": previous_sessions} if previous_sessions else {}),
                **({"episode_plan_sidecar": plan_sidecar} if plan_sidecar else {}),
            },
            manifest_id=existing.id if existing else None,
        )
        return {
            "dataset_id": manifest.id,
            "requested_repo_id": repo_id,
            "recorded_repo_id": recorded,
            "integrity_status": manifest.integrity_status,
            "episodes": manifest.episodes,
            "total_frames": manifest.total_frames,
            "problems": report.get("problems", []),
            **({"salvaged": True} if salvaged else {}),
        }

    def _register_policy(self, job: JobRecord) -> dict[str, Any]:
        output_dir = str(job.parameters.get("output_dir", "")).strip()
        if not output_dir:
            return {"artifact_error": "The training job carried no output directory."}
        try:
            report = self.policies.inspect(output_dir)
        except PolicyError as error:
            return {"artifact_error": str(error), "policy_id": None}
        manifest = self.policies.manifest(
            report,
            name=str(
                job.parameters.get("name", f"{report['policy_type']} @ step {report['step']}")
            ),
            source_dataset_id=job.parameters.get("dataset_id"),
        )
        return {
            "policy_id": manifest.id,
            "checkpoint": manifest.checkpoint,
            "checkpoint_step": manifest.checkpoint_step,
            "compatibility_status": manifest.compatibility_status,
        }

    def _rollout_summary(self, job: JobRecord) -> dict[str, Any]:
        """Report what the rollout measured; success is annotated, never guessed."""
        summary: dict[str, Any] = {
            "episodes_requested": int(job.parameters.get("episodes", 0) or 0),
            "episode_outcomes": [],
            "note": "Mark each episode from the dashboard; success is not inferred.",
        }
        repo_id = str(job.parameters.get("repo_id", "")).strip()
        if repo_id:
            root = job.parameters.get("dataset_root")
            # A rollout writes through the same stamping code path as a
            # recording, so it needs the same resolution; asking for the
            # requested name reported every rollout as having recorded nothing.
            recorded = self.datasets.resolve_recorded(repo_id, root, started_at=_launched_at(job))
            report = self.datasets.inspect(recorded, root)
            summary["requested_repo_id"] = repo_id
            summary["recorded_repo_id"] = recorded
            summary["episodes_recorded"] = report.get("total_episodes", 0)
            summary["rollout_dataset"] = report["root"]
            summary["integrity_status"] = report["integrity_status"]
            if (
                report["integrity_status"] != STATUS_MISSING
                and int(report.get("total_episodes", 0) or 0) > 0
            ):
                targets = job.resolved_targets
                manifest = self.datasets.manifest(
                    report,
                    name=str(job.parameters.get("name", f"Policy rollout · {repo_id}")),
                    task=str(job.parameters.get("task", "")),
                    robot_profile_id=targets.robot_profile_id if targets else None,
                    calibration_revision=(targets.robot_calibration_revision if targets else None),
                    camera_mapping={
                        name: f"observation.images.{name}"
                        for name in (targets.cameras if targets else {})
                    },
                    provenance={
                        "job_id": job.id,
                        "target_mode": job.target_mode.value,
                        "source": "policy-rollout",
                        "adapter": "hashtag-lerobot-rollout",
                        "policy_id": job.parameters.get("policy_id"),
                        "rollout_profile": job.parameters.get("rollout_profile"),
                        "move_id": job.parameters.get("move_id"),
                    },
                )
                summary["dataset_id"] = manifest.id
        return summary

    def _finalize(self, job: JobRecord) -> dict[str, Any]:
        if job.kind == JobKind.CAMERA_PREVIEW:
            camera_id = str(job.parameters.get("camera_id", ""))
            profile = self.repository.get_entity("camera", camera_id, CameraProfile)
            if profile is None:
                raise RuntimeError(f"Camera profile '{camera_id}' was not found.")
            result = self.cameras.probe(profile, samples=int(job.parameters.get("samples", 15)))
            profile.latency_baseline_ms = result["p50_latency_ms"]
            profile.measured_fps = result["measured_fps"]
            profile.format_benchmark = dict(result["format_benchmark"])
            # Picking the pixel format that actually carries the requested rate
            # is a measurement, not a judgement, so an unpinned profile adopts
            # it here instead of leaving a recording to run slower than its
            # metadata claims. The change is reported, never silent.
            recommended = result.get("recommended_fourcc")
            if recommended and not profile.fourcc:
                profile.fourcc = recommended
                result["applied_fourcc"] = recommended
            self.repository.upsert_entity("camera", profile)
            return result

        if job.kind == JobKind.HARDWARE_DISCOVERY:
            devices = self.discovery.discover(include_simulated=True)
            return {
                "device_ids": [device.id for device in devices],
                "physical_devices": len([device for device in devices if not device.is_simulated]),
                "simulated_devices": len([device for device in devices if device.is_simulated]),
            }

        if job.kind == JobKind.RECORDING:
            # Sim mode drives the contract model; it writes no LeRobotDataset,
            # so it must not register one either.
            return {
                **self._contract_run(job),
                "dataset_written": False,
                "note": (
                    "Simulation exercises the contract model. Record with "
                    "target_mode='real' to produce a LeRobotDataset."
                ),
            }

        if job.kind == JobKind.DATASET_VALIDATE:
            dataset_id = str(job.parameters.get("dataset_id", ""))
            dataset = self.repository.get_entity("dataset", dataset_id, DatasetManifest)
            if dataset is None:
                raise RuntimeError(f"Dataset '{dataset_id}' was not found.")
            refreshed = self.datasets.revalidate(dataset)
            return {
                "dataset_id": refreshed.id,
                "integrity_status": refreshed.integrity_status,
                "episodes": refreshed.episodes,
                "total_frames": refreshed.total_frames,
                "problems": refreshed.integrity_report.get("problems", []),
            }

        if job.kind == JobKind.TRAINING:
            # Training has no simulated form; produce the typed config instead
            # of a policy that was never trained.
            plan = self.hardware.preview(self._request_for(job))
            return {
                "executed": False,
                "policy_id": None,
                "planned_command": plan["executable"],
                "planned_arguments": plan["arguments"],
                "note": "Set runtime='lerobot-local' to actually train and register a policy.",
            }

        if job.kind in {JobKind.EVALUATION, JobKind.POLICY_ROLLOUT}:
            return {
                **self._contract_run(job),
                "episodes_completed": 0,
                "note": (
                    "Simulation reports contract-model behaviour only. Episode "
                    "success is annotated by the operator after a real rollout."
                ),
            }

        if job.kind == JobKind.SIMULATION:
            return self._contract_run(job)

        if job.kind == JobKind.REMOTE_INFERENCE_PROBE:
            url = str(job.parameters.get("url", ""))
            tls_required = bool(job.parameters.get("tls_required", True))
            if tls_required and not url.startswith(("https://", "grpcs://", "wss://")):
                raise RuntimeError("Remote inference endpoint must use TLS.")
            return {
                "endpoint": url,
                "transport": job.parameters.get("transport", "grpc"),
                "status": "safe-mock-verified",
                "p50_latency_ms": 21.0,
                "p95_latency_ms": 34.0,
                "network_access_performed": False,
            }

        if job.kind == JobKind.DIAGNOSTICS:
            return diagnostics_payload(self.settings)

        payload = repr(sorted(job.parameters.items())).encode()
        return {
            "adapter": "safe-mock",
            "workflow": job.kind.value,
            "plan_hash": hashlib.sha256(payload).hexdigest()[:16],
        }
