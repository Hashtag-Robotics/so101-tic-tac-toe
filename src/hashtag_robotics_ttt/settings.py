"""Environment settings used by the standalone tic-tac-toe runtime."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


class SettingsError(ValueError):
    pass


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class TicTacToeSettings:
    enable_physical: bool = False
    agent_model: str | None = None
    agent_model_host: str = "http://localhost:11434"
    agent_model_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> TicTacToeSettings:
        raw_options = os.environ.get("HASHTAG_AGENT_MODEL_OPTIONS", "").strip()
        options: dict[str, Any] = {}
        if raw_options:
            try:
                decoded = json.loads(raw_options)
            except json.JSONDecodeError as error:
                raise SettingsError("HASHTAG_AGENT_MODEL_OPTIONS must be valid JSON.") from error
            if not isinstance(decoded, dict):
                raise SettingsError("HASHTAG_AGENT_MODEL_OPTIONS must be a JSON object.")
            options = decoded

        model = os.environ.get("HASHTAG_AGENT_MODEL", "").strip() or None
        host = os.environ.get("HASHTAG_AGENT_MODEL_HOST", "http://localhost:11434").strip()
        if not host:
            raise SettingsError("HASHTAG_AGENT_MODEL_HOST cannot be empty.")
        return cls(
            enable_physical=_enabled("HASHTAG_ENABLE_PHYSICAL"),
            agent_model=model,
            agent_model_host=host,
            agent_model_options=options,
        )
