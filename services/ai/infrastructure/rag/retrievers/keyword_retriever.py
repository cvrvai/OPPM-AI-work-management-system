"""Keyword retriever — full-text search on tasks and objectives via SQLAlchemy."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.task import Task
from shared.models.project import Project
from shared.models.oppm import OPPMObjective
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


class KeywordRetriever(BaseRetriever):
    """Retrieves tasks and objectives via keyword/ILIKE search."""

    name = "keyword"

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
        search_term = f"%{query}%"

        # Search tasks (tasks don't have workspace_id — join through projects)
        try:
            stmt = (
                select(Task)
                .join(Project, Task.project_id == Project.id)
                .where(Project.workspace_id == workspace_id)
                .where(Task.title.ilike(search_term) | Task.description.ilike(search_term))
                .limit(top_k)
            )
            if project_id:
                stmt = stmt.where(Task.project_id == project_id)
            result = await self._session.execute(stmt)
            tasks = result.scalars().all()

            for t in tasks:
                content = f"Task: {t.title}\nStatus: {t.status} | Progress: {t.progress or 0}%"
                if t.description:
                    content += f"\n{t.description}"
                chunks.append(RetrievedChunk(
                    entity_type="task",
                    entity_id=str(t.id),
                    content=content,
                    score=0.7,
                    source=self.name,
                    metadata={"title": t.title, "status": t.status, "project_id": str(t.project_id) if t.project_id else None},
                ))
        except Exception as e:
            logger.warning("Keyword search on tasks failed: %s", e)

        # Search objectives
        try:
            stmt = (
                select(OPPMObjective)
                .where(OPPMObjective.title.ilike(search_term))
                .limit(top_k)
            )
            if project_id:
                stmt = stmt.where(OPPMObjective.project_id == project_id)
            result = await self._session.execute(stmt)
            objectives = result.scalars().all()

            for o in objectives:
                chunks.append(RetrievedChunk(
                    entity_type="objective",
                    entity_id=str(o.id),
                    content=f"Objective: {o.title}",
                    score=0.7,
                    source=self.name,
                    metadata={"title": o.title, "project_id": str(o.project_id) if o.project_id else None},
                ))
        except Exception as e:
            logger.warning("Keyword search on objectives failed: %s", e)

        return chunks[:top_k]
