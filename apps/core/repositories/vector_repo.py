"""
Vector repository — pgvector-backed storage for document embeddings.
"""

import logging
from typing import Any

from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.embedding import DocumentEmbedding

logger = logging.getLogger(__name__)


class VectorRepository:
    """CRUD + similarity search for the document_embeddings table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_embedding(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        metadata: dict[str, Any],
        embedding: list[float],
    ) -> DocumentEmbedding:
        stmt = (
            select(DocumentEmbedding)
            .where(
                DocumentEmbedding.entity_type == entity_type,
                DocumentEmbedding.entity_id == entity_id,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            existing.metadata_ = metadata
            existing.embedding = embedding
            existing.workspace_id = workspace_id
            await self.session.flush()
            return existing

        doc = DocumentEmbedding(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            metadata_=metadata,
            embedding=embedding,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def delete_embedding(self, entity_type: str, entity_id: str) -> bool:
        stmt = delete(DocumentEmbedding).where(
            DocumentEmbedding.entity_type == entity_type,
            DocumentEmbedding.entity_id == entity_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def delete_by_workspace(self, workspace_id: str) -> int:
        stmt = delete(DocumentEmbedding).where(DocumentEmbedding.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def count_by_workspace(self, workspace_id: str) -> int:
        stmt = select(func.count(DocumentEmbedding.id)).where(DocumentEmbedding.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def similarity_search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        entity_types: list[str] | None = None,
    ) -> list[dict]:
        try:
            stmt = (
                select(
                    DocumentEmbedding.id,
                    DocumentEmbedding.entity_type,
                    DocumentEmbedding.entity_id,
                    DocumentEmbedding.content,
                    DocumentEmbedding.metadata_,
                    DocumentEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(DocumentEmbedding.workspace_id == workspace_id)
            )
            if entity_types:
                stmt = stmt.where(DocumentEmbedding.entity_type.in_(entity_types))
            stmt = stmt.order_by("distance").limit(top_k)
            result = await self.session.execute(stmt)
            return [
                {
                    "id": str(r.id),
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "content": r.content,
                    "metadata": r.metadata_,
                    "similarity": 1 - r.distance,
                }
                for r in result.all()
            ]
        except Exception as e:
            logger.warning("Vector similarity search failed: %s", e)
            return []
