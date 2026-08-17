from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import DatasetStore
from hashtag_robotics.policy import PolicyError, PolicyStore
from hashtag_robotics.repository import Repository

REPO_ID = "pausiber/so101_kalemi_al"

# Trimmed from a real LeRobotDataset v3.0 recorded on the SO-101.
INFO = {
    "codebase_version": "v3.0",
    "robot_type": "so101_follower",
    "total_episodes": 3,
    "total_frames": 120,
    "total_tasks": 1,
    "fps": 30,
    "splits": {"train": "0:3"},
    "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
    "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
    "features": {
        "action": {"dtype": "float32", "shape": [6], "names": ["shoulder_pan.pos"]},
        "observation.state": {"dtype": "float32", "shape": [6], "names": ["shoulder_pan.pos"]},
        "observation.images.front": {"dtype": "video", "shape": [480, 640, 3], "names": None},
        "observation.images.wrist": {"dtype": "video", "shape": [480, 640, 3], "names": None},
        "timestamp": {"dtype": "float32", "shape": [1], "names": None},
    },
}


def write_dataset(root: Path, *, info: dict[str, Any] | None = None, complete: bool = True) -> Path:
    directory = root / REPO_ID
    (directory / "meta").mkdir(parents=True, exist_ok=True)
    (directory / "meta" / "info.json").write_text(json.dumps(info if info is not None else INFO))
    if not complete:
        return directory

    (directory / "meta" / "stats.json").write_text("{}")
    (directory / "meta" / "tasks.parquet").write_bytes(b"")
    (directory / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (directory / "data" / "chunk-000" / "file-000.parquet").write_bytes(b"")
    for key in ("observation.images.front", "observation.images.wrist"):
        chunk = directory / "videos" / key / "chunk-000"
        chunk.mkdir(parents=True, exist_ok=True)
        (chunk / "file-000.mp4").write_bytes(b"")
    return directory


def write_episode_contract(
    directory: Path,
    *,
    tasks: list[str],
    video_seconds: list[float] | None = None,
) -> None:
    import pandas as pd

    video_seconds = video_seconds or [40 / 30] * len(tasks)
    cumulative = [0.0]
    for duration in video_seconds:
        cumulative.append(cumulative[-1] + duration)

    rows = []
    for index, task in enumerate(tasks):
        row: dict[str, Any] = {
            "episode_index": index,
            "tasks": [task],
            "length": 40,
        }
        for feature in ("observation.images.front", "observation.images.wrist"):
            prefix = f"videos/{feature}"
            row[f"{prefix}/chunk_index"] = 0
            row[f"{prefix}/file_index"] = 0
            row[f"{prefix}/from_timestamp"] = cumulative[index]
            row[f"{prefix}/to_timestamp"] = cumulative[index + 1]
        rows.append(row)

    episodes = directory / "meta" / "episodes" / "chunk-000"
    episodes.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(episodes / "file-000.parquet", index=False)
    (directory / "meta" / "hashtag_episode_plan.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "dataset_episode_index": index,
                    "global_episode": index + 1,
                    "instruction": task,
                }
            )
            + "\n"
            for index, task in enumerate(tasks)
        )
    )


@pytest.fixture
def store(tmp_path: Path) -> DatasetStore:
    settings = Settings(data_dir=tmp_path / "state", open_browser=False)
    settings.ensure_directories()
    return DatasetStore(settings, Repository(settings.database_path))


def test_a_complete_dataset_is_verified_from_its_files(store: DatasetStore, tmp_path: Path) -> None:
    write_dataset(store.settings.lerobot_home)

    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "verified"
    assert report["problems"] == []
    assert report["total_episodes"] == 3
    assert report["total_frames"] == 120
    assert report["fps"] == 30
    assert report["robot_type"] == "so101_follower"
    assert report["camera_keys"] == [
        "observation.images.front",
        "observation.images.wrist",
    ]
    assert report["action_shape"] == [6]
    assert report["files"]["data_parquet"] == 1
    assert report["files"]["videos"]["observation.images.front"] == 1


def test_episode_plan_and_video_windows_are_part_of_integrity(
    store: DatasetStore,
) -> None:
    directory = write_dataset(store.settings.lerobot_home)
    write_episode_contract(
        directory,
        tasks=["first", "wrong second", "third"],
        video_seconds=[40 / 30, 10.0, 40 / 30],
    )
    sidecar = directory / "meta" / "hashtag_episode_plan.jsonl"
    planned = [json.loads(line) for line in sidecar.read_text().splitlines()]
    planned[1]["instruction"] = "second"
    sidecar.write_text("".join(json.dumps(row) + "\n" for row in planned))

    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "incomplete"
    assert report["episode_audit"]["task_mismatches"] == [1]
    assert {mismatch["camera"] for mismatch in report["episode_audit"]["video_mismatches"]} == {
        "observation.images.front",
        "observation.images.wrist",
    }
    problems = " ".join(report["problems"])
    assert "task mismatch" in problems
    assert "10.000s" in problems


