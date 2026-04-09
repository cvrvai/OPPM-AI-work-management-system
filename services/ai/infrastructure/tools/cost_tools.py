"""Cost and risk management tools."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from repositories.oppm_repo import CostRepository, RiskRepository

logger = logging.getLogger(__name__)


async def _update_project_costs(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = CostRepository(session)
    data = {"project_id": project_id}
    for field in ("category", "description", "planned_amount", "actual_amount", "period"):
        if field in tool_input:
            data[field] = tool_input[field]
    cost = await repo.create(data)
    return ToolResult(success=True, result={"id": str(cost.id), "category": cost.category}, updated_entities=["project_costs"])


async def _create_risk(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = RiskRepository(session)
    data = {
        "project_id": project_id,
        "item_number": tool_input.get("item_number", 1),
        "description": tool_input["description"],
        "rag": tool_input.get("rag", "amber"),
    }
    risk = await repo.create(data)
    return ToolResult(success=True, result={"id": str(risk.id), "description": risk.description, "rag": risk.rag}, updated_entities=["oppm_risks"])


async def _update_risk(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = RiskRepository(session)
    risk_id = tool_input.get("risk_id")
    if not risk_id:
        return ToolResult(success=False, error="risk_id required")
    updates = {k: v for k, v in tool_input.items() if k != "risk_id"}
    risk = await repo.update(risk_id, updates)
    return ToolResult(success=True, result={"id": risk_id, "updated": True}, updated_entities=["oppm_risks"])


async def _create_deliverable(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    from repositories.oppm_repo import DeliverableRepository
    repo = DeliverableRepository(session)
    data = {
        "project_id": project_id,
        "item_number": tool_input.get("item_number", 1),
        "description": tool_input["description"],
    }
    deliv = await repo.create(data)
    return ToolResult(success=True, result={"id": str(deliv.id), "description": deliv.description}, updated_entities=["oppm_deliverables"])


async def _update_project(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    from repositories.project_repo import ProjectRepository
    repo = ProjectRepository(session)
    updates = {k: v for k, v in tool_input.items() if k in (
        "status", "priority", "title", "description", "start_date",
        "deadline", "end_date", "budget", "planning_hours",
        "objective_summary", "deliverable_output",
    )}
    if not updates:
        return ToolResult(success=False, error="No valid fields to update")
    result = await repo.update(project_id, updates)
    return ToolResult(success=True, result=result, updated_entities=["projects"])


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="update_project_costs",
    description="Add a cost entry (planned and/or actual) for a project category",
    category="cost",
    params=[
        ToolParam("category", "string", "Cost category (e.g. 'Personnel', 'Infrastructure', 'Software')", required=True),
        ToolParam("planned_amount", "number", "Planned cost amount", required=False),
        ToolParam("actual_amount", "number", "Actual cost amount", required=False),
        ToolParam("description", "string", "Description of the cost item", required=False),
        ToolParam("period", "string", "Time period (e.g. 'Q1 2026')", required=False),
    ],
    handler=_update_project_costs,
))

_registry.register(ToolDefinition(
    name="create_risk",
    description="Add a risk item to the project with a RAG (Red/Amber/Green) assessment",
    category="cost",
    params=[
        ToolParam("description", "string", "Risk description", required=True),
        ToolParam("rag", "string", "Risk assessment level", required=False, enum=["green", "amber", "red"]),
        ToolParam("item_number", "integer", "Risk item number", required=False),
    ],
    handler=_create_risk,
))

_registry.register(ToolDefinition(
    name="update_risk",
    description="Update an existing risk's description or RAG status",
    category="cost",
    params=[
        ToolParam("risk_id", "string", "UUID of the risk to update", required=True),
        ToolParam("description", "string", "New description", required=False),
        ToolParam("rag", "string", "New RAG status", required=False, enum=["green", "amber", "red"]),
    ],
    handler=_update_risk,
))

_registry.register(ToolDefinition(
    name="create_deliverable",
    description="Add a deliverable item to the project",
    category="cost",
    params=[
        ToolParam("description", "string", "Deliverable description", required=True),
        ToolParam("item_number", "integer", "Deliverable item number", required=False),
    ],
    handler=_create_deliverable,
))

_registry.register(ToolDefinition(
    name="update_project_metadata",
    description="Update project metadata such as status, priority, dates, or budget (project-scoped)",
    category="cost",
    params=[
        ToolParam("status", "string", "Project status", required=False, enum=["planning", "in_progress", "completed", "on_hold", "cancelled"]),
        ToolParam("priority", "string", "Project priority", required=False, enum=["low", "medium", "high", "critical"]),
        ToolParam("title", "string", "Project title", required=False),
        ToolParam("description", "string", "Project description", required=False),
        ToolParam("start_date", "string", "Start date (YYYY-MM-DD)", required=False),
        ToolParam("deadline", "string", "Deadline (YYYY-MM-DD)", required=False),
        ToolParam("budget", "number", "Project budget", required=False),
    ],
    handler=_update_project,
))
