"""MCP tools — commit data retrieval."""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.git import CommitEvent, CommitAnalysis

logger = logging.getLogger(__name__)


async def summarize_recent_commits(workspace_id: str, project_id: str, days: int = 7) -> dict:
    """Summarize recent commit activity for a project."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Project)
            .where(Project.id == project_id, Project.workspace_id == workspace_id)
            .limit(1)
        )
        project = result.scalar_one_or_none()
        if not project:
            return {"error": "Project not found in this workspace"}

        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        commits_result = await session.execute(
            select(CommitEvent)
            .where(
                CommitEvent.project_id == project_id,
                CommitEvent.created_at >= since,
            )
            .order_by(CommitEvent.created_at.desc())
            .limit(50)
        )
        commits = list(commits_result.scalars().all())

        commit_ids = [str(c.id) for c in commits]
        analyses = {}
        if commit_ids:
            analyses_result = await session.execute(
                select(CommitAnalysis)
                .where(CommitAnalysis.commit_event_id.in_(commit_ids))
            )
            analyses = {str(a.commit_event_id): a for a in analyses_result.scalars().all()}

        commit_list = []
        for c in commits:
            entry = {
                "hash": (c.commit_hash or "")[:7],
                "message": c.commit_message,
                "author": c.author_github_username,
                "branch": c.branch,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            analysis = analyses.get(str(c.id))
            if analysis:
                entry["alignment_score"] = analysis.task_alignment_score
                entry["quality_score"] = analysis.code_quality_score
                entry["ai_summary"] = analysis.summary
            commit_list.append(entry)

        return {
            "project": project.title,
            "period_days": days,
            "total_commits": len(commit_list),
            "commits": commit_list,
        }
