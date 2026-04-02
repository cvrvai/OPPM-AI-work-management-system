"""Keyword retriever — Supabase full-text search on tasks and objectives."""

import logging

from shared.database import get_db
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


class KeywordRetriever(BaseRetriever):
    """Retrieves tasks and objectives via keyword/ILIKE search."""

    name = "keyword"

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        db = get_db()
        chunks: list[RetrievedChunk] = []
        project_id: str | None = filters.get("project_id")
        search_term = f"%{query}%"

        # Search tasks
        try:
            q = (
                db.table("tasks")
                .select("id, title, description, status, progress, project_id, oppm_objective_id")
                .eq("workspace_id", workspace_id)
                .or_(f"title.ilike.{search_term},description.ilike.{search_term}")
                .limit(top_k)
            )
            if project_id:
                q = q.eq("project_id", project_id)
            result = q.execute()

            for t in result.data or []:
                content = f"Task: {t['title']}\nStatus: {t['status']} | Progress: {t['progress']}%"
                if t.get("description"):
                    content += f"\n{t['description']}"
                chunks.append(RetrievedChunk(
                    entity_type="task",
                    entity_id=str(t["id"]),
                    content=content,
                    score=0.7,  # fixed score for keyword matches
                    source=self.name,
                    metadata={"title": t["title"], "status": t["status"], "project_id": t.get("project_id")},
                ))
        except Exception as e:
            logger.warning("Keyword search on tasks failed: %s", e)

        # Search objectives
        try:
            q = (
                db.table("oppm_objectives")
                .select("id, title, project_id, sort_order")
                .ilike("title", search_term)
                .limit(top_k)
            )
            if project_id:
                q = q.eq("project_id", project_id)
            result = q.execute()

            for o in result.data or []:
                chunks.append(RetrievedChunk(
                    entity_type="objective",
                    entity_id=str(o["id"]),
                    content=f"Objective: {o['title']}",
                    score=0.7,
                    source=self.name,
                    metadata={"title": o["title"], "project_id": o.get("project_id")},
                ))
        except Exception as e:
            logger.warning("Keyword search on objectives failed: %s", e)

        return chunks[:top_k]
