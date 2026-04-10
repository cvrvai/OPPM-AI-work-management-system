"""
Waterfall service — business logic for project phases and phase documents.
"""

import logging
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.waterfall_repo import ProjectPhaseRepository, PhaseDocumentRepository
from repositories.notification_repo import AuditRepository

logger = logging.getLogger(__name__)


def _parse_dates(data: dict) -> dict:
    """Convert ISO date strings to datetime.date for asyncpg compatibility."""
    for field in ("start_date", "end_date"):
        val = data.get(field)
        if isinstance(val, str) and val:
            try:
                data[field] = date.fromisoformat(val)
            except ValueError:
                pass
    return data


# ── Phases ──

async def list_phases(session: AsyncSession, project_id: str) -> list:
    repo = ProjectPhaseRepository(session)
    return await repo.find_project_phases(project_id)


async def initialize_phases(session: AsyncSession, workspace_id: str, project_id: str) -> list:
    """Create the 6 standard waterfall phases if none exist yet."""
    repo = ProjectPhaseRepository(session)
    existing = await repo.find_project_phases(project_id)
    if existing:
        return existing
    return await repo.initialize_phases(workspace_id, project_id)


async def update_phase(session: AsyncSession, phase_id: str, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = ProjectPhaseRepository(session)
    audit = AuditRepository(session)
    phase = await repo.find_by_id(phase_id)
    if not phase or str(phase.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    _parse_dates(data)
    result = await repo.update(phase_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Phase not found")
    await audit.log(workspace_id, user_id, "update", "project_phase", phase_id, new_data=data)
    return result


async def approve_phase(session: AsyncSession, phase_id: str, workspace_id: str, user_id: str, member_id: str) -> dict:
    repo = ProjectPhaseRepository(session)
    audit = AuditRepository(session)
    phase = await repo.find_by_id(phase_id)
    if not phase or str(phase.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    if phase.status not in ("in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Phase must be in_progress or completed before approval")

    # Enforce sequential gate: previous phases must be approved
    all_phases = await repo.find_project_phases(str(phase.project_id))
    for p in all_phases:
        if p.position < phase.position and p.status != "approved":
            raise HTTPException(
                status_code=400,
                detail=f"Previous phase '{p.phase_type}' must be approved first",
            )

    result = await repo.update(phase_id, {
        "status": "approved",
        "gate_approved_by": member_id,
        "gate_approved_at": datetime.utcnow(),
    })
    await audit.log(workspace_id, user_id, "approve", "project_phase", phase_id)
    return result


# ── Phase Documents ──

async def list_phase_documents(session: AsyncSession, phase_id: str, workspace_id: str) -> dict:
    phase_repo = ProjectPhaseRepository(session)
    phase = await phase_repo.find_by_id(phase_id)
    if not phase or str(phase.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    doc_repo = PhaseDocumentRepository(session)
    items = await doc_repo.find_phase_documents(phase_id)
    return {"items": items, "total": len(items)}


async def create_phase_document(
    session: AsyncSession,
    workspace_id: str,
    project_id: str,
    phase_id: str,
    user_id: str,
    member_id: str,
    data: dict,
) -> dict:
    phase_repo = ProjectPhaseRepository(session)
    phase = await phase_repo.find_by_id(phase_id)
    if not phase or str(phase.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    doc_repo = PhaseDocumentRepository(session)
    audit = AuditRepository(session)
    data["workspace_id"] = workspace_id
    data["project_id"] = project_id
    data["phase_id"] = phase_id
    data["created_by"] = member_id
    doc = await doc_repo.create(data)
    await audit.log(workspace_id, user_id, "create", "phase_document", str(doc.id))
    return doc


async def update_phase_document(
    session: AsyncSession,
    doc_id: str,
    workspace_id: str,
    user_id: str,
    data: dict,
) -> dict:
    doc_repo = PhaseDocumentRepository(session)
    audit = AuditRepository(session)
    doc = await doc_repo.find_by_id(doc_id)
    if not doc or str(doc.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    # Auto-increment version on content update
    if "content" in data and data["content"] is not None:
        data["version"] = doc.version + 1
    result = await doc_repo.update(doc_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    await audit.log(workspace_id, user_id, "update", "phase_document", doc_id)
    return result


async def delete_phase_document(session: AsyncSession, doc_id: str, workspace_id: str, user_id: str) -> bool:
    doc_repo = PhaseDocumentRepository(session)
    audit = AuditRepository(session)
    doc = await doc_repo.find_by_id(doc_id)
    if not doc or str(doc.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    await audit.log(workspace_id, user_id, "delete", "phase_document", doc_id)
    return await doc_repo.delete(doc_id)
