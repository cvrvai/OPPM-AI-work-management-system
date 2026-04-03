"""
OPPM service — objectives, timeline entries, and costs.
"""

import logging
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.oppm_repo import ObjectiveRepository, TimelineRepository, CostRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository

logger = logging.getLogger(__name__)


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


# ── Helpers ──

async def _verify_project_workspace(session: AsyncSession, project_id: str, workspace_id: str):
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
