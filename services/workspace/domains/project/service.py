"""Project service — business logic for project CRUD + progress."""

import logging
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from domains.project.repository import ProjectRepository, ProjectMemberRepository
from domains.notification.repository import AuditRepository
from domains.workspace.repository import WorkspaceMemberRepository

logger = logging.getLogger(__name__)


def _parse_dates(data: dict) -> dict:
    """Convert ISO date strings to datetime.date for asyncpg compatibility."""
    for field in ("start_date", "deadline", "end_date"):
        val = data.get(field)
        if val in (None, ""):
            continue
        if isinstance(val, date):
            continue
        if isinstance(val, str):
            try:
                data[field] = date.fromisoformat(val)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=f"{field} must be a valid ISO date") from error
            continue
        raise HTTPException(status_code=400, detail=f"{field} must be a valid ISO date")
    return data


def _validate_project_dates(existing: object | None = None, updates: dict | None = None) -> None:
    updates = updates or {}
    start_date = updates.get("start_date") if "start_date" in updates else getattr(existing, "start_date", None)
    deadline = updates.get("deadline") if "deadline" in updates else getattr(existing, "deadline", None)
    end_date = updates.get("end_date") if "end_date" in updates else getattr(existing, "end_date", None)

    if start_date and deadline and start_date > deadline:
        raise HTTPException(status_code=400, detail="Start date must be on or before deadline")
    if deadline and end_date and deadline > end_date:
        raise HTTPException(status_code=400, detail="Deadline must be on or before end date")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")


async def _require_workspace_member(
    session: AsyncSession,
    workspace_id: str,
    member_id: str,
    detail: str,
) -> str:
    member_repo = WorkspaceMemberRepository(session)
    member = await member_repo.find_by_id(member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=400, detail=detail)
    return str(member.id)


def _audit_safe(data: dict) -> dict:
    """Return a copy of data safe for JSON (converts date objects to ISO strings)."""
    out = {}
    for k, v in data.items():
        out[k] = v.isoformat() if isinstance(v, date) else v
    return out


async def list_projects(session: AsyncSession, workspace_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    project_repo = ProjectRepository(session)
    items = await project_repo.find_workspace_projects(workspace_id, status=status, limit=limit, offset=offset)
    total = await project_repo.count_in_workspace(workspace_id)
    return {"items": items, "total": total}


async def get_project(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _sync_oppm_all_member(
    session: AsyncSession,
    project_id: str,
    workspace_member_id: str,
    is_leader: bool,
) -> None:
    """Ensure an oppm_project_all_members row exists for this workspace member.

    TaskOwner.member_id FKs to oppm_project_all_members.id, so without this
    bridge row a workspace member cannot be assigned A/B/C priority on tasks.
    Also enforces a single is_leader=True per project.
    """
    from domains.oppm.repository import ProjectAllMemberRepository
    from shared.models.oppm import OPPMProjectAllMember

    repo = ProjectAllMemberRepository(session)
    existing_stmt = (
        select(OPPMProjectAllMember)
        .where(
            OPPMProjectAllMember.project_id == project_id,
            OPPMProjectAllMember.workspace_member_id == workspace_member_id,
        )
        .limit(1)
    )
    result = await session.execute(existing_stmt)
    existing = result.scalar_one_or_none()

    if is_leader:
        # Demote any current leader before promoting this one.
        await session.execute(
            update(OPPMProjectAllMember)
            .where(
                OPPMProjectAllMember.project_id == project_id,
                OPPMProjectAllMember.is_leader.is_(True),
            )
            .values(is_leader=False)
        )

    if existing is None:
        await repo.add_workspace_member(
            project_id=project_id,
            workspace_member_id=workspace_member_id,
            display_order=0 if is_leader else 1,
            is_leader=is_leader,
        )
    elif existing.is_leader != is_leader:
        existing.is_leader = is_leader
        await session.flush()


async def create_project(session: AsyncSession, workspace_id: str, user_id: str, data: dict, member_id: str) -> dict:
    project_repo = ProjectRepository(session)
    project_member_repo = ProjectMemberRepository(session)
    audit_repo = AuditRepository(session)

    data["workspace_id"] = workspace_id
    _parse_dates(data)
    _validate_project_dates(updates=data)
    lead_member_id = await _require_workspace_member(
        session,
        workspace_id,
        data.get("lead_id") or member_id,
        "Lead must be a workspace member",
    )
    data["lead_id"] = lead_member_id

    project = await project_repo.create(data)

    await project_member_repo.add_member(str(project.id), lead_member_id, role="lead")
    await _sync_oppm_all_member(session, str(project.id), lead_member_id, is_leader=True)
    if lead_member_id != member_id:
        await project_member_repo.add_member(str(project.id), member_id, role="contributor")
        await _sync_oppm_all_member(session, str(project.id), member_id, is_leader=False)

    await audit_repo.log(workspace_id, user_id, "create", "project", str(project.id), new_data=_audit_safe(data))
    return project


async def update_project(session: AsyncSession, project_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    project = await get_project(session, project_id, workspace_id)
    _parse_dates(data)
    if data.get("lead_id") is not None:
        data["lead_id"] = await _require_workspace_member(
            session,
            workspace_id,
            data["lead_id"],
            "Lead must be a workspace member",
        )
    _validate_project_dates(existing=project, updates=data)

    result = await project_repo.update(project_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    await audit_repo.log(workspace_id, user_id, "update", "project", project_id, new_data=_audit_safe(data))
    return result


async def delete_project(session: AsyncSession, project_id: str, workspace_id: str, user_id: str) -> bool:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    await get_project(session, project_id, workspace_id)
    await audit_repo.log(workspace_id, user_id, "delete", "project", project_id)
    return await project_repo.delete(project_id)


async def get_project_members(session: AsyncSession, project_id: str) -> list[dict]:
    project_member_repo = ProjectMemberRepository(session)
    return await project_member_repo.find_project_members(project_id)


async def add_project_member(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    member_id: str,
    role: str = "contributor",
) -> dict:
    project_repo = ProjectRepository(session)
    project_member_repo = ProjectMemberRepository(session)

    await get_project(session, project_id, workspace_id)
    member_id = await _require_workspace_member(
        session,
        workspace_id,
        member_id,
        "Project member must belong to this workspace",
    )

    existing_member = await project_member_repo.find_project_member(project_id, member_id)
    if existing_member:
        return existing_member

    if role == "lead":
        existing_lead = await project_member_repo.find_lead_member(project_id)
        if existing_lead and str(existing_lead.member_id) != member_id:
            raise HTTPException(status_code=400, detail="Project already has a lead")

    project_member = await project_member_repo.add_member(project_id, member_id, role)
    await _sync_oppm_all_member(session, project_id, member_id, is_leader=(role == "lead"))
    if role == "lead":
        await project_repo.update(project_id, {"lead_id": member_id})
    return project_member


async def remove_project_member(session: AsyncSession, project_id: str, member_id: str) -> bool:
    project_member_repo = ProjectMemberRepository(session)
    return await project_member_repo.remove_member(project_id, member_id)
