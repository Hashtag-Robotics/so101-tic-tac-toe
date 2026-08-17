"""A row that answers to no URL should never be created.

`id` has a default factory, so leaving it out mints one. Sending an empty
string overrides that default, and the resulting row lists fine but can never
be addressed: `/api/datasets//revalidate` is not a route, and neither is the
DELETE. This came up the first time the API was driven by something other than
the dashboard, which is exactly how an agent will drive it.
"""

from __future__ import annotations

import pytest

from hashtag_robotics.models import CameraProfile, DatasetManifest, RobotProfile


def test_omitting_the_id_mints_one() -> None:
    manifest = DatasetManifest(name="Takes", task="pick")

    assert manifest.id.startswith("dataset_")


def test_a_blank_id_is_refused() -> None:
    with pytest.raises(ValueError, match="may not be blank"):
        DatasetManifest(id="", name="Takes", task="pick")


def test_whitespace_is_not_an_id_either() -> None:
    """`str_strip_whitespace` turns "  " into "" before this validator runs."""
    with pytest.raises(ValueError, match="may not be blank"):
        DatasetManifest(id="   ", name="Takes", task="pick")


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (RobotProfile, {"name": "x"}),
        (CameraProfile, {"name": "x", "device_fingerprint": "f", "semantic_name": "wrist"}),
    ],
)
def test_the_rule_is_not_only_about_datasets(model: type, fields: dict) -> None:
    """Every entity is reachable by id, so every entity needs a usable one."""
    with pytest.raises(ValueError, match="may not be blank"):
        model(id="", **fields)


def test_the_api_refuses_a_blank_id(client) -> None:
    response = client.post("/api/datasets", json={"id": "", "name": "Takes", "task": "pick"})

    assert response.status_code == 422


def test_the_api_still_assigns_one_when_the_field_is_absent(client) -> None:
    response = client.post("/api/datasets", json={"name": "Takes", "task": "pick"})

    assert response.status_code == 200
    assert response.json()["id"].startswith("dataset_")
