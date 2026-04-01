"""
LLM provider adapters — unified interface for AI model calls.
Supports: Ollama, Kimi (Moonshot), Anthropic, OpenAI.
"""

from infrastructure.llm.base import LLMAdapter, LLMResponse
from infrastructure.llm.ollama import OllamaAdapter
from infrastructure.llm.kimi import KimiAdapter
from infrastructure.llm.anthropic import AnthropicAdapter
from infrastructure.llm.openai import OpenAIAdapter

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


__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "get_adapter",
    "OllamaAdapter",
    "KimiAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
]
