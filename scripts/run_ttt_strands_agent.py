#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import termios
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hashtag_robotics_ttt.model_provider import (  # noqa: E402
    StrandsRuntimeError,
    build_model,
    split_model_spec,
)
from hashtag_robotics_ttt.settings import SettingsError, TicTacToeSettings  # noqa: E402
from hashtag_robotics_ttt.strands_agent import (  # noqa: E402
    CHECKPOINTS,
    DEFAULT_MODEL_VARIANT,
    MODEL_VARIANTS,
    TicTacToeAgentConfig,
    TicTacToeAgentError,
    TicTacToeRolloutController,
    build_tic_tac_toe_tools,
    sanitize_strands_messages,
    tic_tac_toe_system_prompt,
)


def interrupt_agent_from_terminal(_signal: int, _frame: object) -> None:
    raise KeyboardInterrupt


def enable_ctrl_d_interrupt() -> tuple[int, list[object]] | None:
    """Make Ctrl-D an asynchronous stop while preserving the terminal afterwards."""
    if not hasattr(signal, "SIGQUIT") or not sys.stdin.isatty():
        return None
    try:
        file_descriptor = sys.stdin.fileno()
        original = termios.tcgetattr(file_descriptor)
        updated = original.copy()
        updated[6] = original[6].copy()
        disabled_character = int(os.fpathconf(file_descriptor, "PC_VDISABLE"))
        updated[6][termios.VQUIT] = b"\x04"
        updated[6][termios.VEOF] = bytes([disabled_character])
        termios.tcsetattr(file_descriptor, termios.TCSANOW, updated)
    except (OSError, ValueError, termios.error):
        return None
    return file_descriptor, original


def restore_terminal(state: tuple[int, list[object]] | None) -> None:
    if state is None:
        return
    file_descriptor, original = state
    with contextlib.suppress(OSError, termios.error):
        termios.tcsetattr(file_descriptor, termios.TCSANOW, original)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a pinned local SmolVLA tic-tac-toe policy behind one narrow move tool. "
            "This command never trains a model."
        )
    )
    parser.add_argument(
        "--checkpoint",
        choices=CHECKPOINTS,
        default="120000",
        help="Pinned checkpoint step to evaluate (default: 120000).",
    )
    parser.add_argument(
        "--model-variant",
        choices=MODEL_VARIANTS,
        default=DEFAULT_MODEL_VARIANT,
        help="Pinned local policy lineage (default: games-1-15).",
    )
    parser.add_argument(
        "--physical",
        action="store_true",
        help=(
            "Opt in to physical actuation for this invocation. "
            "HASHTAG_ENABLE_PHYSICAL=true and one bounded-session approval remain required."
        ),
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print the resolved model/tool/preflight contract without cameras or robot motion.",
    )
    parser.add_argument(
        "--command",
        help=(
            "Initial human instruction. If omitted, the script waits for you to tell the agent "
            "to start the game in the terminal."
        ),
    )
    return parser.parse_args()


