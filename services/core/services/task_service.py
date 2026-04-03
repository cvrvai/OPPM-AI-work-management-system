"""
Task service — CRUD + weighted project progress recalculation.
"""

import asyncio
import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.task_repo import TaskRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository
from services.document_indexer import index_task, remove_entity

logger = logging.getLogger(__name__)


async def _recalculate_project_progress(session: AsyncSession, project_id: str) -> None:
    """Recalculate weighted project progress from all tasks."""
    task_repo = TaskRepository(session)
    project_repo = ProjectRepository(session)
    tasks = await task_repo.get_project_progress_data(project_id)
    if not tasks:
        await project_repo.update_progress(project_id, 0)
        return
    total_weight = sum(t["project_contribution"] for t in tasks)
    if total_weight > 0:
        weighted = sum(t["progress"] * t["project_contribution"] / total_weight for t in tasks)
        await project_repo.update_progress(project_id, round(weighted))


async def list_tasks(
    session: AsyncSession,
    workspace_id: str,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    task_repo = TaskRepository(session)
    if project_id:
        return await task_repo.find_project_tasks(project_id, status=status, limit=limit, offset=offset)
    return await task_repo.find_workspace_tasks(workspace_id, status=status, limit=limit, offset=offset)


async def get_task(session: AsyncSession, task_id: str, workspace_id: str) -> dict:
    task_repo = TaskRepository(session)
    project_repo = ProjectRepository(session)
    task = await task_repo.find_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Tasks don't have workspace_id — scope through project
    project = await project_repo.find_by_id(task.project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def create_task(session: AsyncSession, data: dict, workspace_id: str, user_id: str) -> dict:
    task_repo = TaskRepository(session)
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    # Verify project belongs to workspace
    project = await project_repo.find_by_id(data["project_id"])
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
    data["created_by"] = user_id
    task = await task_repo.create(data)
    await _recalculate_project_progress(session, str(task.project_id))
    await audit_repo.log(workspace_id, user_id, "create", "task", str(task.id), new_data=data)
    asyncio.create_task(index_task(task, workspace_id))
    return task


async def update_task(session: AsyncSession, task_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    task_repo = TaskRepository(session)
    audit_repo = AuditRepository(session)
    task = await get_task(session, task_id, workspace_id)
    result = await task_repo.update(task_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    await _recalculate_project_progress(session, str(result.project_id))
    await audit_repo.log(workspace_id, user_id, "update", "task", task_id, new_data=data)
    asyncio.create_task(index_task(result, workspace_id))
    return result


async def delete_task(session: AsyncSession, task_id: str, workspace_id: str, user_id: str) -> bool:
    task_repo = TaskRepository(session)
    audit_repo = AuditRepository(session)
    task = await get_task(session, task_id, workspace_id)
    project_id = str(task.project_id)
    await audit_repo.log(workspace_id, user_id, "delete", "task", task_id)
    asyncio.create_task(remove_entity("task", task_id))
    await task_repo.delete(task_id)
    await _recalculate_project_progress(session, project_id)
    return True
