"""
Agile service — business logic for epics, user stories, sprints, retrospectives.
"""

import logging
from datetime import date
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agile.repository import (
    EpicRepository,
    UserStoryRepository,
    SprintRepository,
    RetrospectiveRepository,
)
from domains.notification.repository import AuditRepository

logger = logging.getLogger(__name__)


def _parse_dates(data: dict) -> dict:
    """Convert ISO date strings to datetime.date for asyncpg compatibility."""
    for field in ("start_date", "end_date"):
        val = data.get(field)
        if isinstance(val, str) and val:
            try:
                data[field] = date.fromisoformat(val)
            except ValueError:
                pass
    return data


# ── Epics ──

async def list_epics(session: AsyncSession, project_id: str) -> dict:
    repo = EpicRepository(session)
    items = await repo.find_project_epics(project_id)
    return {"items": items, "total": len(items)}


async def create_epic(session: AsyncSession, workspace_id: str, project_id: str, user_id: str, data: dict) -> dict:
    repo = EpicRepository(session)
    audit = AuditRepository(session)
    data["workspace_id"] = workspace_id
    data["project_id"] = project_id
    epic = await repo.create(data)
    await audit.log(workspace_id, user_id, "create", "epic", str(epic.id), new_data=data)
    return epic


async def update_epic(session: AsyncSession, epic_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = EpicRepository(session)
    audit = AuditRepository(session)
    epic = await repo.find_by_id(epic_id)
    if not epic or str(epic.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Epic not found")
    result = await repo.update(epic_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Epic not found")
    await audit.log(workspace_id, user_id, "update", "epic", epic_id, new_data=data)
    return result


async def delete_epic(session: AsyncSession, epic_id: str, workspace_id: str, user_id: str) -> bool:
    repo = EpicRepository(session)
    audit = AuditRepository(session)
    epic = await repo.find_by_id(epic_id)
    if not epic or str(epic.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Epic not found")
    await audit.log(workspace_id, user_id, "delete", "epic", epic_id)
    return await repo.delete(epic_id)


# ── User Stories ──

async def list_user_stories(
    session: AsyncSession,
    project_id: str,
    sprint_id: str | None = None,
    epic_id: str | None = None,
    status: str | None = None,
) -> dict:
    repo = UserStoryRepository(session)
    items = await repo.find_project_stories(project_id, sprint_id=sprint_id, epic_id=epic_id, status=status)
    return {"items": items, "total": len(items)}


async def create_user_story(session: AsyncSession, workspace_id: str, project_id: str, user_id: str, member_id: str, data: dict) -> dict:
    repo = UserStoryRepository(session)
    audit = AuditRepository(session)
    data["workspace_id"] = workspace_id
    data["project_id"] = project_id
    data["created_by"] = member_id
    # Serialize acceptance_criteria list[dict] for JSONB
    if "acceptance_criteria" in data and isinstance(data["acceptance_criteria"], list):
        data["acceptance_criteria"] = [
            item if isinstance(item, dict) else {"criterion": str(item), "met": False}
            for item in data["acceptance_criteria"]
        ]
    story = await repo.create(data)
    await audit.log(workspace_id, user_id, "create", "user_story", str(story.id))
    return story


async def update_user_story(session: AsyncSession, story_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = UserStoryRepository(session)
    audit = AuditRepository(session)
    story = await repo.find_by_id(story_id)
    if not story or str(story.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="User story not found")
    if "acceptance_criteria" in data and isinstance(data["acceptance_criteria"], list):
        data["acceptance_criteria"] = [
            item if isinstance(item, dict) else {"criterion": str(item), "met": False}
            for item in data["acceptance_criteria"]
        ]
    result = await repo.update(story_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="User story not found")
    await audit.log(workspace_id, user_id, "update", "user_story", story_id)
    return result


async def delete_user_story(session: AsyncSession, story_id: str, workspace_id: str, user_id: str) -> bool:
    repo = UserStoryRepository(session)
    audit = AuditRepository(session)
    story = await repo.find_by_id(story_id)
    if not story or str(story.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="User story not found")
    await audit.log(workspace_id, user_id, "delete", "user_story", story_id)
    return await repo.delete(story_id)


async def reorder_user_stories(session: AsyncSession, story_ids: list[str]) -> dict:
    repo = UserStoryRepository(session)
    await repo.reorder(story_ids)
    return {"ok": True}


# ── Sprints ──

async def list_sprints(session: AsyncSession, project_id: str, status: str | None = None) -> dict:
    repo = SprintRepository(session)
    items = await repo.find_project_sprints(project_id, status=status)
    return {"items": items, "total": len(items)}


async def create_sprint(session: AsyncSession, workspace_id: str, project_id: str, user_id: str, data: dict) -> dict:
    repo = SprintRepository(session)
    audit = AuditRepository(session)
    data["workspace_id"] = workspace_id
    data["project_id"] = project_id
    _parse_dates(data)
    sprint = await repo.create(data)
    await audit.log(workspace_id, user_id, "create", "sprint", str(sprint.id))
    return sprint


async def update_sprint(session: AsyncSession, sprint_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = SprintRepository(session)
    audit = AuditRepository(session)
    sprint = await repo.find_by_id(sprint_id)
    if not sprint or str(sprint.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")
    _parse_dates(data)
    result = await repo.update(sprint_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await audit.log(workspace_id, user_id, "update", "sprint", sprint_id)
    return result


async def delete_sprint(session: AsyncSession, sprint_id: str, workspace_id: str, user_id: str) -> bool:
    repo = SprintRepository(session)
    audit = AuditRepository(session)
    sprint = await repo.find_by_id(sprint_id)
    if not sprint or str(sprint.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await audit.log(workspace_id, user_id, "delete", "sprint", sprint_id)
    return await repo.delete(sprint_id)


async def start_sprint(session: AsyncSession, sprint_id: str, workspace_id: str, user_id: str) -> dict:
    repo = SprintRepository(session)
    audit = AuditRepository(session)
    sprint = await repo.find_by_id(sprint_id)
    if not sprint or str(sprint.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if sprint.status != "planning":
        raise HTTPException(status_code=400, detail="Only sprints in planning can be started")
    # Check no other sprint is active in this project
    active = await repo.find_active_sprint(str(sprint.project_id))
    if active:
        raise HTTPException(status_code=400, detail="Another sprint is already active")
    result = await repo.update(sprint_id, {"status": "active"})
    await audit.log(workspace_id, user_id, "update", "sprint", sprint_id, new_data={"status": "active"})
    return result


async def complete_sprint(session: AsyncSession, sprint_id: str, workspace_id: str, user_id: str) -> dict:
    repo = SprintRepository(session)
    story_repo = UserStoryRepository(session)
    audit = AuditRepository(session)
    sprint = await repo.find_by_id(sprint_id)
    if not sprint or str(sprint.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if sprint.status != "active":
        raise HTTPException(status_code=400, detail="Only active sprints can be completed")
    # Calculate velocity as sum of done story points
    velocity = await story_repo.sum_story_points_by_sprint(sprint_id, status="done")
    result = await repo.update(sprint_id, {"status": "completed", "velocity": velocity})
    await audit.log(workspace_id, user_id, "update", "sprint", sprint_id, new_data={"status": "completed", "velocity": velocity})
    return result


async def get_burndown(session: AsyncSession, sprint_id: str, workspace_id: str) -> dict:
    """Return burndown chart data for a sprint."""
    repo = SprintRepository(session)
    story_repo = UserStoryRepository(session)
    sprint = await repo.find_by_id(sprint_id)
    if not sprint or str(sprint.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")

    total_points = await story_repo.sum_story_points_by_sprint(sprint_id)
    done_points = await story_repo.sum_story_points_by_sprint(sprint_id, status="done")

    # Build simple burndown structure
    # Full date-by-date tracking would require daily snapshots — this gives a summary view
    start = sprint.start_date
    end = sprint.end_date
    dates = []
    ideal = []
    actual = []

    if start and end:
        from datetime import timedelta
        num_days = (end - start).days
        if num_days > 0:
            daily_burn = total_points / num_days
            for i in range(num_days + 1):
                d = start + timedelta(days=i)
                dates.append(d.isoformat())
                ideal.append(round(total_points - (daily_burn * i), 1))
            # Simplified actual: we only know current done_points, not daily history
            remaining = total_points - done_points
            actual = [total_points] * len(dates)
            if len(actual) > 0:
                actual[-1] = remaining

    return {
        "total_points": total_points,
        "done_points": done_points,
        "dates": dates,
        "ideal": ideal,
        "actual": actual,
    }


# ── Retrospectives ──

async def get_retrospective(session: AsyncSession, sprint_id: str, workspace_id: str) -> dict:
    repo = RetrospectiveRepository(session)
    retro = await repo.find_by_sprint(sprint_id)
    if not retro or str(retro.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Retrospective not found")
    return retro


async def create_retrospective(session: AsyncSession, workspace_id: str, project_id: str, sprint_id: str, user_id: str, member_id: str, data: dict) -> dict:
    repo = RetrospectiveRepository(session)
    audit = AuditRepository(session)
    existing = await repo.find_by_sprint(sprint_id)
    if existing:
        raise HTTPException(status_code=400, detail="Retrospective already exists for this sprint")
    data["workspace_id"] = workspace_id
    data["project_id"] = project_id
    data["sprint_id"] = sprint_id
    data["created_by"] = member_id
    # Serialize action_items list[dict] for JSONB
    if "action_items" in data and isinstance(data["action_items"], list):
        data["action_items"] = [
            item if isinstance(item, dict) else {"item": str(item), "done": False}
            for item in data["action_items"]
        ]
    retro = await repo.create(data)
    await audit.log(workspace_id, user_id, "create", "retrospective", str(retro.id))
    return retro


async def update_retrospective(session: AsyncSession, sprint_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = RetrospectiveRepository(session)
    audit = AuditRepository(session)
    retro = await repo.find_by_sprint(sprint_id)
    if not retro or str(retro.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Retrospective not found")
    if "action_items" in data and isinstance(data["action_items"], list):
        data["action_items"] = [
            item if isinstance(item, dict) else {"item": str(item), "done": False}
            for item in data["action_items"]
        ]
    result = await repo.update(str(retro.id), data)
    if not result:
        raise HTTPException(status_code=404, detail="Retrospective not found")
    await audit.log(workspace_id, user_id, "update", "retrospective", str(retro.id))
    return result
