from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hashtag_robotics.api import create_app
from hashtag_robotics.config import Settings

# A handful of tests drive a path that reaches LeRobot itself -- a real upload
# plan, a recording stamped the way LeRobot stamps one. Without it preflight
# blocks the job, so the test does not fail on its own subject, it fails on a
# missing install. Those tests belong to the `lerobot-contract` CI job, which
# pays for torch; the fast job skips them rather than reporting a red that says
# nothing about the change being tested.
requires_lerobot = pytest.mark.skipif(
    importlib.util.find_spec("lerobot") is None,
    reason="needs the so101 extra (LeRobot); covered by the lerobot-contract job",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # `_env_file=None` because Settings reads `.env` by default, and this bench
    # has one. The moment it gained a planning model the suite started testing
    # whatever was configured on the machine rather than what the tests set:
    # `test_strands_runtime_is_optional_and_requires_explicit_model` expects a
    # 409 for "no model" and got a 200, because the developer had one. A test
    # run that changes with an untracked file is not a test run.
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        open_browser=False,
        enable_physical=False,
        agent_model=None,
        simulation_step_seconds=0.001,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as test_client:
        test_client.headers["X-Hashtag-Token"] = test_client.app.state.runtime.session_token
        yield test_client
