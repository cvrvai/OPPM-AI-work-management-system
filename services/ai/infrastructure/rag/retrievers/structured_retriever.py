"""Structured retriever — direct DB queries for project/cost/timeline data."""

import logging

from shared.database import get_db
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


class StructuredRetriever(BaseRetriever):
    """Retrieves structured project data (costs, timeline, members)."""

    name = "structured"

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

        # Fetch project overviews
        try:
            q = (
                db.table("projects")
                .select("id, title, description, status, progress, start_date, deadline")
                .eq("workspace_id", workspace_id)
                .limit(top_k)
            )
            if project_id:
                q = q.eq("id", project_id)
            result = q.execute()

            for p in result.data or []:
                content = (
                    f"Project: {p['title']}\n"
                    f"Status: {p['status']} | Progress: {p.get('progress', 0)}%\n"
                    f"Start: {p.get('start_date', '—')} | Deadline: {p.get('deadline', '—')}"
                )
                if p.get("description"):
                    content += f"\n{p['description']}"
                chunks.append(RetrievedChunk(
                    entity_type="project",
                    entity_id=str(p["id"]),
                    content=content,
                    score=0.6,
                    source=self.name,
                    metadata={"title": p["title"], "status": p["status"]},
                ))
        except Exception as e:
            logger.warning("Structured project retrieval failed: %s", e)

        # Fetch cost summaries if query relates to cost/budget
        query_lower = query.lower()
        if any(w in query_lower for w in ("cost", "budget", "spend", "expense", "money")):
            try:
                q = db.table("project_costs").select("*").limit(top_k)
                if project_id:
                    q = q.eq("project_id", project_id)
                result = q.execute()

                for c in result.data or []:
                    content = (
                        f"Cost: {c.get('category', '—')}\n"
                        f"Planned: {c.get('planned_amount', 0)} | Actual: {c.get('actual_amount', 0)}"
                    )
                    chunks.append(RetrievedChunk(
                        entity_type="cost",
                        entity_id=str(c["id"]),
                        content=content,
                        score=0.8,
                        source=self.name,
                        metadata={"category": c.get("category"), "project_id": c.get("project_id")},
                    ))
            except Exception as e:
                logger.warning("Structured cost retrieval failed: %s", e)

        return chunks[:top_k]
