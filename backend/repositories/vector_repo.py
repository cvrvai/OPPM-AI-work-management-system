"""
Vector repository — pgvector-backed storage for document embeddings.

Uses Supabase .rpc() to call the match_documents function for similarity search,
and direct table operations for upsert/delete.
"""

import logging
from typing import Any

from database import get_db

logger = logging.getLogger(__name__)


class VectorRepository:
    """CRUD + similarity search for the document_embeddings table."""

    def __init__(self) -> None:
        self.db = get_db()
        self.table_name = "document_embeddings"

    def _query(self):
        return self.db.table(self.table_name)

    def upsert_embedding(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        metadata: dict[str, Any],
        embedding: list[float],
    ) -> dict:
        """Insert or update an embedding for an entity."""
        data = {
            "workspace_id": workspace_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
            "updated_at": "now()",
        }
        result = (
            self._query()
            .upsert(data, on_conflict="entity_type,entity_id")
            .execute()
        )
        return result.data[0] if result.data else data

    def delete_embedding(self, entity_type: str, entity_id: str) -> bool:
        """Delete an embedding by entity type + id."""
        result = (
            self._query()
            .delete()
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .execute()
        )
        return bool(result.data)

    def delete_by_workspace(self, workspace_id: str) -> int:
        """Delete all embeddings for a workspace. Returns count deleted."""
        result = (
            self._query()
            .delete()
            .eq("workspace_id", workspace_id)
            .execute()
        )
        return len(result.data) if result.data else 0

    def count_by_workspace(self, workspace_id: str) -> int:
        """Count embeddings for a workspace."""
        result = (
            self._query()
            .select("id", count="exact")
            .eq("workspace_id", workspace_id)
            .execute()
        )
        return result.count or 0

    def similarity_search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        entity_types: list[str] | None = None,
    ) -> list[dict]:
        """
        Find the most similar documents using cosine similarity.
        Uses the match_documents RPC function (pgvector).
        """
        params: dict[str, Any] = {
            "p_workspace_id": workspace_id,
            "p_embedding": query_embedding,
            "p_match_count": top_k,
        }
        if entity_types:
            params["p_entity_types"] = entity_types

        try:
            result = self.db.rpc("match_documents", params).execute()
            return result.data or []
        except Exception as e:
            logger.warning("Vector similarity search failed: %s", e)
            return []
