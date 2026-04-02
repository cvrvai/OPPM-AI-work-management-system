"""
LLM provider adapters — unified interface for AI model calls.
Supports: Ollama, Kimi (Moonshot), Anthropic, OpenAI.
"""

import logging
from infrastructure.llm.base import LLMAdapter, LLMResponse, ProviderUnavailableError
from infrastructure.llm.ollama import OllamaAdapter
from infrastructure.llm.kimi import KimiAdapter
from infrastructure.llm.anthropic import AnthropicAdapter
from infrastructure.llm.openai import OpenAIAdapter

logger = logging.getLogger(__name__)

ADAPTERS: dict[str, type[LLMAdapter]] = {
    "ollama": OllamaAdapter,
    "kimi": KimiAdapter,
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
}


def get_adapter(provider: str) -> type[LLMAdapter]:
    adapter_cls = ADAPTERS.get(provider)
    if not adapter_cls:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return adapter_cls


async def call_with_fallback(
    models: list[dict],
    prompt: str,
    *,
    json_mode: bool = False,
) -> LLMResponse | dict | None:
    """Try each model in order; fall back on ProviderUnavailableError.

    Args:
        models: list of ai_models rows (must have provider, model_id, endpoint_url).
        prompt: the prompt text.
        json_mode: if True, use call_json instead of call.

    Returns:
        LLMResponse (text mode) or dict|None (json mode).

    Raises:
        ProviderUnavailableError: if ALL models fail with unavailability.
    """
    last_error: Exception | None = None
    for model in models:
        provider = model["provider"]
        adapter_cls = ADAPTERS.get(provider)
        if not adapter_cls:
            logger.warning("Skipping unknown provider: %s", provider)
            continue
        adapter = adapter_cls()
        try:
            if json_mode:
                return await adapter.call_json(
                    model["model_id"], prompt, endpoint_url=model.get("endpoint_url"),
                )
            else:
                return await adapter.call(
                    model["model_id"], prompt, endpoint_url=model.get("endpoint_url"),
                )
        except ProviderUnavailableError as e:
            logger.warning("Provider %s/%s unavailable, trying next: %s",
                           provider, model["model_id"], e.reason)
            last_error = e
            continue

    raise ProviderUnavailableError(
        "all",
        f"All {len(models)} model(s) unavailable. Last error: {last_error}",
    )


__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "ProviderUnavailableError",
    "get_adapter",
    "call_with_fallback",
    "OllamaAdapter",
    "KimiAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
]
