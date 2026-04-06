"""
OPPM service — objectives, timeline, costs, sub-objectives, task-owners, deliverables, forecasts, risks.
"""

import logging
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.oppm_repo import (
    ObjectiveRepository, TimelineRepository, CostRepository,
    SubObjectiveRepository, TaskOwnerRepository,
    DeliverableRepository, ForecastRepository, RiskRepository,
    _row_to_dict,
)
from repositories.project_repo import ProjectRepository
from repositories.workspace_repo import WorkspaceMemberRepository
from repositories.notification_repo import AuditRepository

logger = logging.getLogger(__name__)


# ── Combined OPPM Data ──

async def get_oppm_data(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    """Return all OPPM data for a project in a single payload."""
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    obj_repo = ObjectiveRepository(session)
    tl_repo = TimelineRepository(session)
    cost_repo = CostRepository(session)
    sub_obj_repo = SubObjectiveRepository(session)
    deliv_repo = DeliverableRepository(session)
    forecast_repo = ForecastRepository(session)
    risk_repo = RiskRepository(session)
    ws_member_repo = WorkspaceMemberRepository(session)

    objectives = await obj_repo.find_with_tasks(project_id)
    timeline_entries = await tl_repo.find_project_timeline(project_id)
    cost_summary = await cost_repo.get_cost_summary(project_id)
    sub_objectives = await sub_obj_repo.find_project_sub_objectives(project_id)
    deliverables = await deliv_repo.find_project_deliverables(project_id)
    forecasts = await forecast_repo.find_project_forecasts(project_id)
    risks = await risk_repo.find_project_risks(project_id)
    ws_members = await ws_member_repo.find_members(workspace_id)

    # Compute weeks
    start_date = _parse_date(project.start_date)
    deadline = _parse_date(project.deadline)
    weeks = _compute_weeks(start_date, deadline)

    # Compute overall progress from timeline
    total_cells = 0
    done_cells = 0
    for entry in timeline_entries:
        total_cells += 1
        if entry.status == "completed":
            done_cells += 1
    progress = round((done_cells / total_cells) * 100) if total_cells else 0

    # Resolve lead name
    lead_name = "—"
    if project.lead_id:
        for m in ws_members:
            if str(m.get("id")) == str(project.lead_id):
                lead_name = m.get("display_name") or m.get("email", "—").split("@")[0]
                break

    return {
        "project": {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "project_code": getattr(project, "project_code", None),
            "objective_summary": getattr(project, "objective_summary", None),
            "deliverable_output": getattr(project, "deliverable_output", None),
            "start_date": str(project.start_date) if project.start_date else None,
            "deadline": str(project.deadline) if project.deadline else None,
            "end_date": str(project.end_date) if project.end_date else None,
            "status": project.status,
            "progress": progress,
            "budget": float(project.budget) if project.budget else 0,
            "planning_hours": float(project.planning_hours) if getattr(project, "planning_hours", None) else 0,
            "lead_id": str(project.lead_id) if project.lead_id else None,
            "lead_name": lead_name,
        },
        "objectives": objectives,
        "sub_objectives": [_row_to_dict(so) for so in sub_objectives],
        "members": ws_members,
        "timeline": [_row_to_dict(e) for e in timeline_entries],
        "weeks": weeks,
        "costs": cost_summary,
        "deliverables": [_row_to_dict(d) for d in deliverables],
        "forecasts": [_row_to_dict(f) for f in forecasts],
        "risks": [_row_to_dict(r) for r in risks],
    }


def _parse_date(val: object) -> date | None:
    """Parse a date value from ORM (date, str, or None)."""
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val[:10])
        except (ValueError, IndexError):
            return None
    return None


