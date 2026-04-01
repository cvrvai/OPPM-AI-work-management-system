import hashlib
import hmac
from fastapi import APIRouter, HTTPException, Request, Header
from database import get_db
from schemas import GitAccountCreate, RepoConfigCreate
from config import get_settings

router = APIRouter()


# ── GitHub Accounts ──

@router.get("/github-accounts")
async def list_github_accounts():
    db = get_db()
    result = (
        db.table("github_accounts")
        .select("id, account_name, github_username, created_at")
        .execute()
    )
    return result.data


@router.post("/github-accounts")
async def create_github_account(data: GitAccountCreate):
    db = get_db()
    result = db.table("github_accounts").insert({
        "account_name": data.account_name,
        "github_username": data.github_username,
        "encrypted_token": data.token,  # In production, encrypt this
    }).execute()
    return result.data[0]


@router.delete("/github-accounts/{account_id}")
async def delete_github_account(account_id: str):
    db = get_db()
    db.table("github_accounts").delete().eq("id", account_id).execute()
    return {"ok": True}


# ── Repo Configurations ──

@router.get("/git/repo-map")
async def list_repo_configs():
    db = get_db()
    result = db.table("repo_configs").select("*").execute()
    return result.data


@router.post("/git/repo-map")
async def create_repo_config(data: RepoConfigCreate):
    db = get_db()
    result = db.table("repo_configs").insert(data.model_dump()).execute()
    return result.data[0]


@router.delete("/git/repo-map/{config_id}")
async def delete_repo_config(config_id: str):
    db = get_db()
    db.table("repo_configs").delete().eq("id", config_id).execute()
    return {"ok": True}


# ── GitHub Webhook Handler ──

@router.post("/git/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    """
    Receives GitHub push webhooks.
    1. Validates HMAC signature
    2. Extracts commit data
    3. Stores commit events
    4. Triggers AI analysis (async)
    """
    body = await request.body()

    # 1. Find matching repo config and validate signature
    payload = await request.json()
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    db = get_db()
    repo_config = (
        db.table("repo_configs")
        .select("*")
        .eq("repo_name", repo_full_name)
        .eq("is_active", True)
        .single()
        .execute()
    )

    if not repo_config.data:
        raise HTTPException(status_code=404, detail="No active repo config found")

    config = repo_config.data

    # Validate HMAC signature
    if x_hub_signature_256:
        expected = "sha256=" + hmac.new(
            config["webhook_secret"].encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Only process push events
    if x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    # 3. Extract and store commits
    commits = payload.get("commits", [])
    branch = payload.get("ref", "").replace("refs/heads/", "")
    stored_commits = []

    for commit in commits:
        commit_data = {
            "repo_config_id": config["id"],
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
        result = db.table("commit_events").insert(commit_data).execute()
        if result.data:
            stored_commits.append(result.data[0])

    # 4. Trigger AI analysis for each commit
    from services.ai_analyzer import analyze_commits
    await analyze_commits(stored_commits, config["project_id"])

    return {
        "status": "processed",
        "commits_stored": len(stored_commits),
        "project_id": config["project_id"],
    }


# ── Commit Events ──

@router.get("/commits")
async def list_commits(project_id: str | None = None, limit: int = 20):
    db = get_db()
    query = db.table("commit_events").select(
        "*, commit_analyses(*)"
    )
    if project_id:
        query = query.eq(
            "repo_config_id",
            db.table("repo_configs")
            .select("id")
            .eq("project_id", project_id)
            .single()
            .execute()
            .data["id"],
        )
    result = query.order("pushed_at", desc=True).limit(limit).execute()

    # Flatten analysis into the commit object
    commits = []
    for c in result.data or []:
        analyses = c.pop("commit_analyses", [])
        c["analysis"] = analyses[0] if analyses else None
        commits.append(c)
    return commits


@router.get("/git/report/{project_id}")
async def get_developer_report(project_id: str, days: int = 7):
    db = get_db()
    # Get repo config for this project
    repo = (
        db.table("repo_configs")
        .select("id")
        .eq("project_id", project_id)
        .execute()
    )
    repo_ids = [r["id"] for r in repo.data or []]
    if not repo_ids:
        return {"total_commits": 0, "developers": [], "report": "No repos linked"}

    events = (
        db.table("commit_events")
        .select("*, commit_analyses(*)")
        .in_("repo_config_id", repo_ids)
        .order("pushed_at", desc=True)
        .execute()
    )

    # Group by developer
    devs: dict = {}
    for e in events.data or []:
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

    return {
        "total_commits": len(events.data or []),
        "developers": developers,
    }
