"""
Git integration service — accounts, repos, webhooks, commits.
"""

import hashlib
import hmac
import logging
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from domains.github.repository import (
    GitAccountRepository,
    RepoConfigRepository,
    CommitRepository,
    CommitAnalysisRepository,
)
from domains.notification.repository import AuditRepository
from domains.project.repository import ProjectRepository

logger = logging.getLogger(__name__)


# ── GitHub Accounts ──

async def list_accounts(session: AsyncSession, workspace_id: str) -> list:
    repo = GitAccountRepository(session)
    return await repo.find_workspace_accounts(workspace_id)


async def create_account(session: AsyncSession, workspace_id: str, data: dict, user_id: str):
    git_account_repo = GitAccountRepository(session)
    audit_repo = AuditRepository(session)
    payload = {
        "workspace_id": workspace_id,
        "account_name": data["account_name"],
        "github_username": data["github_username"],
        "encrypted_token": data["token"],
    }
    account = await git_account_repo.create(payload)
    await audit_repo.log(workspace_id, user_id, "create", "github_account", str(account.id))
    return account


async def delete_account(session: AsyncSession, account_id: str, workspace_id: str, user_id: str) -> bool:
    git_account_repo = GitAccountRepository(session)
    audit_repo = AuditRepository(session)
    account = await git_account_repo.find_by_id(account_id)
    if not account or str(account.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Account not found")
    await audit_repo.log(workspace_id, user_id, "delete", "github_account", account_id)
    return await git_account_repo.delete(account_id)


# ── Repo Configs ──

async def list_repos(session: AsyncSession, workspace_id: str) -> list:
    project_repo = ProjectRepository(session)
    repo_config_repo = RepoConfigRepository(session)
    projects = await project_repo.find_workspace_projects(workspace_id, limit=500)
    project_ids = [str(p.id) for p in projects]
    if not project_ids:
        return []
    all_repos = []
    for pid in project_ids:
        all_repos.extend(await repo_config_repo.find_project_repos(pid))
    return all_repos


async def create_repo(session: AsyncSession, data: dict, workspace_id: str, user_id: str):
    repo_config_repo = RepoConfigRepository(session)
    audit_repo = AuditRepository(session)
    repo = await repo_config_repo.create(data)
    await audit_repo.log(workspace_id, user_id, "create", "repo_config", str(repo.id))
    return repo


async def delete_repo(session: AsyncSession, config_id: str, workspace_id: str, user_id: str) -> bool:
    repo_config_repo = RepoConfigRepository(session)
    audit_repo = AuditRepository(session)
    await audit_repo.log(workspace_id, user_id, "delete", "repo_config", config_id)
    return await repo_config_repo.delete(config_id)


async def update_repo(session: AsyncSession, config_id: str, data: dict, workspace_id: str, user_id: str):
    repo_config_repo = RepoConfigRepository(session)
    audit_repo = AuditRepository(session)
    config = await repo_config_repo.find_by_id(config_id)
    if not config or str(config.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Repo config not found")
    # Remove None values — only update provided fields
    payload = {k: v for k, v in data.items() if v is not None}
    updated = await repo_config_repo.update(config_id, payload)
    await audit_repo.log(workspace_id, user_id, "update", "repo_config", config_id)
    return updated


# ── Webhook processing ──

async def validate_webhook(session: AsyncSession, repo_name: str, body: bytes, signature: str | None) -> dict:
    """Validate GitHub webhook and return the repo config."""
    repo_config_repo = RepoConfigRepository(session)
    config = await repo_config_repo.find_by_repo_name(repo_name)
    if not config:
        raise HTTPException(status_code=404, detail="No active repo config found")

    if signature:
        secret = config.webhook_secret if hasattr(config, 'webhook_secret') else config.get("webhook_secret", "")
        expected = "sha256=" + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    return config


async def store_commits(session: AsyncSession, commits_payload: list[dict], repo_config, branch: str) -> list:
    """Store commit events from webhook payload."""
    commit_repo = CommitRepository(session)
    config_id = str(repo_config.id) if hasattr(repo_config, 'id') else repo_config.get("id", "")
    stored = []
    for commit in commits_payload:
        commit_data = {
            "repo_config_id": config_id,
            "commit_hash": commit.get("id", "")[:12],
            "commit_message": commit.get("message", ""),
            "author_github_username": commit.get("author", {}).get("username", ""),
            "branch": branch,
            "files_changed": (
                commit.get("added", [])
                + commit.get("modified", [])
                + commit.get("removed", [])
            ),
            "additions": len(commit.get("added", [])) + len(commit.get("modified", [])),
            "deletions": len(commit.get("removed", [])),
            "pushed_at": commit.get("timestamp"),
        }
        result = await commit_repo.create(commit_data)
        stored.append(result)
    return stored


async def trigger_ai_analysis(commits: list, project_id: str) -> None:
    """Call AI service to analyze commits via HTTP."""
    import httpx
    from config import get_settings
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ai_service_url}/internal/analyze-commits",
                json={"commits": [{"id": str(c.id) if hasattr(c, 'id') else c.get("id", "")} for c in commits],
                      "project_id": project_id},
                headers={"X-Internal-API-Key": settings.internal_api_key},
            )
            response.raise_for_status()
    except Exception as e:
        logger.warning("Failed to trigger AI analysis: %s", e)


