"""The planning path had one test, and it was the one where planning never runs.

`test_strands_runtime_is_optional_and_requires_explicit_model` asserts that a
machine with no model answers 409. That is the whole of what was covered: every
line after the model check -- validating the plan against the role, deciding
whether to execute it, reading the fields the plan carries -- had never run.

Two of those fields had never been read by anything. `AgentPlan.risks` and
`requires_confirmation` were declared, filled in by the model and ignored, so a
planner could mark its own plan as needing confirmation and have it execute
anyway. The one piece of caution in the output was decorative.

The model is stubbed here. What is being tested is the harness around it, which
is the part that decides what a model's output is permitted to do.
"""

from __future__ import annotations

import importlib.machinery
import sys
import types

import pytest

from hashtag_robotics import strands_runtime
from hashtag_robotics.agents import required_parameters
from hashtag_robotics.models import AgentPlan, AgentPlanRequest, AgentPlanStep
from hashtag_robotics.strands_runtime import (
    StrandsRuntimeError,
    build_model,
    split_model_spec,
    step_warnings,
)


def one_step(action: str, **parameters) -> AgentPlan:
    return AgentPlan(steps=[AgentPlanStep(action=action, parameters=parameters)])


@pytest.fixture
def planner(client, monkeypatch):
    """A configured planner whose model returns whatever the test hands it."""
    runtime = client.app.state.runtime
    monkeypatch.setattr(runtime.settings, "agent_model", "stub-model", raising=False)
    monkeypatch.setattr(runtime.strands.settings, "agent_model", "stub-model", raising=False)

    planned: dict[str, AgentPlan] = {}

    class StubAgent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def structured_output_async(self, output_model, prompt: str):
            return planned["plan"]

    # A real module object with a spec: the runtime asks `find_spec` whether the
    # feature pack is installed, and that reads `__spec__` off sys.modules.
    stub = types.ModuleType("strands")
    stub.Agent = StubAgent
    stub.__spec__ = importlib.machinery.ModuleSpec("strands", loader=None)
    monkeypatch.setitem(sys.modules, "strands", stub)
    # Which provider a model string resolves to is tested on its own; here it
    # would only mean reaching for a client library that is not the subject.
    monkeypatch.setattr(strands_runtime, "build_model", lambda *args: "stub-model")
    return runtime.strands, planned


async def plan_for(planner, plan: AgentPlan, *, execute: bool = False, session: str):
    strands, planned = planner
    planned["plan"] = plan
    return await strands.plan(
        AgentPlanRequest(session_id=session, prompt="Do the thing.", execute=execute)
    )


@pytest.mark.anyio
async def test_a_plan_outside_the_role_is_refused(planner) -> None:
    """The gateway would refuse it too; refusing here says which boundary it hit."""
    with pytest.raises(StrandsRuntimeError, match="outside role"):
        await plan_for(
            planner,
            one_step("request_rollout"),
            session="agent_lab_assistant",
        )


@pytest.mark.anyio
async def test_a_plan_that_asks_for_confirmation_is_not_executed(planner) -> None:
    """The field was declared and never read.

    A model could mark its own plan as needing confirmation and have it run
    regardless, which made the field worse than absent: it read as a safeguard.
    """
    result = await plan_for(
        planner,
        AgentPlan(
            steps=[AgentPlanStep(action="inspect_lab", rationale="Check the bench first.")],
            requires_confirmation=True,
        ),
        execute=True,
        session="agent_lab_assistant",
    )

    assert result.executed is False
    assert all(step.command_result is None for step in result.steps)
    assert "left for a person" in (result.stopped_because or "")


@pytest.mark.anyio
async def test_a_plan_that_does_not_ask_for_confirmation_runs(planner) -> None:
    result = await plan_for(
        planner,
        one_step("inspect_lab"),
        execute=True,
        session="agent_lab_assistant",
    )

    assert result.executed is True
    assert result.steps[0].state == "completed"
    assert result.steps[0].command_result.accepted is True


@pytest.mark.anyio
async def test_the_plan_comes_back_beside_what_the_server_says(planner) -> None:
    """`risks` is the model's account of itself and cannot be checked.

    This is the part that can: the same entry the catalogue serves, so the two
    can be read together rather than the model's word being the only word.
    """
    result = await plan_for(
        planner,
        one_step("prepare_recording"),
        session="agent_robot_operator",
    )

    assert result.steps[0].brief["action"] == "prepare_recording"
    assert result.steps[0].brief["needs_human_approval"] is True


def test_a_plan_missing_a_required_parameter_is_flagged() -> None:
    """It would block on preflight; saying so now costs nothing."""
    brief = {"required": ["repo_id", "task"], "parameters": {"repo_id": "", "task": ""}}

    warnings = step_warnings(
        0,
        AgentPlanStep(action="prepare_recording", parameters={"repo_id": "u/take"}),
        brief,
        expects_confirmation=False,
    )

    assert any("task" in warning for warning in warnings)
    assert not any("repo_id," in warning for warning in warnings)


