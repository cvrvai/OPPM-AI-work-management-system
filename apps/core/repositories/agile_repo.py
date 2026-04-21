"""Agile domain repositories — Epic, UserStory, Sprint, Retrospective."""

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.agile import Epic, UserStory, Sprint, Retrospective


class EpicRepository(BaseRepository):
    model = Epic

    async def find_project_epics(self, project_id: str) -> list[Epic]:
        stmt = (
            select(Epic)
            .where(Epic.project_id == project_id)
            .order_by(Epic.position.asc(), Epic.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class UserStoryRepository(BaseRepository):
    model = UserStory

    async def find_project_stories(
        self,
        project_id: str,
        sprint_id: str | None = None,
        epic_id: str | None = None,
        status: str | None = None,
    ) -> list[UserStory]:
        stmt = select(UserStory).where(UserStory.project_id == project_id)
        if sprint_id:
            stmt = stmt.where(UserStory.sprint_id == sprint_id)
        if epic_id:
            stmt = stmt.where(UserStory.epic_id == epic_id)
        if status:
            stmt = stmt.where(UserStory.status == status)
        stmt = stmt.order_by(UserStory.position.asc(), UserStory.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def reorder(self, story_ids: list[str]) -> None:
        for idx, story_id in enumerate(story_ids):
            stmt = (
                update(UserStory)
                .where(UserStory.id == story_id)
                .values(position=idx)
            )
            await self.session.execute(stmt)
        await self.session.flush()

    async def count_by_sprint_and_status(self, sprint_id: str, status: str) -> int:
        return await self.count(filters={"sprint_id": sprint_id, "status": status})

    async def sum_story_points_by_sprint(self, sprint_id: str, status: str | None = None) -> int:
        from sqlalchemy import func as sa_func
        stmt = select(sa_func.coalesce(sa_func.sum(UserStory.story_points), 0)).where(
            UserStory.sprint_id == sprint_id
        )
        if status:
            stmt = stmt.where(UserStory.status == status)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


class SprintRepository(BaseRepository):
    model = Sprint

    async def find_project_sprints(self, project_id: str, status: str | None = None) -> list[Sprint]:
        stmt = select(Sprint).where(Sprint.project_id == project_id)
        if status:
            stmt = stmt.where(Sprint.status == status)
        stmt = stmt.order_by(Sprint.sprint_number.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_active_sprint(self, project_id: str) -> Sprint | None:
        stmt = (
            select(Sprint)
            .where(Sprint.project_id == project_id, Sprint.status == "active")
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RetrospectiveRepository(BaseRepository):
    model = Retrospective

    async def find_by_sprint(self, sprint_id: str) -> Retrospective | None:
        stmt = select(Retrospective).where(Retrospective.sprint_id == sprint_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