def test_a_matching_episode_contract_is_verified(store: DatasetStore) -> None:
    directory = write_dataset(store.settings.lerobot_home)
    write_episode_contract(directory, tasks=["first", "second", "third"])

    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "verified"
    assert report["episode_audit"]["problems"] == []


def test_metadata_without_data_files_is_incomplete(store: DatasetStore) -> None:
    """The real so101_kalemi_al dataset on this machine is exactly this case."""
    write_dataset(store.settings.lerobot_home, complete=False)

    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "incomplete"
    assert report["total_episodes"] == 3
    problems = " ".join(report["problems"])
    assert "data/" in problems
    assert "stats.json" in problems
    assert "observation.images.front" in problems


def test_a_dataset_that_was_never_recorded_is_missing(store: DatasetStore) -> None:
    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "missing"
    assert "is missing" in report["problems"][0]
    assert "total_episodes" not in report


def test_an_unsupported_codebase_version_is_not_verified(store: DatasetStore) -> None:
    write_dataset(store.settings.lerobot_home, info={**INFO, "codebase_version": "v2.1"})

    report = store.inspect(REPO_ID)

    assert report["integrity_status"] == "unsupported"
    assert "v2.1" in report["problems"][0]


def test_the_manifest_carries_the_measured_numbers(store: DatasetStore) -> None:
    write_dataset(store.settings.lerobot_home)
    report = store.inspect(REPO_ID)

    manifest = store.manifest(report, name="Kalemi al", task="Pick up the pen")

    assert manifest.episodes == 3
    assert manifest.total_frames == 120
    assert manifest.integrity_status == "verified"
    assert manifest.codebase_version == "v3.0"
    assert manifest.action_shape == [6]
    assert "observation.images.front" in manifest.features
    assert store.repository.get_entity("dataset", manifest.id, type(manifest)) is not None


def test_revalidating_updates_the_same_manifest(store: DatasetStore) -> None:
    directory = write_dataset(store.settings.lerobot_home)
    manifest = store.manifest(store.inspect(REPO_ID), name="Kalemi al", task="Pick up the pen")
    assert manifest.integrity_status == "verified"

    # Someone frees disk space by deleting the episode data.
    for parquet in (directory / "data").rglob("*.parquet"):
        parquet.unlink()

    refreshed = store.revalidate(manifest)

    assert refreshed.id == manifest.id
    assert refreshed.integrity_status == "incomplete"
    assert any("data/" in problem for problem in refreshed.integrity_report["problems"])


# --- checkpoints ---------------------------------------------------------------

POLICY_CONFIG = {
    "type": "act",
    "input_features": {
        "observation.state": {"type": "STATE", "shape": [6]},
        "observation.images.front": {"type": "VISUAL", "shape": [3, 480, 640]},
    },
    "output_features": {"action": {"type": "ACTION", "shape": [6]}},
}

TRAIN_CONFIG = {
    "dataset": {"repo_id": REPO_ID},
    "policy": {"type": "act", "device": "cuda"},
    "steps": 20000,
    "batch_size": 8,
}


def write_checkpoint(output_dir: Path, step: str, *, weights: bool = True) -> Path:
    pretrained = output_dir / "checkpoints" / step / "pretrained_model"
    pretrained.mkdir(parents=True, exist_ok=True)
    (pretrained / "config.json").write_text(json.dumps(POLICY_CONFIG))
    (pretrained / "train_config.json").write_text(json.dumps(TRAIN_CONFIG))
    if weights:
        (pretrained / "model.safetensors").write_bytes(b"weights")
    return pretrained


@pytest.fixture
def policies(tmp_path: Path) -> PolicyStore:
    settings = Settings(data_dir=tmp_path / "policy-state", open_browser=False)
    settings.ensure_directories()
    return PolicyStore(settings, Repository(settings.database_path))


