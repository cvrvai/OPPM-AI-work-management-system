"""Vector retriever — pgvector cosine similarity search."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.rag.embedder import generate_embedding
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk
from domains.rag.vector_repository import VectorRepository

logger = logging.getLogger(__name__)


class VectorRetriever(BaseRetriever):
    """Retrieves documents via pgvector cosine similarity."""

    name = "vector"

    def __init__(self, session: AsyncSession) -> None:
        self._repo = VectorRepository(session)

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        entity_types: list[str] | None = filters.get("entity_types")

        query_embedding = await generate_embedding(query)

        # VectorRepository.similarity_search accepts singular `entity_type`
        entity_type = entity_types[0] if entity_types and len(entity_types) == 1 else None

        results = await self._repo.similarity_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=top_k,
            entity_type=entity_type,
        )

        return [
            RetrievedChunk(
                entity_type=r.get("entity_type", "unknown"),
                entity_id=str(r.get("entity_id", "")),
                content=r.get("content", ""),
                score=float(r.get("similarity", 0)),
                source=self.name,
                metadata=r.get("metadata") or {},
            )
            for r in results
        ]
