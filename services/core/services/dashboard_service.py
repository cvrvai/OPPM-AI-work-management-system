"""
Dashboard service — aggregated stats for a workspace.
"""

from datetime import datetime, timezone, timedelta
from repositories.project_repo import ProjectRepository
from repositories.task_repo import TaskRepository
from repositories.git_repo import CommitRepository, CommitAnalysisRepository, RepoConfigRepository
from shared.database import get_db

project_repo = ProjectRepository()
task_repo = TaskRepository()
commit_repo = CommitRepository()
analysis_repo = CommitAnalysisRepository()
repo_config_repo = RepoConfigRepository()


def get_dashboard_stats(workspace_id: str) -> dict:
    db = get_db()

    projects = project_repo.find_all_in_workspace(workspace_id, limit=1000)
    project_ids = [p["id"] for p in projects]

    # Count tasks across workspace projects
    total_tasks = 0
    completed_tasks = 0
    for pid in project_ids:
        tasks = task_repo.find_project_tasks(pid, limit=1000)
        total_tasks += len(tasks)
        completed_tasks += sum(1 for t in tasks if t["status"] == "completed")

    # Commits today
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    repo_ids = []
    for pid in project_ids:
        repo_ids.extend(r["id"] for r in repo_config_repo.find_project_repos(pid))

    commits_today = 0
    if repo_ids:
        commits = commit_repo.find_commits_since(repo_ids, since)
        commits_today = len(commits)

    # AI analysis averages
    analyses = analysis_repo.find_recent(limit=100)
    avg_quality = 0
    avg_alignment = 0
    if analyses:
        avg_quality = sum(a.get("code_quality_score", 0) for a in analyses) / len(analyses)
        avg_alignment = sum(a.get("task_alignment_score", 0) for a in analyses) / len(analyses)

    active = sum(1 for p in projects if p["status"] in ("in_progress", "planning"))

    project_progress = [
        {
            "project_id": p["id"],
            "title": p["title"],
            "progress": p.get("progress", 0),
            "status": p.get("status", "planning"),
        }
        for p in projects
    ]

    return {
        "total_projects": len(projects),
        "active_projects": active,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_commits_today": commits_today,
        "avg_quality_score": round(avg_quality),
        "avg_alignment_score": round(avg_alignment),
        "project_progress": project_progress,
    }