def test_a_parameter_the_server_never_reads_is_flagged() -> None:
    """Dropped without a word, which is a quiet way to lose a whole recording.

    A plan that carefully sets a key nothing reads looks exactly like one that
    worked, right up until the result is missing.
    """
    brief = {"required": [], "parameters": {"dataset_id": "required — the recording"}}

    warnings = step_warnings(
        0,
        AgentPlanStep(
            action="prepare_dataset_validation",
            parameters={"dataset_id": "d1", "episodes": 5},
        ),
        brief,
        expects_confirmation=False,
    )

    assert any("episodes" in warning for warning in warnings)


def test_an_empty_brief_does_not_invent_warnings() -> None:
    """An unknown action is the gateway's refusal to make, not a parameter complaint."""
    step = AgentPlanStep(action="nope", parameters={"a": 1})

    assert step_warnings(0, step, {}, expects_confirmation=False) == []


def test_a_plan_that_expects_no_approval_for_a_real_action_is_corrected() -> None:
    brief = {"required": [], "parameters": {}, "needs_human_approval": True}

    warnings = step_warnings(
        0,
        AgentPlanStep(action="prepare_recording"),
        brief,
        expects_confirmation=False,
    )

    assert any("waits for a person" in warning for warning in warnings)


def test_the_runtime_says_what_is_missing_rather_than_only_that_something_is(
    client,
) -> None:
    """The dashboard offered a plan button and never asked this endpoint.

    On a machine with no model set the button was always there and always
    failed, and an operator cannot tell a broken planner from an unconfigured
    one by pressing it.
    """
    status = client.get("/api/agents/runtime").json()

    assert status["ready"] is False
    assert "HASHTAG_AGENT_MODEL" in status["blocked_by"]


def test_required_parameters_are_read_off_the_hints_that_describe_them(client) -> None:
    """One source, so the machine-readable list cannot drift from the prose."""
    payload = client.get("/api/agents/catalogue?role=robot_operator").json()
    recording = next(item for item in payload["actions"] if item["action"] == "prepare_recording")

    assert "repo_id" in recording["required"]
    assert "task" in recording["required"]
    # Real mode only, so it cannot be checked without knowing the mode. Calling
    # it missing would teach an agent to ignore the warning.
    assert "robot_profile_id" not in recording["required"]


def test_a_model_string_says_where_it_will_be_sent() -> None:
    """A bare id quietly means Bedrock, which is a trap on a board with no AWS.

    Strands wraps any plain string in `BedrockModel` (agent.py:294), so naming a
    model that is running on this machine failed with an authentication error
    for a service the operator never mentioned. Measured here rather than
    inherited silently.
    """
    assert split_model_spec("ollama:qwen2.5:7b") == ("ollama", "qwen2.5:7b")
    assert split_model_spec("anthropic:claude-sonnet-5") == ("anthropic", "claude-sonnet-5")
    assert split_model_spec("qwen2.5:7b") == ("bedrock", "qwen2.5:7b")


def test_a_missing_client_library_is_explained_rather_than_raised(monkeypatch) -> None:
    """strands ships every provider's adapter and none of their clients.

    The import raises three frames down, so a correctly-configured model reached
    the operator as a 500 with a traceback about a module they never named.
    """
    monkeypatch.setitem(sys.modules, "strands.models.ollama", None)

    with pytest.raises(StrandsRuntimeError, match="not"):
        build_model("ollama:qwen2.5:7b", "http://localhost:11434")


@pytest.mark.anyio
async def test_a_model_that_will_not_answer_is_an_ordinary_condition(planner) -> None:
    """The board runs the planner beside a browser and an editor.

    The first real failure here was Ollama reporting it could not allocate a
    CUDA buffer, which arrived as an unexplained 500. Nothing in that tells an
    operator to close a tab.
    """
    strands, planned = planner

    class Failing:
        def __init__(self, **kwargs) -> None:
            pass

        async def structured_output_async(self, output_model, prompt: str):
            raise RuntimeError("cudaMalloc failed: out of memory")

    sys.modules["strands"].Agent = Failing

    with pytest.raises(StrandsRuntimeError, match="out of memory"):
        await strands.plan(
            AgentPlanRequest(session_id="agent_lab_assistant", prompt="Read the bench.")
        )


def test_a_conditional_requirement_is_never_reported_as_unconditional() -> None:
    entry = {
        "parameters": {
            "operation": "required — 'merge' or 'remove_episodes'",
            "new_name": "required for a merge — what to call the result",
            "robot_profile_id": "required in real mode",
            "fps": "playback rate (default 30)",
        }
    }

    assert required_parameters(entry) == ["operation"]
