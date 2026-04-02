"""Base LLM adapter interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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

    async def health_check(self, **kwargs) -> bool:
        """Check if the provider endpoint is reachable. Override in subclasses."""
        return True
