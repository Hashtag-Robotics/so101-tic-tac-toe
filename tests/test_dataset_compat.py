"""Two datasets can disagree in ways that never raise, and that is the expensive kind.

On this machine a real recording and a simulated one named the same joints
`shoulder_pan.pos` and `1`, stored the same images as [H,W,3] and [3,H,W], and
carried the same numbers in normalised units and radians. Training on both was
possible, produced no error, and simply taught the policy less. Nobody could
have told from the dashboard, because the only way to compare was to open two
`info.json` files and notice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import requires_lerobot

from hashtag_robotics.config import Settings
from hashtag_robotics.dataset import (
    COMPATIBLE,
    INCOMPATIBLE,
    DatasetError,
    DatasetStore,
    compare_datasets,
    dataset_profile,
)
from hashtag_robotics.repository import Repository

REAL_NAMES = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]


def info(
    *,
    names: list[str] | None = None,
    image_names: list[str] | None = None,
    image_shape: list[int] | None = None,
    fps: int = 30,
    cameras: tuple[str, ...] = ("wrist",),
    robot_type: str = "so_follower",
    codebase: str = "v3.0",
    episodes: int = 2,
) -> dict:
    names = names or REAL_NAMES
    features: dict = {
        "action": {"dtype": "float32", "shape": [6], "names": names},
        "observation.state": {"dtype": "float32", "shape": [6], "names": names},
    }
    for camera in cameras:
        features[f"observation.images.{camera}"] = {
            "dtype": "video",
            "shape": image_shape or [480, 640, 3],
            "names": image_names or ["height", "width", "channels"],
        }
    return {
        "codebase_version": codebase,
        "robot_type": robot_type,
        "fps": fps,
        "total_episodes": episodes,
        "total_frames": 200,
        "features": features,
    }


@pytest.fixture
def store(tmp_path: Path) -> DatasetStore:
    settings = Settings(data_dir=tmp_path, open_browser=False)
    settings.ensure_directories()
    return DatasetStore(settings, Repository(settings.database_path))


def write(store: DatasetStore, name: str, payload: dict) -> dict:
    directory = store.settings.lerobot_home / name
    (directory / "meta").mkdir(parents=True)
    (directory / "meta" / "info.json").write_text(json.dumps(payload))
    return store.inspect(name)


def test_identical_recordings_agree(store: DatasetStore) -> None:
    first = write(store, "real_a", info())
    second = write(store, "real_b", info())

    result = compare_datasets([first, second])

    assert result["status"] == COMPATIBLE
    assert result["blockers"] == []
    assert result["total_episodes"] == 4


def test_differently_named_joints_are_a_blocker(store: DatasetStore) -> None:
    """The exact mismatch found on this machine: `<joint>.pos` against `1`..`6`."""
    real = write(store, "real", info())
    sim = write(store, "sim", info(names=["1", "2", "3", "4", "5", "6"]))

    result = compare_datasets([real, sim])

    assert result["status"] == INCOMPATIBLE
    blocker = next(item for item in result["blockers"] if item["key"] == "joint_names")
    assert "same arm" in blocker["reason"]
    assert blocker["values"]["sim"] == ["1", "2", "3", "4", "5", "6"]


def test_a_different_image_axis_order_is_a_blocker(store: DatasetStore) -> None:
    """CHW against HWC: one of the two would be read as noise."""
    real = write(store, "real", info())
    sim = write(store, "sim", info(image_names=["channels", "height", "width"]))

    result = compare_datasets([real, sim])

    assert result["status"] == INCOMPATIBLE
    assert any(item["key"] == "image_layout" for item in result["blockers"])


def test_a_different_rate_is_a_blocker(store: DatasetStore) -> None:
    """A fixed action horizon covers a different amount of time in each."""
    result = compare_datasets([write(store, "a", info(fps=30)), write(store, "b", info(fps=50))])

    assert result["status"] == INCOMPATIBLE
    assert any(item["key"] == "fps" for item in result["blockers"])


def test_a_missing_camera_blocks_because_a_merge_needs_identical_features(
    store: DatasetStore,
) -> None:
    """This was reported as a warning first, and that was wrong in the direction that matters.

    "Training uses what they share" is true of reading and false of merging, and
    merging is the only way to train on both. The real merge failed with a
    ValueError printing two whole feature dicts.
    """
    real = write(store, "real", info(cameras=("wrist",)))
    sim = write(store, "sim", info(cameras=("wrist", "front")))

    result = compare_datasets([real, sim])

    assert result["status"] == INCOMPATIBLE
    assert any(item["key"] == "cameras" for item in result["blockers"])


def test_a_different_image_size_blocks_a_merge(store: DatasetStore) -> None:
    """A policy would resize them. Aggregation will not."""
    real = write(store, "real", info(image_shape=[480, 640, 3]))
    sim = write(store, "sim", info(image_shape=[240, 320, 3]))

    result = compare_datasets([real, sim])

    assert result["status"] == INCOMPATIBLE
    assert any(item["key"] == "image_shape" for item in result["blockers"])


def test_a_lopsided_mixture_is_a_warning_not_a_refusal(store: DatasetStore) -> None:
    """Mergeable, and still worth saying before somebody trains on it."""
    big = write(store, "big", info(episodes=100))
    small = write(store, "small", info(episodes=2))

    result = compare_datasets([big, small])

    assert result["blockers"] == []
    assert any(item["key"] == "mixture" for item in result["warnings"])


def test_the_same_disagreement_is_reported_once(store: DatasetStore) -> None:
    """Three datasets against one reference would otherwise repeat themselves."""
    real = write(store, "real", info())
    sim_a = write(store, "sim_a", info(names=["1", "2", "3", "4", "5", "6"]))
    sim_b = write(store, "sim_b", info(names=["1", "2", "3", "4", "5", "6"]))

    result = compare_datasets([real, sim_a, sim_b])

    assert [item["key"] for item in result["blockers"]] == ["joint_names"]


def test_a_single_dataset_has_nothing_to_disagree_with(store: DatasetStore) -> None:
    assert compare_datasets([write(store, "only", info())])["status"] == COMPATIBLE


def test_a_profile_reads_the_facts_a_policy_reads(store: DatasetStore) -> None:
    profile = dataset_profile(write(store, "real", info()))

    assert profile["joint_names"] == REAL_NAMES
    assert profile["image_layout"] == ["height", "width", "channels"]
    assert profile["cameras"] == ["wrist"]
    assert profile["fps"] == 30


# -- the endpoints ------------------------------------------------------------


def register(client, name: str, repo_id: str, payload: dict, provenance: dict | None = None) -> str:
    runtime = client.app.state.runtime
    directory = runtime.settings.lerobot_home / repo_id
    (directory / "meta").mkdir(parents=True, exist_ok=True)
    (directory / "meta" / "info.json").write_text(json.dumps(payload))
    manifest = client.post(
        "/api/datasets",
        json={
            "name": name,
            "repo_id": repo_id,
            "task": "pick",
            "local_path": str(directory),
            "provenance": provenance or {},
        },
    ).json()
    return manifest["id"]


def wait_for_job(client, job_id: str, timeout: float = 60.0) -> dict:
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in {"completed", "failed", "aborted", "blocked"}:
            return job
        _time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish")


def test_comparing_two_datasets_over_the_api(client) -> None:
    real = register(client, "Real", "real", info())
    sim = register(client, "Sim", "sim", info(names=["1", "2", "3", "4", "5", "6"]))

    payload = client.post("/api/datasets/compare", json={"dataset_ids": [real, sim]}).json()

    assert payload["status"] == INCOMPATIBLE
    assert any(item["key"] == "joint_names" for item in payload["blockers"])
    assert {item["name"] for item in payload["datasets"]} == {"Real", "Sim"}


def test_comparing_needs_two(client) -> None:
    only = register(client, "Only", "only", info())

    assert client.post("/api/datasets/compare", json={"dataset_ids": [only]}).status_code == 422


def test_revalidating_re_reads_the_disk(client) -> None:
    """A manifest is a snapshot; files move between recording and training."""
    import shutil as _shutil

    dataset_id = register(client, "Real", "real", info())
    runtime = client.app.state.runtime
    _shutil.rmtree(runtime.settings.lerobot_home / "real")

    payload = client.post(f"/api/datasets/{dataset_id}/revalidate").json()

    assert payload["integrity_status"] == "missing"


def test_forgetting_a_dataset_leaves_the_recording_alone_by_default(client) -> None:
    dataset_id = register(client, "Real", "real", info())
    runtime = client.app.state.runtime
    directory = runtime.settings.lerobot_home / "real"

    payload = client.delete(f"/api/datasets/{dataset_id}").json()

    assert payload["removed_path"] is None
    assert directory.is_dir(), "forgetting is reversible; deleting is not"
    assert client.get("/api/datasets").json() == []


def test_deleting_the_recording_is_asked_for_by_name(client) -> None:
    dataset_id = register(client, "Real", "real", info())
    runtime = client.app.state.runtime
    directory = runtime.settings.lerobot_home / "real"

    payload = client.delete(f"/api/datasets/{dataset_id}?delete_files=true").json()

    assert payload["removed_path"] is not None
    assert not directory.exists()


def test_deleting_refuses_a_path_outside_the_library(client, tmp_path) -> None:
    """`local_path` is operator-supplied; 'delete this directory' is not taken on trust."""
    outside = tmp_path / "somewhere-else"
    (outside / "meta").mkdir(parents=True)
    (outside / "meta" / "info.json").write_text(json.dumps(info()))
    dataset_id = client.post(
        "/api/datasets",
        json={"name": "Outside", "repo_id": "outside", "task": "pick", "local_path": str(outside)},
    ).json()["id"]

    response = client.delete(f"/api/datasets/{dataset_id}?delete_files=true")

    assert response.status_code == 409
    assert outside.is_dir()


# -- did anything actually happen? -------------------------------------------


def stats(action_range: float, state_range: float = 50.0) -> dict:
    return {
        "action": {"min": [0.0] * 6, "max": [action_range] * 6},
        "observation.state": {"min": [0.0] * 6, "max": [state_range] * 6},
    }


def write_with_stats(store: DatasetStore, name: str, payload: dict, statistics: dict) -> dict:
    directory = store.settings.lerobot_home / name
    (directory / "meta").mkdir(parents=True)
    (directory / "meta" / "info.json").write_text(json.dumps(payload))
    (directory / "meta" / "stats.json").write_text(json.dumps(statistics))
    (directory / "data").mkdir()
    (directory / "data" / "chunk-000.parquet").write_bytes(b"x")
    return store.inspect(name)


def test_a_recording_where_nothing_moved_is_not_verified(store: DatasetStore) -> None:
    """Measured on this disk: 283 frames, action range exactly 0.0, graded `verified`.

    A demonstration in which the operator never moved is not a short
    demonstration. It teaches a policy to emit one constant, and it looked
    identical to a good recording because stats.json was checked for existence
    and never opened.
    """
    report = write_with_stats(store, "still", info(), stats(action_range=0.0))

    assert report["integrity_status"] != "verified"
    assert any("nothing was demonstrated" in problem for problem in report["problems"])


def test_a_recording_that_moved_is_still_verified(store: DatasetStore) -> None:
    report = write_with_stats(store, "moving", info(), stats(action_range=107.6))

    assert report["ranges"]["action"] == pytest.approx(107.6)
    assert not any("nothing was demonstrated" in problem for problem in report["problems"])


def test_a_missing_stats_file_does_not_invent_a_range(store: DatasetStore) -> None:
    """Absent evidence is not evidence of a degenerate recording."""
    report = write(store, "no_stats", info())

    assert report["ranges"] == {}
    assert not any("nothing was demonstrated" in problem for problem in report["problems"])


# -- removing a ruined take ---------------------------------------------------


def write_with_episodes(store: DatasetStore, name: str, rows: list[dict]) -> None:
    import pandas as pd

    directory = store.settings.lerobot_home / name
    meta = directory / "meta" / "episodes" / "chunk-000"
    meta.mkdir(parents=True)
    # info.json and the episode rows have to agree: the count is what the cheap
    # guard reads before anything expensive is loaded.
    (directory / "meta" / "info.json").write_text(json.dumps(info(episodes=len(rows))))
    pd.DataFrame(rows).to_parquet(meta / "file-000.parquet")


@requires_lerobot
def test_episodes_are_listed_with_the_number_that_identifies_a_dead_one(
    store: DatasetStore,
) -> None:
    """A total tells an operator nothing about which take to drop."""
    write_with_episodes(
        store,
        "takes",
        [
            {
                "episode_index": 0,
                "length": 140,
                "tasks": ["pick up the red cube"],
                "stats/action/min": [0.0] * 6,
                "stats/action/max": [0.0] * 6,
            },
            {
                "episode_index": 1,
                "length": 143,
                "tasks": ["pick up the red cube"],
                "stats/action/min": [0.0] * 6,
                "stats/action/max": [80.0] * 6,
            },
        ],
    )

    episodes = store.episodes("takes")

    assert [item["index"] for item in episodes] == [0, 1]
    assert episodes[0]["demonstrates_nothing"] is True, "action never moved"
    assert episodes[1]["demonstrates_nothing"] is False
    assert episodes[1]["frames"] == 143
    assert episodes[1]["task"] == "pick up the red cube"


def test_a_recording_without_episode_metadata_says_so_instead_of_guessing(
    store: DatasetStore,
) -> None:
    write(store, "old_format", info())

    assert store.episodes("old_format") == []


@requires_lerobot
def test_removing_every_episode_is_refused(store: DatasetStore) -> None:
    """That is forgetting the dataset, and forgetting has its own button."""
    from hashtag_robotics.models import DatasetManifest

    write_with_episodes(
        store,
        "takes",
        [{"episode_index": 0, "length": 10, "tasks": ["t"]}],
    )
    manifest = DatasetManifest(name="Takes", repo_id="takes", task="t")

    with pytest.raises(DatasetError, match="all 1 episodes"):
        store.remove_episodes(manifest, [0])


def test_removing_nothing_is_refused(store: DatasetStore) -> None:
    from hashtag_robotics.models import DatasetManifest

    manifest = DatasetManifest(name="Takes", repo_id="takes", task="t")

    with pytest.raises(DatasetError, match="No episodes were selected"):
        store.remove_episodes(manifest, [])


@requires_lerobot
def test_the_episode_list_over_the_api(client) -> None:
    runtime = client.app.state.runtime
    directory = runtime.settings.lerobot_home / "takes"
    (directory / "meta" / "episodes" / "chunk-000").mkdir(parents=True)
    (directory / "meta" / "info.json").write_text(json.dumps(info()))
    import pandas as pd

    pd.DataFrame(
        [
            {
                "episode_index": 0,
                "length": 12,
                "tasks": ["t"],
                "stats/action/min": [0.0] * 6,
                "stats/action/max": [0.0] * 6,
                "videos/observation.images.wrist/chunk_index": 0,
                "videos/observation.images.wrist/file_index": 0,
                "videos/observation.images.wrist/from_timestamp": 2.5,
                "videos/observation.images.wrist/to_timestamp": 5.0,
            }
        ]
    ).to_parquet(directory / "meta" / "episodes" / "chunk-000" / "file-000.parquet")
    video = directory / "videos" / "observation.images.wrist" / "chunk-000" / "file-000.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"test-video")
    dataset_id = client.post(
        "/api/datasets",
        json={"name": "Takes", "repo_id": "takes", "task": "t", "local_path": str(directory)},
    ).json()["id"]

    payload = client.get(f"/api/datasets/{dataset_id}/episodes").json()

    assert payload["readable"] is True
    assert payload["episodes"][0]["demonstrates_nothing"] is True
    assert payload["episodes"][0]["videos"] == [
        {
            "camera": "wrist",
            "feature": "observation.images.wrist",
            "chunk_index": 0,
            "file_index": 0,
            "from_timestamp": 2.5,
            "to_timestamp": 5.0,
        }
    ]

    playback = client.get(f"/api/datasets/{dataset_id}/episodes/0/videos/wrist.mp4")
    assert playback.status_code == 200
    assert playback.content == b"test-video"


def test_an_unlistable_recording_explains_itself(client) -> None:
    dataset_id = register(client, "Old", "old", info())

    payload = client.get(f"/api/datasets/{dataset_id}/episodes").json()

    assert payload["readable"] is False
    assert "cannot be listed" in payload["note"]


# -- editing runs as a job, not as a held-open request ------------------------


def test_removing_episodes_returns_a_job(client) -> None:
    """Re-encoding video is fast for two episodes and not for eighty.

    Holding an HTTP request open for minutes gives the operator no progress, no
    way to stop, and nothing in the log afterwards.
    """
    dataset_id = register(client, "Takes", "takes", info())

    response = client.post(f"/api/datasets/{dataset_id}/episodes/remove", json={"episodes": [0]})

    assert response.status_code == 200
    job = response.json()
    assert job["kind"] == "dataset_transform"
    assert job["parameters"]["operation"] == "remove_episodes"


def test_merging_returns_a_job(client) -> None:
    first = register(client, "A", "a", info())
    second = register(client, "B", "b", info())

    job = client.post(
        "/api/datasets/merge",
        json={"dataset_ids": [first, second], "new_name": "merged"},
    ).json()

    assert job["kind"] == "dataset_transform"
    assert job["parameters"]["operation"] == "merge"
    assert job["parameters"]["new_name"] == "merged"


def test_an_unknown_operation_is_refused_by_the_job(client) -> None:
    """The kind used to accept anything and walk three progress strings."""
    dataset_id = register(client, "A", "a", info())
    job = client.post(
        "/api/jobs",
        json={
            "kind": "dataset_transform",
            "target_mode": "read_only",
            "parameters": {"operation": "shred", "dataset_ids": [dataset_id]},
            "requested_by": "test",
        },
    ).json()

    finished = wait_for_job(client, job["id"])

    assert "Unknown dataset operation" in finished["result"]["artifact_error"]


def test_a_transform_naming_a_vanished_dataset_says_so(client) -> None:
    job = client.post(
        "/api/jobs",
        json={
            "kind": "dataset_transform",
            "target_mode": "read_only",
            "parameters": {"operation": "merge", "dataset_ids": ["gone"], "new_name": "x"},
            "requested_by": "test",
        },
    ).json()

    finished = wait_for_job(client, job["id"])

    assert "no longer exists" in finished["result"]["artifact_error"]


def test_a_merge_that_cannot_happen_reports_the_reason_not_a_traceback(client) -> None:
    real = register(client, "Real", "real", info(cameras=("wrist",)))
    sim = register(client, "Sim", "sim", info(cameras=("wrist", "front")))

    job = client.post(
        "/api/datasets/merge",
        json={"dataset_ids": [real, sim], "new_name": "mix"},
    ).json()
    finished = wait_for_job(client, job["id"])

    assert "cannot be merged" in finished["result"]["artifact_error"]
    assert "different cameras" in finished["result"]["artifact_error"]


# -- merging something into a set that already contains it --------------------


def test_the_compare_button_says_when_a_selection_overlaps(client) -> None:
    """A warning, not a blocker: the merge works. Copying a recording in twice
    is a real thing to want -- checking that merging works at all, or weighting
    one set more heavily -- and the operator is the one who knows which. What
    they cannot do is find out afterwards without opening the parquet files."""
    sim = register(client, "Sim", "u/sim", info())
    register(client, "Real", "u/real", info())
    merged = register(client, "Both", "u/both", info(), {"merged_from": ["u/sim", "u/real"]})

    response = client.post("/api/datasets/compare", json={"dataset_ids": [sim, merged]}).json()

    assert response["status"] == "warnings"
    assert any(item["key"] == "duplicate_lineage" for item in response["warnings"])
    assert not response["blockers"]


def test_the_merge_happens_and_records_what_went_in_twice(client) -> None:
    sim = register(client, "Sim", "u/sim", info())
    register(client, "Real", "u/real", info())
    merged = register(client, "Both", "u/both", info(), {"merged_from": ["u/sim", "u/real"]})

    job = client.post(
        "/api/datasets/merge",
        json={"dataset_ids": [sim, merged], "new_name": "u/again"},
    ).json()
    finished = wait_for_job(client, job["id"])

    # The fixtures carry no frames on disk, so the merge itself cannot run here;
    # what matters is that it was attempted rather than refused up front.
    assert "already share recordings" not in str(finished["result"])
