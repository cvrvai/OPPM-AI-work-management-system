"""Minimal project repository for integrations service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.project import Project


class ProjectRepository:
    """Minimal project repo — only what integrations needs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_workspace_projects(
        self,
        workspace_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Project]:
        stmt = select(Project).where(Project.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