# ── Commits listing ──

async def list_commits(session: AsyncSession, workspace_id: str, project_id: str | None = None, limit: int = 20, offset: int = 0) -> list:
    project_repo = ProjectRepository(session)
    repo_config_repo = RepoConfigRepository(session)
    commit_repo = CommitRepository(session)

    if project_id:
        repos = await repo_config_repo.find_project_repos(project_id)
        repo_ids = [str(r.id) for r in repos]
    else:
        projects = await project_repo.find_workspace_projects(workspace_id, limit=500)
        project_ids = [str(p.id) for p in projects]
        repo_ids = []
        for pid in project_ids:
            repo_ids.extend(str(r.id) for r in await repo_config_repo.find_project_repos(pid))

    if not repo_ids:
        return []
    return await commit_repo.find_with_analyses(repo_ids, limit=limit, offset=offset)


async def get_developer_report(session: AsyncSession, project_id: str, days: int = 7) -> dict:
    from datetime import datetime, timezone, timedelta
    repo_config_repo = RepoConfigRepository(session)
    commit_repo = CommitRepository(session)

    repos = await repo_config_repo.find_project_repos(project_id)
    repo_ids = [str(r.id) for r in repos]
    if not repo_ids:
        return {"total_commits": 0, "developers": []}

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    events = await commit_repo.find_commits_since(repo_ids, since)

    devs: dict = {}
    for e in events:
        author = e.author_github_username if hasattr(e, 'author_github_username') else e.get("author_github_username", "")
        if author not in devs:
            devs[author] = {"commits": 0, "quality_sum": 0, "alignment_sum": 0}
        devs[author]["commits"] += 1
        analyses = e.commit_analyses if hasattr(e, 'commit_analyses') else e.get("commit_analyses", [])
        if analyses:
            first = analyses[0]
            devs[author]["quality_sum"] += (first.code_quality_score if hasattr(first, 'code_quality_score') else first.get("code_quality_score", 0))
            devs[author]["alignment_sum"] += (first.task_alignment_score if hasattr(first, 'task_alignment_score') else first.get("task_alignment_score", 0))

    developers = [
        {
            "username": k,
            "commits": v["commits"],
            "avg_quality": round(v["quality_sum"] / v["commits"]) if v["commits"] else 0,
            "avg_alignment": round(v["alignment_sum"] / v["commits"]) if v["commits"] else 0,
        }
        for k, v in devs.items()
    ]
    return {"total_commits": len(events), "developers": developers}


async def get_recent_analyses(session: AsyncSession, workspace_id: str, limit: int = 5) -> list:
    analysis_repo = CommitAnalysisRepository(session)
    return await analysis_repo.find_recent_for_workspace(workspace_id, limit)
