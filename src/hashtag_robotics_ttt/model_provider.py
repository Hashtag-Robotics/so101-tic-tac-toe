"""Standard Strands model-provider selection for the game agent."""

from __future__ import annotations

from typing import Any


class StrandsRuntimeError(RuntimeError):
    pass


MODEL_PROVIDERS = ("ollama", "anthropic", "bedrock")


def split_model_spec(spec: str) -> tuple[str, str]:
    """Resolve a provider-prefixed model specification.

    A bare model id retains the standard Strands meaning and resolves to
    Amazon Bedrock. Everything after the first recognized prefix belongs to
    that provider, so an Ollama tag such as ``qwen2.5:7b`` remains intact.
    """

    provider, _, model_id = spec.partition(":")
    if provider in MODEL_PROVIDERS and model_id:
        return provider, model_id
    return "bedrock", spec


def build_model(spec: str, host: str, options: dict[str, Any] | None = None):
    """Construct a model through a standard Strands provider adapter."""

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
        raise StrandsRuntimeError(
            f"The '{provider}' provider needs a client library that is not installed "
            f"({error.name})."
        ) from error
