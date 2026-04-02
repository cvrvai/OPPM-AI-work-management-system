"""
Project service — business logic for project CRUD + progress.
"""

import asyncio
from fastapi import HTTPException
from repositories.project_repo import ProjectRepository, ProjectMemberRepository
from repositories.notification_repo import AuditRepository
from services.document_indexer import index_project, remove_entity

project_repo = ProjectRepository()
project_member_repo = ProjectMemberRepository()
audit_repo = AuditRepository()


def list_projects(workspace_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    items = project_repo.find_workspace_projects(workspace_id, status=status, limit=limit, offset=offset)
    total = project_repo.count_in_workspace(workspace_id)
    return {"items": items, "total": total}


def get_project(project_id: str, workspace_id: str) -> dict:
    project = project_repo.find_by_id(project_id)
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def create_project(workspace_id: str, user_id: str, data: dict, member_id: str) -> dict:
    data["workspace_id"] = workspace_id
    project = project_repo.create(data)
    # Auto-add creator as project lead
    project_member_repo.add_member(project["id"], member_id, role="lead")
    audit_repo.log(workspace_id, user_id, "create", "project", project["id"], new_data=data)
    asyncio.create_task(index_project(project, workspace_id))
    return project


def update_project(project_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    project = get_project(project_id, workspace_id)
    result = project_repo.update(project_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    audit_repo.log(workspace_id, user_id, "update", "project", project_id, new_data=data)
    asyncio.create_task(index_project(result, workspace_id))
    return result


def delete_project(project_id: str, workspace_id: str, user_id: str) -> bool:
    get_project(project_id, workspace_id)  # verify exists + workspace
    audit_repo.log(workspace_id, user_id, "delete", "project", project_id)
    asyncio.create_task(remove_entity("project", project_id))
    return project_repo.delete(project_id)


def get_project_members(project_id: str) -> list[dict]:
    return project_member_repo.find_project_members(project_id)


def add_project_member(project_id: str, member_id: str, role: str = "contributor") -> dict:
    return project_member_repo.add_member(project_id, member_id, role)


def remove_project_member(project_id: str, member_id: str) -> bool:
    return project_member_repo.remove_member(project_id, member_id)
