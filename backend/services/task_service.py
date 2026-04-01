"""
Task service — CRUD + weighted project progress recalculation.
"""

from fastapi import HTTPException
from repositories.task_repo import TaskRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository

task_repo = TaskRepository()
project_repo = ProjectRepository()
audit_repo = AuditRepository()


def _recalculate_project_progress(project_id: str):
    """Recalculate weighted project progress from all tasks."""
    tasks = task_repo.get_project_progress_data(project_id)
    if not tasks:
        project_repo.update_progress(project_id, 0)
        return
    total_weight = sum(t["project_contribution"] for t in tasks)
    if total_weight > 0:
        weighted = sum(t["progress"] * t["project_contribution"] / total_weight for t in tasks)
        project_repo.update_progress(project_id, round(weighted))


def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    if project_id:
        return task_repo.find_project_tasks(project_id, status=status, limit=limit, offset=offset)
    filters = {}
    if status:
        filters["status"] = status
    return task_repo.find_all(filters=filters or None, limit=limit, offset=offset)


def get_task(task_id: str) -> dict:
    task = task_repo.find_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def create_task(data: dict, workspace_id: str, user_id: str) -> dict:
    # Verify project belongs to workspace
    project = project_repo.find_by_id(data["project_id"])
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
    data["created_by"] = user_id
    task = task_repo.create(data)
    _recalculate_project_progress(task["project_id"])
    audit_repo.log(workspace_id, user_id, "create", "task", task["id"], new_data=data)
    asyncio.create_task(index_task(task, workspace_id))
    return task


def update_task(task_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    task = get_task(task_id)
    # Verify workspace
    project = project_repo.find_by_id(task["project_id"])
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=403, detail="Task not in this workspace")
    result = task_repo.update(task_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    _recalculate_project_progress(result["project_id"])
    audit_repo.log(workspace_id, user_id, "update", "task", task_id, new_data=data)
    asyncio.create_task(index_task(result, workspace_id))
    return result


def delete_task(task_id: str, workspace_id: str, user_id: str) -> bool:
    task = get_task(task_id)
    project = project_repo.find_by_id(task["project_id"])
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=403, detail="Task not in this workspace")
    project_id = task["project_id"]
    audit_repo.log(workspace_id, user_id, "delete", "task", task_id)
    asyncio.create_task(remove_entity("task", task_id))
    task_repo.delete(task_id)
    _recalculate_project_progress(project_id)
    return True