def persist_agent_trace(
    controller: TicTacToeRolloutController,
    agent: object,
    result: object | None,
    error: str | None,
) -> None:
    messages = getattr(agent, "messages", [])
    trace = {
        "session_id": controller.session_id,
        "checkpoint": controller.config.checkpoint,
        "model_variant": controller.config.model_variant,
        "result": str(result) if result is not None else None,
        "error": error,
        "messages": sanitize_strands_messages(messages),
        "completed_moves": controller.completed_moves,
        "game": controller.game_state(),
    }
    destination = controller.session_dir / "strands-trace.json"
    destination.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_agent(args: argparse.Namespace) -> int:
    try:
        settings = TicTacToeSettings.from_environment()
    except SettingsError as error:
        raise TicTacToeAgentError(str(error)) from error
    config = TicTacToeAgentConfig.from_environment(
        REPO_ROOT,
        args.checkpoint,
        physical_enabled=settings.enable_physical,
        explicit_physical_opt_in=args.physical,
        model_variant=args.model_variant,
    )
    controller = TicTacToeRolloutController(config)
    if args.inspect:
        payload = controller.inspect()
        payload["agent_model"] = settings.agent_model
        provider = split_model_spec(settings.agent_model)[0] if settings.agent_model else None
        payload["agent_model_provider"] = provider
        payload["agent_model_host"] = settings.agent_model_host if provider == "ollama" else None
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        controller.close()
        return 0

    if not settings.agent_model:
        controller.close()
        raise TicTacToeAgentError(
            "Set HASHTAG_AGENT_MODEL in the shell environment to a vision-capable model."
        )
    try:
        config.assert_physical_ready()
    except TicTacToeAgentError:
        controller.close()
        raise

    try:
        from strands import Agent
        from strands.tools.executors import SequentialToolExecutor
    except ImportError as error:
        controller.close()
        raise TicTacToeAgentError(
            "Strands is not installed. Install the project with the 'agents' feature pack."
        ) from error

    tools = build_tic_tac_toe_tools(controller)
    try:
        model = build_model(
            settings.agent_model,
            settings.agent_model_host,
            settings.agent_model_options,
        )
    except StrandsRuntimeError as error:
        controller.close()
        raise TicTacToeAgentError(str(error)) from error
    agent = Agent(
        model=model,
        name="hashtag_tic_tac_toe_operator",
        description=(
            "Vision-guided human opponent using one deterministic, training-backed move tool."
        ),
        system_prompt=tic_tac_toe_system_prompt(
            config.checkpoint,
            config.model_variant,
            config.forced_agent_symbol,
        ),
        tools=tools,
        tool_executor=SequentialToolExecutor(),
        trace_attributes={
            "hashtag.workflow": "tic-tac-toe-smolvla-agent",
            "hashtag.session_id": controller.session_id,
            "hashtag.checkpoint": config.checkpoint,
            "hashtag.model_variant": config.model_variant,
        },
    )
    print(f"Strands tic-tac-toe session: {controller.session_id}")
    print(f"Policy variant: {config.model_variant}")
    print(f"Checkpoint: {config.checkpoint}")
    policy_preflight = config.static_preflight()
    print(f"Local policy: {policy_preflight['model_repo_id']}@{policy_preflight['model_revision']}")
    print(f"Local policy path: {policy_preflight['checkpoint_path']}")
    print(f"Diagnostic directory: {controller.session_dir}")
    provider, _model_id = split_model_spec(settings.agent_model)
    print(f"Strands provider: {provider}")
    human_symbol = "O" if config.forced_agent_symbol == "X" else "X"
    print(
        f"The agent is {config.forced_agent_symbol}; the human is {human_symbol}. "
        "The agent moves first and symbols remain fixed for the entire game."
    )
    print("The first physical move requires one natural-language approval for this game only.")
    print("Later moves continue automatically after hands leave the workspace.")
    print("No-motion or grasp failures on an unchanged board retry at most three times.")
    print("Use the physical E-STOP if unsafe. Ctrl-C or Ctrl-D stops the agent process.")

    result: object | None = None
    agent_error: str | None = None
    try:
        command = args.command
        if command is None:
            command = input("\nTell the agent what you want it to do: ").strip()
        if not command:
            raise TicTacToeAgentError("Provide a natural-language request before starting.")
        result = agent(command, limits={"turns": config.max_agent_turns})
        print(f"\nAgent result:\n{result}")
        return 0
    except KeyboardInterrupt:
        agent_error = "Operator interrupted the Strands agent with Ctrl-C or Ctrl-D."
        stop = controller.emergency_stop(
            "Operator interrupted the Strands agent with Ctrl-C or Ctrl-D."
        )
        print(f"\nAgent interrupted: {json.dumps(stop, ensure_ascii=False)}", file=sys.stderr)
        return 130
    except Exception as error:
        agent_error = f"{type(error).__name__}: {error}"
        raise TicTacToeAgentError(f"The Strands game agent failed: {error}") from error
    finally:
        persist_agent_trace(controller, agent, result, agent_error)
        controller.close()


def main() -> int:
    args = parse_args()
    previous_sigquit: object | None = None
    if hasattr(signal, "SIGQUIT"):
        previous_sigquit = signal.signal(signal.SIGQUIT, interrupt_agent_from_terminal)
    terminal_state = enable_ctrl_d_interrupt()
    try:
        return run_agent(args)
    finally:
        restore_terminal(terminal_state)
        if hasattr(signal, "SIGQUIT") and previous_sigquit is not None:
            signal.signal(signal.SIGQUIT, previous_sigquit)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TicTacToeAgentError as error:
        print(f"Tic-tac-toe agent refused to start: {error}", file=sys.stderr)
        raise SystemExit(2) from error
