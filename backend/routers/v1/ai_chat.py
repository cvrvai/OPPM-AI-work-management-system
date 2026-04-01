"""AI Chat routes — workspace-scoped chat with LLM for OPPM projects."""

import logging
from fastapi import APIRouter, Depends, Path
from middleware.workspace import WorkspaceContext, get_workspace_context, require_write
from schemas.ai_chat import ChatRequest, ChatResponse, SuggestPlanRequest, SuggestPlanResponse, CommitPlanRequest
from services.ai_chat_service import chat, suggest_plan, commit_plan, weekly_summary

logger = logging.getLogger(__name__)
router = APIRouter()


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
