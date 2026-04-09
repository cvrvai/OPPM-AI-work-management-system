"""Project management tools — create projects and list workspace projects.

These tools are available in both workspace-level and project-level chat
because projects are workspace-scoped (not project-scoped).
"""

import logging
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from repositories.project_repo import ProjectRepository
from shared.models.project import Project

logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> date | None:
    """Parse a date string (YYYY-MM-DD) to a datetime.date object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


async def _create_project(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Create a new project in the workspace."""
    title = (tool_input.get("title") or "").strip()
    if not title:
        return ToolResult(success=False, error="title is required")

    data: dict = {
        "workspace_id": workspace_id,
        "title": title,
    }
    for field in ("description", "status", "priority", "budget"):
        if field in tool_input and tool_input[field]:
            data[field] = tool_input[field]

    # Normalise legacy status value the LLM may still send
    if data.get("status") == "active":
        data["status"] = "in_progress"

    # Parse date fields to datetime.date objects
    for date_field in ("start_date", "deadline"):
        if date_field in tool_input and tool_input[date_field]:
            parsed = _parse_date(tool_input[date_field])
            if parsed:
                data[date_field] = parsed
            else:
                return ToolResult(success=False, error=f"Invalid {date_field} format. Use YYYY-MM-DD.")

    repo = ProjectRepository(session)
    project = await repo.create_project(data)

    return ToolResult(
        success=True,
        result={
            "id": str(project.id),
            "title": project.title,
            "status": project.status,
            "workspace_id": str(project.workspace_id),
        },
        updated_entities=["projects"],
    )


async def _list_workspace_projects(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """List all projects in the workspace."""
    result = await session.execute(
        select(Project.id, Project.title, Project.status, Project.priority, Project.progress)
        .where(Project.workspace_id == workspace_id)
        .order_by(Project.created_at.desc())
        .limit(50)
    )
    rows = result.all()
    projects = [
        {
            "id": str(r.id),
            "title": r.title,
            "status": r.status,
            "priority": r.priority,
            "progress": r.progress,
        }
        for r in rows
    ]
    return ToolResult(success=True, result={"projects": projects, "count": len(projects)})


async def _update_project(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Update an existing project's metadata."""
    target_id = tool_input.get("project_id") or project_id
    if not target_id:
        return ToolResult(success=False, error="project_id required")

    updates = {k: v for k, v in tool_input.items() if k != "project_id" and v is not None}
    if not updates:
        return ToolResult(success=False, error="No fields to update provided")

    # Normalise legacy status value
    if updates.get("status") == "active":
        updates["status"] = "in_progress"

    # Parse date fields to datetime.date objects
    for date_field in ("start_date", "deadline"):
        if date_field in updates and isinstance(updates[date_field], str):
            parsed = _parse_date(updates[date_field])
            if parsed:
                updates[date_field] = parsed
            else:
                return ToolResult(success=False, error=f"Invalid {date_field} format. Use YYYY-MM-DD.")

    repo = ProjectRepository(session)
    updated = await repo.update(target_id, updates)
    if not updated:
        return ToolResult(success=False, error="Project not found")

    return ToolResult(
        success=True,
        result={"id": str(updated.id), "title": updated.title, "status": updated.status},
        updated_entities=["projects"],
    )


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="create_project",
    description=(
        "Create a new project in the workspace with a title, description, and optional "
        "status, priority, budget, and timeline dates. Use this when the user asks to "
        "create a project or set up a new initiative."
    ),
    category="project",
    requires_project=False,
    params=[
        ToolParam("title", "string", "Project name/title", required=True),
        ToolParam("description", "string", "Project description or objective summary", required=False),
        ToolParam("status", "string", "Initial status", required=False,
                  enum=["planning", "in_progress", "on_hold", "completed", "cancelled"]),
        ToolParam("priority", "string", "Project priority", required=False,
                  enum=["low", "medium", "high", "critical"]),
        ToolParam("budget", "number", "Total budget in currency units", required=False),
        ToolParam("start_date", "string", "Start date (YYYY-MM-DD)", required=False),
        ToolParam("deadline", "string", "Deadline date (YYYY-MM-DD)", required=False),
    ],
    handler=_create_project,
))

_registry.register(ToolDefinition(
    name="list_workspace_projects",
    description="List all projects in the current workspace with their status and progress",
    category="project",
    requires_project=False,
    params=[],
    handler=_list_workspace_projects,
))

_registry.register(ToolDefinition(
    name="update_project",
    description=(
        "Update an existing project's title, description, status, priority, budget, "
        "start_date, or deadline. Use the current project_id if the user is in a project "
        "context, or specify project_id explicitly."
    ),
    category="project",
    requires_project=False,
    params=[
        ToolParam("project_id", "string", "UUID of the project to update (optional if already in project context)", required=False),
        ToolParam("title", "string", "New title", required=False),
        ToolParam("description", "string", "New description", required=False),
        ToolParam("status", "string", "New status", required=False,
                  enum=["planning", "active", "on_hold", "completed", "cancelled"]),
        ToolParam("priority", "string", "New priority", required=False,
                  enum=["low", "medium", "high", "critical"]),
        ToolParam("budget", "number", "New budget", required=False),
        ToolParam("start_date", "string", "New start date (YYYY-MM-DD)", required=False),
        ToolParam("deadline", "string", "New deadline (YYYY-MM-DD)", required=False),
        ToolParam("objective_summary", "string", "High-level objective statement", required=False),
    ],
    handler=_update_project,
))
