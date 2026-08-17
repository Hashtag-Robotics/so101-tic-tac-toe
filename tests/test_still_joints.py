"""Five moving joints hide a sixth that did not move.

The degenerate check takes the widest joint, so a recording where one joint
held still for the whole take grades `verified`. Measured on this disk: a real
recording whose `shoulder_lift` travelled 0.27 units across 597 frames, and a
simulated take of a grasping task where the gripper never opened.

Reported, never graded: whether a still joint is a fault depends on the task,
and that is the operator's call.
"""

from __future__ import annotations

import json

import pytest

from hashtag_robotics.dataset import STILL_JOINT_RANGE, DatasetStore
from hashtag_robotics.repository import Repository


@pytest.fixture
def store(settings) -> DatasetStore:
    return DatasetStore(settings, Repository(settings.database_path))


def write_stats(root, minimum: list[float], maximum: list[float]) -> None:
    meta = root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "stats.json").write_text(json.dumps({"action": {"min": minimum, "max": maximum}}))


NAMES = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos"]
INFO = {"features": {"action": {"names": NAMES}}}


def test_a_joint_that_never_moved_is_named(store, tmp_path) -> None:
    write_stats(tmp_path, [0.0, -103.87, 10.0], [95.0, -103.60, 90.0])

    still = store._still_joints(tmp_path, INFO)

    assert still == ["shoulder_lift.pos"]


def test_a_recording_where_everything_moved_names_nothing(store, tmp_path) -> None:
    write_stats(tmp_path, [0.0, -50.0, 10.0], [95.0, 50.0, 90.0])

    assert store._still_joints(tmp_path, INFO) == []


def test_the_threshold_is_not_exact_equality(store, tmp_path) -> None:
    """Servo noise means a held joint reports a small non-zero span."""
    assert STILL_JOINT_RANGE > 0

    write_stats(tmp_path, [0.0, 0.0, 0.0], [200.0, STILL_JOINT_RANGE / 2, 200.0])

    assert store._still_joints(tmp_path, INFO) == ["shoulder_lift.pos"]


def test_a_position_is_named_when_the_recording_did_not_name_it(store, tmp_path) -> None:
    write_stats(tmp_path, [0.0, 0.0], [200.0, 0.0])

    still = store._still_joints(tmp_path, {"features": {}})

    assert still == ["joint 1"]


def test_a_still_joint_does_not_fail_the_recording(store, tmp_path) -> None:
    """A grasping task that never uses the wrist is still a real recording."""
    write_stats(tmp_path, [0.0, -103.87, 10.0], [95.0, -103.60, 90.0])

    report = {
        "problems": [],
        "codebase_version": "v3.0",
        "total_episodes": 1,
        "files": {"data_parquet": 1, "stats": True, "videos": {}},
        "ranges": {"action": 95.0},
        "still_joints": ["shoulder_lift.pos"],
    }

    assert store._grade(report) == "verified"
    assert report["problems"] == []


@pytest.mark.parametrize("payload", ["{", ""])
def test_unreadable_statistics_report_nothing_rather_than_raising(
    store, tmp_path, payload: str
) -> None:
    (tmp_path / "meta").mkdir(parents=True, exist_ok=True)
    (tmp_path / "meta" / "stats.json").write_text(payload)

    assert store._still_joints(tmp_path, INFO) == []
