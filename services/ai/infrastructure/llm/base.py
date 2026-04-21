"""Base LLM adapter interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class ProviderUnavailableError(Exception):
    """Raised when an LLM provider is unreachable or returns a non-retryable error."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider} unavailable: {reason}")


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""
    text: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    provider: str = ""

    @abstractmethod
    async def call(self, model_id: str, prompt: str, **kwargs) -> LLMResponse:
        """Send a prompt to the model and return the response text."""
        ...

    @abstractmethod
    async def call_json(self, model_id: str, prompt: str, **kwargs) -> dict | None:
        """Send a prompt and parse the response as JSON."""
        ...

    async def call_with_tools(
        self,
        model_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send messages with tool definitions and return response with tool calls.

        Default implementation falls back to prompt-based calling (no native tools).
        Override in subclasses that support native function calling.
        """
        # Default: concatenate messages into a single prompt string
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.capitalize()}: {content}")
        prompt_parts.append("Assistant: ")
        prompt = "\n\n".join(prompt_parts)

        response = await self.call(model_id, prompt, **kwargs)
        return response

    async def health_check(self, **kwargs) -> bool:
        """Check if the provider endpoint is reachable. Override in subclasses."""
        return True
