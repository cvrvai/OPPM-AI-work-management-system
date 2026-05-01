"""Graph retriever — multi-hop entity traversal using PostgreSQL recursive CTEs.

Traverses the OPPM entity graph (Project → Task → TaskDependency → Member → Objective)
without a dedicated graph database. Each traversal produces RetrievedChunk entries that
carry relationship context the vector and keyword retrievers cannot surface.

Supported traversal modes (selected by query classification):
  - dependency_chain  : blocking chain from a task (upstream blockers + downstream blocked)
  - member_workload   : all tasks assigned to members who appear in the query context
  - objective_tasks   : all tasks linked to an objective (and their statuses)
  - project_graph     : full project → objectives → tasks snapshot

The mode is chosen heuristically from the query text; multiple modes can fire.
"""

import logging
import uuid
from textwrap import dedent

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

# Keywords that trigger each traversal mode
_DEPENDENCY_KEYWORDS = {"block", "depend", "wait", "prerequisite", "before", "after", "delay"}
_WORKLOAD_KEYWORDS = {"overload", "assign", "who", "workload", "capacity", "member", "people", "team"}
_OBJECTIVE_KEYWORDS = {"objective", "goal", "okr", "milestone", "contribut"}
_PROJECT_GRAPH_KEYWORDS = {"overview", "full", "all tasks", "project status", "summary"}

_MAX_HOPS = 5  # cap recursive CTE depth

# Keywords that signal relational/graph traversal is needed (used by rag_service)
_GRAPH_TRIGGER_KEYWORDS = {
    "block", "depend", "wait", "prerequisite", "before", "after",
    "overload", "workload", "assign", "who is working",
    "objective", "goal", "okr", "milestone",
    "delay", "capacity",
}


def _needs_graph(query: str) -> bool:
    """Return True if the query benefits from graph traversal."""
    q = query.lower()
    return any(k in q for k in _GRAPH_TRIGGER_KEYWORDS)


def _detect_modes(query: str) -> list[str]:
    """Heuristically pick traversal modes from the query text."""
    q = query.lower()
    modes: list[str] = []
    if any(k in q for k in _DEPENDENCY_KEYWORDS):
        modes.append("dependency_chain")
    if any(k in q for k in _WORKLOAD_KEYWORDS):
        modes.append("member_workload")
    if any(k in q for k in _OBJECTIVE_KEYWORDS):
        modes.append("objective_tasks")
    if not modes:
        # Default: lightweight project graph overview
        modes.append("project_graph")
    return modes


