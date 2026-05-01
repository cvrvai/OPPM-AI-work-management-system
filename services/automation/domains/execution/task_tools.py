"""MCP tools — task data retrieval."""

import logging
from sqlalchemy import select
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.task import Task

logger = logging.getLogger(__name__)


async def get_task_summary(workspace_id: str, project_id: str) -> dict:
    """Get a summary of tasks grouped by status for a project."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Project)
            .where(Project.id == project_id, Project.workspace_id == workspace_id)
            .limit(1)
        )
        if not result.scalar_one_or_none():
            return {"error": "Project not found in this workspace"}

        tasks_result = await session.execute(
            select(Task).where(Task.project_id == project_id)
        )
        all_tasks = list(tasks_result.scalars().all())

        summary: dict[str, list[dict]] = {"todo": [], "in_progress": [], "completed": []}
        for t in all_tasks:
            status = t.status or "todo"
            if status in summary:
                summary[status].append({
                    "id": str(t.id),
                    "title": t.title,
                    "progress": t.progress,
                    "priority": t.priority or "medium",
                })

        return {
            "total": len(all_tasks),
            "by_status": {k: len(v) for k, v in summary.items()},
            "tasks": summary,
        }
