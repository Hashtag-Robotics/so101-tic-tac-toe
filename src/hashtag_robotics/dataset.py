from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from hashtag_robotics.config import Settings
from hashtag_robotics.models import DatasetManifest
from hashtag_robotics.repository import Repository

SUPPORTED_CODEBASE_VERSIONS = {"v3.0"}

STATUS_VERIFIED = "verified"
STATUS_INCOMPLETE = "incomplete"
STATUS_MISSING = "missing"
STATUS_UNSUPPORTED = "unsupported"

# Below this, a recorded signal is constant rather than merely small. Units are
# whatever the dataset stores; real teleoperation moves joints by tens.
DEGENERATE_RANGE = 1e-6
# Below this a joint held still for the whole recording. Not a fault -- a task
# may genuinely not use the wrist -- but a policy trained on it learns a
# constant for that joint, and nothing said so. The threshold is in the same
# normalised units the arm reports, where a full sweep is about 200.
STILL_JOINT_RANGE = 1.0
# Encoders can round a boundary by one frame. Anything beyond two frames is a
# different take length, not container jitter.
VIDEO_DURATION_TOLERANCE_FRAMES = 2


class DatasetError(RuntimeError):
    pass


class DatasetStore:
    """Reads what LeRobot actually wrote to disk.

    Nothing here infers episode or frame counts from the job parameters; every
    number comes from `meta/info.json` and the files next to it, so a dataset
    whose data was deleted or never written cannot report itself as verified.
    """

    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def root_for(self, repo_id: str, root: str | Path | None = None) -> Path:
        """Where this dataset lives on disk.

        `root` is not a parent directory to hang `repo_id` under: in LeRobot it
        *is* the dataset's own directory (`lerobot_dataset.py:654`,
        `self.meta.root = self._requested_root`). Treating it as a base made
        every recording written to an external disk report itself as never
        recorded, because nothing was ever at `<root>/<repo_id>`.
        """
        if root:
            return Path(root)
        return self.settings.lerobot_home / repo_id

    def write_episode_plan(
        self,
        root: str | Path,
        episodes: list[dict[str, Any]],
        dataset_episode_start: int,
    ) -> Path:
        """Persist game/global episode lineage beside LeRobot's own metadata."""
        directory = Path(root) / "meta"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "hashtag_episode_plan.jsonl"
        indexed: dict[int, dict[str, Any]] = {}
        if path.is_file():
            for line in path.read_text().splitlines():
                try:
                    item = json.loads(line)
                    indexed[int(item["dataset_episode_index"])] = item
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue

        for offset, episode in enumerate(episodes):
            if not isinstance(episode, dict) or not str(episode.get("instruction", "")).strip():
                raise DatasetError("Every episode plan row needs a non-empty instruction.")
            dataset_index = dataset_episode_start + offset
            indexed[dataset_index] = {
                "dataset_episode_index": dataset_index,
                **episode,
            }

        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            "".join(
                json.dumps(indexed[index], ensure_ascii=False, separators=(",", ":")) + "\n"
                for index in sorted(indexed)
            )
        )
        temporary.replace(path)
        return path

    def resolve_recorded(
        self,
        repo_id: str,
        root: str | Path | None = None,
        started_at: datetime | None = None,
    ) -> str:
        """Find the directory *this* recording produced.

        LeRobot stamps `_YYYYMMDD_HHMMSS` onto `repo_id` at creation
        (`DatasetRecordConfig.stamp_repo_id`), so the name the job asked for
        never exists on disk. Looking only for the requested name reported every
        successful recording as 'nothing was recorded'.

        Matching the stamp needs more care than a glob, because two different
        wrong answers are available:

        A glob of `{repo_id}_[0-9]*` also matches a *different* dataset the
        operator happened to name `pens_2`, and it ranks by string, so `pens_9`
        beats `pens_20260731_120000`. The stamp is therefore matched exactly --
        eight digits, an underscore, six digits, end of name -- and ordered by
        the timestamp it encodes rather than by how the name sorts.

        Worse, a stamped directory left by an *earlier* run of the same job is
        indistinguishable by name from this run's. A recording that crashed
        before writing anything would quietly adopt yesterday's data and report
        it as today's -- a wrong dataset is more expensive than no dataset,
        because it trains. When the caller knows when the job started, anything
        untouched since then is not this run's output.

        A stamped directory always wins over an unstamped one of the same name.
        The stamp is the evidence that a recording ran: LeRobot only skips it on
        resume, and there the repo id it is handed is already stamped. A bare
        directory sharing the name is an older or imported dataset, and handing
        that back means reporting someone else's episodes as this run's.

        With an explicit `root` there is nothing to search: the path is fixed
        regardless of what the repo id was stamped to.
        """
        if root:
            return repo_id

        base = self.settings.lerobot_home
        stamped = re.compile(rf"^{re.escape(repo_id)}_(\d{{8}}_\d{{6}})$")
        if not base.is_dir():
            return repo_id

        candidates: list[tuple[str, str]] = []
        for candidate in base.glob(f"{repo_id}_*"):
            # A repo id is usually namespaced ('mertkirgil/so101_hil_t7'), so the
            # name to match is the path relative to the library, not the leaf.
            relative = candidate.relative_to(base).as_posix()
            match = stamped.match(relative)
            if match is None or not (candidate / "meta" / "info.json").is_file():
                continue
            if started_at is not None and not self._touched_since(candidate, started_at):
                continue
            candidates.append((match.group(1), relative))

        if not candidates:
            # Either nothing was written, or a resumed recording wrote into the
            # unstamped directory. Both answer with the requested name; `inspect`
            # is what decides whether anything is actually there.
            return repo_id
        return max(candidates, key=lambda item: item[0])[1]

    def _touched_since(self, directory: Path, started_at: datetime) -> bool:
        """Did this run write here, or is it a leftover from an earlier one?

        The stamp itself cannot answer: LeRobot builds it from `datetime.now()`
        in local time while jobs are timestamped in UTC, so comparing the two
        would be right for whoever happens to run at UTC. The filesystem is not
        ambiguous.
        """
        try:
            modified = directory.stat().st_mtime
        except OSError:
            return False
        # A second of slack: job timestamps and filesystem timestamps do not
        # share a clock granularity, and being one tick early must not discard a
        # real recording.
        return modified >= started_at.timestamp() - 1

    def recording_status(
        self,
        repo_id: str,
        root: str | Path | None = None,
        *,
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Read the durable and buffered parts of an in-progress recording.

        LeRobot updates ``meta/info.json`` only after ``save_episode()`` and
        keeps the current take as PNGs until it is encoded.  Reporting both is
        the only honest answer while a session is live: a buffered take is not
        yet a saved episode, while a saved episode remains recoverable even if
        the session later aborts.
        """
        recorded_repo_id = self.resolve_recorded(repo_id, root, started_at=started_at)
        directory = self.root_for(recorded_repo_id, root)
        info_path = directory / "meta" / "info.json"
        info: dict[str, Any] = {}
        if info_path.is_file():
            try:
                info = json.loads(info_path.read_text())
            except (json.JSONDecodeError, OSError):
                info = {}

        image_root = directory / "images"
        buffered_by_camera: dict[str, int] = {}
        if image_root.is_dir():
            for camera_dir in sorted(image_root.glob("observation.images.*")):
                buffered_by_camera[camera_dir.name] = sum(1 for _ in camera_dir.rglob("*.png"))

        aligned_buffered = min(buffered_by_camera.values()) if buffered_by_camera else 0
        return {
            "requested_repo_id": repo_id,
            "recorded_repo_id": recorded_repo_id if info_path.is_file() else None,
            "root": str(directory),
            "saved_episodes": int(info.get("total_episodes", 0) or 0),
            "saved_frames": int(info.get("total_frames", 0) or 0),
            "buffered_frames": aligned_buffered,
            "buffered_frames_by_camera": buffered_by_camera,
            "fps": int(info.get("fps", 0) or 0),
            "metadata_present": info_path.is_file(),
        }

    def inspect(self, repo_id: str, root: str | Path | None = None) -> dict[str, Any]:
        directory = self.root_for(repo_id, root)
        info_path = directory / "meta" / "info.json"
        report: dict[str, Any] = {
            "repo_id": repo_id,
            "root": str(directory),
            "integrity_status": STATUS_MISSING,
            "problems": [],
        }

        if not info_path.is_file():
            report["problems"].append(f"'{info_path}' is missing; nothing was recorded.")
            return report

        try:
            info = json.loads(info_path.read_text())
        except json.JSONDecodeError as error:
            report["problems"].append(f"'{info_path}' is not valid JSON: {error}.")
            return report

        features: dict[str, Any] = info.get("features", {}) or {}
        camera_keys = sorted(
            key for key, value in features.items() if value.get("dtype") == "video"
        )
        action = features.get("action", {})

        report.update(
            {
                "codebase_version": info.get("codebase_version"),
                "robot_type": info.get("robot_type"),
                "fps": int(info.get("fps", 0) or 0),
                "total_episodes": int(info.get("total_episodes", 0) or 0),
                "total_frames": int(info.get("total_frames", 0) or 0),
                "total_tasks": int(info.get("total_tasks", 0) or 0),
                "splits": info.get("splits", {}),
                "features": sorted(features),
                "camera_keys": camera_keys,
                "action_shape": list(action.get("shape", []) or []),
                # Kept whole so a comparison can ask questions this report did
                # not anticipate; two datasets disagree in ways a summary hides.
                "info": info,
                "ranges": self._value_ranges(directory),
                "still_joints": self._still_joints(directory, info),
                "files": self._count_files(directory, camera_keys),
            }
        )
        episode_audit = self._episode_contract_audit(directory, info, camera_keys)
        report["episode_audit"] = episode_audit
        report["problems"].extend(episode_audit["problems"])
        report["integrity_status"] = self._grade(report)
        return report

    def _episode_contract_audit(
        self,
        directory: Path,
        info: dict[str, Any],
        camera_keys: list[str],
    ) -> dict[str, Any]:
        """Compare the roadmap, embedded language and video windows.

        File-existence checks cannot catch a semantically wrong demonstration:
        the failed Game 1 run had every required file, but three Parquet task
        labels were shifted and one 31.6 second take owned a 599.8 second video
        window.  The roadmap sidecar is the intended contract; LeRobot episode
        metadata is what a trainer actually consumes.
        """
        sidecar = directory / "meta" / "hashtag_episode_plan.jsonl"
        episode_files = sorted((directory / "meta" / "episodes").rglob("*.parquet"))
        problems: list[str] = []
        task_mismatches: list[int] = []
        video_mismatches: list[dict[str, Any]] = []
        episodes = self.episodes("", directory) if episode_files else []
        total_episodes = int(info.get("total_episodes", 0) or 0)
        fps = int(info.get("fps", 0) or 0)

        if episode_files:
            indices = [int(item["index"]) for item in episodes]
            expected_indices = list(range(total_episodes))
            if indices != expected_indices:
                problems.append(
                    "Episode metadata indices do not match the continuous range "
                    f"0..{max(total_episodes - 1, 0)}: found {indices}."
                )

            expected_cameras = set(camera_keys)
            for episode in episodes:
                index = int(episode["index"])
                frames = int(episode.get("frames", 0) or 0)
                if frames <= 0:
                    problems.append(f"Episode {index} has zero frames.")
                    continue

                videos = {str(video.get("feature")): video for video in episode.get("videos", [])}
                missing = sorted(expected_cameras - set(videos))
                if missing:
                    problems.append(f"Episode {index} is missing camera videos: {missing}.")

                if fps <= 0:
                    continue
                expected_duration = frames / fps
                tolerance = VIDEO_DURATION_TOLERANCE_FRAMES / fps
                for feature, video in videos.items():
                    duration = float(video["to_timestamp"]) - float(video["from_timestamp"])
                    if abs(duration - expected_duration) <= tolerance:
                        continue
                    mismatch = {
                        "episode_index": index,
                        "camera": feature,
                        "frames": frames,
                        "expected_seconds": expected_duration,
                        "video_seconds": duration,
                    }
                    video_mismatches.append(mismatch)
                    problems.append(
                        f"Episode {index} camera '{feature}' spans {duration:.3f}s, but "
                        f"{frames} frames at {fps} FPS require {expected_duration:.3f}s."
                    )

        planned_rows: list[dict[str, Any]] = []
        if sidecar.is_file():
            for line_number, line in enumerate(sidecar.read_text().splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    row["dataset_episode_index"] = int(row["dataset_episode_index"])
                    if not str(row["instruction"]).strip():
                        raise ValueError("instruction is empty")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    problems.append(f"Episode plan line {line_number} is malformed: {error}.")
                    continue
                planned_rows.append(row)

            planned_indices = [row["dataset_episode_index"] for row in planned_rows]
            if planned_indices != list(range(total_episodes)):
                problems.append(
                    "Episode plan indices do not cover the dataset exactly: "
                    f"expected 0..{max(total_episodes - 1, 0)}, found {planned_indices}."
                )

            actual_by_index = {int(item["index"]): str(item.get("task", "")) for item in episodes}
            for row in planned_rows:
                index = int(row["dataset_episode_index"])
                expected_task = str(row["instruction"]).strip()
                actual_task = actual_by_index.get(index)
                if actual_task is None:
                    problems.append(
                        f"Episode {index} is planned as '{expected_task}', "
                        "but has no readable metadata."
                    )
                elif actual_task != expected_task:
                    task_mismatches.append(index)
                    problems.append(
                        f"Episode {index} task mismatch: plan is '{expected_task}', "
                        f"embedded task is '{actual_task}'."
                    )

        return {
            "checked_episode_metadata": bool(episode_files),
            "checked_episode_plan": sidecar.is_file(),
            "task_mismatches": task_mismatches,
            "video_mismatches": video_mismatches,
            "problems": problems,
        }

    def _value_ranges(self, directory: Path) -> dict[str, float]:
        """How far each recorded signal actually travelled.

        `meta/stats.json` was checked for existence and never opened, so the one
        question it answers went unasked: did anything happen? Measured on this
        disk, a simulated recording whose leader was never touched has an action
        range of exactly 0.0 across all six joints -- 283 frames demonstrating
        nothing -- and was graded `verified`.
        """
        stats_path = directory / "meta" / "stats.json"
        if not stats_path.is_file():
            return {}
        try:
            stats = json.loads(stats_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        ranges: dict[str, float] = {}
        for name, value in stats.items():
            low, high = value.get("min"), value.get("max")
            if not isinstance(low, list) or not isinstance(high, list):
                continue
            if len(low) != len(high) or not low:
                continue
            try:
                ranges[name] = max(float(b) - float(a) for a, b in zip(low, high, strict=True))
            except (TypeError, ValueError):
                continue
        return ranges

    def _still_joints(self, directory: Path, info: dict[str, Any]) -> list[str]:
        """Joints that never moved, by name.

        The range check takes the widest joint, so five moving joints hide a
        sixth that did not. Measured on this disk: a real recording graded
        `verified` whose `shoulder_lift` travelled 0.27 units across 597 frames
        -- a policy trained on it can only ever emit that one number for that
        joint. Reported, not graded: whether a still joint is a fault depends on
        the task, and that is the operator's call to make.
        """
        stats_path = directory / "meta" / "stats.json"
        if not stats_path.is_file():
            return []
        try:
            stats = json.loads(stats_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []
        action = stats.get("action") or {}
        low, high = action.get("min"), action.get("max")
        names = ((info.get("features") or {}).get("action") or {}).get("names") or []
        if not isinstance(low, list) or not isinstance(high, list) or len(low) != len(high):
            return []
        still: list[str] = []
        for index, (a, b) in enumerate(zip(low, high, strict=True)):
            try:
                travelled = float(b) - float(a)
            except (TypeError, ValueError):
                continue
            if travelled <= STILL_JOINT_RANGE:
                still.append(str(names[index]) if index < len(names) else f"joint {index}")
        return still

    def _count_files(self, directory: Path, camera_keys: list[str]) -> dict[str, Any]:
        videos = {
            key: len(list((directory / "videos" / key).rglob("*.mp4"))) for key in camera_keys
        }
        return {
            "data_parquet": len(list((directory / "data").rglob("*.parquet"))),
            "videos": videos,
            "stats": (directory / "meta" / "stats.json").is_file(),
            "tasks": (directory / "meta" / "tasks.parquet").is_file(),
            "episode_metadata": len(list((directory / "meta" / "episodes").rglob("*.parquet"))),
        }

    def _grade(self, report: dict[str, Any]) -> str:
        problems: list[str] = report["problems"]
        version = report.get("codebase_version")
        if version not in SUPPORTED_CODEBASE_VERSIONS:
            problems.append(
                f"Dataset codebase version '{version}' is outside the supported set "
                f"{sorted(SUPPORTED_CODEBASE_VERSIONS)}."
            )
            return STATUS_UNSUPPORTED

        files = report["files"]
        if report["total_episodes"] <= 0:
            problems.append("The metadata reports no episodes.")
        if files["data_parquet"] == 0:
            problems.append("No episode parquet file exists under data/.")
        if not files["stats"]:
            problems.append("meta/stats.json is missing.")
        for key, count in files["videos"].items():
            if count == 0:
                problems.append(f"Camera feature '{key}' has no recorded video file.")

        # A demonstration in which the operator never moved is not a short
        # demonstration; it is a recording of nothing, and training on it teaches
        # a policy to emit one constant. It looked identical to a good one here.
        action_range = report.get("ranges", {}).get("action")
        if action_range is not None and action_range <= DEGENERATE_RANGE:
            problems.append(
                f"The action never changes across the whole recording (range "
                f"{action_range:.6f}); nothing was demonstrated."
            )

        return STATUS_VERIFIED if not problems else STATUS_INCOMPLETE

    def manifest(
        self,
        report: dict[str, Any],
        *,
        name: str,
        task: str,
        robot_profile_id: str | None = None,
        teleoperator_profile_id: str | None = None,
        calibration_revision: str | None = None,
        camera_mapping: dict[str, str] | None = None,
        provenance: dict[str, Any] | None = None,
        manifest_id: str | None = None,
    ) -> DatasetManifest:
        manifest = DatasetManifest(
            **({"id": manifest_id} if manifest_id else {}),
            name=name,
            repo_id=report["repo_id"],
            local_path=report["root"],
            task=task,
            robot_profile_id=robot_profile_id,
            teleoperator_profile_id=teleoperator_profile_id,
            calibration_revision=calibration_revision,
            features=list(report.get("features", [])),
            camera_mapping=dict(camera_mapping or {}),
            fps=int(report.get("fps", 0) or 0),
            episodes=int(report.get("total_episodes", 0) or 0),
            total_frames=int(report.get("total_frames", 0) or 0),
            codebase_version=report.get("codebase_version"),
            robot_type=report.get("robot_type"),
            action_shape=list(report.get("action_shape", [])),
            integrity_status=report["integrity_status"],
            integrity_report=report,
            provenance=dict(provenance or {}),
        )
        self.repository.upsert_entity("dataset", manifest)
        return manifest

    def base_of(self, manifest: DatasetManifest) -> Path | None:
        """Recover the library directory a manifest was inspected under.

        `local_path` ends with the whole repo id, which is usually more than one
        path segment ('mertkirgil/so101_kalemi_al'), so every segment is
        stripped. This is the *library* base, not the `root` LeRobot means --
        see `root_for` for why those are different things.
        """
        if not manifest.local_path or not manifest.repo_id:
            return None
        base = Path(manifest.local_path)
        for _ in Path(manifest.repo_id).parts:
            base = base.parent
        return base

    def revalidate(self, manifest: DatasetManifest) -> DatasetManifest:
        """Re-read the dataset a manifest points at and update it in place.

        `local_path` already is the dataset's directory, so it is passed as the
        root directly. Reconstructing a base and re-appending the repo id was
        only ever correct for datasets living under the default library.
        """
        if not manifest.repo_id:
            raise DatasetError(f"Dataset '{manifest.name}' has no repo id to validate.")
        manifest = self._follow_stamp(manifest)
        report = self.inspect(manifest.repo_id, manifest.local_path or None)
        return self.manifest(
            report,
            name=manifest.name,
            task=manifest.task,
            robot_profile_id=manifest.robot_profile_id,
            teleoperator_profile_id=manifest.teleoperator_profile_id,
            calibration_revision=manifest.calibration_revision,
            camera_mapping=manifest.camera_mapping,
            provenance=manifest.provenance,
            manifest_id=manifest.id,
        )

    def _follow_stamp(self, manifest: DatasetManifest) -> DatasetManifest:
        """Point a manifest at the stamped directory its recording actually wrote.

        `lerobot-record` appends `_YYYYMMDD_HHMMSS` to every directory it
        creates. A manifest registered under the asked-for name before that was
        understood reports `missing` forever while its 477 frames sit on disk
        one directory over. The fix belongs here rather than in a migration:
        anything registered by hand under the wrong name is the same case.

        Only when the manifest's own directory is absent, and only when exactly
        one stamped sibling exists -- two would be a choice, and guessing which
        recording someone meant is how the wrong data gets adopted.
        """
        root = (
            Path(manifest.local_path)
            if manifest.local_path
            else self.root_for(manifest.repo_id or "")
        )
        if (root / "meta" / "info.json").is_file():
            return manifest

        parent, name = root.parent, root.name
        if not parent.is_dir():
            return manifest
        stamped = re.compile(rf"^{re.escape(name)}_(\d{{8}}_\d{{6}})$")
        candidates = [
            item
            for item in sorted(parent.iterdir())
            if item.is_dir()
            and stamped.match(item.name)
            and (item / "meta" / "info.json").is_file()
        ]
        if len(candidates) != 1:
            return manifest

        found = candidates[0]
        namespace = (manifest.repo_id or "").rsplit("/", 1)
        repo_id = f"{namespace[0]}/{found.name}" if len(namespace) == 2 else found.name
        return manifest.model_copy(
            update={
                "repo_id": repo_id,
                "local_path": str(found),
                "provenance": {**manifest.provenance, "followed_stamp_from": manifest.repo_id},
            }
        )

    def episodes(self, repo_id: str, root: str | Path | None = None) -> list[dict[str, Any]]:
        """What each episode contains, so a bad one can be picked out by name.

        The dashboard only ever showed a total. An operator who knows the third
        take was ruined had no way to say so, and no way to find out which take
        the ruined one was.

        `meta/episodes/**.parquet` already carries per-episode statistics, so the
        action range comes for free -- and that is the number that identifies an
        episode nobody demonstrated anything in.
        """
        directory = self.root_for(repo_id, root)
        files = sorted((directory / "meta" / "episodes").rglob("*.parquet"))
        if not files:
            return []

        # Joint names come from the recording itself; a position in a vector is
        # not something an operator can act on.
        action_names: list[str] = []
        info_path = directory / "meta" / "info.json"
        if info_path.is_file():
            try:
                info = json.loads(info_path.read_text())
                action_names = list(
                    ((info.get("features") or {}).get("action") or {}).get("names") or []
                )
            except (json.JSONDecodeError, OSError):
                action_names = []

        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - pandas ships with lerobot
            return []

        episodes: list[dict[str, Any]] = []
        for path in files:
            try:
                frame = pd.read_parquet(path)
            except Exception:  # noqa: BLE001 - a listing must not fail the page
                continue
            for row in frame.to_dict("records"):
                episodes.append(
                    {
                        "index": int(row.get("episode_index", -1)),
                        "frames": int(row.get("length", 0) or 0),
                        "task": _first_task(row.get("tasks")),
                        "action_range": _range_of(row, "action"),
                        "state_range": _range_of(row, "observation.state"),
                        "still_joints": _still_joints_of(row, action_names),
                        "videos": _episode_videos(row),
                        "_action_signature": _signature_of(row, "action"),
                        "_state_signature": _signature_of(row, "observation.state"),
                    }
                )
        episodes.sort(key=lambda item: item["index"])
        _mark_duplicates(episodes)
        for episode in episodes:
            action_range = episode["action_range"]
            episode["demonstrates_nothing"] = (
                action_range is not None and action_range <= DEGENERATE_RANGE
            )
        return episodes

    def merge(
        self,
        manifests: list[DatasetManifest],
        new_repo_id: str,
    ) -> dict[str, Any]:
        """Physically join several recordings into one, for co-training.

        LeRobot 0.6 will not train on more than one dataset: `make_dataset`
        raises `NotImplementedError: The MultiLeRobotDataset isn't supported for
        now.` and `DatasetConfig.repo_id` is a single string. So mixing
        simulated and real demonstrations -- the whole point of collecting the
        simulated ones -- means merging them on disk first.

        The compatibility check runs before anything is written, and blockers
        refuse the merge. That check exists because these two disagreed silently
        on this machine: same-looking datasets, different joint names, different
        units, different image axis order. `aggregate_datasets` would have
        failed somewhere deep inside instead of saying which of the two was
        wrong and how.

        Warnings do not refuse. A recording carrying a camera the other lacks is
        readable; training simply uses what they share, and that is the
        operator's call to make.
        """
        if len(manifests) < 2:
            raise DatasetError("Merging needs at least two datasets.")

        reports = []
        for manifest in manifests:
            if not manifest.repo_id:
                raise DatasetError(f"Dataset '{manifest.name}' has no repo id to read.")
            reports.append(self.inspect(manifest.repo_id, manifest.local_path or None))

        verdict = compare_datasets(reports)
        if verdict["blockers"]:
            reasons = "; ".join(item["reason"] for item in verdict["blockers"])
            raise DatasetError(
                f"These recordings cannot be merged: {reasons} "
                "Compare them first to see the values."
            )

        for manifest, report in zip(manifests, reports, strict=True):
            if report["integrity_status"] != STATUS_VERIFIED:
                reasons = "; ".join(str(item) for item in report.get("problems", []))
                raise DatasetError(f"Dataset '{manifest.name}' is not safe to merge: {reasons}")

        target_root = self.settings.lerobot_home / new_repo_id
        if target_root.exists():
            raise DatasetError(f"'{new_repo_id}' already exists; choose another name.")

        from lerobot.datasets.dataset_tools import aggregate_datasets

        aggregate_datasets(
            repo_ids=[manifest.repo_id for manifest in manifests],
            aggr_repo_id=new_repo_id,
            roots=[
                Path(manifest.local_path)
                if manifest.local_path
                else self.root_for(manifest.repo_id)
                for manifest in manifests
            ],
            aggr_root=target_root,
        )
        merged = self.inspect(new_repo_id)
        return {
            "repo_id": new_repo_id,
            "root": str(target_root),
            "sources": [manifest.repo_id for manifest in manifests],
            "episodes": merged.get("total_episodes", 0),
            "frames": merged.get("total_frames", 0),
            "warnings": verdict["warnings"],
        }

    def remove_episodes(
        self,
        manifest: DatasetManifest,
        episode_indices: list[int],
        new_repo_id: str | None = None,
    ) -> dict[str, Any]:
        """Write a copy of a recording without the episodes that were no good.

        LeRobot's `delete_episodes` produces a NEW dataset rather than editing
        in place, which is the right shape for this: a ruined take is a
        judgement, and a judgement should be reversible. The original is left
        exactly where it was.
        """
        if not manifest.repo_id:
            raise DatasetError(f"Dataset '{manifest.name}' has no repo id to edit.")
        if not episode_indices:
            raise DatasetError("No episodes were selected.")

        # Refuse before loading anything. `LeRobotDataset(...)` reads the whole
        # dataset and reaches for the Hub when a file is missing; a request that
        # was never going to be honoured should not cost that.
        source_root = manifest.local_path or str(self.root_for(manifest.repo_id))
        report = self.inspect(manifest.repo_id, source_root)
        total = int(report.get("total_episodes", 0) or 0)
        if total and len(set(episode_indices)) >= total:
            raise DatasetError(
                f"That would remove all {total} episodes. Forget the whole dataset "
                "instead if that is what you mean."
            )

        target_repo_id = new_repo_id or f"{manifest.repo_id}_trimmed"
        target_root = self.settings.lerobot_home / target_repo_id
        if target_root.exists():
            raise DatasetError(f"'{target_repo_id}' already exists; choose another name.")

        from lerobot.datasets.dataset_tools import delete_episodes
        from lerobot.datasets.lerobot_dataset import LeRobotDataset

        source = LeRobotDataset(manifest.repo_id, root=source_root)
        edited = delete_episodes(
            source,
            episode_indices=sorted(set(episode_indices)),
            output_dir=str(target_root),
            repo_id=target_repo_id,
        )
        return {
            "source_repo_id": manifest.repo_id,
            "repo_id": target_repo_id,
            "root": str(target_root),
            "removed": sorted(set(episode_indices)),
            "episodes_before": source.num_episodes,
            "episodes_after": edited.num_episodes,
        }


# What two datasets must agree on before one policy can be trained on both.
#
# Every entry here is something that was seen to differ silently on this machine
# between a real recording and a simulated one: the joints were named
# `shoulder_pan.pos` in one and `1` in the other, the units were normalised in
# one and radians in the other, the images were [H,W,3] in one and [3,H,W] in
# the other. Nothing raised. The policy simply learned less, and nobody could
# have told from the dashboard. A check that only happens when a human opens two
# info.json files side by side is a check that stops happening.
INCOMPATIBLE = "incompatible"
COMPATIBLE = "compatible"
COMPARABLE_WITH_WARNINGS = "warnings"

COMPATIBILITY_REASONS = {
    "joint_names": (
        "The joints are named differently, so nothing tells a policy that the two "
        "datasets describe the same arm."
    ),
    "state_shape": "The state vectors are different widths.",
    "action_shape": "The action vectors are different widths.",
    "image_layout": (
        "The images are stored in a different axis order; one of the two would be read as noise."
    ),
    "image_shape": (
        "The images are different sizes. A policy would resize them, but a merge "
        "will not: aggregation requires identical features."
    ),
    "cameras": (
        "The recordings carry different cameras. Aggregation requires identical "
        "features, so the one with an extra camera cannot be merged with the other "
        "until they are recorded with the same set."
    ),
    "fps": (
        "The recordings run at different rates, so a fixed action horizon covers a "
        "different amount of time in each."
    ),
    "robot_type": "The datasets declare different robots.",
    "codebase_version": "The datasets were written by different LeRobot dataset versions.",
    "features": (
        "LeRobot considers these feature sets incompatible for aggregation, for a "
        "reason not covered by the checks above."
    ),
}


def _features_of(report: dict[str, Any]) -> dict[str, Any]:
    return (report.get("info") or {}).get("features") or {}


def _mergeable(features_a: dict[str, Any], features_b: dict[str, Any]) -> bool:
    """Ask LeRobot itself whether these can be aggregated.

    Its predicate is the one that actually runs, so re-implementing it here would
    only create something to drift. Ours exists to say *which* key differs, since
    a bare False sends the operator to compare two JSON files by eye -- which is
    how the mismatch on this machine went unnoticed in the first place.
    """
    try:
        from lerobot.datasets.feature_utils import features_equal_for_merge
    except ImportError:
        return features_a == features_b
    return bool(features_equal_for_merge(features_a, features_b))


def _first_task(tasks: Any) -> str:
    if tasks is None:
        return ""
    if isinstance(tasks, str):
        return tasks
    try:
        return str(next(iter(tasks), ""))
    except TypeError:
        return str(tasks)


def _episode_videos(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve LeRobot v3 video segments without exposing filesystem paths."""
    videos: list[dict[str, Any]] = []
    suffix = "/chunk_index"
    for key in sorted(row):
        if not key.startswith("videos/observation.images.") or not key.endswith(suffix):
            continue
        feature = key[len("videos/") : -len(suffix)]
        if re.fullmatch(r"observation\.images\.[A-Za-z0-9_-]+", feature) is None:
            continue
        prefix = f"videos/{feature}"
        try:
            chunk_index = int(row[key])
            file_index = int(row[f"{prefix}/file_index"])
            from_timestamp = float(row[f"{prefix}/from_timestamp"])
            to_timestamp = float(row[f"{prefix}/to_timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        videos.append(
            {
                "camera": feature.rsplit(".", 1)[-1],
                "feature": feature,
                "chunk_index": chunk_index,
                "file_index": file_index,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
            }
        )
    return videos


def _mark_duplicates(episodes: list[dict[str, Any]]) -> None:
    """Name the episodes that are copies of an earlier one in the same dataset.

    Merging a set with something it already contains succeeds and grades
    `verified`; the duplication only shows up here. Two episodes with the same
    frame count and the same action statistics to the last digit are the same
    take: the statistics are computed from the frames, so agreeing on all of
    min, max, mean and standard deviation by accident is not something a hand
    on a leader arm does.

    Only the later copy is marked. The first occurrence is the take itself.
    """
    seen: dict[tuple[Any, ...], int] = {}
    for episode in episodes:
        signature = (
            episode.get("frames"),
            episode.get("_action_signature"),
            episode.get("_state_signature"),
        )
        if signature[1] is None:
            episode["duplicate_of"] = None
            continue
        first = seen.get(signature)
        episode["duplicate_of"] = first
        if first is None:
            seen[signature] = episode["index"]
    for episode in episodes:
        episode.pop("_action_signature", None)
        episode.pop("_state_signature", None)


def _signature_of(row: dict[str, Any], feature: str) -> tuple[Any, ...] | None:
    """A fingerprint of one episode's statistics for one feature."""
    parts: list[Any] = []
    for statistic in ("min", "max", "mean", "std"):
        value = row.get(f"stats/{feature}/{statistic}")
        if value is None:
            return None
        try:
            parts.append(tuple(round(float(item), 9) for item in value))
        except (TypeError, ValueError):
            return None
    return tuple(parts)


def _still_joints_of(row: dict[str, Any], names: list[str]) -> list[str]:
    """Which joints held still for this one episode.

    Per episode rather than per dataset, because a take where the operator
    forgot the wrist is a take to drop, not a reason to distrust the rest.
    """
    low, high = row.get("stats/action/min"), row.get("stats/action/max")
    if low is None or high is None:
        return []
    still: list[str] = []
    for index, (a, b) in enumerate(zip(low, high, strict=False)):
        try:
            travelled = float(b) - float(a)
        except (TypeError, ValueError):
            continue
        if travelled <= STILL_JOINT_RANGE:
            still.append(str(names[index]) if index < len(names) else f"joint {index}")
    return still


def _range_of(row: dict[str, Any], feature: str) -> float | None:
    """How far one feature travelled inside a single episode."""
    low, high = row.get(f"stats/{feature}/min"), row.get(f"stats/{feature}/max")
    if low is None or high is None:
        return None
    try:
        return max(float(b) - float(a) for a, b in zip(low, high, strict=True))
    except (TypeError, ValueError):
        return None


def _first_camera(features: dict[str, Any]) -> dict[str, Any]:
    for name, value in sorted(features.items()):
        if str(name).startswith("observation.images."):
            return value or {}
    return {}


def _feature_differences(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Which feature field disagrees, down to the sub-key, in words.

    LeRobot's own predicate answers only False. When every field the comparison
    knows by name agrees and it still refuses, this is the only thing standing
    between the operator and a guess.
    """
    # LeRobot ignores its own encoder bookkeeping when deciding, so listing it
    # here would show eight disagreements where only one blocks anything. Taken
    # from LeRobot rather than copied, so the two cannot drift apart.
    try:
        from lerobot.configs import VIDEO_ENCODER_INFO_KEYS as ignored
    except ImportError:  # pragma: no cover - lerobot ships with the sim extra
        ignored = frozenset()

    differences: dict[str, Any] = {}
    for name in sorted(set(left) | set(right)):
        one, two = left.get(name), right.get(name)
        if one == two:
            continue
        if not isinstance(one, dict) or not isinstance(two, dict):
            differences[name] = {"a": one, "b": two}
            continue
        fields: dict[str, Any] = {}
        for field_name in sorted(set(one) | set(two)):
            first, second = one.get(field_name), two.get(field_name)
            if first == second:
                continue
            if isinstance(first, dict) and isinstance(second, dict):
                inner_fields = {
                    inner: {"a": first.get(inner), "b": second.get(inner)}
                    for inner in sorted(set(first) | set(second))
                    if first.get(inner) != second.get(inner) and inner not in ignored
                }
                if inner_fields:
                    fields[field_name] = inner_fields
            else:
                fields[field_name] = {"a": first, "b": second}
        if fields:
            differences[name] = fields
    return differences


def dataset_profile(report: dict[str, Any]) -> dict[str, Any]:
    """The handful of facts that decide whether two recordings can be merged."""
    info = report.get("info") or {}
    features = info.get("features") or {}
    state = features.get("observation.state") or {}
    action = features.get("action") or {}
    camera = _first_camera(features)
    return {
        "repo_id": report.get("repo_id"),
        "joint_names": list(state.get("names") or []),
        "action_names": list(action.get("names") or []),
        "state_shape": list(state.get("shape") or []),
        "action_shape": list(action.get("shape") or []),
        "image_layout": list(camera.get("names") or []),
        "image_shape": list(camera.get("shape") or []),
        "cameras": sorted(
            name.rsplit(".", 1)[-1]
            for name in features
            if str(name).startswith("observation.images.")
        ),
        "fps": int(info.get("fps", 0) or 0),
        "robot_type": info.get("robot_type"),
        "codebase_version": info.get("codebase_version"),
        "episodes": int(info.get("total_episodes", 0) or 0),
        "frames": int(info.get("total_frames", 0) or 0),
    }


def recording_lineage(manifest: DatasetManifest, library: dict[str, DatasetManifest]) -> set[str]:
    """Which original recordings this dataset's frames actually came from.

    A merge records its inputs in `provenance.merged_from`, so a merged dataset
    can be resolved back to the takes it is made of. One that was never merged
    stands for itself.
    """
    seen: set[str] = set()
    originals: set[str] = set()
    pending = [manifest]
    while pending:
        current = pending.pop()
        repo_id = current.repo_id or ""
        if not repo_id or repo_id in seen:
            continue
        seen.add(repo_id)
        sources = current.provenance.get("merged_from") or []
        if not isinstance(sources, list) or not sources:
            originals.add(repo_id)
            continue
        for source in sources:
            parent = library.get(str(source))
            if parent is None:
                # The input was forgotten or renamed; it still stands for a
                # recording, and saying nothing would let it overlap unnoticed.
                originals.add(str(source))
            else:
                pending.append(parent)
    return originals


def lineage_overlaps(
    selected: list[DatasetManifest], library: list[DatasetManifest]
) -> list[dict[str, Any]]:
    """Recordings that would end up in the result more than once.

    Merging A with a set that already contains A does not fail: aggregation
    copies both and the result grades `verified`, with those frames counted
    twice and the mixture silently reweighted. Measured on this disk: five
    simulated episodes and one real one merged into eleven episodes, of which
    five were byte-for-byte duplicates -- ten sim against one real, not five.

    Said, not refused. Copying a recording in twice is a real thing to want --
    checking that merging works at all, or weighting one set more heavily -- and
    the operator is the one who knows which it is. What they cannot do is find
    out afterwards without opening the parquet files, so this says it up front,
    with the number of frames it will cost.
    """
    by_repo = {item.repo_id: item for item in library if item.repo_id}
    frames_by_repo = {item.repo_id: item.total_frames for item in library if item.repo_id}
    lineages = [(item, recording_lineage(item, by_repo)) for item in selected]
    overlaps: list[dict[str, Any]] = []
    for index, (left, left_sources) in enumerate(lineages):
        for right, right_sources in lineages[index + 1 :]:
            shared = sorted(left_sources & right_sources)
            if not shared:
                continue
            duplicated = sum(frames_by_repo.get(name, 0) for name in shared)
            overlaps.append(
                {
                    "key": "duplicate_lineage",
                    "reason": (
                        "These already share recordings, so the same frames go in "
                        f"twice: {duplicated} frame(s) counted double. Merge the "
                        "original recordings instead if that was not the intent."
                    ),
                    "values": {
                        str(left.repo_id): sorted(left_sources),
                        str(right.repo_id): sorted(right_sources),
                    },
                    "shared": shared,
                    "duplicated_frames": duplicated,
                }
            )
    return overlaps


def compare_datasets(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Can one policy be trained on all of these at once?

    The question is narrower than it sounds. LeRobot 0.6 will not train on more
    than one dataset -- `make_dataset` raises "The MultiLeRobotDataset isn't
    supported for now" -- so training on both means *merging* them on disk, and
    aggregation demands identical `fps`, identical `robot_type` and identical
    features. That is the bar this check measures against, because it is the bar
    the operator will actually hit.

    It measured against a looser bar first, and was wrong in the direction that
    matters: a camera present in one recording and absent in the other was
    reported as a warning ("training uses what they share"), which is true of
    reading and false of merging. The merge failed with a ValueError listing two
    entire feature dicts. A warning that guarantees a failure downstream is a
    blocker wearing the wrong label.

    Answers with reasons rather than a boolean, because the next question is
    always "what do I do about it", and because LeRobot's own predicate returns
    only False.
    """
    profiles = [dataset_profile(report) for report in reports]
    if len(profiles) < 2:
        return {
            "status": COMPATIBLE,
            "profiles": profiles,
            "blockers": [],
            "warnings": [],
            "summary": "Nothing to compare against.",
        }

    reference, reference_features = profiles[0], _features_of(reports[0])
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def note(bucket: list[dict[str, Any]], key: str, other: dict[str, Any]) -> None:
        bucket.append(
            {
                "key": key,
                "reason": COMPATIBILITY_REASONS[key],
                "values": {
                    reference["repo_id"]: reference.get(key),
                    other["repo_id"]: other.get(key),
                },
            }
        )

    for other, other_report in zip(profiles[1:], reports[1:], strict=True):
        # Exactly what `aggregate_datasets` checks, in the order it checks it.
        for key in ("fps", "robot_type", "codebase_version"):
            if reference.get(key) != other.get(key):
                note(blockers, key, other)

        other_features = _features_of(other_report)
        if not _mergeable(reference_features, other_features):
            explained = False
            for key in (
                "joint_names",
                "state_shape",
                "action_shape",
                "cameras",
                "image_layout",
                "image_shape",
            ):
                if reference.get(key) != other.get(key):
                    note(blockers, key, other)
                    explained = True
            if not explained:
                # Everything named agreed and LeRobot still said no. Naming the
                # field that actually differs is the difference between a wall
                # and a next step: measured on this disk, two real recordings of
                # the same arm were refused because one LeRobot version wrote
                # `video.is_depth_map` and a later one wrote `is_depth_map` --
                # same value, renamed key, and nothing said so.
                blockers.append(
                    {
                        "key": "features",
                        "reason": COMPATIBILITY_REASONS["features"],
                        "values": _feature_differences(reference_features, other_features),
                    }
                )

        # Readable, mergeable, and still worth a word before training on it.
        bigger, smaller = sorted((reference["episodes"], other["episodes"]), reverse=True)
        if smaller and bigger >= smaller * 5:
            warnings.append(
                {
                    "key": "mixture",
                    "reason": (
                        "One recording is at least five times the size of the other, so "
                        "the smaller one contributes little to what the policy sees."
                    ),
                    "values": {
                        reference["repo_id"]: reference["episodes"],
                        other["repo_id"]: other["episodes"],
                    },
                }
            )

    # The same disagreement is reported once, not once per pair.
    blockers = list({item["key"]: item for item in blockers}.values())
    warnings = list({item["key"]: item for item in warnings}.values())

    if blockers:
        status = INCOMPATIBLE
        summary = (
            f"These cannot be merged, so they cannot be trained on together: "
            f"{len(blockers)} thing(s) differ."
        )
    elif warnings:
        status = COMPARABLE_WITH_WARNINGS
        summary = "These can be merged, with something worth knowing first."
    else:
        status = COMPATIBLE
        summary = "These can be merged and trained on together."

    return {
        "status": status,
        "profiles": profiles,
        "blockers": blockers,
        "warnings": warnings,
        "summary": summary,
        "total_episodes": sum(profile["episodes"] for profile in profiles),
        "total_frames": sum(profile["frames"] for profile in profiles),
    }


def compare_selection(
    selected: list[DatasetManifest],
    store: DatasetStore,
    library: list[DatasetManifest],
) -> dict[str, Any]:
    """The whole answer to 'can these be trained together', from manifests.

    `compare_datasets` above compares what is on disk; this is the rest of what
    the operator is told -- reading each recording, and adding the overlap
    warning that reading alone cannot see. It lives here rather than in the HTTP
    handler because there is now more than one door asking the question, and two
    doors deriving the same answer separately is how they come to disagree.
    """
    if len(selected) < 2:
        raise DatasetError("Comparing needs at least two recordings.")
    reports = []
    for manifest in selected:
        if not manifest.repo_id:
            raise DatasetError(f"Dataset '{manifest.name}' has no repo id to read.")
        reports.append(store.inspect(manifest.repo_id, manifest.local_path or None))

    comparison = compare_datasets(reports)
    # A warning and not a blocker: the merge works, and copying a recording in
    # twice is a real thing to want. What the operator cannot do is find out
    # afterwards without opening the parquet files.
    overlaps = lineage_overlaps(selected, library)
    if overlaps:
        comparison["warnings"] = [*comparison["warnings"], *overlaps]
        if not comparison["blockers"]:
            comparison["status"] = "warnings"
            comparison["summary"] = (
                "These can be merged, with something worth knowing first: they "
                "already share recordings."
            )
    return {
        "datasets": [{"id": manifest.id, "name": manifest.name} for manifest in selected],
        **comparison,
    }
