"""Silent wrong data is more expensive than visible failure, because it trains.

Three ways a recording could be mis-attributed, all of them quiet:
a glob that matches the neighbouring dataset, a stamped directory left by an
earlier run of the same job, and a `root` treated as a parent when LeRobot means
it as the dataset itself. None of them raise; they hand back a plausible answer.

The names here are the ones actually on the bench.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import STATUS_MISSING, DatasetStore
from hashtag_robotics.repository import Repository

INFO = {
    "codebase_version": "v3.0",
    "robot_type": "so101_follower",
    "fps": 30,
    "total_episodes": 1,
    "total_frames": 597,
    "total_tasks": 1,
    "features": {"action": {"dtype": "float32", "shape": [6]}},
}


@pytest.fixture
def store(tmp_path: Path) -> DatasetStore:
    settings = Settings(data_dir=tmp_path, open_browser=False)
    settings.ensure_directories()
    return DatasetStore(settings, Repository(settings.database_path))


def write_dataset(store: DatasetStore, name: str, *, when: datetime | None = None) -> Path:
    directory = store.settings.lerobot_home / name
    (directory / "meta").mkdir(parents=True)
    (directory / "meta" / "info.json").write_text(json.dumps(INFO))
    if when is not None:
        stamp = when.timestamp()
        os.utime(directory, (stamp, stamp))
    return directory


def test_the_stamped_directory_is_found(store: DatasetStore) -> None:
    """Without this every successful recording reported 'nothing was recorded'."""
    write_dataset(store, "so101_hil_t7_kamerali_20260730_235700")

    assert (
        store.resolve_recorded("so101_hil_t7_kamerali") == "so101_hil_t7_kamerali_20260730_235700"
    )


def test_a_namespaced_repo_id_resolves(store: DatasetStore) -> None:
    """Repo ids carry a namespace, so the name to match is a path, not a leaf.

    Matching against the directory's own name instead of its path relative to
    the library silently resolved nothing for every real dataset on this bench.
    """
    write_dataset(store, "mertkirgil/so101_hil_t7_kamerali_20260730_235700")

    assert store.resolve_recorded("mertkirgil/so101_hil_t7_kamerali") == (
        "mertkirgil/so101_hil_t7_kamerali_20260730_235700"
    )


def test_a_longer_sibling_name_is_not_swallowed_by_a_shorter_request(
    store: DatasetStore,
) -> None:
    """The three datasets that actually sit side by side on this machine."""
    write_dataset(store, "mertkirgil/so101_hil_t7_20260730_233434")
    write_dataset(store, "mertkirgil/so101_hil_t7_kamerali_20260730_235700")
    write_dataset(store, "mertkirgil/so101_hil_t7_kamerasiz_20260730_234146")

    assert store.resolve_recorded("mertkirgil/so101_hil_t7") == (
        "mertkirgil/so101_hil_t7_20260730_233434"
    )
    assert store.resolve_recorded("mertkirgil/so101_hil_t7_kamerali") == (
        "mertkirgil/so101_hil_t7_kamerali_20260730_235700"
    )


def test_a_neighbouring_dataset_is_not_mistaken_for_this_one(store: DatasetStore) -> None:
    """`pens_2` is somebody's dataset, not a timestamp."""
    write_dataset(store, "so101_pens_2")
    write_dataset(store, "so101_pens_notes_20260731_120000")

    assert store.resolve_recorded("so101_pens") == "so101_pens"


def test_a_neighbour_cannot_outrank_a_real_stamp_by_sorting_higher(
    store: DatasetStore,
) -> None:
    """The old code ranked by string, and '9' sorts above '2'."""
    write_dataset(store, "so101_pens_9")
    write_dataset(store, "so101_pens_20260731_120000")

    assert store.resolve_recorded("so101_pens") == "so101_pens_20260731_120000"


def test_the_newest_stamp_wins_when_several_runs_share_a_name(store: DatasetStore) -> None:
    write_dataset(store, "so101_hil_t7_20260730_233434")
    write_dataset(store, "so101_hil_t7_20260730_234146")

    assert store.resolve_recorded("so101_hil_t7") == "so101_hil_t7_20260730_234146"


def test_an_earlier_runs_directory_is_not_adopted_as_this_runs_output(
    store: DatasetStore,
) -> None:
    """The expensive one: a crashed run inheriting yesterday's data and training on it."""
    yesterday = datetime.now(UTC) - timedelta(days=1)
    write_dataset(store, "so101_pens_20260730_120000", when=yesterday)

    started_now = store.resolve_recorded("so101_pens", started_at=datetime.now(UTC))

    assert started_now == "so101_pens", "a run that wrote nothing must resolve to nothing"


def test_a_directory_this_run_wrote_is_still_accepted(store: DatasetStore) -> None:
    started = datetime.now(UTC)
    write_dataset(store, "so101_pens_20260731_120000")

    assert store.resolve_recorded("so101_pens", started_at=started) == (
        "so101_pens_20260731_120000"
    )


def test_a_filesystem_a_tick_behind_the_clock_does_not_lose_the_recording(
    store: DatasetStore,
) -> None:
    """Job timestamps and file timestamps do not share a granularity."""
    started = datetime.now(UTC)
    write_dataset(store, "so101_pens_20260731_120000", when=started - timedelta(milliseconds=800))

    assert store.resolve_recorded("so101_pens", started_at=started) == (
        "so101_pens_20260731_120000"
    )


