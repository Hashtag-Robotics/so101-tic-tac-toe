from __future__ import annotations

import importlib.util
import re
from typing import Any
from warnings import catch_warnings, simplefilter

from hashtag_robotics.agents import ROLE_PERMISSIONS, AgentGateway
from hashtag_robotics.config import Settings
from hashtag_robotics.models import (
    AgentCommandRequest,
    AgentPlan,
    AgentPlanRequest,
    AgentPlanResult,
    AgentPlanStep,
    AgentSession,
    AgentStepResult,
    AgentTurn,
)
from hashtag_robotics.repository import Repository


class StrandsRuntimeError(RuntimeError):
    pass


# Providers this build knows how to construct, and what the rest of the setting
# means to each. Everything after the first colon is the provider's own model id,
# so 'ollama:qwen2.5:7b' keeps the tag Ollama itself uses.
MODEL_PROVIDERS = ("ollama", "anthropic", "bedrock")


def split_model_spec(spec: str) -> tuple[str, str]:
    """'ollama:qwen2.5:7b' -> ('ollama', 'qwen2.5:7b').

    A string with no known provider prefix is a Bedrock model id, because that
    is what Strands does with a bare string: `Agent.__init__` wraps any str in
    `BedrockModel`. Naming it here rather than inheriting it silently, since on
    a machine with no AWS credentials the inherited behaviour turns 'the model I
    have running locally' into an authentication failure for a service the
    operator never mentioned.
    """
    provider, _, model_id = spec.partition(":")
    if provider in MODEL_PROVIDERS and model_id:
        return provider, model_id
    return "bedrock", spec


def build_model(spec: str, host: str, options: dict[str, Any] | None = None):
    """The Strands provider object for a configured model string.

    Imported inside the function: the providers pull in their own client
    libraries, and a control plane that only ever uses the deterministic gateway
    should not pay for an SDK it will not call.
    """
    provider, model_id = split_model_spec(spec)
    try:
        if provider == "ollama":
            from strands.models.ollama import OllamaModel

            return OllamaModel(host, model_id=model_id, options=options or None)
        if provider == "anthropic":
            from strands.models.anthropic import AnthropicModel

            return AnthropicModel(model_id=model_id)
        from strands.models.bedrock import BedrockModel

        return BedrockModel(model_id=model_id)
    except ImportError as error:
        # Strands ships every provider's adapter and none of their clients, so
        # this is the normal way a correctly-configured model fails: the import
        # raises three frames down and reaches the operator as a 500.
        raise StrandsRuntimeError(
            f"The '{provider}' provider needs a client library that is not "
            f"installed here ({error.name})."
        ) from error


# How many exchanges the model is shown. Four because the board runs a 3B model
# on CPU: every turn added is context it reads before it starts answering, and
# the questions that need more history than this are usually a new question.
CONVERSATION_DEPTH = 4

# Per-step room in the transcript. Enough for a list of recordings with their
# ids, not enough for one step to crowd out the rest of the conversation.
DIGEST_LIMIT = 700


def digest(data: dict[str, Any], limit: int = DIGEST_LIMIT) -> str:
    """A step's result, reduced to what a follow-up question needs.

    Not a truncation. Cutting `{"datasets": [{...}` at seven hundred characters
    removes precisely the ids the next turn has to name, which is the one thing
    the transcript exists to carry. So a list is rendered as the handle for each
    item -- its id, and its name if it has one -- and everything else is kept as
    it is until the budget runs out.
    """
    if not data:
        return "(no data)"
    parts: list[str] = []
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            handles = [
                str(item.get("id") or item.get("name") or item.get("index", "?"))
                + (f" ({item['name']})" if item.get("id") and item.get("name") else "")
                for item in value
            ]
            parts.append(f"{key}[{len(value)}]: {', '.join(handles)}")
            continue
        rendered = value if isinstance(value, str) else repr(value)
        parts.append(f"{key}: {rendered}")
    text = "; ".join(parts)
    return text if len(text) <= limit else f"{text[:limit]}… (truncated)"


