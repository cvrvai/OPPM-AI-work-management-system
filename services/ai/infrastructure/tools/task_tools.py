"""Task management tools — create, update, delete, assign tasks."""

import logging
import uuid as _uuid
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)


async def _resolve_assignee_id(
    session: AsyncSession,
    val: str,
    workspace_id: str,
) -> tuple[str | None, str | None]:
    """Resolve assignee_id to a users.id UUID.

    Returns (resolved_user_id, warning_message).
    - If val is already a valid UUID → (val, None)
    - If val looks like a name/email → attempt ILIKE match on display_name, full_name, email → (user_id, None) if found
    - If name not found in workspace → (None, warning message)
    """
    # Already a valid UUID — use as-is
    try:
        _uuid.UUID(str(val))
        return val, None
    except ValueError:
        pass

    # Attempt name/email lookup
    from shared.models.workspace import WorkspaceMember
    from shared.models.user import User
    from sqlalchemy import or_, func

    name_pattern = f"%{val}%"
    row = await session.execute(
        select(WorkspaceMember.user_id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            or_(
                func.lower(WorkspaceMember.display_name).contains(val.lower()),
                func.lower(User.full_name).contains(val.lower()),
                func.lower(User.email).contains(val.lower()),
            ),
        )
        .limit(1)
    )
    match = row.scalar_one_or_none()
    if match:
        logger.info("Resolved assignee name '%s' → user_id %s", val, match)
        return str(match), None

    warning = f"Assignee '{val}' not found in workspace — task created without assignee. Invite them to the workspace first."
    logger.warning(warning)
    return None, warning


def _parse_date(value: str | None) -> date | None:
    """Parse a date string (YYYY-MM-DD) to a datetime.date object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


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
    warnings: list[str] = []
    for field in ("description", "priority", "oppm_objective_id",
                  "assignee_id", "project_contribution", "parent_task_id"):
        if field in tool_input:
            val = tool_input[field]
            if val and field == "assignee_id":
                # Graceful resolution: accept name/email or UUID
                resolved, warning = await _resolve_assignee_id(session, str(val), workspace_id)
                if warning:
                    warnings.append(warning)
                if resolved:
                    data["assignee_id"] = resolved
                # If not resolved → skip assignee_id, task still gets created
                continue
            if val and field in ("oppm_objective_id", "parent_task_id"):
                # These cannot be resolved by name — hard UUID validation
                try:
                    _uuid.UUID(str(val))
                except ValueError:
                    return ToolResult(success=False, error=f"Invalid UUID for {field}: '{val}'. Use the full UUID returned by the previous tool call.")
            data[field] = val

    # Parse date fields to datetime.date objects
    for date_field in ("due_date", "start_date"):
        if date_field in tool_input and tool_input[date_field]:
            parsed = _parse_date(tool_input[date_field])
            if parsed:
                data[date_field] = parsed
            else:
                return ToolResult(success=False, error=f"Invalid {date_field} format. Use YYYY-MM-DD.")

    task = await repo.create(data)
    result_data: dict = {
        "id": str(task.id),
        "title": task.title,
        "project_id": str(task.project_id),
        "status": task.status,
    }
    if warnings:
        result_data["warnings"] = warnings
    return ToolResult(
        success=True,
        result=result_data,
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

    # Parse date fields to datetime.date objects
    for date_field in ("due_date", "start_date"):
        if date_field in updates and isinstance(updates[date_field], str):
            parsed = _parse_date(updates[date_field])
            if parsed:
                updates[date_field] = parsed
            else:
                return ToolResult(success=False, error=f"Invalid {date_field} format. Use YYYY-MM-DD.")

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
    """Assign a workspace member to a task: writes to task_assignees AND updates tasks.assignee_id."""
    import re
    from shared.models.task import Task, TaskAssignee
    from shared.models.workspace import WorkspaceMember
    from sqlalchemy import select

    task_id   = tool_input.get("task_id")
    member_id = tool_input.get("member_id")
    if not task_id or not member_id:
        return ToolResult(success=False, error="task_id and member_id required")

    _UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if not _UUID_RE.match(task_id):
        return ToolResult(success=False, error=f"task_id is not a valid UUID: '{task_id}'. Call get_team_workload to get full member UUIDs and search_tasks for task UUIDs.")
    if not _UUID_RE.match(member_id):
        return ToolResult(success=False, error=f"member_id is not a valid UUID: '{member_id}'. Call get_team_workload to retrieve the full member_id values.")

    # Load the workspace member — need user_id to update tasks.assignee_id
    member = await session.scalar(
        select(WorkspaceMember).where(WorkspaceMember.id == member_id, WorkspaceMember.workspace_id == workspace_id).limit(1)
    )
    if member is None:
        return ToolResult(success=False, error=f"member_id '{member_id}' not found in this workspace. Call get_team_workload to get valid member_id values.")

    # Load the task
    task_filter = [Task.id == task_id]
    if project_id:
        task_filter.append(Task.project_id == project_id)
    task = await session.scalar(select(Task).where(*task_filter).limit(1))
    if task is None:
        return ToolResult(success=False, error=f"task_id '{task_id}' not found. Call search_tasks to get valid task IDs.")

    # Upsert task_assignees row
    existing = await session.scalar(
        select(TaskAssignee)
        .where(TaskAssignee.task_id == task_id, TaskAssignee.member_id == member_id)
        .limit(1)
    )
    if not existing:
        session.add(TaskAssignee(task_id=task_id, member_id=member_id))

    # Also update tasks.assignee_id (the "Owner" field shown in the UI) with the member's user_id
    task.assignee_id = member.user_id

    await session.flush()
    return ToolResult(success=True, result={"assigned": True, "owner_set_to": str(member.user_id)}, updated_entities=["task_assignees", "tasks"])


async def _set_task_dependency(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Add a dependency between two tasks."""
    from shared.models.task import Task, TaskDependency
    from sqlalchemy import select

    task_id = tool_input.get("task_id")
    depends_on = tool_input.get("depends_on_task_id")
    if not task_id or not depends_on:
        return ToolResult(success=False, error="task_id and depends_on_task_id required")

    if task_id == depends_on:
        return ToolResult(success=False, error="A task cannot depend on itself")

    # Validate both tasks exist before inserting
    for tid, label in [(task_id, "task_id"), (depends_on, "depends_on_task_id")]:
        check = await session.execute(
            select(Task.id).where(Task.id == tid).limit(1)
        )
        if check.scalar_one_or_none() is None:
            return ToolResult(
                success=False,
                error=f"Task not found: {label}={tid}. Use search_tasks to get the correct IDs.",
            )

    # Cycle detection: BFS from depends_on — if task_id is reachable, adding this edge would create a cycle
    visited: set[str] = set()
    queue: list[str] = [depends_on]
    while queue:
        current = queue.pop()
        if current == task_id:
            return ToolResult(success=False, error=f"Circular dependency detected: adding this would create a cycle between task '{task_id}' and '{depends_on}'.")
        if current in visited:
            continue
        visited.add(current)
        children = await session.execute(
            select(TaskDependency.task_id).where(TaskDependency.depends_on_task_id == current)
        )
        queue.extend(str(r) for r in children.scalars().all())

    existing = await session.scalar(
        select(TaskDependency)
        .where(TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == depends_on)
        .limit(1)
    )
    if existing:
        return ToolResult(success=True, result={"status": "already_exists"}, updated_entities=[])

    dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on)
    session.add(dep)
    await session.flush()
    return ToolResult(success=True, result={"created": True}, updated_entities=["task_dependencies", "tasks"])


