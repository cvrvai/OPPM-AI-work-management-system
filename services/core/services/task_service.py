"""
Task service — CRUD + weighted project progress recalculation.
"""

import asyncio
import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.task_repo import TaskRepository, TaskReportRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository
from services.document_indexer import index_task, remove_entity
logger = logging.getLogger(__name__)


def _coerce_dates(data: dict) -> dict:
    """Convert ISO string dates to datetime.date for SQLAlchemy asyncpg."""
    for field in ("start_date", "due_date"):
        val = data.get(field)
        if isinstance(val, str) and val:
            data[field] = date.fromisoformat(val)
    return data


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


def _report_to_dict(report) -> dict:
    """Convert a TaskReport ORM object to a serializable dict."""
    return {
        "id": str(report.id),
        "task_id": str(report.task_id),
        "reporter_id": str(report.reporter_id) if report.reporter_id else None,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "hours": float(report.hours),
        "description": report.description,
        "is_approved": report.is_approved,
        "approved_by": str(report.approved_by) if report.approved_by else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "created_at": report.created_at.isoformat(),
    }


def _task_to_dict(task, depends_on: list[str] | None = None) -> dict:
    """Convert a Task ORM object to a dict, adding the depends_on field."""
    d = {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "project_id": str(task.project_id),
        "oppm_objective_id": str(task.oppm_objective_id) if task.oppm_objective_id else None,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress,
        "project_contribution": task.project_contribution,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_by": str(task.created_by) if task.created_by else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "depends_on": depends_on if depends_on is not None else [],
    }
    return d


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
        tasks = await task_repo.find_project_tasks(project_id, status=status, limit=limit, offset=offset)
    else:
        tasks = await task_repo.find_workspace_tasks(workspace_id, status=status, limit=limit, offset=offset)
    task_ids = [str(t.id) for t in tasks]
    deps_map = await task_repo.get_dependencies_for_tasks(task_ids)
    return [_task_to_dict(t, deps_map.get(str(t.id), [])) for t in tasks]


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
    depends_on = await task_repo.get_dependencies(task_id)
    return _task_to_dict(task, depends_on)


async def create_task(session: AsyncSession, data: dict, workspace_id: str, user_id: str, member_id: str | None = None) -> dict:
    task_repo = TaskRepository(session)
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    # Verify project belongs to workspace
    project = await project_repo.find_by_id(data["project_id"])
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
    if project.lead_id and member_id and str(project.lead_id) != member_id:
        raise HTTPException(status_code=403, detail="Only the project lead can create tasks")
    depends_on = data.pop("depends_on", None) or []
    data["created_by"] = user_id
    audit_data = {**data}
    _coerce_dates(data)
    task = await task_repo.create(data)
    if depends_on:
        await task_repo.set_dependencies(str(task.id), depends_on)
    await _recalculate_project_progress(session, str(task.project_id))
    await audit_repo.log(workspace_id, user_id, "create", "task", str(task.id), new_data=audit_data)
    asyncio.create_task(index_task(task, workspace_id))
    return _task_to_dict(task, depends_on)


async def update_task(session: AsyncSession, task_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    task_repo = TaskRepository(session)
    audit_repo = AuditRepository(session)
    task = await get_task(session, task_id, workspace_id)
    depends_on = data.pop("depends_on", None)
    audit_data = {**data}
    _coerce_dates(data)
    result = await task_repo.update(task_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    if depends_on is not None:
        await task_repo.set_dependencies(task_id, depends_on)
    else:
        depends_on = await task_repo.get_dependencies(task_id)
    await _recalculate_project_progress(session, str(result.project_id))
    await audit_repo.log(workspace_id, user_id, "update", "task", task_id, new_data=audit_data)
    asyncio.create_task(index_task(result, workspace_id))
    return _task_to_dict(result, depends_on)


async def delete_task(session: AsyncSession, task_id: str, workspace_id: str, user_id: str) -> bool:
    task_repo = TaskRepository(session)
    audit_repo = AuditRepository(session)
    task = await get_task(session, task_id, workspace_id)
    project_id = str(task["project_id"])
    await audit_repo.log(workspace_id, user_id, "delete", "task", task_id)
    asyncio.create_task(remove_entity("task", task_id))
    await task_repo.delete(task_id)
    await _recalculate_project_progress(session, project_id)
    return True


# --- Task Daily Reports ---

async def list_task_reports(session: AsyncSession, task_id: str, workspace_id: str) -> list:
    await get_task(session, task_id, workspace_id)  # validates ownership
    report_repo = TaskReportRepository(session)
    reports = await report_repo.find_by_task(task_id)
    return [_report_to_dict(r) for r in reports]


async def create_task_report(
    session: AsyncSession,
    task_id: str,
    data: dict,
    workspace_id: str,
    user_id: str,
) -> dict:
    task_data = await get_task(session, task_id, workspace_id)
    if task_data.get("assignee_id") and task_data["assignee_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the assigned user can submit reports")
    report_repo = TaskReportRepository(session)
    data["task_id"] = task_id
    data["reporter_id"] = user_id
    data["is_approved"] = False
    val = data.get("report_date")
    if isinstance(val, str) and val:
        data["report_date"] = date.fromisoformat(val)
    report = await report_repo.create(data)
    return _report_to_dict(report)


async def approve_task_report(
    session: AsyncSession,
    task_id: str,
    report_id: str,
    is_approved: bool,
    workspace_id: str,
    user_id: str,
    member_id: str | None = None,
) -> dict:
    from datetime import datetime, timezone
    task_data = await get_task(session, task_id, workspace_id)
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(task_data["project_id"])
    if project and project.lead_id and member_id and str(project.lead_id) != member_id:
        raise HTTPException(status_code=403, detail="Only the project lead can approve reports")
    report_repo = TaskReportRepository(session)
    report = await report_repo.find_by_id(report_id)
    if not report or str(report.task_id) != task_id:
        raise HTTPException(status_code=404, detail="Report not found")
    approved_by = user_id if is_approved else None
    approved_at = datetime.now(timezone.utc) if is_approved else None
    result = await report_repo.update_approval(report_id, is_approved, approved_by, approved_at)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_to_dict(result)


async def delete_task_report(
    session: AsyncSession,
    task_id: str,
    report_id: str,
    workspace_id: str,
    user_id: str,
) -> bool:
    await get_task(session, task_id, workspace_id)
    report_repo = TaskReportRepository(session)
    report = await report_repo.find_by_id(report_id)
    if not report or str(report.task_id) != task_id:
        raise HTTPException(status_code=404, detail="Report not found")
    await report_repo.delete(report_id)
    return True
