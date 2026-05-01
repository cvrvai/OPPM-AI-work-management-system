"""OPPM objective and timeline tools — migrated from oppm_tool_executor."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from domains.analysis.oppm_repository import ObjectiveRepository, TimelineRepository

logger = logging.getLogger(__name__)


async def _create_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    resolved_project_id = tool_input.get("project_id") or project_id
    if not resolved_project_id:
        return ToolResult(success=False, error="project_id is required — create a project first")
    data = {
        "project_id": resolved_project_id,
        "title": tool_input["title"],
        "sort_order": tool_input.get("sort_order", 999),
    }
    if tool_input.get("owner_id"):
        data["owner_id"] = tool_input["owner_id"]
    obj = await repo.create(data)
    return ToolResult(
        success=True,
        result={"id": str(obj.id), "title": obj.title, "project_id": str(obj.project_id), "sort_order": obj.sort_order},
        updated_entities=["oppm_objectives"],
    )


async def _update_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    obj_id = tool_input.get("objective_id")
    if not obj_id:
        return ToolResult(success=False, error="objective_id required")
    updates = {k: v for k, v in tool_input.items() if k != "objective_id"}
    obj = await repo.update(obj_id, updates)
    return ToolResult(
        success=True,
        result={"id": str(obj.id), "title": obj.title} if obj else {"updated": True},
        updated_entities=["oppm_objectives"],
    )


async def _delete_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    obj_id = tool_input.get("objective_id")
    if not obj_id:
        return ToolResult(success=False, error="objective_id required")
    deleted = await repo.delete(obj_id)
    return ToolResult(success=deleted, result={"deleted": deleted}, updated_entities=["oppm_objectives"])


async def _set_timeline_status(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TimelineRepository(session)
    entry_data = {
        "project_id": project_id,
        "task_id": tool_input["task_id"],
        "week_start": tool_input["week_start"],
        "status": tool_input["status"],
    }
    if tool_input.get("notes"):
        entry_data["notes"] = tool_input["notes"]
    entry = await repo.upsert_entry(entry_data)
    return ToolResult(
        success=True,
        result={"id": str(entry.id), "status": entry.status} if entry else {"updated": True},
        updated_entities=["oppm_timeline_entries"],
    )


async def _bulk_set_timeline(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TimelineRepository(session)
    results = []
    for entry in tool_input.get("entries", []):
        entry_data = {
            "project_id": project_id,
            "task_id": entry["task_id"],
            "week_start": entry["week_start"],
            "status": entry["status"],
        }
        if entry.get("notes"):
            entry_data["notes"] = entry["notes"]
        results.append(await repo.upsert_entry(entry_data))
    return ToolResult(
        success=True,
        result={"count": len(results)},
        updated_entities=["oppm_timeline_entries"],
    )


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="create_objective",
    description="Create a new OPPM objective for a project. In workspace context, pass the project_id returned by create_project.",
    category="oppm",
    params=[
        ToolParam("title", "string", "Objective title", required=True),
        ToolParam("project_id", "string", "UUID of the target project (required in workspace chat, optional in project chat)", required=False),
        ToolParam("sort_order", "integer", "Display order (1-based)", required=False),
        ToolParam("owner_id", "string", "UUID of the workspace member who owns this objective", required=False),
    ],
    handler=_create_objective,
))

_registry.register(ToolDefinition(
    name="update_objective",
    description="Update an existing OPPM objective's title or sort order",
    category="oppm",
    params=[
        ToolParam("objective_id", "string", "UUID of the objective to update", required=True),
        ToolParam("title", "string", "New title", required=False),
        ToolParam("sort_order", "integer", "New display order", required=False),
    ],
    handler=_update_objective,
))

_registry.register(ToolDefinition(
    name="delete_objective",
    description="Delete an OPPM objective and its associated data",
    category="oppm",
    params=[
        ToolParam("objective_id", "string", "UUID of the objective to delete", required=True),
    ],
    handler=_delete_objective,
))

_registry.register(ToolDefinition(
    name="set_timeline_status",
    description="Set the timeline status for a task in a specific week",
    category="oppm",
    params=[
        ToolParam("task_id", "string", "UUID of the task", required=True),
        ToolParam("week_start", "string", "Week start date (YYYY-MM-DD)", required=True),
        ToolParam("status", "string", "Timeline status", required=True, enum=["planned", "in_progress", "completed", "at_risk", "blocked"]),
        ToolParam("notes", "string", "Optional notes for this timeline entry", required=False),
    ],
    handler=_set_timeline_status,
))

_registry.register(ToolDefinition(
    name="bulk_set_timeline",
    description="Set timeline status for multiple tasks/weeks at once (more efficient than individual calls)",
    category="oppm",
    params=[
        ToolParam("entries", "array", "Array of {task_id, week_start, status, notes?} objects", required=True),
    ],
    handler=_bulk_set_timeline,
))
