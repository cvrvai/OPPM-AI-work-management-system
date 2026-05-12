"""Project file repository — CRUD for uploaded project files."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domains.workspace.base_repository import BaseRepository
from shared.models.project_file import ProjectFile


class ProjectFileRepository(BaseRepository):
    model = ProjectFile

    async def find_by_project(self, project_id: str) -> list[ProjectFile]:
        stmt = (
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_id(self, file_id: str) -> bool:
        stmt = delete(ProjectFile).where(ProjectFile.id == file_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
