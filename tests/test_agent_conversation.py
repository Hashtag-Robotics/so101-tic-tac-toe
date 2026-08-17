"""Planning was stateless, so nobody could ask a follow-up.

"Which of these can be trained together" had to name the recordings again,
because the model had never seen the answer to "what do I have" -- it produced
the step that asked, and then the process forgot both the question and the
result. Every request started from nothing, which made the page a form with one
field rather than something you could talk to.

What carries a conversation here is not the model's previous answer. It is what
happened when that answer ran: a model shown only its own last plan proposes the
same first step again.
"""

from __future__ import annotations

import importlib.machinery
import sys
import types

import pytest

from hashtag_robotics import strands_runtime
from hashtag_robotics.models import (
    AgentCommandResult,
    AgentPlan,
    AgentPlanRequest,
    AgentPlanResult,
    AgentPlanStep,
    AgentStepResult,
    AgentTurn,
    DatasetManifest,
)
from hashtag_robotics.strands_runtime import digest, transcript


@pytest.fixture
def planner(client, monkeypatch):
    """A planner whose model records the messages it was handed."""
    runtime = client.app.state.runtime
    monkeypatch.setattr(runtime.strands.settings, "agent_model", "stub-model", raising=False)
    seen: dict[str, object] = {}
    planned: dict[str, AgentPlan] = {}

    class StubAgent:
        def __init__(self, **kwargs) -> None:
            seen["messages"] = kwargs.get("messages")
            seen["system_prompt"] = kwargs.get("system_prompt")

        async def structured_output_async(self, output_model, prompt: str):
            return planned["plan"]

    stub = types.ModuleType("strands")
    stub.Agent = StubAgent
    stub.__spec__ = importlib.machinery.ModuleSpec("strands", loader=None)
    monkeypatch.setitem(sys.modules, "strands", stub)
    monkeypatch.setattr(strands_runtime, "build_model", lambda *args: "stub-model")
    return runtime.strands, planned, seen


@pytest.fixture
def recordings(client):
    for name in ("take_one", "take_two"):
        client.app.state.runtime.repository.upsert_entity(
            "dataset",
            DatasetManifest(id=f"dataset_{name}", name=name, task="pick", repo_id=f"u/{name}"),
        )


async def ask(planner, prompt: str, *steps: AgentPlanStep, session: str, execute: bool = True):
    strands, planned, _ = planner
    planned["plan"] = AgentPlan(steps=list(steps))
    return await strands.plan(AgentPlanRequest(session_id=session, prompt=prompt, execute=execute))


# --- the digest, on its own -------------------------------------------------


def test_a_list_result_keeps_the_handle_for_every_item() -> None:
    """The one thing the transcript exists to carry.

    Truncating the JSON at seven hundred characters removes precisely the ids a
    follow-up has to name.
    """
    text = digest({"datasets": [{"id": "dataset_a", "name": "cube"}, {"id": "dataset_b"}]})

    assert "dataset_a (cube)" in text
    assert "dataset_b" in text


def test_a_long_list_says_how_many_there_were(client) -> None:
    text = digest({"datasets": [{"id": f"d{index}"} for index in range(40)]})

    assert "datasets[40]" in text


def test_an_answer_that_is_not_a_list_is_kept_as_it_is() -> None:
    text = digest({"status": "incompatible", "total_episodes": 86})

    assert "status: incompatible" in text
    assert "total_episodes: 86" in text


def test_a_result_that_would_crowd_out_the_conversation_is_cut() -> None:
    text = digest({"blob": "x" * 5_000})

    assert len(text) < 800
    assert text.endswith("(truncated)")


def test_an_empty_result_says_so_rather_than_nothing() -> None:
    assert digest({}) == "(no data)"


# --- the transcript ---------------------------------------------------------


def make_turn(prompt: str, action: str, data: dict) -> AgentTurn:
    return AgentTurn(
        session_id="agent_dataset_curator",
        prompt=prompt,
        result=AgentPlanResult(
            plan=AgentPlan(steps=[AgentPlanStep(action=action)]),
            executed=True,
            steps=[
                AgentStepResult(
                    index=0,
                    action=action,
                    state="completed",
                    message="done",
                    command_result=AgentCommandResult(
                        accepted=True, action=action, message="done", data=data
                    ),
                )
            ],
        ),
    )


