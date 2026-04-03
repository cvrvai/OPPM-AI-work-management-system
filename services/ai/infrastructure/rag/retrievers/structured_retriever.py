"""Structured retriever — direct DB queries for project/cost/timeline data via SQLAlchemy."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.project import Project
from shared.models.oppm import ProjectCost
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


class StructuredRetriever(BaseRetriever):
    """Retrieves structured project data (costs, timeline, members)."""

    name = "structured"

    def __init__(self, session: AsyncSession):
        self._session = session

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        project_id: str | None = filters.get("project_id")

        # Fetch project overviews
        try:
            stmt = (
                select(Project)
                .where(Project.workspace_id == workspace_id)
                .limit(top_k)
            )
            if project_id:
                stmt = stmt.where(Project.id == project_id)
            result = await self._session.execute(stmt)
            projects = result.scalars().all()

            for p in projects:
                content = (
                    f"Project: {p.title}\n"
                    f"Status: {p.status} | Progress: {p.progress or 0}%\n"
                    f"Start: {p.start_date or '—'} | Deadline: {p.deadline or '—'}"
                )
                if p.description:
                    content += f"\n{p.description}"
                chunks.append(RetrievedChunk(
                    entity_type="project",
                    entity_id=str(p.id),
                    content=content,
                    score=0.6,
                    source=self.name,
                    metadata={"title": p.title, "status": p.status},
                ))
        except Exception as e:
            logger.warning("Structured project retrieval failed: %s", e)

        # Fetch cost summaries if query relates to cost/budget
        query_lower = query.lower()
        if any(w in query_lower for w in ("cost", "budget", "spend", "expense", "money")):
            try:
                stmt = select(ProjectCost).limit(top_k)
                if project_id:
                    stmt = stmt.where(ProjectCost.project_id == project_id)
                result = await self._session.execute(stmt)
                costs = result.scalars().all()

                for c in costs:
                    content = (
                        f"Cost: {c.category or '—'}\n"
                        f"Planned: {c.planned_amount or 0} | Actual: {c.actual_amount or 0}"
                    )
                    chunks.append(RetrievedChunk(
                        entity_type="cost",
                        entity_id=str(c.id),
                        content=content,
                        score=0.8,
                        source=self.name,
                        metadata={"category": c.category, "project_id": str(c.project_id) if c.project_id else None},
                    ))
            except Exception as e:
                logger.warning("Structured cost retrieval failed: %s", e)

        return chunks[:top_k]
