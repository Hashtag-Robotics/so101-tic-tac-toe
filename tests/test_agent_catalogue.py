"""An agent that has to read the source to drive this is not being offered an interface.

Until the catalogue existed the only machine-readable thing was
`AgentSession.permissions`: a list of bare action names. An agent could learn
that it may `prepare_recording` and nothing more -- not that the server reads
`repo_id`, `task` and `episodes` out of an untyped parameter bag and silently
ignores everything else, not that a real recording waits for a human, not that
asking in sim mode gets a different recorder entirely.
"""

from __future__ import annotations

from hashtag_robotics.agents import (
    ACTION_CATALOGUE,
    ROLE_PERMISSIONS,
    UNEXPOSED_JOB_KINDS,
    reachable_job_kinds,
)
from hashtag_robotics.models import JobKind


def test_every_permission_a_role_has_is_described(client) -> None:
    """A permission with no entry is an action an agent can call and cannot understand."""
    granted = {action for actions in ROLE_PERMISSIONS.values() for action in actions}

    assert granted <= set(ACTION_CATALOGUE), (
        f"undocumented actions: {sorted(granted - set(ACTION_CATALOGUE))}"
    )


def test_every_job_kind_is_either_offered_or_explicitly_withheld() -> None:
    """The guard the catalogue never had, and the reason it went stale.

    The check above only runs one way: it proves granted permissions are
    documented. Nothing ran the other way, so nine capabilities -- publishing to
    the Hub, merging recordings, calibration -- accumulated on the far side of a
    hand-written dict while every test stayed green. Adding a job kind was free;
    deciding whether an agent may reach it was optional.

    It is not optional now. A new kind has to be offered through the catalogue
    or written into UNEXPOSED_JOB_KINDS with a reason. "Not offered yet" is a
    perfectly good answer. Silence is what this test exists to reject.
    """
    unaccounted = set(JobKind) - reachable_job_kinds() - set(UNEXPOSED_JOB_KINDS)

    assert not unaccounted, (
        "job kinds no agent can reach and nobody decided to withhold: "
        f"{sorted(kind.value for kind in unaccounted)}. Add an ACTION_CATALOGUE "
        "entry, or say why not in UNEXPOSED_JOB_KINDS."
    )


def test_nothing_is_both_offered_and_withheld() -> None:
    """A kind on both lists means the written reason is describing something untrue."""
    both = reachable_job_kinds() & set(UNEXPOSED_JOB_KINDS)

    assert not both, sorted(kind.value for kind in both)


def test_a_withheld_kind_carries_a_reason_somebody_wrote() -> None:
    for kind, reason in UNEXPOSED_JOB_KINDS.items():
        assert len(reason.split()) >= 8, f"{kind.value} is withheld without an explanation"


def test_recording_in_simulation_counts_as_reach(client) -> None:
    """The kind an agent names is not always the kind that runs.

    `prepare_recording` with target_mode 'sim' is rewritten to a sim_recording
    inside JobCreateRequest, so counting only the names in the catalogue would
    report the sim kinds as unreachable and invite somebody to withhold them.
    """
    reachable = reachable_job_kinds()

    assert JobKind.SIM_RECORDING in reachable
    assert JobKind.SIM_TELEOPERATION in reachable


def test_the_published_permissions_match_the_role(client) -> None:
    """The stored list was a snapshot, and it drifted two permissions behind.

    Sessions were seeded once, when the table was empty. `inspect_safety` and
    `emergency_stop` were added afterwards and no existing installation ever
    saw them: execution allowed both, the published list denied both, and the
    dashboard believes the published list.
    """
    for session in client.get("/api/agents/sessions").json():
        assert session["permissions"] == sorted(ROLE_PERMISSIONS[session["role"]]), (
            f"{session['role']} publishes a stale permission list"
        )


