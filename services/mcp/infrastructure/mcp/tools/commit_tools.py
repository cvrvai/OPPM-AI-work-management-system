"""MCP tools — commit data retrieval."""

import logging
from datetime import datetime, timedelta
from shared.database import get_db

logger = logging.getLogger(__name__)


def summarize_recent_commits(workspace_id: str, project_id: str, days: int = 7) -> dict:
    """Summarize recent commit activity for a project."""
    db = get_db()

    project = (
        db.table("projects")
        .select("id, title")
        .eq("id", project_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if not project.data:
        return {"error": "Project not found in this workspace"}

    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    commits = (
        db.table("commit_events")
        .select("id, commit_hash, commit_message, author_github_username, branch, created_at")
        .eq("project_id", project_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    commit_ids = [c["id"] for c in (commits.data or [])]
    analyses = {}
    if commit_ids:
        analysis_result = (
            db.table("commit_analyses")
            .select("commit_event_id, task_alignment_score, code_quality_score, summary")
            .in_("commit_event_id", commit_ids)
            .execute()
        )
        analyses = {a["commit_event_id"]: a for a in (analysis_result.data or [])}

    commit_list = []
    for c in commits.data or []:
        entry = {
            "hash": c["commit_hash"][:7],
            "message": c["commit_message"],
            "author": c["author_github_username"],
            "branch": c["branch"],
            "created_at": c["created_at"],
        }
        analysis = analyses.get(c["id"])
        if analysis:
            entry["alignment_score"] = analysis["task_alignment_score"]
            entry["quality_score"] = analysis["code_quality_score"]
            entry["ai_summary"] = analysis["summary"]
        commit_list.append(entry)

    return {
        "project": project.data[0]["title"],
        "period_days": days,
        "total_commits": len(commit_list),
        "commits": commit_list,
    }
