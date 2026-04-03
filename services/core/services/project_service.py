"""
Project service — business logic for project CRUD + progress.
"""

import asyncio
import logging
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.project_repo import ProjectRepository, ProjectMemberRepository
from repositories.notification_repo import AuditRepository

logger = logging.getLogger(__name__)


async def list_projects(session: AsyncSession, workspace_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    project_repo = ProjectRepository(session)
    items = await project_repo.find_workspace_projects(workspace_id, status=status, limit=limit, offset=offset)
    total = await project_repo.count_in_workspace(workspace_id)
    return {"items": items, "total": total}


async def get_project(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def create_project(session: AsyncSession, workspace_id: str, user_id: str, data: dict, member_id: str) -> dict:
    project_repo = ProjectRepository(session)
    project_member_repo = ProjectMemberRepository(session)
    audit_repo = AuditRepository(session)

    data["workspace_id"] = workspace_id
    project = await project_repo.create(data)
    await project_member_repo.add_member(str(project.id), member_id, role="lead")
    await audit_repo.log(workspace_id, user_id, "create", "project", str(project.id), new_data=data)
    return project


async def update_project(session: AsyncSession, project_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    await get_project(session, project_id, workspace_id)
    result = await project_repo.update(project_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    await audit_repo.log(workspace_id, user_id, "update", "project", project_id, new_data=data)
    return result


async def delete_project(session: AsyncSession, project_id: str, workspace_id: str, user_id: str) -> bool:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    await get_project(session, project_id, workspace_id)
    await audit_repo.log(workspace_id, user_id, "delete", "project", project_id)
    return await project_repo.delete(project_id)


async def get_project_members(session: AsyncSession, project_id: str) -> list[dict]:
    project_member_repo = ProjectMemberRepository(session)
    return await project_member_repo.find_project_members(project_id)


async def add_project_member(session: AsyncSession, project_id: str, member_id: str, role: str = "contributor") -> dict:
    project_member_repo = ProjectMemberRepository(session)
    return await project_member_repo.add_member(project_id, member_id, role)


async def remove_project_member(session: AsyncSession, project_id: str, member_id: str) -> bool:
    project_member_repo = ProjectMemberRepository(session)
    return await project_member_repo.remove_member(project_id, member_id)
