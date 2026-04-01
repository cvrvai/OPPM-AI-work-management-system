from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from database import get_db

router = APIRouter()


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    db = get_db()

    projects = db.table("projects").select("id, status, progress").execute()
    tasks = db.table("tasks").select("id, status").execute()
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    commits_today = (
        db.table("commit_events")
        .select("id", count="exact")
        .gte("pushed_at", since)
        .execute()
    )
    analyses = (
        db.table("commit_analyses")
        .select("code_quality_score, task_alignment_score")
        .execute()
    )

    proj_list = projects.data or []
    task_list = tasks.data or []
    analysis_list = analyses.data or []

    active = sum(1 for p in proj_list if p["status"] in ("in_progress", "planning"))
    completed_tasks = sum(1 for t in task_list if t["status"] == "completed")

    avg_quality = (
        sum(a["code_quality_score"] for a in analysis_list) / len(analysis_list)
        if analysis_list
        else 0
    )
    avg_alignment = (
        sum(a["task_alignment_score"] for a in analysis_list) / len(analysis_list)
        if analysis_list
        else 0
    )

    return {
        "total_projects": len(proj_list),
        "active_projects": active,
        "total_tasks": len(task_list),
        "completed_tasks": completed_tasks,
        "total_commits_today": commits_today.count or 0,
        "avg_quality_score": round(avg_quality),
        "avg_alignment_score": round(avg_alignment),
    }