def test_an_installation_that_predates_a_permission_picks_it_up(client) -> None:
    """The case above cannot fail on a fresh install; this is the one that broke.

    A bench that has been running since before a permission existed keeps
    serving the list it was seeded with, because seeding only ran on an empty
    table. Restarting has to be enough to correct it -- there is no other repair
    path, and nobody would know to look.
    """
    from hashtag_robotics.models import AgentSession
    from hashtag_robotics.seeding import seed_repository

    repository = client.app.state.runtime.repository
    before = repository.get_entity("agent_session", "agent_robot_operator", AgentSession)
    repository.upsert_entity(
        "agent_session",
        before.model_copy(update={"permissions": ["inspect_lab"]}),
    )

    seed_repository(repository)

    after = repository.get_entity("agent_session", "agent_robot_operator", AgentSession)
    assert after.permissions == sorted(ROLE_PERMISSIONS["robot_operator"])
    # Corrected, not replaced: an agent's age is the one thing a reboot cannot restate.
    assert after.created_at == before.created_at


def test_the_catalogue_narrows_to_the_role_that_asks(client) -> None:
    """Reading the whole surface and then being refused half of it is worse than useless."""
    payload = client.get("/api/agents/catalogue?role=dataset_curator").json()
    actions = {item["action"] for item in payload["actions"]}

    assert actions == ROLE_PERMISSIONS["dataset_curator"]
    assert "request_rollout" not in actions


def test_an_action_says_which_parameters_the_server_actually_reads(client) -> None:
    payload = client.get("/api/agents/catalogue?role=robot_operator").json()
    recording = next(item for item in payload["actions"] if item["action"] == "prepare_recording")

    assert "repo_id" in recording["parameters"]
    assert "task" in recording["parameters"]
    assert recording["creates_job"] is True
    assert set(recording["target_modes"]) == {"sim", "real"}


def test_an_action_says_whether_a_human_has_to_approve_it(client) -> None:
    """The two things an agent most needs to predict before it commits."""
    payload = client.get("/api/agents/catalogue?role=robot_operator").json()
    by_action = {item["action"]: item for item in payload["actions"]}

    assert by_action["prepare_recording"]["needs_human_approval"] is True
    assert by_action["inspect_lab"]["needs_human_approval"] is False


def test_workspace_confirmed_is_described_as_a_human_judgement(client) -> None:
    """It is a claim about a room, and an agent cannot see the room."""
    payload = client.get("/api/agents/catalogue?role=robot_operator").json()
    recording = next(item for item in payload["actions"] if item["action"] == "prepare_recording")

    assert "cannot see" in recording["parameters"]["workspace_confirmed"]


def test_an_agent_can_read_the_safety_state_it_is_gated_on(client) -> None:
    """Refusing to say whether the stop is latched only makes it guess."""
    runtime = client.app.state.runtime
    session = client.get("/api/agents/sessions").json()
    operator = next(item for item in session if item["role"] == "robot_operator")
    runtime.safety.engage_estop("test")

    result = client.post(
        "/api/agents/commands",
        json={"session_id": operator["id"], "action": "inspect_safety", "parameters": {}},
    ).json()

    assert result["accepted"] is True
    assert result["data"]["emergency_stop_engaged"] is True


def test_an_agent_that_can_start_the_arm_can_stop_it(client) -> None:
    session = client.get("/api/agents/sessions").json()
    operator = next(item for item in session if item["role"] == "robot_operator")

    result = client.post(
        "/api/agents/commands",
        json={"session_id": operator["id"], "action": "emergency_stop", "parameters": {}},
    ).json()

    assert result["accepted"] is True
    assert client.get("/api/safety/status").json()["emergency_stop_engaged"] is True


def test_no_role_can_clear_the_emergency_stop(client) -> None:
    """Stopping is a judgement a model can make; deciding it is over is not.

    Somebody has to look at the bench.
    """
    granted = {action for actions in ROLE_PERMISSIONS.values() for action in actions}

    assert "clear_estop" not in granted
    assert "clear_emergency_stop" not in granted
    assert "emergency_stop" in ACTION_CATALOGUE
    assert "no matching action to clear it" in ACTION_CATALOGUE["emergency_stop"]["note"]


def test_a_session_id_resolves_its_own_reach(client) -> None:
    session = client.get("/api/agents/sessions").json()[0]

    payload = client.get(f"/api/agents/catalogue?session_id={session['id']}").json()

    assert payload["role"] == session["role"]
    assert {item["action"] for item in payload["actions"]} == ROLE_PERMISSIONS[session["role"]]


def test_an_unknown_session_is_a_404(client) -> None:
    assert client.get("/api/agents/catalogue?session_id=nope").status_code == 404
