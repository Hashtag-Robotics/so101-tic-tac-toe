"""When LeRobot refuses and every named field agrees, say which field differs.

Measured on this disk: two real recordings of the same arm, same camera, same
resolution, same codec, same fps, were refused for aggregation because one
LeRobot version wrote `video.is_depth_map` and a later one wrote
`is_depth_map`. Same value, renamed key. The dashboard said "features" and
showed nothing, which is a wall rather than a next step.
"""

from __future__ import annotations

from conftest import requires_lerobot

from hashtag_robotics.dataset import _feature_differences

VIDEO = {
    "dtype": "video",
    "shape": [480, 640, 3],
    "names": ["height", "width", "channels"],
}


def video(info: dict) -> dict:
    return {"observation.images.wrist": {**VIDEO, "info": info}}


def test_a_renamed_key_is_named_on_both_sides() -> None:
    older = video({"video.is_depth_map": False, "video.fps": 30})
    newer = video({"is_depth_map": False, "video.fps": 30})

    differences = _feature_differences(older, newer)

    info = differences["observation.images.wrist"]["info"]
    assert info["video.is_depth_map"] == {"a": False, "b": None}
    assert info["is_depth_map"] == {"a": None, "b": False}


@requires_lerobot
def test_encoder_settings_are_not_reported_because_lerobot_ignores_them() -> None:
    """Listing them would show eight disagreements where only one blocks."""
    older = video({"video.fps": 30})
    newer = video({"video.fps": 30, "video.crf": 30, "video.preset": 12})

    assert _feature_differences(older, newer) == {}


@requires_lerobot
def test_a_real_disagreement_survives_the_filter() -> None:
    older = video({"video.fps": 30, "video.crf": 30})
    newer = video({"video.fps": 60, "video.crf": 51})

    info = _feature_differences(older, newer)["observation.images.wrist"]["info"]

    assert info == {"video.fps": {"a": 30, "b": 60}}


def test_a_missing_feature_is_reported_whole() -> None:
    differences = _feature_differences(video({}), {})

    assert "observation.images.wrist" in differences


def test_identical_features_report_nothing() -> None:
    assert _feature_differences(video({"video.fps": 30}), video({"video.fps": 30})) == {}


def test_a_shape_difference_is_named() -> None:
    left = {"action": {"dtype": "float32", "shape": [6]}}
    right = {"action": {"dtype": "float32", "shape": [7]}}

    assert _feature_differences(left, right) == {"action": {"shape": {"a": [6], "b": [7]}}}
