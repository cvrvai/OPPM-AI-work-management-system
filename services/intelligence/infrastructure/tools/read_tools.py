"""Read-only query tools — let the AI fetch data on-demand when context is insufficient."""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from repositories.project_repo import ProjectRepository
from repositories.task_repo import TaskRepository
from repositories.oppm_repo import (
    ObjectiveRepository, CostRepository, RiskRepository,
    DeliverableRepository, ForecastRepository, TaskDetailRepository,
)
from shared.models.task import Task, TaskReport
from shared.models.workspace import WorkspaceMember
from shared.models.user import User

logger = logging.getLogger(__name__)


async def _get_project_summary(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ProjectRepository(session)
    project = await repo.find_by_id(project_id)
    if not project:
        return ToolResult(success=False, error="Project not found")
    data = {c.name: getattr(project, c.name) for c in project.__table__.columns}
    # Convert non-serializable types
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
        elif hasattr(v, "hex"):
            data[k] = str(v)
    return ToolResult(success=True, result=data)


async def _get_task_details(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Get full details for a single task including assignees, owners, deps, reports."""
    task_id = tool_input.get("task_id")
    if not task_id:
        return ToolResult(success=False, error="task_id required")

    repo = TaskRepository(session)
    task = await repo.find_by_id(task_id)
    if not task:
        return ToolResult(success=False, error="Task not found")

    data = {c.name: getattr(task, c.name) for c in task.__table__.columns}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
        elif hasattr(v, "hex"):
            data[k] = str(v)

    # Load assignees
    detail_repo = TaskDetailRepository(session)
    assignees = await detail_repo.find_assignees(str(task.project_id))
    data["assignees"] = assignees.get(str(task_id), [])

    # Load owners
    owners = await detail_repo.find_owners(str(task.project_id))
    data["owners"] = owners.get(str(task_id), [])

    # Load dependencies
    deps = await detail_repo.find_dependencies(str(task.project_id))
    data["depends_on"] = deps.get(str(task_id), [])

    # Load recent reports (last 5)
    reports_stmt = (
        select(TaskReport)
        .where(TaskReport.task_id == task_id)
        .order_by(TaskReport.report_date.desc())
        .limit(5)
    )
    reports_result = await session.execute(reports_stmt)
    data["recent_reports"] = [
        {
            "date": str(r.report_date),
            "hours": r.hours,
            "description": r.description[:200] if r.description else "",
            "approved": r.is_approved,
        }
        for r in reports_result.scalars().all()
    ]

    return ToolResult(success=True, result=data)


async def _search_tasks(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Search/filter tasks by status, priority, or keyword."""
    stmt = select(Task).where(Task.project_id == project_id)

    if tool_input.get("status"):
        stmt = stmt.where(Task.status == tool_input["status"])
    if tool_input.get("priority"):
        stmt = stmt.where(Task.priority == tool_input["priority"])
    if tool_input.get("objective_id"):
        stmt = stmt.where(Task.oppm_objective_id == tool_input["objective_id"])
    if tool_input.get("keyword"):
        kw = f"%{tool_input['keyword']}%"
        stmt = stmt.where(Task.title.ilike(kw) | Task.description.ilike(kw))

    stmt = stmt.order_by(Task.created_at.desc()).limit(20)
    result = await session.execute(stmt)
    tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "progress": t.progress,
            "due_date": str(t.due_date) if t.due_date else None,
            "objective_id": str(t.oppm_objective_id) if t.oppm_objective_id else None,
        }
        for t in result.scalars().all()
    ]
    return ToolResult(success=True, result={"tasks": tasks, "count": len(tasks)})


async def _get_risk_status(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = RiskRepository(session)
    risks = await repo.find_by_project(project_id)
    red = [r for r in risks if r["rag"] == "red"]
    amber = [r for r in risks if r["rag"] == "amber"]
    green = [r for r in risks if r["rag"] == "green"]
    return ToolResult(success=True, result={
        "risks": risks,
        "total": len(risks),
        "red": len(red),
        "amber": len(amber),
        "green": len(green),
    })


async def _get_cost_breakdown(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = CostRepository(session)
    summary = await repo.get_cost_summary(project_id)
    breakdown = await repo.get_cost_breakdown(project_id)
    return ToolResult(success=True, result={
        "total_planned": summary["total_planned"],
        "total_actual": summary["total_actual"],
        "variance": summary["variance"],
        "categories": breakdown,
    })


async def _get_team_workload(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Get all workspace members with their full IDs and task counts for this project."""
    from shared.models.task import TaskAssignee

    # Fetch all workspace members with their user email as fallback display name
    members_result = await session.execute(
        select(WorkspaceMember, User.email, User.full_name)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.role)
    )
    all_members = members_result.all()

    # Count tasks assigned per member (via task_assignees) for this project
    counts_result = await session.execute(
        select(
            TaskAssignee.member_id,
            func.count(Task.id).label("task_count"),
        )
        .join(Task, Task.id == TaskAssignee.task_id)
        .where(Task.project_id == project_id)
        .group_by(TaskAssignee.member_id)
    )
    counts = {str(row.member_id): row.task_count for row in counts_result.all()}

    members = [
        {
            "member_id": str(m.id),   # workspace_members.id — use for assign_task
            "user_id": str(m.user_id),  # users.id — use for create_task assignee_id
            "display_name": m.display_name or full_name or email or "(no name)",
            "email": email,
            "role": m.role,
            "task_count_in_project": counts.get(str(m.id), 0),
        }
        for m, email, full_name in all_members
    ]
    return ToolResult(success=True, result={"members": members, "total": len(members)})


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="get_project_summary",
    description="Get full project metadata including status, progress, dates, budget",
    category="read",
    params=[],
    handler=_get_project_summary,
))

_registry.register(ToolDefinition(
    name="get_task_details",
    description="Get comprehensive details for a single task including assignees, owners, dependencies, and recent reports",
    category="read",
    params=[
        ToolParam("task_id", "string", "UUID of the task to inspect", required=True),
    ],
    handler=_get_task_details,
))

_registry.register(ToolDefinition(
    name="search_tasks",
    description="Search or filter tasks by status, priority, objective, or keyword",
    category="read",
    params=[
        ToolParam("status", "string", "Filter by status", required=False, enum=["todo", "in_progress", "completed"]),
        ToolParam("priority", "string", "Filter by priority", required=False, enum=["low", "medium", "high", "critical"]),
        ToolParam("objective_id", "string", "Filter by OPPM objective UUID", required=False),
        ToolParam("keyword", "string", "Search in title and description", required=False),
    ],
    handler=_search_tasks,
))

_registry.register(ToolDefinition(
    name="get_risk_status",
    description="Get all risks with their RAG (Red/Amber/Green) assessment and counts",
    category="read",
    params=[],
    handler=_get_risk_status,
))

_registry.register(ToolDefinition(
    name="get_cost_breakdown",
    description="Get detailed cost breakdown by category with planned vs actual amounts",
    category="read",
    params=[],
    handler=_get_cost_breakdown,
))

_registry.register(ToolDefinition(
    name="get_team_workload",
    description="Get all workspace members with their full member_id UUIDs, roles, and task counts. Always call this before assign_task to retrieve the correct member_id.",
    category="read",
    params=[],
    handler=_get_team_workload,
))
