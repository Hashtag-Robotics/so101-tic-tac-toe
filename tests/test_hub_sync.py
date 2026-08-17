"""Publishing was a declared job kind that walked three strings and sent nothing.

It returned `{"adapter": "safe-mock"}` and finished green, which for the last
step of the pipeline means the dataset never leaves the machine that cannot
train on it. These pin the shape of a real one: a plan before an upload, and a
human between the operator and an action that cannot be taken back.
"""

from __future__ import annotations

import pytest

from hashtag_robotics import safety
from hashtag_robotics.models import DatasetManifest, JobCreateRequest, JobKind, TargetMode
from hashtag_robotics.safety import PUBLISHING_JOB_KINDS


@pytest.fixture
def a_credential(monkeypatch) -> None:
    """A Hub token, without asking the machine whether it has one.

    Publishing is gated on a real credential, so every test below used to pass
    only on a machine someone had run `hf auth login` on -- true of the bench,
    never true of a CI runner, and invisible either way because the job reports
    the ordinary `blocked` rather than an error. The gate itself is pinned by
    `test_publishing_without_a_credential_is_blocked`; these pin what happens
    after it.
    """
    monkeypatch.setattr(safety, "_hub_token", lambda: "hf_a_token_shaped_string")


def register(client, name: str, repo_id: str, *, verified: bool = True) -> str:
    import json

    runtime = client.app.state.runtime
    directory = runtime.settings.lerobot_home / repo_id
    (directory / "meta").mkdir(parents=True, exist_ok=True)
    (directory / "meta" / "info.json").write_text(json.dumps({"total_episodes": 1}))
    manifest = DatasetManifest(
        name=name,
        task="pick",
        repo_id=repo_id,
        local_path=str(directory),
        integrity_status="verified" if verified else "incomplete",
        episodes=1,
        total_frames=100,
    )
    return client.post("/api/datasets", json=manifest.model_dump(mode="json")).json()["id"]


def wait_for(client, job_id: str, timeout: float = 30.0) -> dict:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in {"completed", "failed", "aborted", "blocked", "awaiting_confirmation"}:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not settle")


def test_a_dry_run_reports_what_it_would_send_and_sends_nothing(client, a_credential) -> None:
    dataset_id = register(client, "Takes", "u/takes")

    job = client.post(
        f"/api/datasets/{dataset_id}/publish",
        json={"repo_id": "u/takes", "dry_run": True},
    ).json()
    finished = wait_for(client, job["id"])

    assert finished["state"] == "completed"
    assert finished["result"]["uploaded"] is False
    assert finished["result"]["repo_id"] == "u/takes"
    assert finished["result"]["bytes"] > 0


def test_a_dry_run_needs_nobody_to_confirm_it(client) -> None:
    """It reports and sends nothing, so it needs no more permission than reading."""
    dataset_id = register(client, "Takes", "u/takes")

    job = client.post(
        f"/api/datasets/{dataset_id}/publish",
        json={"repo_id": "u/takes", "dry_run": True},
    ).json()

    assert job["state"] != "awaiting_confirmation"


def test_an_upload_waits_for_a_human(client, a_credential) -> None:
    """An upload cannot be taken back, and a recording carries video of a room."""
    dataset_id = register(client, "Takes", "u/takes")

    job = client.post(
        f"/api/datasets/{dataset_id}/publish",
        json={"repo_id": "u/takes", "dry_run": False},
    ).json()

    assert job["state"] == "awaiting_confirmation"
    assert job["approval_id"]


def test_publishing_without_a_credential_is_blocked(client, monkeypatch) -> None:
    """The gate the other tests step over, pinned on its own.

    Nothing asserted this, so the check could have stopped working and the only
    symptom would have been uploads succeeding where they should not.
    """
    monkeypatch.setattr(safety, "_hub_token", lambda: None)
    dataset_id = register(client, "Takes", "u/takes")

    job = wait_for(
        client,
        client.post(
            f"/api/datasets/{dataset_id}/publish",
            json={"repo_id": "u/takes", "dry_run": False},
        ).json()["id"],
    )

    assert job["state"] == "blocked"
    assert "hf auth login" in str(job["result"])


def test_publishing_is_declared_as_an_outward_action() -> None:
    assert JobKind.HUB_SYNC in PUBLISHING_JOB_KINDS


def test_a_repository_without_a_namespace_is_refused(client) -> None:
    dataset_id = register(client, "Takes", "u/takes")

    job = client.post(
        "/api/jobs",
        json={
            "kind": "hub_sync",
            "target_mode": "read_only",
            "requested_by": "test",
            "parameters": {"dataset_id": dataset_id, "repo_id": "takes", "dry_run": True},
        },
    ).json()
    finished = wait_for(client, job["id"])

    assert "needs a namespace" in str(finished["result"])


def test_a_broken_recording_is_not_published(client) -> None:
    """Somewhere other people can take it is the wrong place for a broken one."""
    dataset_id = register(client, "Broken", "u/broken", verified=False)
    runtime = client.app.state.runtime

    result = runtime.safety.preflight(
        JobCreateRequest(
            kind=JobKind.HUB_SYNC,
            target_mode=TargetMode.READ_ONLY,
            requested_by="test",
            parameters={"dataset_id": dataset_id, "repo_id": "u/broken"},
        )
    )

    integrity = next(c for c in result.checks if c.code == "hub.integrity")
    assert integrity.status.value == "blocked"
    assert result.allowed is False


def test_asking_for_a_public_repository_says_so(client) -> None:
    from hashtag_robotics.models import CheckStatus

    dataset_id = register(client, "Takes", "u/takes")
    runtime = client.app.state.runtime

    result = runtime.safety.preflight(
        JobCreateRequest(
            kind=JobKind.HUB_SYNC,
            target_mode=TargetMode.READ_ONLY,
            requested_by="test",
            parameters={"dataset_id": dataset_id, "repo_id": "u/takes", "private": False},
        )
    )

    visibility = next(c for c in result.checks if c.code == "hub.visibility")
    assert visibility.status == CheckStatus.WARNING
    assert "PUBLIC" in visibility.message


def test_a_dataset_that_is_gone_never_reaches_the_upload(client) -> None:
    """Preflight refuses it, so the reason arrives before anything is attempted."""
    job = client.post(
        "/api/jobs",
        json={
            "kind": "hub_sync",
            "target_mode": "read_only",
            "requested_by": "test",
            "parameters": {"dataset_id": "gone", "repo_id": "u/x", "dry_run": True},
        },
    ).json()
    finished = wait_for(client, job["id"])

    assert finished["state"] == "blocked"
    assert "No dataset is registered" in str(finished["result"])


@pytest.mark.parametrize("private", [True, False])
def test_the_plan_carries_the_visibility_it_will_use(client, a_credential, private: bool) -> None:
    dataset_id = register(client, "Takes", "u/takes")

    job = client.post(
        f"/api/datasets/{dataset_id}/publish",
        json={"repo_id": "u/takes", "private": private, "dry_run": True},
    ).json()
    finished = wait_for(client, job["id"])

    assert finished["result"]["private"] is private
