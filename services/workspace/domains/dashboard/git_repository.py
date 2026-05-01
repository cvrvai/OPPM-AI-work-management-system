"""Git-related repositories (copy — used by dashboard_service for commit stats)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.workspace.base_repository import BaseRepository
from shared.models.git import GithubAccount, RepoConfig, CommitEvent, CommitAnalysis


class GitAccountRepository(BaseRepository):
    model = GithubAccount

    async def find_workspace_accounts(self, workspace_id: str) -> list[dict]:
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
            # Fetch analysis separately
            analysis_stmt = select(CommitAnalysis).where(CommitAnalysis.commit_event_id == ce.id).limit(1)
            analysis_result = await self.session.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
            d["analysis"] = {c.name: getattr(analysis, c.name) for c in analysis.__table__.columns} if analysis else None
            commits.append(d)
        return commits

    async def find_commits_since(self, repo_config_ids: list[str], since: str) -> list[dict]:
        stmt = (
            select(CommitEvent)
            .where(
                CommitEvent.repo_config_id.in_(repo_config_ids),
                CommitEvent.pushed_at >= since,
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
            d["analysis"] = {c.name: getattr(analysis, c.name) for c in analysis.__table__.columns} if analysis else None
            commits.append(d)
        return commits


class CommitAnalysisRepository(BaseRepository):
    model = CommitAnalysis

    async def find_recent(self, limit: int = 5) -> list[CommitAnalysis]:
        return await self.find_all(order_by="analyzed_at", desc=True, limit=limit)
