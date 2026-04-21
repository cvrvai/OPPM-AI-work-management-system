"""Base retriever interface for RAG retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    """A single retrieved document chunk with relevance score."""
    entity_type: str
    entity_id: str
    content: str
    score: float
    source: str  # retriever name that produced this result
    metadata: dict = field(default_factory=dict)


class BaseRetriever(ABC):
    """Abstract base class for RAG retrievers."""

    name: str = "base"

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for the given query."""
        ...