def test_an_explicit_root_is_the_dataset_directory_not_a_parent(
    store: DatasetStore,
    tmp_path: Path,
) -> None:
    """LeRobot sets `meta.root = _requested_root`; nothing is ever at <root>/<repo_id>."""
    external = tmp_path / "usb-disk" / "so101_pens"
    (external / "meta").mkdir(parents=True)
    (external / "meta" / "info.json").write_text(json.dumps(INFO))

    assert store.root_for("so101_pens", external) == external

    report = store.inspect("so101_pens", external)
    assert report["integrity_status"] != STATUS_MISSING
    assert report["total_frames"] == 597


def test_the_old_reading_of_root_would_have_found_nothing(
    store: DatasetStore,
    tmp_path: Path,
) -> None:
    """Pins why the change was needed: the old path simply does not exist."""
    external = tmp_path / "usb-disk" / "so101_pens"
    (external / "meta").mkdir(parents=True)
    (external / "meta" / "info.json").write_text(json.dumps(INFO))

    assert not (external / "so101_pens" / "meta" / "info.json").exists()


def test_an_explicit_root_needs_no_stamp_search(store: DatasetStore, tmp_path: Path) -> None:
    external = tmp_path / "usb-disk" / "so101_pens"
    (external / "meta").mkdir(parents=True)
    (external / "meta" / "info.json").write_text(json.dumps(INFO))

    assert store.resolve_recorded("so101_pens", external) == "so101_pens"


def test_a_missing_library_directory_answers_instead_of_raising(store: DatasetStore) -> None:
    import shutil

    shutil.rmtree(store.settings.lerobot_home)

    assert store.resolve_recorded("so101_pens") == "so101_pens"


# -- what a stopped recording leaves behind -----------------------------------


def build_engine(store: DatasetStore):
    from hashtag_robotics.calibration import CalibrationStore
    from hashtag_robotics.camera import CameraService
    from hashtag_robotics.discovery import DiscoveryService
    from hashtag_robotics.hardware import LeRobotCliAdapter
    from hashtag_robotics.policy import PolicyStore
    from hashtag_robotics.workflows import WorkflowEngine

    settings, repository = store.settings, store.repository
    discovery = DiscoveryService(repository)
    return WorkflowEngine(
        repository=repository,
        discovery=discovery,
        settings=settings,
        hardware=LeRobotCliAdapter(settings, repository),
        cameras=CameraService(settings, repository, discovery),
        datasets=store,
        policies=PolicyStore(settings, repository),
        calibration=CalibrationStore(settings, repository),
    )


def recording_job(repo_id: str, launched_at: datetime | None = None):
    """A recording job, optionally one whose command launched at a given moment.

    `started_at` lives on `JobProcess`, not on the job: a job that never got as
    far as launching has no start, only a submission.
    """
    from hashtag_robotics.models import JobKind, JobProcess, JobRecord, TargetMode

    process = (
        JobProcess(pid=1, pgid=1, executable="lerobot-record", started_at=launched_at)
        if launched_at is not None
        else None
    )
    return JobRecord(
        kind=JobKind.RECORDING,
        target_mode=TargetMode.REAL,
        parameters={"repo_id": repo_id, "name": "salvage", "task": "pick"},
        requested_by="test",
        process=process,
    )


def test_episodes_written_before_the_crash_are_registered_not_lost(
    store: DatasetStore,
) -> None:
    """`_finalize` never runs on a failure, so eight good episodes stayed invisible."""
    started = datetime.now(UTC)
    write_dataset(store, "so101_pens_20260731_120000")
    engine = build_engine(store)

    result = engine.salvage_recording(recording_job("so101_pens", started))

    assert result["dataset_id"], "the operator must be able to reach the data from the panel"
    assert result["recorded_repo_id"] == "so101_pens_20260731_120000"
    assert result["total_frames"] == 597
    assert result["salvaged"] is True


def test_a_salvaged_recording_is_never_graded_verified(store: DatasetStore) -> None:
    """A run that did not finish has not earned it, whatever the file count says."""
    started = datetime.now(UTC)
    write_dataset(store, "so101_pens_20260731_120000")
    engine = build_engine(store)

    result = engine.salvage_recording(recording_job("so101_pens", started))

    assert result["integrity_status"] == "incomplete"
    assert any("did not finish" in problem for problem in result["problems"])


def test_a_recording_that_wrote_nothing_says_so_instead_of_inventing_a_dataset(
    store: DatasetStore,
) -> None:
    engine = build_engine(store)

    result = engine.salvage_recording(recording_job("so101_pens", datetime.now(UTC)))

    assert result["recorded_repo_id"] is None
    assert "before writing anything" in result["artifact_error"]
    assert "dataset_id" not in result


def test_salvage_ignores_a_job_that_was_not_a_recording(store: DatasetStore) -> None:
    from hashtag_robotics.models import JobKind, JobRecord, TargetMode

    engine = build_engine(store)
    job = JobRecord(
        kind=JobKind.TELEOPERATION,
        target_mode=TargetMode.REAL,
        parameters={"repo_id": "so101_pens"},
        requested_by="test",
    )

    assert engine.salvage_recording(job) == {}