def test_the_last_symlink_wins_over_the_highest_step(
    policies: PolicyStore,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "outputs" / "train" / "act"
    write_checkpoint(output_dir, "005000")
    write_checkpoint(output_dir, "010000")
    (output_dir / "checkpoints" / "last").symlink_to(output_dir / "checkpoints" / "005000")

    assert policies.latest_checkpoint(output_dir).name == "005000"


def test_without_a_link_the_highest_step_is_used(policies: PolicyStore, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs" / "train" / "act"
    write_checkpoint(output_dir, "005000")
    write_checkpoint(output_dir, "010000")

    assert policies.latest_checkpoint(output_dir).name == "010000"


def test_a_checkpoint_is_read_from_its_own_config(policies: PolicyStore, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs" / "train" / "act"
    write_checkpoint(output_dir, "010000")

    report = policies.inspect(output_dir)

    assert report["step"] == 10000
    assert report["policy_type"] == "act"
    assert report["source_repo_id"] == REPO_ID
    assert report["training_steps"] == 20000
    assert report["device"] == "cuda"
    assert report["action_shape"] == [6]
    assert report["weights_bytes"] > 0


def test_a_checkpoint_without_weights_is_refused(policies: PolicyStore, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs" / "train" / "act"
    write_checkpoint(output_dir, "010000", weights=False)

    with pytest.raises(PolicyError, match="model.safetensors"):
        policies.inspect(output_dir)


def test_a_training_run_that_never_wrote_a_checkpoint_has_no_policy(
    policies: PolicyStore,
    tmp_path: Path,
) -> None:
    with pytest.raises(PolicyError, match="No checkpoints directory"):
        policies.inspect(tmp_path / "outputs" / "train" / "never-ran")


def test_the_policy_manifest_maps_its_own_camera_features(
    policies: PolicyStore,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "outputs" / "train" / "act"
    write_checkpoint(output_dir, "010000")

    manifest = policies.manifest(policies.inspect(output_dir), name="ACT @ 10k")

    assert manifest.policy_type == "act"
    assert manifest.checkpoint_step == 10000
    assert manifest.source_repo_id == REPO_ID
    assert manifest.camera_mapping == {"front": "observation.images.front"}
    assert manifest.compatibility_status == "checkpoint-read"
    assert "action" in manifest.expected_features


def test_a_hub_policy_is_downloaded_at_a_pinned_revision_and_registered(
    policies: PolicyStore,
    monkeypatch,
) -> None:
    revision = "a" * 40
    monkeypatch.setattr("hashtag_robotics.policy.get_token", lambda: "hf_test_credential")
    monkeypatch.setattr(
        "hashtag_robotics.policy.model_info",
        lambda *args, **kwargs: SimpleNamespace(sha=revision),
    )

    def fake_download(*, local_dir: Path, ignore_patterns: list[str], **kwargs) -> str:
        assert "checkpoints/**" in ignore_patterns
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True)
        config = {
            **POLICY_CONFIG,
            "type": "smolvla",
            "input_features": {
                "observation.state": {"shape": [6]},
                "observation.images.camera1": {"shape": [3, 256, 256]},
                "observation.images.camera2": {"shape": [3, 256, 256]},
                "observation.images.camera3": {"shape": [3, 256, 256]},
                "observation.images.empty_camera_0": {"shape": [3, 480, 640]},
            },
            "empty_cameras": 1,
        }
        (local_dir / "config.json").write_text(json.dumps(config))
        (local_dir / "model.safetensors").write_bytes(b"weights")
        (local_dir / "policy_preprocessor.json").write_text("{}")
        (local_dir / "policy_postprocessor.json").write_text("{}")
        return str(local_dir)

    monkeypatch.setattr("hashtag_robotics.policy.snapshot_download", fake_download)

    manifest = policies.import_from_hub(
        "HashtagRobotics/tic-tac-toe",
        name="Tic-Tac-Toe 80K",
        camera_mapping={
            "observation.images.top": "observation.images.camera1",
            "observation.images.wrist": "observation.images.camera2",
        },
    )

    assert manifest.model_revision == revision
    assert manifest.model_repo_id == "HashtagRobotics/tic-tac-toe"
    assert manifest.compatibility_status == "hub-checkpoint-read"
    assert manifest.empty_cameras == 1
    assert manifest.action_shape == [6]
    assert "observation.images.empty_camera_0" not in manifest.expected_features
    assert manifest.checkpoint is not None
    assert Path(manifest.checkpoint).is_relative_to(policies.settings.policy_dir)
    assert (Path(manifest.checkpoint) / "model.safetensors").is_file()


def test_dataset_validation_rereads_the_disk(client: TestClient, tmp_path: Path) -> None:
    directory = write_dataset(tmp_path / "lerobot-data")
    created = client.post(
        "/api/datasets",
        json={"name": "Kalemi al", "task": "Pick up the pen", "repo_id": REPO_ID},
    ).json()
    assert created["integrity_status"] == "unverified"

    def validate() -> dict[str, Any]:
        response = client.post(
            "/api/jobs",
            json={
                "kind": "dataset_validate",
                "target_mode": "read_only",
                "parameters": {"dataset_id": created["id"]},
                "resources": [],
                "requested_by": "test",
            },
        )
        job_id = response.json()["id"]
        for _ in range(200):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["state"] in {"completed", "failed", "aborted", "blocked"}:
                return job
            time.sleep(0.05)
        raise AssertionError("dataset_validate never finished")

    verified = validate()
    assert verified["result"]["integrity_status"] == "verified"
    assert verified["result"]["episodes"] == 3
    assert verified["result"]["total_frames"] == 120

    for video in directory.rglob("*.mp4"):
        video.unlink()

    degraded = validate()
    assert degraded["result"]["integrity_status"] == "incomplete"
    assert any("observation.images" in problem for problem in degraded["result"]["problems"])


def write_at(root: Path, repo_id: str, *, episodes: int, frames: int) -> Path:
    """A minimal but complete dataset under an arbitrary repo id."""
    info = {**INFO, "total_episodes": episodes, "total_frames": frames}
    directory = root / repo_id
    (directory / "meta").mkdir(parents=True, exist_ok=True)
    (directory / "meta" / "info.json").write_text(json.dumps(info))
    return directory


def test_a_recording_is_found_under_the_name_lerobot_actually_used(
    store: DatasetStore,
) -> None:
    """LeRobot stamps a timestamp onto repo_id when it creates a dataset.

    Looking only for the requested name reported a successful 20-second
    recording as 'nothing was recorded'.
    """
    root = store.settings.lerobot_home
    requested = "mertkirgil/so101_session"
    stamped = f"{requested}_20260730_234146"
    write_at(root, stamped, episodes=1, frames=477)

    assert store.resolve_recorded(requested) == stamped

    report = store.inspect(store.resolve_recorded(requested))
    assert report["integrity_status"] != "missing"
    assert report["total_episodes"] == 1
    assert report["total_frames"] == 477


def test_the_newest_run_wins_when_a_name_was_recorded_twice(store: DatasetStore) -> None:
    root = store.settings.lerobot_home
    requested = "mertkirgil/so101_session"
    write_at(root, f"{requested}_20260730_120000", episodes=1, frames=100)
    write_at(root, f"{requested}_20260730_234146", episodes=2, frames=500)

    assert store.resolve_recorded(requested).endswith("_20260730_234146")


def test_a_stamped_directory_beats_an_unstamped_one_of_the_same_name(
    store: DatasetStore,
) -> None:
    """Reversed deliberately: the stamp is the evidence a recording ran.

    LeRobot stamps at creation and only skips it on resume, where the repo id it
    is handed is *already* stamped. So a directory under the bare requested name
    cannot be what this recording produced -- it is an older or imported dataset
    that happens to share the name. Preferring it handed the operator someone
    else's three episodes instead of the one just recorded, and nothing about
    the answer looked wrong.
    """
    root = store.settings.lerobot_home
    requested = "mertkirgil/so101_session"
    write_at(root, requested, episodes=3, frames=900)
    write_at(root, f"{requested}_20260730_234146", episodes=1, frames=100)

    assert store.resolve_recorded(requested) == f"{requested}_20260730_234146"


def test_a_resumed_recording_keeps_its_already_stamped_name(store: DatasetStore) -> None:
    """`stamp_repo_id` is not called on resume, so the id arrives already stamped."""
    root = store.settings.lerobot_home
    resumed = "mertkirgil/so101_session_20260730_234146"
    write_at(root, resumed, episodes=4, frames=1200)

    assert store.resolve_recorded(resumed) == resumed


def test_resolve_falls_back_to_the_requested_name_when_nothing_exists(
    store: DatasetStore,
) -> None:
    assert store.resolve_recorded("mertkirgil/nothing") == "mertkirgil/nothing"


def test_recording_status_separates_saved_episodes_from_the_current_buffer(
    store: DatasetStore,
) -> None:
    requested = "hashtagrobotics/tic-tac-toe-so101"
    stamped = f"{requested}_20260814_162030"
    directory = store.settings.lerobot_home / stamped
    (directory / "meta").mkdir(parents=True)
    (directory / "meta" / "info.json").write_text(
        json.dumps({"total_episodes": 2, "total_frames": 900, "fps": 30})
    )
    for role, count in (("top", 17), ("wrist", 16)):
        episode = directory / "images" / f"observation.images.{role}" / "episode-000002"
        episode.mkdir(parents=True)
        for index in range(count):
            (episode / f"frame-{index:06d}.png").touch()

    status = store.recording_status(requested)

    assert status["recorded_repo_id"] == stamped
    assert status["saved_episodes"] == 2
    assert status["saved_frames"] == 900
    assert status["buffered_frames"] == 16
    assert status["buffered_frames_by_camera"] == {
        "observation.images.top": 17,
        "observation.images.wrist": 16,
    }
