"""
Dashboard service — aggregated stats for a workspace.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from domains.project.repository import ProjectRepository
from domains.task.repository import TaskRepository
from domains.dashboard.git_repository import CommitRepository, CommitAnalysisRepository, RepoConfigRepository


async def get_dashboard_stats(session: AsyncSession, workspace_id: str) -> dict:
    project_repo = ProjectRepository(session)
    task_repo = TaskRepository(session)
    commit_repo = CommitRepository(session)
    analysis_repo = CommitAnalysisRepository(session)
    repo_config_repo = RepoConfigRepository(session)

    projects = await project_repo.find_all_in_workspace(workspace_id, limit=1000)
    project_ids = [str(p.id) for p in projects]

    # Count tasks across workspace projects
    total_tasks = 0
    completed_tasks = 0
    for pid in project_ids:
        tasks = await task_repo.find_project_tasks(pid, limit=1000)
        total_tasks += len(tasks)
        completed_tasks += sum(1 for t in tasks if t["status"] == "completed")

    # Commits today
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    repo_ids = []
    for pid in project_ids:
        repo_ids.extend(r["id"] for r in await repo_config_repo.find_project_repos(pid))

    commits_today = 0
    if repo_ids:
        commits = await commit_repo.find_commits_since(repo_ids, since)
        commits_today = len(commits)

    # AI analysis averages
    analyses = await analysis_repo.find_recent(limit=100)
    avg_quality = 0
    avg_alignment = 0
    if analyses:
        avg_quality = sum(a.get("code_quality_score", 0) for a in analyses) / len(analyses)
        avg_alignment = sum(a.get("task_alignment_score", 0) for a in analyses) / len(analyses)

    active = sum(1 for p in projects if p.status in ("in_progress", "planning"))

    project_progress = [
        {
            "project_id": str(p.id),
            "title": p.title,
            "progress": p.progress or 0,
            "status": p.status or "planning",
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
