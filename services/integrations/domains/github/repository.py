"""Git-related repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.git import GithubAccount, RepoConfig, CommitEvent, CommitAnalysis


class GitAccountRepository(BaseRepository):
    model = GithubAccount

    async def find_workspace_accounts(self, workspace_id: str) -> list[dict]:
        """List accounts without tokens."""
        stmt = (
            select(
                GithubAccount.id,
                GithubAccount.workspace_id,
                GithubAccount.account_name,
                GithubAccount.github_username,
                GithubAccount.created_at,
            )
            .where(GithubAccount.workspace_id == workspace_id)
            .order_by(GithubAccount.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(r._mapping) for r in result.all()]


class RepoConfigRepository(BaseRepository):
    model = RepoConfig

    async def find_by_repo_name(self, repo_name: str, active_only: bool = True) -> RepoConfig | None:
        stmt = select(RepoConfig).where(RepoConfig.repo_name == repo_name)
        if active_only:
            stmt = stmt.where(RepoConfig.is_active == True)
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_project_repos(self, project_id: str) -> list[RepoConfig]:
        return await self.find_all(filters={"project_id": project_id}, order_by="created_at")


class CommitRepository(BaseRepository):
    model = CommitEvent

    async def find_with_analyses(
        self,
        repo_config_ids: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        stmt = select(CommitEvent).order_by(CommitEvent.pushed_at.desc())
        if repo_config_ids:
            stmt = stmt.where(CommitEvent.repo_config_id.in_(repo_config_ids))
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        commits = []
        for ce in result.scalars().all():
            d = {c.name: getattr(ce, c.name) for c in ce.__table__.columns}
            # Fetch analysis
            analysis_stmt = select(CommitAnalysis).where(CommitAnalysis.commit_event_id == ce.id).limit(1)
            analysis_result = await self.session.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
            d["analysis"] = {c.name: getattr(analysis, c.name) for c in analysis.__table__.columns} if analysis else None
            commits.append(d)
        return commits

    async def find_commits_since(self, repo_config_ids: list[str], since: str) -> list:
        from datetime import datetime
        since_dt = datetime.fromisoformat(since)
        stmt = (
            select(CommitEvent)
            .where(
                CommitEvent.repo_config_id.in_(repo_config_ids),
                CommitEvent.pushed_at >= since_dt,
            )
            .order_by(CommitEvent.pushed_at.desc())
        )
        result = await self.session.execute(stmt)
        commits = []
        for ce in result.scalars().all():
            d = {c.name: getattr(ce, c.name) for c in ce.__table__.columns}
            analysis_stmt = select(CommitAnalysis).where(CommitAnalysis.commit_event_id == ce.id).limit(1)
            analysis_result = await self.session.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
            d["commit_analyses"] = [{c_col.name: getattr(analysis, c_col.name) for c_col in analysis.__table__.columns}] if analysis else []
            commits.append(d)
        return commits


class CommitAnalysisRepository(BaseRepository):
    model = CommitAnalysis

    async def find_recent(self, limit: int = 5) -> list:
        return await self.find_all(order_by="analyzed_at", desc=True, limit=limit)

    async def find_recent_for_workspace(self, workspace_id: str, limit: int = 5) -> list:
        """Workspace-scoped recent analyses via project → repo → commit chain."""
        from shared.models.project import Project
        # Get project IDs
        proj_result = await self.session.execute(
            select(Project.id).where(Project.workspace_id == workspace_id)
        )
        project_ids = [str(row[0]) for row in proj_result.all()]
        if not project_ids:
            return []
        # Get repo config IDs
        repo_result = await self.session.execute(
            select(RepoConfig.id).where(RepoConfig.project_id.in_(project_ids))
        )
        repo_ids = [str(row[0]) for row in repo_result.all()]
        if not repo_ids:
            return []
        # Get commit event IDs
        event_result = await self.session.execute(
            select(CommitEvent.id).where(CommitEvent.repo_config_id.in_(repo_ids))
        )
        event_ids = [str(row[0]) for row in event_result.all()]
        if not event_ids:
            return []
        # Get analyses with commit info
        stmt = (
            select(CommitAnalysis)
            .where(CommitAnalysis.commit_event_id.in_(event_ids))
            .order_by(CommitAnalysis.analyzed_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        analyses = []
        for a in result.scalars().all():
            d = {c.name: getattr(a, c.name) for c in a.__table__.columns}
            # Fetch commit info
            ce_result = await self.session.execute(
                select(CommitEvent).where(CommitEvent.id == a.commit_event_id).limit(1)
            )
            ce = ce_result.scalar_one_or_none()
            if ce:
                d["commit_event"] = {
                    "commit_hash": ce.commit_hash,
                    "commit_message": ce.commit_message,
                    "branch": ce.branch,
                    "author_github_username": ce.author_github_username,
                }
            analyses.append(d)
        return analyses