def transcript(turns: list[AgentTurn]) -> list[dict[str, Any]]:
    """Earlier exchanges in the shape Strands wants, newest last.

    The assistant side is not the plan the model wrote -- it is what happened
    when the plan ran. A model shown only its own previous answer would plan the
    same first step again; a model shown the *result* can take the next one.
    """
    messages: list[dict[str, Any]] = []
    for turn in turns[-CONVERSATION_DEPTH:]:
        messages.append({"role": "user", "content": [{"text": turn.prompt}]})
        lines = []
        for step in turn.result.steps:
            outcome = step.command_result.data if step.command_result else None
            # Deliberately unnumbered.
            #
            # Numbering them read as an invitation: asked a follow-up after a
            # transcript beginning "0. inspect_datasets", qwen2.5:3b picked the
            # right next action and passed "$0.datasets.*.id" -- referencing
            # step zero of a plan whose only step was the one writing the
            # reference. It was imitating the transcript, reasonably. References
            # reach the current plan only, so nothing in the history should look
            # like something to reference.
            lines.append(
                f"{step.action} [{step.state}] " + (digest(outcome) if outcome else step.message)
            )
        if turn.result.stopped_because:
            lines.append(f"stopped: {turn.result.stopped_because}")
        messages.append(
            {"role": "assistant", "content": [{"text": "\n".join(lines) or "(no steps)"}]}
        )
    return messages


def _action_lines(catalogue: list[dict[str, object]]) -> list[str]:
    """One line per action, plus its parameters, for a system prompt.

    Kept terse on purpose: a local 3-to-7B model reading twenty actions in full
    prose spends its context on the catalogue instead of the request.
    """
    lines: list[str] = []
    for entry in catalogue:
        modes = entry.get("target_modes") or []
        suffix = f" [modes: {', '.join(modes)}]" if modes else ""
        approval = " [a person must approve]" if entry.get("needs_human_approval") else ""
        lines.append(f"- {entry['action']}: {entry['summary']}{suffix}{approval}")
        required = entry.get("required") or []
        optional = sorted(set(entry.get("parameters") or {}) - set(required))
        if required:
            lines.append(f"    required: {', '.join(required)}")
        if optional:
            lines.append(f"    optional: {', '.join(optional)}")
    return lines


# A parameter value of the form '$2.datasets.*.id' reads an earlier step's
# result. Deliberately small: a path of dict keys, list indices and '*' for
# 'each of these'. Anything richer is a query language, and a planner that has
# to write one will get it wrong more often than it gets an answer.
REFERENCE = re.compile(r"^\$(\d+)\.(.+)$")


def _walk(current: Any, parts: list[str], reference: str) -> Any:
    for position, part in enumerate(parts):
        if part == "*":
            if not isinstance(current, list):
                raise StrandsRuntimeError(f"'{reference}' maps over something that is not a list.")
            return [_walk(item, parts[position + 1 :], reference) for item in current]
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                raise StrandsRuntimeError(f"'{reference}' indexes past the end of a list.")
            current = current[int(part)]
            continue
        if not isinstance(current, dict) or part not in current:
            raise StrandsRuntimeError(
                f"'{reference}' names '{part}', which the result has not got."
            )
        current = current[part]
    return current


def resolve_reference(
    value: Any,
    results: list[dict[str, Any]],
    earlier: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
) -> Any:
    """A step's parameter, with any reference to an earlier result filled in.

    This is what makes a plan a plan rather than a list. The second step of
    "which of my recordings go together" has to name the recordings the first
    step found, and the model cannot know their ids when it writes the plan.

    `earlier` is the previous exchange's results, and it exists because of what
    a small model actually does. Asked a follow-up, qwen2.5:3b picked the right
    action and passed `$0.datasets.*.id` -- step zero of a plan whose only step
    was the one writing the reference. Three prompt rewrites did not shift it,
    and on reflection it was not being unreasonable: it wanted the thing that
    had just been found, and `$0` was the only way it had been shown to ask.
    So a reference that overruns this plan looks in the last one, and the step
    records that it did. Forgiving the instinct beats losing the conversation.
    """
    if isinstance(value, list):
        return [resolve_reference(item, results, earlier, notes) for item in value]
    if not isinstance(value, str):
        return value
    match = REFERENCE.match(value)
    if match is None:
        return value
    index = int(match.group(1))
    path = match.group(2).split(".")
    if index < len(results):
        return _walk(results[index], path, value)
    if earlier and index < len(earlier):
        if notes is not None:
            notes.append(
                f"'{value}' names a step this plan does not have, so it was read "
                "from the previous exchange instead."
            )
        return _walk(earlier[index], path, value)
    raise StrandsRuntimeError(
        f"'{value}' reads step {index}, which is in neither this plan nor the exchange before it."
    )


