"""Waterfall routes — project phases and phase documents (workspace-scoped)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from shared.schemas.common import SuccessResponse
from domains.waterfall.schemas import PhaseUpdate, PhaseDocumentCreate, PhaseDocumentUpdate
from domains.waterfall.service import (
    list_phases,
    initialize_phases,
    update_phase,
    approve_phase,
    list_phase_documents,
    create_phase_document,
    update_phase_document,
    delete_phase_document,
)

router = APIRouter()


# ── Phases ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/phases")
async def list_phases_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    phases = await list_phases(session, project_id)
    if not phases:
        phases = await initialize_phases(session, ws.workspace_id, project_id)
    return phases


@router.put("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}")
async def update_phase_route(
    project_id: str,
    phase_id: str,
    data: PhaseUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_phase(session, phase_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))


@router.post("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}/approve")
async def approve_phase_route(
    project_id: str,
    phase_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await approve_phase(session, phase_id, ws.workspace_id, ws.user.id, ws.member_id)


# ── Phase Documents ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}/documents")
async def list_phase_documents_route(
    project_id: str,
    phase_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_phase_documents(session, phase_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}/documents", status_code=201)
async def create_phase_document_route(
    project_id: str,
    phase_id: str,
    data: PhaseDocumentCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_phase_document(session, ws.workspace_id, project_id, phase_id, ws.user.id, ws.member_id, data.model_dump(mode="json"))


@router.put("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}/documents/{doc_id}")
async def update_phase_document_route(
    project_id: str,
    phase_id: str,
    doc_id: str,
    data: PhaseDocumentUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_phase_document(session, doc_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/phases/{phase_id}/documents/{doc_id}")
async def delete_phase_document_route(
    project_id: str,
    phase_id: str,
    doc_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_phase_document(session, doc_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()