def _compute_weeks(start: date | None, end: date | None, max_weeks: int = 20) -> list[dict]:
    """Compute week entries from start to end date."""
    if not start:
        start = date.today()
    if not end:
        end = start + timedelta(weeks=12)

    start_monday = start - timedelta(days=start.weekday())
    weeks: list[dict] = []
    current = start_monday
    while current <= end + timedelta(days=6) and len(weeks) < max_weeks:
        weeks.append({
            "label": f"{current.month}/{current.day}",
            "start": current.isoformat(),
        })
        current += timedelta(weeks=1)
    return weeks


# ── Objectives ──

async def get_objectives_with_tasks(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    objective_repo = ObjectiveRepository(session)
    return await objective_repo.find_with_tasks(project_id)


async def create_objective(session: AsyncSession, project_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    objective_repo = ObjectiveRepository(session)
    audit_repo = AuditRepository(session)

    data["project_id"] = project_id
    obj = await objective_repo.create(data)
    await audit_repo.log(workspace_id, user_id, "create", "oppm_objective", str(obj.id), new_data=data)
    return obj


async def update_objective(session: AsyncSession, objective_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    objective_repo = ObjectiveRepository(session)
    audit_repo = AuditRepository(session)

    obj = await objective_repo.find_by_id(objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    result = await objective_repo.update(objective_id, data)
    await audit_repo.log(workspace_id, user_id, "update", "oppm_objective", objective_id, new_data=data)
    return result


async def delete_objective(session: AsyncSession, objective_id: str, workspace_id: str, user_id: str) -> bool:
    objective_repo = ObjectiveRepository(session)
    audit_repo = AuditRepository(session)

    obj = await objective_repo.find_by_id(objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    await audit_repo.log(workspace_id, user_id, "delete", "oppm_objective", objective_id)
    return await objective_repo.delete(objective_id)


# ── Sub-Objectives ──

async def get_sub_objectives(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = SubObjectiveRepository(session)
    items = await repo.find_project_sub_objectives(project_id)
    return [_row_to_dict(i) for i in items]


async def create_sub_objective(session: AsyncSession, project_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = SubObjectiveRepository(session)
    data["project_id"] = project_id
    obj = await repo.create(data)
    return _row_to_dict(obj)


async def update_sub_objective(session: AsyncSession, sub_obj_id: str, data: dict, workspace_id: str) -> dict:
    repo = SubObjectiveRepository(session)
    obj = await repo.find_by_id(sub_obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Sub-objective not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    result = await repo.update(sub_obj_id, data)
    return _row_to_dict(result)


async def delete_sub_objective(session: AsyncSession, sub_obj_id: str, workspace_id: str) -> bool:
    repo = SubObjectiveRepository(session)
    obj = await repo.find_by_id(sub_obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Sub-objective not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    return await repo.delete(sub_obj_id)


async def set_task_sub_objectives(session: AsyncSession, project_id: str, task_id: str, sub_objective_ids: list[str], workspace_id: str) -> list[str]:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = SubObjectiveRepository(session)
    return await repo.set_task_sub_objectives(task_id, sub_objective_ids)


# ── Task Owners ──

async def set_task_owner(session: AsyncSession, project_id: str, task_id: str, member_id: str, priority: str, workspace_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = TaskOwnerRepository(session)
    return await repo.set_owner(task_id, member_id, priority)


async def remove_task_owner(session: AsyncSession, project_id: str, task_id: str, member_id: str, workspace_id: str) -> bool:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = TaskOwnerRepository(session)
    return await repo.remove_owner(task_id, member_id)


# ── Timeline ──

async def get_timeline(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    timeline_repo = TimelineRepository(session)
    return await timeline_repo.find_project_timeline(project_id)


async def upsert_timeline_entry(session: AsyncSession, data: dict, workspace_id: str, user_id: str) -> dict:
    await _verify_project_workspace(session, data["project_id"], workspace_id)
    timeline_repo = TimelineRepository(session)
    return await timeline_repo.upsert_entry(data)


# ── Costs ──

async def get_costs(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    cost_repo = CostRepository(session)
    return await cost_repo.get_cost_summary(project_id)


async def create_cost(session: AsyncSession, project_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    cost_repo = CostRepository(session)
    audit_repo = AuditRepository(session)

    data["project_id"] = project_id
    cost = await cost_repo.create(data)
    await audit_repo.log(workspace_id, user_id, "create", "project_cost", str(cost.id), new_data=data)
    return cost


async def update_cost(session: AsyncSession, cost_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    cost_repo = CostRepository(session)
    audit_repo = AuditRepository(session)

    cost = await cost_repo.find_by_id(cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="Cost entry not found")
    await _verify_project_workspace(session, str(cost.project_id), workspace_id)
    result = await cost_repo.update(cost_id, data)
    await audit_repo.log(workspace_id, user_id, "update", "project_cost", cost_id, new_data=data)
    return result


async def delete_cost(session: AsyncSession, cost_id: str, workspace_id: str, user_id: str) -> bool:
    cost_repo = CostRepository(session)
    audit_repo = AuditRepository(session)

    cost = await cost_repo.find_by_id(cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="Cost entry not found")
    await _verify_project_workspace(session, str(cost.project_id), workspace_id)
    await audit_repo.log(workspace_id, user_id, "delete", "project_cost", cost_id)
    return await cost_repo.delete(cost_id)


# ── Deliverables ──

async def get_deliverables(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = DeliverableRepository(session)
    items = await repo.find_project_deliverables(project_id)
    return [_row_to_dict(i) for i in items]


async def create_deliverable(session: AsyncSession, project_id: str, data: dict, workspace_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = DeliverableRepository(session)
    data["project_id"] = project_id
    obj = await repo.create(data)
    return _row_to_dict(obj)


async def update_deliverable(session: AsyncSession, item_id: str, data: dict, workspace_id: str) -> dict:
    repo = DeliverableRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    result = await repo.update(item_id, data)
    return _row_to_dict(result)


async def delete_deliverable(session: AsyncSession, item_id: str, workspace_id: str) -> bool:
    repo = DeliverableRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    return await repo.delete(item_id)


# ── Forecasts ──

async def get_forecasts(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = ForecastRepository(session)
    items = await repo.find_project_forecasts(project_id)
    return [_row_to_dict(i) for i in items]


async def create_forecast(session: AsyncSession, project_id: str, data: dict, workspace_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = ForecastRepository(session)
    data["project_id"] = project_id
    obj = await repo.create(data)
    return _row_to_dict(obj)


async def update_forecast(session: AsyncSession, item_id: str, data: dict, workspace_id: str) -> dict:
    repo = ForecastRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Forecast not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    result = await repo.update(item_id, data)
    return _row_to_dict(result)


async def delete_forecast(session: AsyncSession, item_id: str, workspace_id: str) -> bool:
    repo = ForecastRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Forecast not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    return await repo.delete(item_id)


# ── Risks ──

async def get_risks(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict]:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = RiskRepository(session)
    items = await repo.find_project_risks(project_id)
    return [_row_to_dict(i) for i in items]


async def create_risk(session: AsyncSession, project_id: str, data: dict, workspace_id: str) -> dict:
    await _verify_project_workspace(session, project_id, workspace_id)
    repo = RiskRepository(session)
    data["project_id"] = project_id
    obj = await repo.create(data)
    return _row_to_dict(obj)


async def update_risk(session: AsyncSession, item_id: str, data: dict, workspace_id: str) -> dict:
    repo = RiskRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Risk not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    result = await repo.update(item_id, data)
    return _row_to_dict(result)


async def delete_risk(session: AsyncSession, item_id: str, workspace_id: str) -> bool:
    repo = RiskRepository(session)
    obj = await repo.find_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Risk not found")
    await _verify_project_workspace(session, str(obj.project_id), workspace_id)
    return await repo.delete(item_id)


# ── Helpers ──

async def _verify_project_workspace(session: AsyncSession, project_id: str, workspace_id: str):
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
