"""AI Chat routes — workspace-scoped chat with LLM for OPPM projects."""

import logging
from fastapi import APIRouter, Depends, Path, BackgroundTasks
from middleware.workspace import WorkspaceContext, get_workspace_context, require_write, require_admin
from schemas.ai_chat import (
    ChatRequest, ChatResponse, SuggestPlanRequest, SuggestPlanResponse,
    CommitPlanRequest, CapabilitiesResponse, ReindexResponse,
)
from services.ai_chat_service import chat, suggest_plan, commit_plan, weekly_summary, workspace_chat
from services.document_indexer import reindex_workspace
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)
router = APIRouter()
vector_repo = VectorRepository()


# ── Workspace-level chat (no project_id) ──

@router.post("/workspaces/{workspace_id}/ai/chat", response_model=ChatResponse)
async def workspace_chat_route(
    data: ChatRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Workspace-level AI chat — cross-project questions, no tool execution."""
    return workspace_chat(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        messages=[m.model_dump() for m in data.messages],
        model_id=data.model_id,
    )


@router.get("/workspaces/{workspace_id}/ai/chat/capabilities", response_model=CapabilitiesResponse)
async def capabilities_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Return AI capabilities for the current context."""
    count = vector_repo.count_by_workspace(ws.workspace_id)
    return CapabilitiesResponse(
        has_project=False,
        can_execute_tools=False,
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


# ── Project-scoped chat ──


@router.post("/workspaces/{workspace_id}/projects/{project_id}/ai/chat", response_model=ChatResponse)
async def chat_route(
    project_id: str,
    data: ChatRequest,
    ws: WorkspaceContext = Depends(require_write),
):
    """Send a message to the project AI assistant."""
    return chat(
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
):
    """Ask AI to generate an OPPM plan from a description."""
    return suggest_plan(
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
):
    """Commit a previously suggested AI plan — creates objectives and timeline entries."""
    return commit_plan(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        commit_token=data.commit_token,
    )


@router.get("/workspaces/{workspace_id}/projects/{project_id}/ai/weekly-summary")
async def weekly_summary_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Generate an AI weekly status summary for the project."""
    return weekly_summary(
        project_id=project_id,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
    )
