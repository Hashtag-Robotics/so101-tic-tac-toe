"""The whole data pipeline was on the far side of the agent gateway.

Collecting, editing and publishing a recording were built, proven on the bench
against eighty-six episodes, and reachable only from a browser. An agent could
list recordings and start new ones; it could not look inside one, ask whether
two could be trained together, drop a ruined take, or send the result anywhere.
The role called `dataset_curator` could not curate.

These tests drive the actions through the gateway rather than the HTTP
endpoints, because the gateway is the door that had no coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hashtag_robotics.models import DatasetManifest, JobKind


def write_recording(
    tmp_path: Path,
    name: str,
    *,
    fps: int = 30,
    robot_type: str = "so101_follower",
) -> Path:
    """A recording as LeRobot leaves one, reduced to what the reader opens."""
    root = tmp_path / name
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(
        json.dumps(
            {
                "codebase_version": "v3.0",
                "robot_type": robot_type,
                "fps": fps,
                "total_episodes": 2,
                "total_frames": 120,
                "features": {
                    "action": {"dtype": "float32", "shape": [6]},
                    "observation.state": {"dtype": "float32", "shape": [6]},
                },
            }
        )
    )
    return root


@pytest.fixture
def library(client, tmp_path):
    """Two recordings that agree, registered the way a real one is."""
    registered = []
    for index, name in enumerate(("take_one", "take_two")):
        root = write_recording(tmp_path, name)
        manifest = DatasetManifest(
            id=f"dataset_{name}",
            name=name,
            task="pick",
            repo_id=f"u/{name}",
            local_path=str(root),
            episodes=2,
            total_frames=120,
            integrity_status="verified",
            provenance={"source": "simulation" if index else "real-arm"},
        )
        client.app.state.runtime.repository.upsert_entity("dataset", manifest)
        registered.append(manifest)
    return registered


def command(client, action: str, session: str = "agent_dataset_curator", **parameters):
    return client.post(
        "/api/agents/commands",
        json={"session_id": session, "action": action, "parameters": parameters},
    ).json()


def test_the_curator_can_look_inside_a_recording(client, library) -> None:
    """A total is not something an agent can act on.

    Knowing a recording holds two hundred frames says nothing about which take
    was ruined, and naming the take is the only way to remove it.
    """
    result = command(client, "inspect_dataset_episodes", dataset_id="dataset_take_one")

    assert result["accepted"] is True
    assert "episodes" in result["data"]


def test_an_unknown_recording_is_refused_by_name(client, library) -> None:
    result = command(client, "inspect_dataset_episodes", dataset_id="dataset_nope")

    assert result["accepted"] is False
    assert "dataset_nope" in result["message"]


def test_the_curator_can_ask_whether_two_can_be_trained_together(client, library) -> None:
    result = command(
        client,
        "compare_datasets",
        dataset_ids=["dataset_take_one", "dataset_take_two"],
    )

    assert result["accepted"] is True
    assert result["data"]["status"] in {"compatible", "warnings", "incompatible"}
    assert result["data"]["total_episodes"] == 4


def test_a_disagreement_names_the_field_rather_than_saying_no(client, tmp_path) -> None:
    """An agent told only 'no' requests the merge anyway."""
    repository = client.app.state.runtime.repository
    for name, fps in (("slow", 30), ("fast", 60)):
        repository.upsert_entity(
            "dataset",
            DatasetManifest(
                id=f"dataset_{name}",
                name=name,
                task="pick",
                repo_id=f"u/{name}",
                local_path=str(write_recording(tmp_path, name, fps=fps)),
                episodes=2,
                total_frames=120,
            ),
        )

    result = command(client, "compare_datasets", dataset_ids=["dataset_slow", "dataset_fast"])

    assert result["accepted"] is True
    assert result["data"]["blockers"], "a differing fps has to be named"
    assert any(item["key"] == "fps" for item in result["data"]["blockers"])


def test_the_training_advisor_can_compare_too(client, library) -> None:
    """It decides what a training run is possible on; this is that question."""
    result = command(
        client,
        "compare_datasets",
        session="agent_training_advisor",
        dataset_ids=["dataset_take_one", "dataset_take_two"],
    )

    assert result["accepted"] is True


def test_comparing_one_recording_is_refused_rather_than_answered(client, library) -> None:
    result = command(client, "compare_datasets", dataset_ids=["dataset_take_one"])

    assert result["accepted"] is False


def test_the_curator_can_ask_for_a_merge(client, library) -> None:
    """Editing was a job with a stop button and a log; the gateway could not reach it."""
    result = command(
        client,
        "prepare_dataset_transform",
        operation="merge",
        dataset_ids=["dataset_take_one", "dataset_take_two"],
        new_name="u/joined",
    )

    assert result["job"] is not None, result["message"]
    assert result["job"]["kind"] == JobKind.DATASET_TRANSFORM.value
    assert result["job"]["parameters"]["operation"] == "merge"


def test_editing_a_recording_is_not_labelled_a_simulation(client, library) -> None:
    """The default target mode was a blanket 'sim' for every job-creating action.

    Nothing about rewriting a recording is simulated, and a job in the log
    claiming a target it never had is the sort of thing nobody notices until
    they are counting simulated runs.
    """
    result = command(
        client,
        "prepare_dataset_transform",
        operation="remove_episodes",
        dataset_ids=["dataset_take_one"],
        episodes=[1],
        new_name="u/trimmed",
    )

    assert result["job"]["target_mode"] == "read_only"


def test_publishing_says_a_human_has_to_approve_it(client) -> None:
    """It moves no joint, and the preflight holds it anyway.

    needs_human_approval read only PHYSICAL_JOB_KINDS, so the catalogue promised
    an agent that publishing runs unattended. It would then wait on a job it was
    told would not stop.
    """
    payload = client.get("/api/agents/catalogue?role=dataset_curator").json()
    by_action = {item["action"]: item for item in payload["actions"]}

    assert by_action["publish_dataset"]["needs_human_approval"] is True
    assert by_action["compare_datasets"]["needs_human_approval"] is False


def test_publishing_an_unverified_recording_is_blocked_before_anything_uploads(
    client, tmp_path
) -> None:
    client.app.state.runtime.repository.upsert_entity(
        "dataset",
        DatasetManifest(
            id="dataset_broken",
            name="broken",
            task="pick",
            repo_id="u/broken",
            local_path=str(write_recording(tmp_path, "broken")),
            episodes=2,
            total_frames=120,
            integrity_status="degraded",
        ),
    )

    result = command(client, "publish_dataset", dataset_id="dataset_broken", repo_id="u/broken")

    assert result["job"]["state"] == "blocked"
    assert "hub.integrity" in json.dumps(result["job"]["result"])


def test_a_curator_still_cannot_move_the_arm(client, library) -> None:
    """Curating gained four actions and no reach onto the bench."""
    result = command(client, "request_rollout", policy_id="policy_x")

    assert result["accepted"] is False
    assert "cannot run" in result["message"]


def test_replay_is_offered_to_the_operator_and_nobody_else(client) -> None:
    """It drives recorded targets at speed with no leader in the loop."""
    curator = client.get("/api/agents/catalogue?role=dataset_curator").json()
    operator = client.get("/api/agents/catalogue?role=robot_operator").json()

    assert "prepare_replay" not in {item["action"] for item in curator["actions"]}
    replay = next(item for item in operator["actions"] if item["action"] == "prepare_replay")
    assert replay["needs_human_approval"] is True
    assert replay["target_modes"] == ["real"]
