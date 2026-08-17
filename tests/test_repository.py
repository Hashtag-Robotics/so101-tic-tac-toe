from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from hashtag_robotics.models import ResourceRequest, utc_now
from hashtag_robotics.repository import Repository, ResourceBusyError


def test_exclusive_resource_lease_blocks_second_job(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.db")
    resource = ResourceRequest(
        resource_id="serial-follower",
        resource_type="robot",
        mode="exclusive",
    )
    repository.acquire_leases("job-one", [resource])
    with pytest.raises(ResourceBusyError):
        repository.acquire_leases("job-two", [resource])

    repository.release_leases("job-one")
    acquired = repository.acquire_leases("job-two", [resource])
    assert acquired[0].owner_job_id == "job-two"


def test_shared_read_leases_are_compatible(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.db")
    resource = ResourceRequest(
        resource_id="camera-front",
        resource_type="camera",
        mode="shared_read",
    )
    repository.acquire_leases("job-one", [resource])
    repository.acquire_leases("job-two", [resource])
    assert {lease.owner_job_id for lease in repository.list_leases()} == {
        "job-one",
        "job-two",
    }


def test_expired_lease_is_removed(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "state.db")
    resource = ResourceRequest(
        resource_id="robot",
        resource_type="robot",
        mode="exclusive",
    )
    leases = repository.acquire_leases("job-one", [resource], ttl_seconds=-1)
    assert leases[0].expires_at < utc_now() + timedelta(seconds=1)
    assert repository.list_leases() == []
