"""MCP tools — project data retrieval."""

import logging
from sqlalchemy import select
from shared.database import get_session_factory
from shared.models.project import Project

logger = logging.getLogger(__name__)


async def get_project_status(workspace_id: str, project_id: str) -> dict:
    """Get the current status and progress of a project."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Project)
            .where(Project.id == project_id, Project.workspace_id == workspace_id)
            .limit(1)
        )
        p = result.scalar_one_or_none()
        if not p:
            return {"error": "Project not found"}
        return {
            "id": str(p.id), "title": p.title, "description": p.description,
            "status": p.status, "progress": p.progress,
            "start_date": str(p.start_date) if p.start_date else None,
            "deadline": str(p.deadline) if p.deadline else None,
        }


async def list_projects(workspace_id: str) -> list[dict]:
    """List all projects in the workspace with basic status info."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        return [
            {
                "id": str(p.id), "title": p.title, "status": p.status,
                "progress": p.progress,
                "start_date": str(p.start_date) if p.start_date else None,
                "deadline": str(p.deadline) if p.deadline else None,
            }
            for p in projects
        ]
