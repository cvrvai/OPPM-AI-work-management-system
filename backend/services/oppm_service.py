"""
OPPM service — objectives, timeline entries, and costs.
"""

from fastapi import HTTPException
from repositories.oppm_repo import ObjectiveRepository, TimelineRepository, CostRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository

objective_repo = ObjectiveRepository()
timeline_repo = TimelineRepository()
cost_repo = CostRepository()
project_repo = ProjectRepository()
audit_repo = AuditRepository()


# ── Objectives ──

def get_objectives_with_tasks(project_id: str, workspace_id: str) -> list[dict]:
    _verify_project_workspace(project_id, workspace_id)
    return objective_repo.find_with_tasks(project_id)


def create_objective(project_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    _verify_project_workspace(project_id, workspace_id)
    data["project_id"] = project_id
    obj = objective_repo.create(data)
    audit_repo.log(workspace_id, user_id, "create", "oppm_objective", obj["id"], new_data=data)
    asyncio.create_task(index_objective(obj, workspace_id, project_id))
    return obj


def update_objective(objective_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    obj = objective_repo.find_by_id(objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    _verify_project_workspace(obj["project_id"], workspace_id)
    result = objective_repo.update(objective_id, data)
    audit_repo.log(workspace_id, user_id, "update", "oppm_objective", objective_id, new_data=data)
    asyncio.create_task(index_objective(result, workspace_id, obj["project_id"]))
    return result


def delete_objective(objective_id: str, workspace_id: str, user_id: str) -> bool:
    obj = objective_repo.find_by_id(objective_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    _verify_project_workspace(obj["project_id"], workspace_id)
    audit_repo.log(workspace_id, user_id, "delete", "oppm_objective", objective_id)
    asyncio.create_task(remove_entity("objective", objective_id))
    return objective_repo.delete(objective_id)


# ── Timeline ──

def get_timeline(project_id: str, workspace_id: str) -> list[dict]:
    _verify_project_workspace(project_id, workspace_id)
    return timeline_repo.find_project_timeline(project_id)


def upsert_timeline_entry(data: dict, workspace_id: str, user_id: str) -> dict:
    _verify_project_workspace(data["project_id"], workspace_id)
    entry = timeline_repo.upsert_entry(data)
    return entry


# ── Costs ──

def get_costs(project_id: str, workspace_id: str) -> dict:
    _verify_project_workspace(project_id, workspace_id)
    return cost_repo.get_cost_summary(project_id)


def create_cost(project_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    _verify_project_workspace(project_id, workspace_id)
    data["project_id"] = project_id
    cost = cost_repo.create(data)
    audit_repo.log(workspace_id, user_id, "create", "project_cost", cost["id"], new_data=data)
    asyncio.create_task(index_cost(cost, workspace_id, project_id))
    return cost


def update_cost(cost_id: str, data: dict, workspace_id: str, user_id: str) -> dict:
    cost = cost_repo.find_by_id(cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="Cost entry not found")
    _verify_project_workspace(cost["project_id"], workspace_id)
    result = cost_repo.update(cost_id, data)
    audit_repo.log(workspace_id, user_id, "update", "project_cost", cost_id, new_data=data)
    asyncio.create_task(index_cost(result, workspace_id, cost["project_id"]))
    return result


def delete_cost(cost_id: str, workspace_id: str, user_id: str) -> bool:
    cost = cost_repo.find_by_id(cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="Cost entry not found")
    _verify_project_workspace(cost["project_id"], workspace_id)
    audit_repo.log(workspace_id, user_id, "delete", "project_cost", cost_id)
    asyncio.create_task(remove_entity("cost", cost_id))
    return cost_repo.delete(cost_id)


# ── Helpers ──

def _verify_project_workspace(project_id: str, workspace_id: str):
    project = project_repo.find_by_id(project_id)
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")
