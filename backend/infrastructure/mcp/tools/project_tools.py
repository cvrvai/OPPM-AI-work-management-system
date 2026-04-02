"""MCP tools — project data retrieval."""

import logging

from database import get_db

logger = logging.getLogger(__name__)


def get_project_status(workspace_id: str, project_id: str) -> dict:
    """Get the current status and progress of a project."""
    db = get_db()
    result = (
        db.table("projects")
        .select("id, title, description, status, progress, start_date, deadline")
        .eq("id", project_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": "Project not found"}
    return result.data[0]


def list_projects(workspace_id: str) -> list[dict]:
    """List all projects in the workspace with basic status info."""
    db = get_db()
    result = (
        db.table("projects")
        .select("id, title, status, progress, start_date, deadline")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