def test_the_assistant_side_is_what_happened_not_what_was_planned() -> None:
    """A model shown only its own previous answer plans the same step again."""
    turn = make_turn("what do I have?", "inspect_datasets", {"datasets": [{"id": "dataset_a"}]})

    messages = transcript([turn])

    assert messages[0]["role"] == "user"
    assert messages[0]["content"][0]["text"] == "what do I have?"
    assert messages[1]["role"] == "assistant"
    assert "dataset_a" in messages[1]["content"][0]["text"]


def test_only_the_last_few_exchanges_are_shown() -> None:
    """Every turn added is context a 3B model reads before it starts answering."""
    turns = [make_turn(f"question {index}", "inspect_datasets", {}) for index in range(10)]

    messages = transcript(turns)

    assert len(messages) == strands_runtime.CONVERSATION_DEPTH * 2
    assert messages[0]["content"][0]["text"] == "question 6"


# --- through the planner ----------------------------------------------------


@pytest.mark.anyio
async def test_an_exchange_is_remembered(planner, recordings) -> None:
    strands, _, _ = planner

    await ask(
        planner,
        "what do I have?",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
    )

    turns = strands.turns("agent_dataset_curator")
    assert len(turns) == 1
    assert turns[0].prompt == "what do I have?"


@pytest.mark.anyio
async def test_the_second_question_is_asked_with_the_first_one_answered(
    planner, recordings
) -> None:
    """The whole point: the model sees the ids rather than being told to guess."""
    _, _, seen = planner
    await ask(
        planner,
        "what do I have?",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
    )

    await ask(
        planner,
        "can they be trained together?",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
    )

    handed = seen["messages"]
    assert handed[0]["content"][0]["text"] == "what do I have?"
    assert "dataset_take_one" in handed[1]["content"][0]["text"]


@pytest.mark.anyio
async def test_a_plan_that_was_only_planned_is_remembered_too(planner, recordings) -> None:
    """Otherwise asking to see a plan and then asking to change it starts over."""
    strands, _, _ = planner

    await ask(
        planner,
        "what would you do?",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
        execute=False,
    )

    assert len(strands.turns("agent_dataset_curator")) == 1


@pytest.mark.anyio
async def test_conversations_do_not_leak_between_roles(planner, recordings) -> None:
    strands, _, _ = planner
    await ask(
        planner,
        "curator question",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
    )

    assert strands.turns("agent_lab_assistant") == []


@pytest.mark.anyio
async def test_a_conversation_can_be_abandoned(planner, recordings) -> None:
    """Easier than arguing a model out of somewhere unhelpful."""
    strands, _, _ = planner
    await ask(
        planner,
        "what do I have?",
        AgentPlanStep(action="inspect_datasets"),
        session="agent_dataset_curator",
    )

    cleared = strands.forget("agent_dataset_curator")

    assert cleared == 1
    assert strands.turns("agent_dataset_curator") == []


def test_the_conversation_survives_a_reload(client) -> None:
    """Kept server-side, because a browser refresh should not make the model
    forget what it found."""
    runtime = client.app.state.runtime
    runtime.strands.remember(
        "agent_dataset_curator",
        "what do I have?",
        AgentPlanResult(plan=AgentPlan(steps=[AgentPlanStep(action="inspect_datasets")])),
    )

    payload = client.get("/api/agents/sessions/agent_dataset_curator/turns").json()

    assert [turn["prompt"] for turn in payload] == ["what do I have?"]


def test_turns_for_an_unknown_session_are_a_404(client) -> None:
    assert client.get("/api/agents/sessions/nope/turns").status_code == 404


def test_clearing_says_how_much_it_removed(client) -> None:
    runtime = client.app.state.runtime
    for prompt in ("one", "two"):
        runtime.strands.remember(
            "agent_lab_assistant",
            prompt,
            AgentPlanResult(plan=AgentPlan(steps=[AgentPlanStep(action="inspect_lab")])),
        )

    response = client.delete("/api/agents/sessions/agent_lab_assistant/turns").json()

    assert response["cleared"] == 2
    assert client.get("/api/agents/sessions/agent_lab_assistant/turns").json() == []