def resolve_parameters(
    parameters: dict[str, Any],
    results: list[dict[str, Any]],
    earlier: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    resolved = {
        key: resolve_reference(value, results, earlier, notes) for key, value in parameters.items()
    }
    return resolved, notes


def step_warnings(
    index: int,
    step: AgentPlanStep,
    brief: dict[str, object],
    *,
    expects_confirmation: bool,
    has_earlier: bool = False,
) -> list[str]:
    """Where a step and the server disagree about what the step will do.

    A model's `risks` list is its own account of itself, and there is nothing to
    check it against. This is the part that can be checked: the parameters the
    server actually reads, whether it will hold the job for a person, and what
    it does with everything else in the bag.

    Reported rather than refused. Submitting the plan is how an operator finds
    out what the preflight says, and a planner that silently withheld plans it
    disapproved of would be a worse instrument than one that shows its
    reservations.
    """
    warnings: list[str] = []
    parameters = step.parameters or {}

    # A reference is an answer to 'required', so a key holding one is not
    # missing -- it is filled in later, by the step it names.
    missing = [
        key
        for key in (brief.get("required") or [])
        if not str(parameters.get(key, "")).strip() and key not in parameters
    ]
    if missing:
        warnings.append(
            f"Step {index} leaves out {', '.join(missing)}, which "
            f"'{step.action}' needs. The job will block on preflight."
        )

    # Anything the server does not read is dropped without a word, which is a
    # quiet way to lose a whole recording: a plan that carefully sets `episodes`
    # on an action that never reads it looks exactly like one that worked.
    known = set(brief.get("parameters") or {}) | {"target_mode"}
    unread = sorted(set(parameters) - known)
    if unread and brief:
        warnings.append(
            f"The server ignores {', '.join(unread)} for '{step.action}'; "
            "they will be dropped without an error."
        )

    # A step that reads itself or something later never runs, and the failure
    # arrives at execution rather than here, where the plan is still readable.
    #
    # Silent when there is an earlier exchange to fall back on, because then it
    # is not a mistake: a follow-up referencing a step this plan does not have
    # resolves against the previous one, and saying otherwise would put a
    # warning on the normal shape of a conversation.
    if not has_earlier:
        for value in _reference_strings(parameters):
            match = REFERENCE.match(value)
            if match and int(match.group(1)) >= index:
                warnings.append(
                    f"Step {index} reads '{value}', which is itself or a step that runs after it."
                )

    if brief.get("needs_human_approval") and not expects_confirmation:
        warnings.append(
            f"'{step.action}' waits for a person whatever the plan says, and "
            "this plan did not expect to."
        )

    return warnings


def _reference_strings(parameters: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for value in parameters.values():
        candidates = value if isinstance(value, list) else [value]
        found.extend(item for item in candidates if isinstance(item, str) and item.startswith("$"))
    return found


def last_results(turns: list[AgentTurn]) -> list[dict[str, Any]]:
    """What the previous exchange's steps produced, in step order."""
    if not turns:
        return []
    return [
        (step.command_result.data if step.command_result else {}) or {}
        for step in turns[-1].result.steps
    ]


async def execute_plan(
    plan: AgentPlan,
    session_id: str,
    gateway: AgentGateway,
    allowed_actions: set[str],
    earlier: list[dict[str, Any]] | None = None,
) -> tuple[list[AgentStepResult], str | None]:
    """Run the steps in order, and stop at the first one that is not ours to take.

    Three things end a run, and they are not failures in the same sense:

    - a step a person has to approve. The plan is right and the run is over;
      somebody submits the rest. Nothing about it is executed here, not even to
      see what the preflight would say, because creating the job is the thing
      that needs approving.
    - a step the preflight blocked. Later steps read this one's result, so
      carrying on would run them against a result that does not exist.
    - a reference that does not resolve. Same reason.

    Whatever is left is recorded as skipped rather than dropped, so the operator
    reads the whole plan and can see where it stopped rather than inferring it
    from a short list.
    """
    results: list[AgentStepResult] = []
    data: list[dict[str, Any]] = []
    stopped: str | None = None

    for index, step in enumerate(plan.steps):
        brief = gateway.brief(step.action)
        warnings = step_warnings(
            index,
            step,
            brief,
            expects_confirmation=plan.requires_confirmation,
            has_earlier=bool(earlier),
        )

        if step.action not in allowed_actions:
            stopped = f"Step {index} plans '{step.action}', which this role cannot run."
            results.append(
                AgentStepResult(
                    index=index,
                    action=step.action,
                    state="failed",
                    message=stopped,
                    brief=brief,
                    warnings=warnings,
                )
            )
            break

        if brief.get("needs_human_approval"):
            stopped = (
                f"Step {index} ('{step.action}') needs a person to approve it, "
                "so the plan stops here and waits."
            )
            # The smallest useful form of the roadmap's sim-first gate: say that
            # the same step has a simulated shape, which runs unattended and
            # touches nothing. Not the whole idea -- there is no collision
            # analysis here and no automatic promotion to the real arm -- but it
            # is the part an operator can act on while reading the plan, and it
            # costs a sentence rather than a phase.
            if "sim" in (brief.get("target_modes") or []):
                warnings.append(
                    f"'{step.action}' also runs in simulation, where nothing "
                    "moves and nobody has to approve it. Set target_mode to "
                    "'sim' to try it there first."
                )
            results.append(
                AgentStepResult(
                    index=index,
                    action=step.action,
                    state="awaiting_human",
                    message=stopped,
                    brief=brief,
                    warnings=warnings,
                )
            )
            break

        try:
            parameters, notes = resolve_parameters(step.parameters, data, earlier)
            warnings.extend(notes)
        except StrandsRuntimeError as error:
            stopped = str(error)
            results.append(
                AgentStepResult(
                    index=index,
                    action=step.action,
                    state="failed",
                    message=stopped,
                    brief=brief,
                    warnings=warnings,
                )
            )
            break

        outcome = await gateway.execute(
            AgentCommandRequest(session_id=session_id, action=step.action, parameters=parameters)
        )
        results.append(
            AgentStepResult(
                index=index,
                action=step.action,
                state="completed" if outcome.accepted else "blocked",
                message=outcome.message,
                command_result=outcome,
                brief=brief,
                warnings=warnings,
            )
        )
        data.append(outcome.data or {})
        if not outcome.accepted:
            stopped = f"Step {index} did not go through, and the rest read its result."
            break

    for index in range(len(results), len(plan.steps)):
        results.append(
            AgentStepResult(
                index=index,
                action=plan.steps[index].action,
                state="skipped",
                message="The run stopped before this step.",
                brief=gateway.brief(plan.steps[index].action),
            )
        )
    return results, stopped


class StrandsPlanner:
    """Use Strands for structured planning; execution remains in AgentGateway."""

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        gateway: AgentGateway,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.gateway = gateway

    def status(self) -> dict[str, object]:
        installed = importlib.util.find_spec("strands") is not None
        configured = bool(self.settings.agent_model)
        # Says what is missing, not only that something is.
        #
        # The dashboard offered a 'plan with Strands' button and never asked
        # this endpoint, so on a machine with no model set the button was always
        # there and always failed. An operator cannot tell a broken planner from
        # an unconfigured one by pressing it.
        blocked_by = None
        if not installed:
            blocked_by = "The 'agents' feature pack is not installed."
        elif not configured:
            blocked_by = "No planning model is set. Set HASHTAG_AGENT_MODEL to use one."
        # Which provider the setting resolved to, spelled out. A model id with
        # no prefix quietly means Bedrock, so an operator who set the name of
        # something running on this board would otherwise learn where it was
        # being sent only from the authentication error.
        provider, model_id = (
            split_model_spec(self.settings.agent_model)
            if self.settings.agent_model
            else (None, None)
        )
        return {
            "installed": installed,
            "model_configured": configured,
            "model": self.settings.agent_model,
            "provider": provider,
            "model_id": model_id,
            "host": self.settings.agent_model_host if provider == "ollama" else None,
            "ready": installed and configured,
            "blocked_by": blocked_by,
            "execution_boundary": "deterministic-command-gateway",
            "raw_robot_tools_exposed": False,
        }

    async def plan(self, request: AgentPlanRequest) -> AgentPlanResult:
        session = self.repository.get_entity("agent_session", request.session_id, AgentSession)
        if session is None:
            raise StrandsRuntimeError("Agent session was not found.")
        if importlib.util.find_spec("strands") is None:
            raise StrandsRuntimeError("Install the 'agents' feature pack first.")
        if not self.settings.agent_model:
            raise StrandsRuntimeError(
                "Set HASHTAG_AGENT_MODEL before invoking a live Strands model."
            )

        allowed_actions = sorted(ROLE_PERMISSIONS.get(session.role, set()))
        system_prompt = "\n".join(
            [
                "You are a planning component inside Hashtag Robotics.",
                "Return one structured plan using the provided AgentPlan schema.",
                "A plan is an ordered list of steps, at most eight. Use as few as",
                "answer the request, and more than one when one does not.",
                # Measured: asked to record five demonstrations, qwen2.5:3b
                # planned prepare_recording five times rather than once with
                # episodes set. Five jobs is five sessions the operator has to
                # approve and sit through, for something one parameter says.
                "Never repeat a step to do something several times. If an action",
                "takes a count, use it: one step with episodes=5, not five steps.",
                f"Your role is {session.role}.",
                "",
                # How a step reaches the step before it.
                #
                # Without this the second step of any real question is
                # unwritable: 'which of my recordings go together' has to name
                # the recordings the first step found, and the model cannot know
                # their ids when it writes the plan.
                "A parameter may read an earlier step's result instead of a",
                "literal value, written as $<step number>.<path>. Steps are",
                "numbered from 0. Use '*' to take a field from every item of a",
                "list. For example, after a step that returns",
                '{"datasets": [{"id": "dataset_a"}, {"id": "dataset_b"}]},',
                'a later step may pass {"dataset_ids": "$0.datasets.*.id"}.',
                "A step may only read steps that come before it.",
                # The failure a conversation makes possible.
                #
                # Asked a follow-up, qwen2.5:3b picked the right action and
                # referenced $0 -- step zero of a plan whose only step was the
                # one writing the reference. It had learned the syntax from the
                # turn before and did not know it does not reach across turns.
                "A reference only reaches the plan you are writing now. Values",
                "from earlier exchanges are already spelled out in the history",
                "above; copy those literally instead of referencing them.",
                "",
                # The catalogue, not a list of names.
                #
                # The prompt used to carry the bare action names and nothing
                # else, so the model had to guess which parameters the server
                # reads -- the exact problem the catalogue was built to solve for
                # agents outside this process, reproduced for the one inside it.
                # A plan that names the right action and gets its parameters
                # wrong produces a job that blocks, which reads as the planner
                # being useless rather than uninformed.
                "These are the actions available to you, and the parameters the",
                "server actually reads. Anything else you send is discarded",
                "without an error.",
                *_action_lines(self.gateway.catalogue(session.role)),
                "",
                "Never invent raw serial, shell, Python, joint-stream or servo-loop actions.",
                "Prefer read-only inspection and simulation.",
                "Real robot actions always require deterministic preflight and human approval.",
                "Set requires_confirmation when a person should look before it runs;",
                "a plan that sets it will not be executed automatically.",
                "Do not claim that a command has executed.",
                "",
                "Earlier exchanges in this conversation are above, and the",
                "assistant side of each is what actually happened rather than",
                "what was planned. Use those results: a follow-up should take",
                "the next step, not repeat one that already ran.",
                "Every answer is a new plan for the newest question and always",
                "has at least one step. The history is what you already know,",
                "not an answer you have already given.",
            ]
        )
        history = self.turns(session.id)

        async def invoke() -> AgentPlan:
            from strands import Agent

            agent = Agent(
                model=build_model(
                    self.settings.agent_model,
                    self.settings.agent_model_host,
                    self.settings.agent_model_options,
                ),
                name=session.name,
                system_prompt=system_prompt,
                messages=transcript(history),
                tools=[],
                trace_attributes={
                    "hashtag.session_id": session.id,
                    "hashtag.role": session.role,
                },
            )
            # `structured_output_async`, not `structured_output_model` on the
            # agent, and the difference decides whether a local model can be
            # used here at all.
            #
            # Passing the model to the constructor makes the event loop invent a
            # tool and force the model to call it. Measured on this board:
            # qwen2.5:3b and llama3.2:3b both fail that, and qwen2.5:3b fails it
            # while printing the correct JSON as ordinary text -- it knew the
            # answer and could not make the tool call.
            #
            # This path asks the provider for structured output instead, which
            # for Ollama means sending the JSON schema as `format` and letting
            # decoding be constrained by it. The model does not have to be good
            # at tool calls, only at the answer. Same request, 10 s and a valid
            # two-step plan.
            #
            # Strands marks the method deprecated in favour of the constructor
            # argument. Kept anyway: the recommended path does not work with the
            # models this board can hold, and a planner nobody can run is not a
            # planner.
            with catch_warnings():
                simplefilter("ignore", DeprecationWarning)
                plan = await agent.structured_output_async(AgentPlan, request.prompt)
            if not isinstance(plan, AgentPlan):
                return AgentPlan.model_validate(plan)
            return plan

        try:
            plan = await invoke()
        except StrandsRuntimeError:
            raise
        except Exception as error:  # noqa: BLE001 - every provider raises its own
            # A model that will not answer is an ordinary condition here, not a
            # fault in this server: the board runs the planner on its own GPU
            # beside everything else, and the first real failure was Ollama
            # reporting it could not allocate. That reached the operator as an
            # unexplained 500, which says nothing about closing a browser tab.
            raise StrandsRuntimeError(f"The planning model did not answer: {error}") from error
        # Refused on the whole plan, not on the first step, because a plan whose
        # third step is outside the role is not half a good plan: running the
        # first two would spend the operator's time on a chain that cannot
        # finish, and the last step is usually the point of the request.
        outside = sorted({step.action for step in plan.steps} - set(allowed_actions))
        if outside:
            raise StrandsRuntimeError(
                f"Planned action(s) {', '.join(outside)} are outside role '{session.role}'."
            )

        result = await self._resolve(
            plan, session, request, set(allowed_actions), last_results(history)
        )
        self.remember(session.id, request.prompt, result)
        return result

    async def _resolve(
        self,
        plan: AgentPlan,
        session: AgentSession,
        request: AgentPlanRequest,
        allowed_actions: set[str],
        earlier: list[dict[str, Any]],
    ) -> AgentPlanResult:
        if not request.execute:
            # Nothing has run, so nothing can be read back; what the operator
            # gets is the plan with the server's own account of each step
            # against it.
            steps = [
                AgentStepResult(
                    index=index,
                    action=step.action,
                    state="planned",
                    message="Not run; this is the plan.",
                    brief=self.gateway.brief(step.action),
                    warnings=step_warnings(
                        index,
                        step,
                        self.gateway.brief(step.action),
                        expects_confirmation=plan.requires_confirmation,
                        has_earlier=bool(earlier),
                    ),
                )
                for index, step in enumerate(plan.steps)
            ]
            return AgentPlanResult(plan=plan, executed=False, steps=steps)

        if plan.requires_confirmation:
            # The field was declared and never read, so a model could mark its
            # own plan as needing confirmation and then have it run anyway --
            # the one piece of caution in the output was decorative. A planner
            # that says this should be confirmed does not get to skip the
            # confirming.
            return AgentPlanResult(
                plan=plan,
                executed=False,
                steps=[
                    AgentStepResult(
                        index=index,
                        action=step.action,
                        state="planned",
                        message="Not run; the plan asks for confirmation.",
                        brief=self.gateway.brief(step.action),
                    )
                    for index, step in enumerate(plan.steps)
                ],
                stopped_because=(
                    "The plan asks for confirmation, so it is left for a person to submit."
                ),
            )

        steps, stopped = await execute_plan(
            plan, session.id, self.gateway, allowed_actions, earlier
        )
        return AgentPlanResult(
            plan=plan,
            executed=any(step.state == "completed" for step in steps),
            steps=steps,
            stopped_because=stopped,
        )

    def turns(self, session_id: str) -> list[AgentTurn]:
        """This session's exchanges, oldest first."""
        return sorted(
            (
                turn
                for turn in self.repository.list_entities("agent_turn", AgentTurn)
                if turn.session_id == session_id
            ),
            key=lambda turn: turn.created_at,
        )

    def remember(self, session_id: str, prompt: str, result: AgentPlanResult) -> AgentTurn:
        turn = AgentTurn(session_id=session_id, prompt=prompt, result=result)
        self.repository.upsert_entity("agent_turn", turn)
        return turn

    def forget(self, session_id: str) -> int:
        """Start again. A conversation that has gone somewhere unhelpful is
        easier to abandon than to argue out of, and the model has no other way
        to be told that the last four exchanges no longer apply."""
        turns = self.turns(session_id)
        for turn in turns:
            self.repository.delete_entity("agent_turn", turn.id)
        return len(turns)
