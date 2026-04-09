"""Task management tools — create, update, delete, assign tasks."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)


async def _create_task(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TaskRepository(session)
    resolved_project_id = tool_input.get("project_id") or project_id
    if not resolved_project_id:
        return ToolResult(success=False, error="project_id is required — create a project first")
    data = {
        "project_id": resolved_project_id,
        "title": tool_input["title"],
        "created_by": user_id,
    }
    for field in ("description", "priority", "due_date", "oppm_objective_id",
                  "assignee_id", "project_contribution", "start_date"):
        if field in tool_input:
            data[field] = tool_input[field]
    task = await repo.create(data)
    return ToolResult(
        success=True,
        result={"id": str(task.id), "title": task.title, "project_id": str(task.project_id), "status": task.status},
        updated_entities=["tasks", "projects"],
    )


async def _update_task(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TaskRepository(session)
    task_id = tool_input.get("task_id")
    if not task_id:
        return ToolResult(success=False, error="task_id required")
    updates = {k: v for k, v in tool_input.items() if k != "task_id"}
    task = await repo.update(task_id, updates)
    return ToolResult(
        success=True,
        result={"id": str(task.id), "title": task.title, "status": task.status} if task else {"updated": True},
        updated_entities=["tasks", "projects"],
    )


async def _delete_task(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TaskRepository(session)
    task_id = tool_input.get("task_id")
    if not task_id:
        return ToolResult(success=False, error="task_id required")
    deleted = await repo.delete(task_id)
    return ToolResult(success=deleted, result={"deleted": deleted}, updated_entities=["tasks", "projects"])


async def _assign_task(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Add or change a task's assignee via task_assignees table."""
    from shared.models.task import TaskAssignee
    from sqlalchemy import select

    task_id = tool_input.get("task_id")
    member_id = tool_input.get("member_id")
    if not task_id or not member_id:
        return ToolResult(success=False, error="task_id and member_id required")

    # Check if already assigned
    stmt = (
        select(TaskAssignee)
        .where(TaskAssignee.task_id == task_id, TaskAssignee.member_id == member_id)
        .limit(1)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return ToolResult(success=True, result={"status": "already_assigned"}, updated_entities=[])

    assignee = TaskAssignee(task_id=task_id, member_id=member_id)
    session.add(assignee)
    await session.flush()
    return ToolResult(success=True, result={"assigned": True}, updated_entities=["task_assignees", "tasks"])


async def _set_task_dependency(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Add a dependency between two tasks."""
    from shared.models.task import TaskDependency
    from sqlalchemy import select

    task_id = tool_input.get("task_id")
    depends_on = tool_input.get("depends_on_task_id")
    if not task_id or not depends_on:
        return ToolResult(success=False, error="task_id and depends_on_task_id required")

    if task_id == depends_on:
        return ToolResult(success=False, error="A task cannot depend on itself")

    stmt = (
        select(TaskDependency)
        .where(TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == depends_on)
        .limit(1)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return ToolResult(success=True, result={"status": "already_exists"}, updated_entities=[])

    dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on)
    session.add(dep)
    await session.flush()
    return ToolResult(success=True, result={"created": True}, updated_entities=["task_dependencies", "tasks"])


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="create_task",
    description="Create a new task under a project, optionally linked to an objective. In workspace context, pass project_id explicitly.",
    category="task",
    params=[
        ToolParam("project_id", "string", "UUID of the target project (required in workspace chat, optional in project chat)", required=False),
        ToolParam("title", "string", "Task title", required=True),
        ToolParam("description", "string", "Task description", required=False),
        ToolParam("priority", "string", "Task priority", required=False, enum=["low", "medium", "high", "critical"]),
        ToolParam("oppm_objective_id", "string", "UUID of the OPPM objective this task belongs to", required=False),
        ToolParam("assignee_id", "string", "UUID of the user to assign", required=False),
        ToolParam("due_date", "string", "Due date (YYYY-MM-DD)", required=False),
        ToolParam("project_contribution", "integer", "How much this task contributes to project progress (0-100)", required=False),
        ToolParam("start_date", "string", "Start date (YYYY-MM-DD)", required=False),
    ],
    handler=_create_task,
))

_registry.register(ToolDefinition(
    name="update_task",
    description="Update an existing task's status, progress, priority, or other fields",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the task to update", required=True),
        ToolParam("status", "string", "New status", required=False, enum=["todo", "in_progress", "completed"]),
        ToolParam("progress", "integer", "Progress percentage (0-100)", required=False),
        ToolParam("title", "string", "New title", required=False),
        ToolParam("priority", "string", "New priority", required=False, enum=["low", "medium", "high", "critical"]),
        ToolParam("description", "string", "New description", required=False),
        ToolParam("due_date", "string", "New due date (YYYY-MM-DD)", required=False),
    ],
    handler=_update_task,
))

_registry.register(ToolDefinition(
    name="delete_task",
    description="Delete a task from the project",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the task to delete", required=True),
    ],
    handler=_delete_task,
))

_registry.register(ToolDefinition(
    name="assign_task",
    description="Assign a workspace member to a task",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the task", required=True),
        ToolParam("member_id", "string", "UUID of the workspace member to assign", required=True),
    ],
    handler=_assign_task,
))

_registry.register(ToolDefinition(
    name="set_task_dependency",
    description="Add a dependency: task_id depends on (is blocked by) depends_on_task_id",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the dependent task", required=True),
        ToolParam("depends_on_task_id", "string", "UUID of the prerequisite task", required=True),
    ],
    handler=_set_task_dependency,
))
