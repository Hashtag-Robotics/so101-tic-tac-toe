#!/usr/bin/env python3
"""Natural-language entry point for the physical tic-tac-toe Strands agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_ROOT = REPO_ROOT / ".venv"
VENV_PYTHON = VENV_ROOT / "bin" / "python"


def _ensure_project_venv() -> None:
    """Re-exec with the project interpreter without requiring shell activation."""
    if Path(sys.prefix).resolve() == VENV_ROOT.resolve():
        return
    if not VENV_PYTHON.is_file():
        raise RuntimeError(f"Project virtual environment not found: {VENV_PYTHON}")
    os.execv(
        str(VENV_PYTHON),
        [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
    )


def _runner_arguments(arguments: list[str]) -> list[str]:
    if "--inspect" in arguments or "--physical" in arguments:
        return arguments
    return ["--physical", *arguments]


def main() -> int:
    _ensure_project_venv()
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from run_ttt_strands_agent import main as run_agent

    sys.argv = [sys.argv[0], *_runner_arguments(sys.argv[1:])]
    return run_agent()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Agent could not start: {error}", file=sys.stderr)
        raise SystemExit(2) from error
