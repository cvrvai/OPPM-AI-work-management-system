"""AI Chat routes — workspace-scoped chat with LLM for OPPM projects."""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write, require_admin
from shared.database import get_session
from schemas.ai_chat import (
    ChatRequest, ChatResponse, SuggestPlanRequest, SuggestPlanResponse,
    CommitPlanRequest, CapabilitiesResponse, ReindexResponse, FeedbackRequest,
    FileParseResponse,
)
from services.ai_chat_service import chat, suggest_plan, commit_plan, weekly_summary, workspace_chat
from services.document_indexer import reindex_workspace
from repositories.vector_repo import VectorRepository
from repositories.notification_repo import AuditRepository
from shared.database import get_session
from infrastructure.file_parser import parse_file, MAX_FILE_BYTES

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Workspace-level chat (no project_id) ──

@router.post("/workspaces/{workspace_id}/ai/chat", response_model=ChatResponse)
async def workspace_chat_route(
    data: ChatRequest,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Workspace-level AI chat — cross-project questions with workspace-scoped tool execution."""
    return await workspace_chat(
        session=session,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        messages=[m.model_dump() for m in data.messages],
        model_id=data.model_id,
    )


@router.get("/workspaces/{workspace_id}/ai/chat/capabilities", response_model=CapabilitiesResponse)
async def capabilities_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Return AI capabilities for the current context."""
    vector_repo = VectorRepository(session)
    count = await vector_repo.count_by_workspace(ws.workspace_id)
    return CapabilitiesResponse(
        has_project=False,
        can_execute_tools=ws.can_write,
        indexed_documents=count,
    )


# ── Reindex ──

@router.post("/workspaces/{workspace_id}/ai/reindex", response_model=ReindexResponse)
async def reindex_route(
    ws: WorkspaceContext = Depends(require_admin),
):
    """Re-index all workspace data for RAG. Requires admin role."""
    result = await reindex_workspace(ws.workspace_id)
    return ReindexResponse(total_indexed=result["total_indexed"])


# ── File parsing ──

@router.post("/workspaces/{workspace_id}/ai/parse-file", response_model=FileParseResponse)
async def parse_file_route(
    file: UploadFile,
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Extract text from an uploaded binary file (xlsx, pdf, docx, csv)."""
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (10 MB limit)")
    result = parse_file(file.filename or "unknown", content)
    return FileParseResponse(
        filename=file.filename or "unknown",
        content_type=file.content_type or "",
        extracted_text=result.text,
        truncated=result.truncated,
        error=result.error,
    )


# ── Project-scoped chat ──

@router.post("/workspaces/{workspace_id}/projects/{project_id}/ai/chat", response_model=ChatResponse)
async def chat_route(
    project_id: str,
    data: ChatRequest,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Send a message to the project AI assistant."""
    return await chat(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        messages=[m.model_dump() for m in data.messages],
        model_id=data.model_id,
    )


@router.post("/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan", response_model=SuggestPlanResponse)
async def suggest_plan_route(
    project_id: str,
    data: SuggestPlanRequest,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Ask AI to generate an OPPM plan from a description."""
    return await suggest_plan(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        description=data.description,
    )


@router.post("/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan/commit")
async def commit_plan_route(
    project_id: str,
    data: CommitPlanRequest,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Commit a previously suggested AI plan — creates objectives and timeline entries."""
    return await commit_plan(
        session=session,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        commit_token=data.commit_token,
    )


@router.get("/workspaces/{workspace_id}/projects/{project_id}/ai/weekly-summary")
async def weekly_summary_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Generate an AI weekly status summary for the project."""
    return await weekly_summary(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
    )


# ── User feedback (thumbs up/down) ──

@router.post("/workspaces/{workspace_id}/projects/{project_id}/ai/feedback", status_code=201)
async def project_feedback_route(
    project_id: str,
    data: FeedbackRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Record a thumbs-up or thumbs-down rating on an AI response."""
    audit_repo = AuditRepository(session)
    await audit_repo.log(
        ws.workspace_id,
        ws.user.id,
        "ai_feedback",
        "project_chat",
        new_data={
            "project_id": project_id,
            "rating": data.rating,
            "user_message": data.user_message[:500] if data.user_message else "",
            "ai_message": data.message_content[:500] if data.message_content else "",
            "comment": data.comment,
            "model_id": data.model_id,
        },
    )
    return {"ok": True}


@router.post("/workspaces/{workspace_id}/ai/feedback", status_code=201)
async def workspace_feedback_route(
    data: FeedbackRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Record a thumbs-up or thumbs-down rating on a workspace-level AI response."""
    audit_repo = AuditRepository(session)
    await audit_repo.log(
        ws.workspace_id,
        ws.user.id,
        "ai_feedback",
        "workspace_chat",
        new_data={
            "rating": data.rating,
            "user_message": data.user_message[:500] if data.user_message else "",
            "ai_message": data.message_content[:500] if data.message_content else "",
            "comment": data.comment,
            "model_id": data.model_id,
        },
    )
    return {"ok": True}
