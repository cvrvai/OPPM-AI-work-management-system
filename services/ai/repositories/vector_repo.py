"""Vector repository for AI service — embedding storage and similarity search."""

from shared.database import get_db


class VectorRepository:
    """Manages pgvector embeddings for RAG retrieval."""

    def __init__(self):
        self.table = "document_embeddings"

    def upsert_embedding(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        metadata: dict,
        embedding: list[float],
    ) -> dict:
        db = get_db()
        existing = (
            db.table(self.table)
            .select("id")
            .eq("entity_type", entity_type)
            .eq("entity_id", entity_id)
            .limit(1)
            .execute()
        )
        data = {
            "workspace_id": workspace_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
        }
        if existing.data:
            result = db.table(self.table).update(data).eq("id", existing.data[0]["id"]).execute()
        else:
            result = db.table(self.table).insert(data).execute()
        return result.data[0] if result.data else {}

    def similarity_search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        entity_type: str | None = None,
    ) -> list[dict]:
        db = get_db()
        params = {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "p_workspace_id": workspace_id,
        }
        if entity_type:
            params["p_entity_type"] = entity_type
        result = db.rpc("match_documents", params).execute()
        return result.data or []

    def delete_embedding(self, entity_type: str, entity_id: str) -> None:
        db = get_db()
        db.table(self.table).delete().eq("entity_type", entity_type).eq("entity_id", entity_id).execute()

    def count_by_workspace(self, workspace_id: str) -> int:
        db = get_db()
        result = db.table(self.table).select("id", count="exact").eq("workspace_id", workspace_id).execute()
        return result.count or 0
