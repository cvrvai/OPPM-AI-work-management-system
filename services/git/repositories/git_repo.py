"""Git-related repositories."""

from repositories.base import BaseRepository
from shared.database import get_db


class GitAccountRepository(BaseRepository):
    def __init__(self):
        super().__init__("github_accounts")

    def find_workspace_accounts(self, workspace_id: str) -> list[dict]:
        """List accounts without tokens."""
        result = (
            self._query()
            .select("id, workspace_id, account_name, github_username, created_at")
            .eq("workspace_id", workspace_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []


class RepoConfigRepository(BaseRepository):
    def __init__(self):
        super().__init__("repo_configs")

    def find_by_repo_name(self, repo_name: str, active_only: bool = True) -> dict | None:
        q = self._query().select("*").eq("repo_name", repo_name)
        if active_only:
            q = q.eq("is_active", True)
        result = q.limit(1).execute()
        return result.data[0] if result.data else None

    def find_project_repos(self, project_id: str) -> list[dict]:
        return self.find_all(filters={"project_id": project_id}, order_by="created_at")


class CommitRepository(BaseRepository):
    def __init__(self):
        super().__init__("commit_events")

    def find_with_analyses(
        self,
        repo_config_ids: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        db = get_db()
        q = db.table("commit_events").select("*, commit_analyses(*)")
        if repo_config_ids:
            q = q.in_("repo_config_id", repo_config_ids)
        result = q.order("pushed_at", desc=True).range(offset, offset + limit - 1).execute()
        # Flatten analysis
        commits = []
        for c in result.data or []:
            analyses = c.pop("commit_analyses", [])
            c["analysis"] = analyses[0] if analyses else None
            commits.append(c)
        return commits

    def find_commits_since(self, repo_config_ids: list[str], since: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("commit_events")
            .select("*, commit_analyses(*)")
            .in_("repo_config_id", repo_config_ids)
            .gte("pushed_at", since)
            .order("pushed_at", desc=True)
            .execute()
        )
        return result.data or []


class CommitAnalysisRepository(BaseRepository):
    def __init__(self):
        super().__init__("commit_analyses")

    def find_recent(self, limit: int = 5) -> list[dict]:
        return self.find_all(order_by="analyzed_at", desc=True, limit=limit)

    def find_recent_for_workspace(self, workspace_id: str, limit: int = 5) -> list[dict]:
        """Workspace-scoped recent analyses via project → repo → commit chain."""
        db = get_db()
        projects = db.table("projects").select("id").eq("workspace_id", workspace_id).execute()
        project_ids = [p["id"] for p in (projects.data or [])]
        if not project_ids:
            return []
        repos = db.table("repo_configs").select("id").in_("project_id", project_ids).execute()
        repo_ids = [r["id"] for r in (repos.data or [])]
        if not repo_ids:
            return []
        events = db.table("commit_events").select("id").in_("repo_config_id", repo_ids).execute()
        event_ids = [e["id"] for e in (events.data or [])]
        if not event_ids:
            return []
        result = (
            db.table("commit_analyses")
            .select("*, commit_events(commit_hash, commit_message, branch, author_github_username)")
            .in_("commit_event_id", event_ids)
            .order("analyzed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
