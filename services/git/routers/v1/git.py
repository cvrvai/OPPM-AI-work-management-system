"""Git integration routes — accounts, repos, commits, webhooks."""

import hashlib
import hmac
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write, require_admin
from schemas.git import GitAccountCreate, RepoConfigCreate
from shared.schemas.common import SuccessResponse
from shared.database import get_session, get_session_factory
from shared.models.git import RepoConfig
from services.git_service import (
    list_accounts,
    create_account,
    delete_account,
    list_repos,
    create_repo,
    delete_repo,
    list_commits,
    get_developer_report,
    get_recent_analyses,
    store_commits,
    trigger_ai_analysis,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GitHub Accounts ──

@router.get("/workspaces/{workspace_id}/github-accounts")
async def list_accounts_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_accounts(session, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/github-accounts", status_code=201)
async def create_account_route(
    data: GitAccountCreate,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await create_account(session, ws.workspace_id, data.model_dump(), ws.user.id)


@router.delete("/workspaces/{workspace_id}/github-accounts/{account_id}")
async def delete_account_route(
    account_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_account(session, account_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Repo Configs ──

@router.get("/workspaces/{workspace_id}/git/repos")
async def list_repos_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_repos(session, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/git/repos", status_code=201)
async def create_repo_route(
    data: RepoConfigCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_repo(session, data.model_dump(), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/git/repos/{config_id}")
async def delete_repo_route(
    config_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_repo(session, config_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Commits ──

@router.get("/workspaces/{workspace_id}/commits")
async def list_commits_route(
    project_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_commits(session, ws.workspace_id, project_id, limit)


@router.get("/workspaces/{workspace_id}/git/report/{project_id}")
async def developer_report_route(
    project_id: str,
    days: int = Query(7, ge=1, le=90),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_developer_report(session, project_id, days)


@router.get("/workspaces/{workspace_id}/git/recent-analyses")
async def recent_analyses_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_recent_analyses(session, ws.workspace_id)


# ── Webhook (no auth — uses HMAC signature) ──

@router.post("/git/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Receives GitHub push webhooks. Validates HMAC, accepts instantly,
    stores commits and triggers AI analysis in the background."""
    body = await request.body()
    payload = await request.json()
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    result = await session.execute(
        select(RepoConfig)
        .where(RepoConfig.repo_name == repo_full_name, RepoConfig.is_active == True)
        .limit(1)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="No active repo config found")

    # Validate HMAC signature — required; reject if header missing or invalid
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")
    if not config.webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured for this repo")
    expected = "sha256=" + hmac.new(
        config.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    # Accept instantly — GitHub won't retry on slow responses
    commits = payload.get("commits", [])
    branch = payload.get("ref", "").replace("refs/heads/", "")
    project_id = str(config.project_id)
    config_id = str(config.id)
    background_tasks.add_task(_process_push_event, commits, config_id, project_id, branch)

    return {"status": "accepted", "project_id": project_id}


async def _process_push_event(commits: list[dict], config_id: str, project_id: str, branch: str):
    """Runs after the webhook response is already sent. Creates own session."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            from repositories.git_repo import RepoConfigRepository, CommitRepository
            repo_config_repo = RepoConfigRepository(session)
            config = await repo_config_repo.find_by_id(config_id)
            if not config:
                logger.error("Config %s not found in background task", config_id)
                return
            stored = await store_commits(session, commits, config, branch)
            await session.commit()
        await trigger_ai_analysis(stored, project_id)
    except Exception as e:
        logger.error("Webhook background task failed: %s", e)
