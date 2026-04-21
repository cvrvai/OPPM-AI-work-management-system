"""Vector repository for AI service — embedding storage and similarity search."""

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.embedding import DocumentEmbedding


class VectorRepository:
    """Manages pgvector embeddings for RAG retrieval."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_embedding(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        metadata: dict,
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
            existing.workspace_id = workspace_id
            existing.content = content
            existing.metadata_ = metadata
            existing.embedding = embedding
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

    async def similarity_search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        entity_type: str | None = None,
    ) -> list[dict]:
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
        if entity_type:
            stmt = stmt.where(DocumentEmbedding.entity_type == entity_type)
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

    async def delete_embedding(self, entity_type: str, entity_id: str) -> None:
        stmt = delete(DocumentEmbedding).where(
            DocumentEmbedding.entity_type == entity_type,
            DocumentEmbedding.entity_id == entity_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def count_by_workspace(self, workspace_id: str) -> int:
        stmt = select(func.count(DocumentEmbedding.id)).where(DocumentEmbedding.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
