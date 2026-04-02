"""Git integration routes — accounts, repos, commits, webhooks."""

import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
from shared.auth import WorkspaceContext, get_workspace_context, require_write, require_admin
from schemas.git import GitAccountCreate, RepoConfigCreate
from shared.schemas.common import SuccessResponse
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
from shared.database import get_db

router = APIRouter()


# ── GitHub Accounts ──

@router.get("/workspaces/{workspace_id}/github-accounts")
async def list_accounts_route(ws: WorkspaceContext = Depends(get_workspace_context)):
    return list_accounts(ws.workspace_id)


@router.post("/workspaces/{workspace_id}/github-accounts", status_code=201)
async def create_account_route(data: GitAccountCreate, ws: WorkspaceContext = Depends(require_admin)):
    return create_account(ws.workspace_id, data.model_dump(), ws.user.id)


@router.delete("/workspaces/{workspace_id}/github-accounts/{account_id}")
async def delete_account_route(account_id: str, ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    delete_account(account_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Repo Configs ──

@router.get("/workspaces/{workspace_id}/git/repos")
async def list_repos_route(ws: WorkspaceContext = Depends(get_workspace_context)):
    return list_repos(ws.workspace_id)


@router.post("/workspaces/{workspace_id}/git/repos", status_code=201)
async def create_repo_route(data: RepoConfigCreate, ws: WorkspaceContext = Depends(require_write)):
    return create_repo(data.model_dump(), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/git/repos/{config_id}")
async def delete_repo_route(config_id: str, ws: WorkspaceContext = Depends(require_write)) -> SuccessResponse:
    delete_repo(config_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Commits ──

@router.get("/workspaces/{workspace_id}/commits")
async def list_commits_route(
    project_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    return list_commits(ws.workspace_id, project_id, limit)


@router.get("/workspaces/{workspace_id}/git/report/{project_id}")
async def developer_report_route(project_id: str, days: int = Query(7, ge=1, le=90), ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_developer_report(project_id, days)


@router.get("/workspaces/{workspace_id}/git/recent-analyses")
async def recent_analyses_route(ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_recent_analyses(ws.workspace_id)


# ── Webhook (no auth — uses HMAC signature) ──

@router.post("/git/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    """Receives GitHub push webhooks. Validates HMAC, stores commits, triggers AI analysis."""
    body = await request.body()
    payload = await request.json()
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    db = get_db()
    repo_config = (
        db.table("repo_configs")
        .select("*")
        .eq("repo_name", repo_full_name)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not repo_config.data:
        raise HTTPException(status_code=404, detail="No active repo config found")

    config = repo_config.data[0]

    # Validate HMAC signature — required; reject if header missing or invalid
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")
    if not config.get("webhook_secret"):
        raise HTTPException(status_code=500, detail="Webhook secret not configured for this repo")
    expected = "sha256=" + hmac.new(
        config["webhook_secret"].encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    # Store commits
    commits = payload.get("commits", [])
    branch = payload.get("ref", "").replace("refs/heads/", "")
    stored = store_commits(commits, config, branch)

    # Trigger AI analysis via HTTP to AI service (fire-and-forget, non-blocking)
    import asyncio
    asyncio.create_task(trigger_ai_analysis(stored, config["project_id"]))

    return {"status": "processed", "commits_stored": len(stored), "project_id": config["project_id"]}