class GraphRetriever(BaseRetriever):
    """Multi-hop graph traversal using PostgreSQL recursive CTEs.

    Uses the existing task_dependencies, task_assignees, oppm_objectives, and
    project_members tables — no additional graph infrastructure required.
    """

    name = "graph"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        project_id: str | None = filters.get("project_id")
        modes = _detect_modes(query)

        chunks: list[RetrievedChunk] = []
        for mode in modes:
            try:
                if mode == "dependency_chain":
                    chunks.extend(await self._dependency_chain(workspace_id, project_id, top_k))
                elif mode == "member_workload":
                    chunks.extend(await self._member_workload(workspace_id, project_id, top_k))
                elif mode == "objective_tasks":
                    chunks.extend(await self._objective_tasks(workspace_id, project_id, top_k))
                else:
                    chunks.extend(await self._project_graph(workspace_id, project_id, top_k))
            except Exception as e:
                logger.warning("GraphRetriever mode=%s failed: %s", mode, e)

        return chunks[:top_k]

    # ──────────────────────────────────────────────────────────────
    # Traversal: blocking dependency chain (upstream + downstream)
    # ──────────────────────────────────────────────────────────────

    async def _dependency_chain(
        self,
        workspace_id: str,
        project_id: str | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Find all tasks involved in blocking chains within the workspace."""
        # Recursive CTE: walk task_dependencies to find multi-hop chains
        sql = dedent(f"""
            WITH RECURSIVE dep_chain AS (
                -- Seed: tasks that have at least one dependency
                SELECT
                    td.task_id,
                    td.depends_on_task_id,
                    1 AS hop,
                    ARRAY[td.task_id] AS visited
                FROM task_dependencies td
                JOIN tasks t_blocker ON t_blocker.id = td.task_id
                JOIN projects p ON p.id = t_blocker.project_id
                WHERE p.workspace_id = :workspace_id
                  {" AND p.id = :project_id " if project_id else ""}

                UNION ALL

                -- Recurse: follow the chain further
                SELECT
                    td2.task_id,
                    td2.depends_on_task_id,
                    dc.hop + 1,
                    dc.visited || td2.task_id
                FROM task_dependencies td2
                JOIN dep_chain dc ON dc.depends_on_task_id = td2.task_id
                WHERE dc.hop < {_MAX_HOPS}
                  AND NOT td2.task_id = ANY(dc.visited)   -- cycle guard
            )
            SELECT DISTINCT
                t.id::text        AS task_id,
                t.title           AS task_title,
                t.status          AS status,
                t.priority        AS priority,
                t.progress        AS progress,
                bt.id::text       AS blocks_task_id,
                bt.title          AS blocks_task_title,
                bt.status         AS blocks_status,
                dc.hop            AS depth
            FROM dep_chain dc
            JOIN tasks t  ON t.id  = dc.depends_on_task_id
            JOIN tasks bt ON bt.id = dc.task_id
            ORDER BY dc.hop
            LIMIT :top_k
        """)

        params: dict = {"workspace_id": workspace_id, "top_k": top_k}
        if project_id:
            params["project_id"] = project_id

        async with self._session.begin_nested():
            rows = (await self._session.execute(text(sql), params)).mappings().all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            blocker_status = row["status"]
            is_blocking = blocker_status not in ("completed",)
            flag = "🔴 BLOCKING" if is_blocking else "✅ resolved"
            content = (
                f"[Graph] Dependency chain (depth {row['depth']})\n"
                f"  {flag} Task '{row['task_title']}' ({row['status']}, {row['progress']}% done)\n"
                f"  ↳ is blocking → '{row['blocks_task_title']}' ({row['blocks_status']})"
            )
            chunks.append(RetrievedChunk(
                entity_type="task_dependency",
                entity_id=row["task_id"],
                content=content,
                score=0.85 - (row["depth"] * 0.05),  # closer blockers score higher
                source=self.name,
                metadata={
                    "task_title": row["task_title"],
                    "blocks_task_id": row["blocks_task_id"],
                    "blocks_task_title": row["blocks_task_title"],
                    "depth": row["depth"],
                    "is_blocking": is_blocking,
                    "project_id": project_id,
                },
            ))
        return chunks

    # ──────────────────────────────────────────────────────────────
    # Traversal: member workload across all assigned tasks
    # ──────────────────────────────────────────────────────────────

    async def _member_workload(
        self,
        workspace_id: str,
        project_id: str | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Aggregate open task count and avg progress per workspace member."""
        sql = dedent(f"""
            SELECT
                u.id::text          AS user_id,
                u.name              AS member_name,
                COUNT(t.id)         AS open_tasks,
                ROUND(AVG(t.progress), 1) AS avg_progress,
                COUNT(CASE WHEN t.status = 'in_progress' THEN 1 END) AS in_progress_count,
                COUNT(CASE WHEN t.priority IN ('high','critical') THEN 1 END) AS high_priority_count
            FROM workspace_members wm
            JOIN users u ON u.id = wm.user_id
            JOIN task_assignees ta ON ta.member_id = wm.id
            JOIN tasks t ON t.id = ta.task_id AND t.status != 'completed'
            JOIN projects p ON p.id = t.project_id
            WHERE wm.workspace_id = :workspace_id
              {" AND p.id = :project_id " if project_id else ""}
            GROUP BY u.id, u.name
            ORDER BY open_tasks DESC
            LIMIT :top_k
        """)

        params: dict = {"workspace_id": workspace_id, "top_k": top_k}
        if project_id:
            params["project_id"] = project_id

        async with self._session.begin_nested():
            rows = (await self._session.execute(text(sql), params)).mappings().all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            open_tasks = int(row["open_tasks"] or 0)
            high_pri = int(row["high_priority_count"] or 0)
            flag = "⚠️ OVERLOADED" if open_tasks >= 5 else ("🟡 busy" if open_tasks >= 3 else "🟢 ok")
            content = (
                f"[Graph] Member workload: {row['member_name']} {flag}\n"
                f"  Open tasks: {open_tasks} | In-progress: {row['in_progress_count']}\n"
                f"  High/critical priority: {high_pri} | Avg progress: {row['avg_progress']}%"
            )
            chunks.append(RetrievedChunk(
                entity_type="member_workload",
                entity_id=row["user_id"],
                content=content,
                score=0.80,
                source=self.name,
                metadata={
                    "member_name": row["member_name"],
                    "open_tasks": open_tasks,
                    "high_priority_count": high_pri,
                    "project_id": project_id,
                },
            ))
        return chunks

    # ──────────────────────────────────────────────────────────────
    # Traversal: objective → contributing tasks
    # ──────────────────────────────────────────────────────────────

    async def _objective_tasks(
        self,
        workspace_id: str,
        project_id: str | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """For each objective, aggregate its linked tasks' statuses."""
        sql = dedent(f"""
            SELECT
                o.id::text              AS objective_id,
                o.title                 AS objective_title,
                o.priority              AS priority,
                COUNT(t.id)             AS total_tasks,
                COUNT(CASE WHEN t.status = 'completed' THEN 1 END)   AS done,
                COUNT(CASE WHEN t.status = 'in_progress' THEN 1 END) AS in_progress,
                COUNT(CASE WHEN t.status = 'todo' THEN 1 END)        AS todo,
                ROUND(AVG(t.progress), 1)                            AS avg_progress
            FROM oppm_objectives o
            JOIN projects p ON p.id = o.project_id
            LEFT JOIN tasks t ON t.oppm_objective_id = o.id
            WHERE p.workspace_id = :workspace_id
              {" AND p.id = :project_id " if project_id else ""}
            GROUP BY o.id, o.title, o.priority
            ORDER BY avg_progress ASC NULLS LAST
            LIMIT :top_k
        """)

        params: dict = {"workspace_id": workspace_id, "top_k": top_k}
        if project_id:
            params["project_id"] = project_id

        async with self._session.begin_nested():
            rows = (await self._session.execute(text(sql), params)).mappings().all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            total = int(row["total_tasks"] or 0)
            done = int(row["done"] or 0)
            avg = float(row["avg_progress"] or 0)
            health = "🔴 at risk" if avg < 30 else ("🟡 in progress" if avg < 75 else "🟢 on track")
            content = (
                f"[Graph] Objective '{row['objective_title']}' ({row['priority']}) {health}\n"
                f"  Tasks: {total} total | {done} done | {row['in_progress']} in-progress | {row['todo']} todo\n"
                f"  Average progress: {avg}%"
            )
            chunks.append(RetrievedChunk(
                entity_type="objective_graph",
                entity_id=row["objective_id"],
                content=content,
                score=0.82,
                source=self.name,
                metadata={
                    "objective_title": row["objective_title"],
                    "avg_progress": avg,
                    "total_tasks": total,
                    "project_id": project_id,
                },
            ))
        return chunks

    # ──────────────────────────────────────────────────────────────
    # Traversal: full project graph snapshot
    # ──────────────────────────────────────────────────────────────

    async def _project_graph(
        self,
        workspace_id: str,
        project_id: str | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """One-row-per-project summary: objective count, task breakdown, dependency count."""
        sql = dedent(f"""
            SELECT
                p.id::text              AS project_id,
                p.title                 AS project_title,
                p.status                AS status,
                p.progress              AS project_progress,
                COUNT(DISTINCT o.id)    AS objectives,
                COUNT(DISTINCT t.id)    AS total_tasks,
                COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) AS done_tasks,
                COUNT(DISTINCT td.task_id) AS dependent_tasks
            FROM projects p
            LEFT JOIN oppm_objectives o  ON o.project_id = p.id
            LEFT JOIN tasks t            ON t.project_id = p.id
            LEFT JOIN task_dependencies td ON td.task_id = t.id
            WHERE p.workspace_id = :workspace_id
              {" AND p.id = :project_id " if project_id else ""}
            GROUP BY p.id, p.title, p.status, p.progress
            LIMIT :top_k
        """)

        params: dict = {"workspace_id": workspace_id, "top_k": top_k}
        if project_id:
            params["project_id"] = project_id

        async with self._session.begin_nested():
            rows = (await self._session.execute(text(sql), params)).mappings().all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            total = int(row["total_tasks"] or 0)
            done = int(row["done_tasks"] or 0)
            pct = int(row["project_progress"] or 0)
            content = (
                f"[Graph] Project '{row['project_title']}' ({row['status']}, {pct}% complete)\n"
                f"  Objectives: {row['objectives']} | Tasks: {total} ({done} completed)\n"
                f"  Tasks with dependencies: {row['dependent_tasks']}"
            )
            chunks.append(RetrievedChunk(
                entity_type="project_graph",
                entity_id=row["project_id"],
                content=content,
                score=0.75,
                source=self.name,
                metadata={
                    "project_title": row["project_title"],
                    "status": row["status"],
                    "project_id": row["project_id"],
                },
            ))
        return chunks