async def _delete_task_dependency(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Remove a dependency edge between two tasks."""
    from shared.models.task import TaskDependency
    from sqlalchemy import select, delete

    task_id    = tool_input.get("task_id")
    depends_on = tool_input.get("depends_on_task_id")
    if not task_id or not depends_on:
        return ToolResult(success=False, error="task_id and depends_on_task_id required")

    result = await session.execute(
        delete(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on,
        )
    )
    if result.rowcount == 0:
        return ToolResult(success=False, error="Dependency not found — nothing deleted.")
    return ToolResult(success=True, result={"deleted": True}, updated_entities=["task_dependencies", "tasks"])


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
        ToolParam("assignee_id", "string", "user_id of the member to assign (NOT member_id) — call get_team_workload first and use the 'user_id' field from the result. NEVER pass a person's display name or email here. If you do not have the UUID, omit this field and use assign_task afterwards.", required=False),
        ToolParam("due_date", "string", "Due date (YYYY-MM-DD)", required=False),
        ToolParam("project_contribution", "integer", "How much this task contributes to project progress (0-100)", required=False),
        ToolParam("start_date", "string", "Start date (YYYY-MM-DD)", required=False),
        ToolParam("parent_task_id", "string", "UUID of the parent task (set this to create a sub-task under an existing task)", required=False),
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
    description="Assign a workspace member to a task. member_id must be the full UUID from workspace_members.id — call get_team_workload first to get it. Never use truncated or guessed IDs.",
    category="task",
    params=[
        ToolParam("task_id", "string", "Full UUID of the task (from search_tasks)", required=True),
        ToolParam("member_id", "string", "Full UUID from workspace_members.id (from get_team_workload)", required=True),
    ],
    handler=_assign_task,
))

_registry.register(ToolDefinition(
    name="set_task_dependency",
    description="Add a dependency: task_id depends on (is blocked by) depends_on_task_id. Cycle detection is enforced. IMPORTANT: always call search_tasks first to retrieve real task UUIDs — never guess or reuse IDs from memory.",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the dependent task (must be verified via search_tasks)", required=True),
        ToolParam("depends_on_task_id", "string", "UUID of the prerequisite task (must be verified via search_tasks)", required=True),
    ],
    handler=_set_task_dependency,
))

_registry.register(ToolDefinition(
    name="delete_task_dependency",
    description="Remove an existing dependency between two tasks. Use this to fix a backwards or incorrect dependency. Always call search_tasks first to verify task UUIDs.",
    category="task",
    params=[
        ToolParam("task_id", "string", "UUID of the dependent task (the one that was blocked)", required=True),
        ToolParam("depends_on_task_id", "string", "UUID of the prerequisite task (the blocker)", required=True),
    ],
    handler=_delete_task_dependency,
))
