"""
Project service — business logic for project CRUD + progress.
Migrated from services/core/services/project_service.py.
"""

import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.project_repo import ProjectRepository, ProjectMemberRepository
from repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


def _parse_dates(data: dict) -> dict:
    for field in ("start_date", "deadline", "end_date"):
        val = data.get(field)
        if isinstance(val, str) and val:
            try:
                data[field] = date.fromisoformat(val)
            except ValueError:
                pass
    return data


def _audit_safe(data: dict) -> dict:
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in data.items()}


async def list_projects(
    session: AsyncSession,
    workspace_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    repo = ProjectRepository(session)
    items = await repo.find_workspace_projects(workspace_id, status=status, limit=limit, offset=offset)
    total = await repo.count_in_workspace(workspace_id)
    return {"items": items, "total": total}


async def get_project(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    repo = ProjectRepository(session)
    project = await repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def create_project(
    session: AsyncSession, workspace_id: str, user_id: str, data: dict, member_id: str
) -> dict:
    repo = ProjectRepository(session)
    member_repo = ProjectMemberRepository(session)
    audit_repo = AuditRepository(session)

    data["workspace_id"] = workspace_id
    _parse_dates(data)
    project = await repo.create(data)
    await member_repo.add_member(str(project.id), member_id, role="lead")
    await audit_repo.log(workspace_id, user_id, "create", "project", str(project.id), new_data=_audit_safe(data))
    return project


async def update_project(
    session: AsyncSession, project_id: str, workspace_id: str, user_id: str, data: dict
) -> dict:
    repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    await get_project(session, project_id, workspace_id)
    _parse_dates(data)
    result = await repo.update(project_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    await audit_repo.log(workspace_id, user_id, "update", "project", project_id, new_data=_audit_safe(data))
    return result


async def delete_project(
    session: AsyncSession, project_id: str, workspace_id: str, user_id: str
) -> None:
    repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    await get_project(session, project_id, workspace_id)
    await audit_repo.log(workspace_id, user_id, "delete", "project", project_id)
    await repo.delete(project_id)


async def get_project_members(session: AsyncSession, project_id: str) -> list[dict]:
    repo = ProjectMemberRepository(session)
    return await repo.find_project_members(project_id)


async def add_project_member(
    session: AsyncSession, project_id: str, member_id: str, role: str = "contributor"
) -> dict:
    repo = ProjectMemberRepository(session)
    return await repo.add_member(project_id, member_id, role)


async def remove_project_member(
    session: AsyncSession, project_id: str, member_id: str
) -> None:
    repo = ProjectMemberRepository(session)
    await repo.remove_member(project_id, member_id)
