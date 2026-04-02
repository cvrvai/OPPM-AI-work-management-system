"""MCP tools — task data retrieval."""

import logging
from shared.database import get_db

logger = logging.getLogger(__name__)


def get_task_summary(workspace_id: str, project_id: str) -> dict:
    """Get a summary of tasks grouped by status for a project."""
    db = get_db()

    project = (
        db.table("projects")
        .select("id")
        .eq("id", project_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not project.data:
        return {"error": "Project not found in this workspace"}

    tasks = (
        db.table("tasks")
        .select("id, title, status, progress, priority")
        .eq("project_id", project_id)
        .execute()
    )

    all_tasks = tasks.data or []
    summary: dict[str, list[dict]] = {"todo": [], "in_progress": [], "completed": []}
    for t in all_tasks:
        status = t.get("status", "todo")
        if status in summary:
            summary[status].append({
                "id": t["id"],
                "title": t["title"],
                "progress": t["progress"],
                "priority": t.get("priority", "medium"),
            })

    return {
        "total": len(all_tasks),
        "by_status": {k: len(v) for k, v in summary.items()},
        "tasks": summary,
    }
