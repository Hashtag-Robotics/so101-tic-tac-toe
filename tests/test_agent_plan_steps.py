"""One action was never the whole answer.

Asked "can I train on what I recorded yesterday", the planner could list the
recordings and stop -- because a plan was a single action. Finding out whether
they went together was a second question the operator had to ask by hand,
carrying the ids across themselves. That is the work they wanted the planner to
do.

So a plan is an ordered list now, a step can read what an earlier step found,
and the run stops at the first step somebody has to approve rather than
pretending it may take it.
"""

from __future__ import annotations

import importlib.machinery
import sys
import types

import pytest

from hashtag_robotics import strands_runtime
from hashtag_robotics.models import (
    AgentPlan,
    AgentPlanRequest,
    AgentPlanStep,
    DatasetManifest,
)
from hashtag_robotics.strands_runtime import (
    StrandsRuntimeError,
    resolve_parameters,
    resolve_reference,
    step_warnings,
)


@pytest.fixture
def planner(client, monkeypatch):
    runtime = client.app.state.runtime
    monkeypatch.setattr(runtime.strands.settings, "agent_model", "stub-model", raising=False)
    planned: dict[str, AgentPlan] = {}

    class StubAgent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def structured_output_async(self, output_model, prompt: str):
            return planned["plan"]

    stub = types.ModuleType("strands")
    stub.Agent = StubAgent
    stub.__spec__ = importlib.machinery.ModuleSpec("strands", loader=None)
    monkeypatch.setitem(sys.modules, "strands", stub)
    monkeypatch.setattr(strands_runtime, "build_model", lambda *args: "stub-model")
    return runtime.strands, planned


@pytest.fixture
def recordings(client):
    for name in ("take_one", "take_two"):
        client.app.state.runtime.repository.upsert_entity(
            "dataset",
            DatasetManifest(id=f"dataset_{name}", name=name, task="pick", repo_id=f"u/{name}"),
        )


async def run(planner, *steps: AgentPlanStep, session: str, execute: bool = True, **plan_kwargs):
    strands, planned = planner
    planned["plan"] = AgentPlan(steps=list(steps), **plan_kwargs)
    return await strands.plan(
        AgentPlanRequest(session_id=session, prompt="Do the thing.", execute=execute)
    )


# --- the reference syntax, on its own ---------------------------------------


def test_a_reference_reads_a_field_out_of_an_earlier_result() -> None:
    results = [{"status": "warnings", "total_episodes": 86}]

    assert resolve_reference("$0.status", results) == "warnings"


def test_a_star_takes_the_field_from_every_item() -> None:
    """The shape a list endpoint actually returns."""
    results = [{"datasets": [{"id": "dataset_a"}, {"id": "dataset_b"}]}]

    assert resolve_reference("$0.datasets.*.id", results) == ["dataset_a", "dataset_b"]


def test_a_plain_value_is_left_alone() -> None:
    resolved, notes = resolve_parameters({"task": "pick up the cube"}, [])

    assert resolved == {"task": "pick up the cube"}
    assert notes == []


def test_a_reference_to_a_step_that_exists_nowhere_is_named() -> None:
    with pytest.raises(StrandsRuntimeError, match="neither this plan"):
        resolve_reference("$3.datasets", [{"datasets": []}])


def test_a_reference_past_this_plan_falls_back_to_the_previous_exchange() -> None:
    """Forgiving the instinct beats losing the conversation.

    Asked a follow-up, qwen2.5:3b passed `$0.datasets.*.id` on a one-step plan:
    step zero of the plan writing the reference. Three prompt rewrites did not
    shift it, and it was not being unreasonable -- it wanted what had just been
    found, and `$0` was the only way it had been shown to ask.
    """
    earlier = [{"datasets": [{"id": "dataset_a"}, {"id": "dataset_b"}]}]

    resolved, notes = resolve_parameters({"dataset_ids": "$0.datasets.*.id"}, [], earlier)

    assert resolved["dataset_ids"] == ["dataset_a", "dataset_b"]
    assert any("previous exchange" in note for note in notes)


def test_the_current_plan_wins_over_the_previous_exchange() -> None:
    """A reference that resolves here means here; the fallback is a fallback."""
    resolved, notes = resolve_parameters(
        {"dataset_ids": "$0.datasets.*.id"},
        [{"datasets": [{"id": "now"}]}],
        [{"datasets": [{"id": "before"}]}],
    )

    assert resolved["dataset_ids"] == ["now"]
    assert notes == []


def test_a_reference_to_a_field_that_is_not_there_is_named() -> None:
    """Which field, not 'lookup failed'."""
    with pytest.raises(StrandsRuntimeError, match="policies"):
        resolve_reference("$0.policies.*.id", [{"datasets": []}])


def test_a_reference_can_be_one_item_of_a_list_parameter() -> None:
    results = [{"datasets": [{"id": "dataset_a"}]}]

    resolved, _ = resolve_parameters(
        {"dataset_ids": ["$0.datasets.0.id", "dataset_fixed"]}, results
    )

    assert resolved["dataset_ids"] == ["dataset_a", "dataset_fixed"]


def test_a_step_that_reads_itself_is_flagged_while_the_plan_is_still_readable() -> None:
    """It never runs, and the failure would otherwise arrive at execution."""
    step = AgentPlanStep(action="compare_datasets", parameters={"dataset_ids": "$1.datasets.*.id"})

    brief = {"parameters": {"dataset_ids": ""}}

    warnings = step_warnings(1, step, brief, expects_confirmation=False)

    assert any("runs after it" in warning for warning in warnings)


