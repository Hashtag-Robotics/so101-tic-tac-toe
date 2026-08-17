"""A manifest registered under the asked-for name reports `missing` forever.

`lerobot-record` appends `_YYYYMMDD_HHMMSS` to every directory it creates. On
this disk a real recording -- 477 frames off the arm -- sat one directory over
from where its row pointed, and the dashboard called it missing.
"""

from __future__ import annotations

import json

import pytest

from hashtag_robotics.dataset import DatasetStore
from hashtag_robotics.models import DatasetManifest
from hashtag_robotics.repository import Repository


@pytest.fixture
def store(settings) -> DatasetStore:
    return DatasetStore(settings, Repository(settings.database_path))


def write(settings, repo_id: str) -> None:
    directory = settings.lerobot_home / repo_id
    (directory / "meta").mkdir(parents=True, exist_ok=True)
    (directory / "meta" / "info.json").write_text(
        json.dumps({"codebase_version": "v3.0", "fps": 30, "total_episodes": 1, "features": {}})
    )


def manifest(repo_id: str) -> DatasetManifest:
    return DatasetManifest(name="Take", task="pick", repo_id=repo_id)


def test_a_row_pointing_at_the_unstamped_name_finds_the_recording(store, settings) -> None:
    write(settings, "u/take_20260730_234146")

    followed = store._follow_stamp(manifest("u/take"))

    assert followed.repo_id == "u/take_20260730_234146"
    assert followed.provenance["followed_stamp_from"] == "u/take"


def test_a_row_that_already_points_at_its_data_is_left_alone(store, settings) -> None:
    write(settings, "u/take")

    followed = store._follow_stamp(manifest("u/take"))

    assert followed.repo_id == "u/take"
    assert "followed_stamp_from" not in followed.provenance


def test_two_stamped_recordings_are_not_guessed_between(store, settings) -> None:
    """Which one someone meant is a choice, and guessing is how wrong data is adopted."""
    write(settings, "u/take_20260730_234146")
    write(settings, "u/take_20260731_101500")

    followed = store._follow_stamp(manifest("u/take"))

    assert followed.repo_id == "u/take"


def test_a_stamped_directory_with_no_metadata_is_not_adopted(store, settings) -> None:
    (settings.lerobot_home / "u" / "take_20260730_234146").mkdir(parents=True)

    assert store._follow_stamp(manifest("u/take")).repo_id == "u/take"


def test_nothing_on_disk_at_all_changes_nothing(store) -> None:
    assert store._follow_stamp(manifest("u/take")).repo_id == "u/take"


def test_the_namespace_survives(store, settings) -> None:
    write(settings, "mertkirgil/so101_hil_t7_kamerasiz_20260730_234146")

    followed = store._follow_stamp(manifest("mertkirgil/so101_hil_t7_kamerasiz"))

    assert followed.repo_id == "mertkirgil/so101_hil_t7_kamerasiz_20260730_234146"


def test_revalidating_over_the_api_recovers_the_recording(client) -> None:
    runtime = client.app.state.runtime
    write(runtime.settings, "u/take_20260730_234146")
    dataset_id = client.post(
        "/api/datasets", json={"name": "Take", "task": "pick", "repo_id": "u/take"}
    ).json()["id"]

    revalidated = client.post(f"/api/datasets/{dataset_id}/revalidate").json()

    assert revalidated["repo_id"] == "u/take_20260730_234146"
    assert revalidated["integrity_status"] != "missing"
