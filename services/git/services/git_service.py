"""
Git integration service — accounts, repos, webhooks, commits.
"""

import hashlib
import hmac
import logging
from fastapi import HTTPException
from repositories.git_repo import (
    GitAccountRepository,
    RepoConfigRepository,
    CommitRepository,
    CommitAnalysisRepository,
)
from repositories.notification_repo import AuditRepository
from repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)

git_account_repo = GitAccountRepository()
repo_config_repo = RepoConfigRepository()
commit_repo = CommitRepository()
analysis_repo = CommitAnalysisRepository()
audit_repo = AuditRepository()
project_repo = ProjectRepository()


# ── GitHub Accounts ──

def list_accounts(workspace_id: str) -> list[dict]:
    return git_account_repo.find_workspace_accounts(workspace_id)


def create_account(workspace_id: str, data: dict, user_id: str) -> dict:
    payload = {
        "workspace_id": workspace_id,
        "account_name": data["account_name"],
        "github_username": data["github_username"],
        "encrypted_token": data["token"],
    }
    account = git_account_repo.create(payload)
    audit_repo.log(workspace_id, user_id, "create", "github_account", account["id"])
    return account


def delete_account(account_id: str, workspace_id: str, user_id: str) -> bool:
    account = git_account_repo.find_by_id(account_id)
    if not account or account.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Account not found")
    audit_repo.log(workspace_id, user_id, "delete", "github_account", account_id)
    return git_account_repo.delete(account_id)


# ── Repo Configs ──

def list_repos(workspace_id: str) -> list[dict]:
    projects = project_repo.find_workspace_projects(workspace_id, limit=500)
    project_ids = [p["id"] for p in projects]
    if not project_ids:
        return []
    all_repos = []
    for pid in project_ids:
        all_repos.extend(repo_config_repo.find_project_repos(pid))
    return all_repos


def create_repo(data: dict, workspace_id: str, user_id: str) -> dict:
    repo = repo_config_repo.create(data)
    audit_repo.log(workspace_id, user_id, "create", "repo_config", repo["id"])
    return repo


def delete_repo(config_id: str, workspace_id: str, user_id: str) -> bool:
    audit_repo.log(workspace_id, user_id, "delete", "repo_config", config_id)
    return repo_config_repo.delete(config_id)


# ── Webhook processing ──

def validate_webhook(repo_name: str, body: bytes, signature: str | None) -> dict:
    """Validate GitHub webhook and return the repo config."""
    config = repo_config_repo.find_by_repo_name(repo_name)
    if not config:
        raise HTTPException(status_code=404, detail="No active repo config found")

    if signature:
        expected = "sha256=" + hmac.new(
            config["webhook_secret"].encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    return config


def store_commits(commits_payload: list[dict], repo_config: dict, branch: str) -> list[dict]:
    """Store commit events from webhook payload."""
    stored = []
    for commit in commits_payload:
        commit_data = {
            "repo_config_id": repo_config["id"],
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
        result = commit_repo.create(commit_data)
        stored.append(result)
    return stored


async def trigger_ai_analysis(commits: list[dict], project_id: str) -> None:
    """Call AI service to analyze commits via HTTP."""
    import httpx
    from config import get_settings
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ai_service_url}/internal/analyze-commits",
                json={"commits": commits, "project_id": project_id},
                headers={"X-Internal-API-Key": settings.internal_api_key},
            )
            response.raise_for_status()
    except Exception as e:
        logger.warning("Failed to trigger AI analysis: %s", e)


# ── Commits listing ──

def list_commits(workspace_id: str, project_id: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    if project_id:
        repos = repo_config_repo.find_project_repos(project_id)
        repo_ids = [r["id"] for r in repos]
    else:
        projects = project_repo.find_workspace_projects(workspace_id, limit=500)
        project_ids = [p["id"] for p in projects]
        repo_ids = []
        for pid in project_ids:
            repo_ids.extend(r["id"] for r in repo_config_repo.find_project_repos(pid))

    if not repo_ids:
        return []
    return commit_repo.find_with_analyses(repo_ids, limit=limit, offset=offset)


def get_developer_report(project_id: str, days: int = 7) -> dict:
    from datetime import datetime, timezone, timedelta
    repos = repo_config_repo.find_project_repos(project_id)
    repo_ids = [r["id"] for r in repos]
    if not repo_ids:
        return {"total_commits": 0, "developers": []}

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    events = commit_repo.find_commits_since(repo_ids, since)

    devs: dict = {}
    for e in events:
        author = e["author_github_username"]
        if author not in devs:
            devs[author] = {"commits": 0, "quality_sum": 0, "alignment_sum": 0}
        devs[author]["commits"] += 1
        analyses = e.get("commit_analyses", [])
        if analyses:
            devs[author]["quality_sum"] += analyses[0].get("code_quality_score", 0)
            devs[author]["alignment_sum"] += analyses[0].get("task_alignment_score", 0)

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


def get_recent_analyses(workspace_id: str, limit: int = 5) -> list[dict]:
    return analysis_repo.find_recent_for_workspace(workspace_id, limit)