def test_a_key_holding_a_reference_is_not_reported_as_missing() -> None:
    """It is filled in later, by the step it names."""
    step = AgentPlanStep(action="compare_datasets", parameters={"dataset_ids": "$0.datasets.*.id"})
    brief = {"required": ["dataset_ids"], "parameters": {"dataset_ids": "required — two or more"}}

    assert step_warnings(1, step, brief, expects_confirmation=False) == []


# --- running a chain --------------------------------------------------------


@pytest.mark.anyio
async def test_a_second_step_uses_what_the_first_one_found(planner, recordings) -> None:
    """The whole point. The model cannot know the ids when it writes the plan."""
    result = await run(
        planner,
        AgentPlanStep(action="inspect_datasets", rationale="See what is here."),
        AgentPlanStep(
            action="compare_datasets",
            rationale="Can they be trained together?",
            parameters={"dataset_ids": "$0.datasets.*.id"},
        ),
        session="agent_dataset_curator",
    )

    assert [step.state for step in result.steps] == ["completed", "completed"]
    assert result.steps[1].command_result.data["total_episodes"] is not None


@pytest.mark.anyio
async def test_the_run_stops_at_the_step_a_person_has_to_approve(planner, recordings) -> None:
    """Not executed at all, not even to see what the preflight would say.

    Creating the job is the thing that needs approving.
    """
    result = await run(
        planner,
        AgentPlanStep(action="inspect_datasets"),
        AgentPlanStep(action="publish_dataset", parameters={"dataset_id": "dataset_take_one"}),
        session="agent_dataset_curator",
    )

    assert result.steps[0].state == "completed"
    assert result.steps[1].state == "awaiting_human"
    assert result.steps[1].command_result is None
    assert "needs a person" in result.stopped_because


@pytest.mark.anyio
async def test_a_step_held_for_approval_says_it_has_a_simulated_shape(planner) -> None:
    """The smallest useful form of the roadmap's sim-first gate.

    Not the whole idea -- no collision analysis, no automatic promotion -- but
    the part an operator can act on while reading the plan.
    """
    result = await run(
        planner,
        AgentPlanStep(action="prepare_recording", parameters={"target_mode": "real"}),
        session="agent_robot_operator",
    )

    assert result.steps[0].state == "awaiting_human"
    assert any("also runs in simulation" in warning for warning in result.steps[0].warnings)


@pytest.mark.anyio
async def test_a_step_with_no_simulated_shape_does_not_claim_one(planner) -> None:
    """Replay drives recorded targets onto the arm; there is no sim form of it."""
    result = await run(
        planner,
        AgentPlanStep(action="prepare_replay", parameters={"repo_id": "u/take"}),
        session="agent_robot_operator",
    )

    assert result.steps[0].state == "awaiting_human"
    assert not any("also runs in simulation" in warning for warning in result.steps[0].warnings)


@pytest.mark.anyio
async def test_what_is_left_after_a_stop_is_recorded_rather_than_dropped(
    planner, recordings
) -> None:
    """A short list reads as a short plan; the operator should see where it stopped."""
    result = await run(
        planner,
        AgentPlanStep(action="inspect_datasets"),
        AgentPlanStep(action="publish_dataset", parameters={"dataset_id": "dataset_take_one"}),
        AgentPlanStep(action="inspect_safety"),
        session="agent_dataset_curator",
    )

    assert len(result.steps) == 3
    assert result.steps[2].state == "skipped"


@pytest.mark.anyio
async def test_a_plan_whose_later_step_is_outside_the_role_runs_none_of_it(planner) -> None:
    """Running the first two would spend the operator's time on a chain that cannot finish.

    The refused step is usually the point of the request, not an afterthought.
    """
    with pytest.raises(StrandsRuntimeError, match="request_rollout"):
        await run(
            planner,
            AgentPlanStep(action="inspect_datasets"),
            AgentPlanStep(action="request_rollout"),
            session="agent_dataset_curator",
        )


@pytest.mark.anyio
async def test_a_reference_that_does_not_resolve_stops_the_run(planner, recordings) -> None:
    """Later steps read this one, so carrying on runs them against nothing."""
    result = await run(
        planner,
        AgentPlanStep(action="inspect_datasets"),
        AgentPlanStep(action="compare_datasets", parameters={"dataset_ids": "$0.policies.*.id"}),
        session="agent_dataset_curator",
    )

    assert result.steps[1].state == "failed"
    assert "policies" in result.stopped_because


@pytest.mark.anyio
async def test_planning_without_executing_still_says_what_each_step_would_do(
    planner, recordings
) -> None:
    """Nothing has run, so nothing can be read back -- but the briefs are free."""
    result = await run(
        planner,
        AgentPlanStep(action="inspect_datasets"),
        AgentPlanStep(action="publish_dataset", parameters={"dataset_id": "dataset_take_one"}),
        session="agent_dataset_curator",
        execute=False,
    )

    assert result.executed is False
    assert [step.state for step in result.steps] == ["planned", "planned"]
    assert result.steps[1].brief["needs_human_approval"] is True


def test_a_plan_needs_at_least_one_step() -> None:
    """The bound lives on the field so it reaches the model's schema.

    Ollama constrains decoding to the JSON schema, so `minItems: 1` is
    something the model cannot violate. A validator would run afterwards and
    only turn an empty plan into an error -- which is what happened: the second
    turn of a conversation came back with no steps at all.
    """
    assert AgentPlan.model_json_schema()["properties"]["steps"]["minItems"] == 1
    with pytest.raises(ValueError, match="at least 1 item"):
        AgentPlan(steps=[])


@pytest.mark.anyio
async def test_a_plan_longer_than_eight_steps_is_refused(planner) -> None:
    """A model that wants more has misunderstood the request; an unbounded list is a loop."""
    with pytest.raises(ValueError):
        AgentPlan(steps=[AgentPlanStep(action="inspect_lab") for _ in range(9)])
