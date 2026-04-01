"""Base LLM adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
