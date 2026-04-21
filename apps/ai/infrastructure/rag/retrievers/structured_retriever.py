"""Structured retriever — direct DB queries for project/cost/risk/deliverable/dependency data."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.project import Project
from shared.models.oppm import ProjectCost, OPPMRisk, OPPMDeliverable, OPPMForecast
from shared.models.task import Task, TaskDependency, TaskAssignee
from shared.models.workspace import WorkspaceMember, MemberSkill
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk

logger = logging.getLogger(__name__)


class StructuredRetriever(BaseRetriever):
    """Retrieves structured project data (costs, risks, deliverables, deps, members)."""

    name = "structured"

    def __init__(self, session: AsyncSession):
        self._session = session

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        project_id: str | None = filters.get("project_id")
        query_lower = query.lower()

        # Fetch project overviews
        try:
            stmt = (
                select(Project)
                .where(Project.workspace_id == workspace_id)
                .limit(top_k)
            )
            if project_id:
                stmt = stmt.where(Project.id == project_id)
            result = await self._session.execute(stmt)
            projects = result.scalars().all()

            for p in projects:
                content = (
                    f"Project: {p.title}\n"
                    f"Status: {p.status} | Progress: {p.progress or 0}%\n"
                    f"Start: {p.start_date or '—'} | Deadline: {p.deadline or '—'}"
                )
                if p.description:
                    content += f"\n{p.description}"
                chunks.append(RetrievedChunk(
                    entity_type="project",
                    entity_id=str(p.id),
                    content=content,
                    score=0.6,
                    source=self.name,
                    metadata={"title": p.title, "status": p.status},
                ))
        except Exception as e:
            logger.warning("Structured project retrieval failed: %s", e)

        # Fetch cost summaries if query relates to cost/budget
        if any(w in query_lower for w in ("cost", "budget", "spend", "expense", "money", "financial")):
            try:
                stmt = select(ProjectCost).limit(top_k)
                if project_id:
                    stmt = stmt.where(ProjectCost.project_id == project_id)
                result = await self._session.execute(stmt)
                costs = result.scalars().all()

                for c in costs:
                    content = (
                        f"Cost: {c.category or '—'}\n"
                        f"Planned: {c.planned_amount or 0} | Actual: {c.actual_amount or 0}"
                    )
                    if c.description:
                        content += f"\n{c.description}"
                    chunks.append(RetrievedChunk(
                        entity_type="cost",
                        entity_id=str(c.id),
                        content=content,
                        score=0.8,
                        source=self.name,
                        metadata={"category": c.category, "project_id": str(c.project_id) if c.project_id else None},
                    ))
            except Exception as e:
                logger.warning("Structured cost retrieval failed: %s", e)

        # Fetch risks if query relates to risk/issue/problem
        if any(w in query_lower for w in ("risk", "issue", "problem", "concern", "danger", "threat")):
            try:
                stmt = select(OPPMRisk).limit(top_k)
                if project_id:
                    stmt = stmt.where(OPPMRisk.project_id == project_id)
                result = await self._session.execute(stmt)
                for r in result.scalars().all():
                    content = f"Risk #{r.item_number} [{r.rag.upper()}]: {r.description}"
                    chunks.append(RetrievedChunk(
                        entity_type="risk",
                        entity_id=str(r.id),
                        content=content,
                        score=0.8,
                        source=self.name,
                        metadata={"rag": r.rag, "project_id": str(r.project_id)},
                    ))
            except Exception as e:
                logger.warning("Structured risk retrieval failed: %s", e)

        # Fetch deliverables if query relates to deliverable/output/result
        if any(w in query_lower for w in ("deliverable", "output", "result", "artifact", "produce")):
            try:
                stmt = select(OPPMDeliverable).limit(top_k)
                if project_id:
                    stmt = stmt.where(OPPMDeliverable.project_id == project_id)
                result = await self._session.execute(stmt)
                for d in result.scalars().all():
                    content = f"Deliverable #{d.item_number}: {d.description}"
                    chunks.append(RetrievedChunk(
                        entity_type="deliverable",
                        entity_id=str(d.id),
                        content=content,
                        score=0.7,
                        source=self.name,
                        metadata={"project_id": str(d.project_id)},
                    ))
            except Exception as e:
                logger.warning("Structured deliverable retrieval failed: %s", e)

        # Fetch forecasts if query relates to forecast/expected/prediction
        if any(w in query_lower for w in ("forecast", "expected", "prediction", "outlook", "estimate")):
            try:
                stmt = select(OPPMForecast).limit(top_k)
                if project_id:
                    stmt = stmt.where(OPPMForecast.project_id == project_id)
                result = await self._session.execute(stmt)
                for f in result.scalars().all():
                    content = f"Forecast #{f.item_number}: {f.description}"
                    chunks.append(RetrievedChunk(
                        entity_type="forecast",
                        entity_id=str(f.id),
                        content=content,
                        score=0.7,
                        source=self.name,
                        metadata={"project_id": str(f.project_id)},
                    ))
            except Exception as e:
                logger.warning("Structured forecast retrieval failed: %s", e)

        # Fetch dependencies if query relates to blocking/dependencies
        if any(w in query_lower for w in ("dependency", "dependencies", "blocked", "blocking", "prerequisite", "depends")):
            try:
                stmt = (
                    select(
                        TaskDependency.task_id,
                        TaskDependency.depends_on_task_id,
                        Task.title,
                    )
                    .join(Task, Task.id == TaskDependency.task_id)
                )
                if project_id:
                    stmt = stmt.where(Task.project_id == project_id)
                stmt = stmt.limit(top_k)
                result = await self._session.execute(stmt)
                for row in result.all():
                    content = f"Task '{row.title}' depends on task {row.depends_on_task_id}"
                    chunks.append(RetrievedChunk(
                        entity_type="dependency",
                        entity_id=f"{row.task_id}:{row.depends_on_task_id}",
                        content=content,
                        score=0.7,
                        source=self.name,
                        metadata={"task_id": str(row.task_id)},
                    ))
            except Exception as e:
                logger.warning("Structured dependency retrieval failed: %s", e)

        # Fetch team/skills if query relates to team/skill/who
        if any(w in query_lower for w in ("team", "skill", "who can", "expert", "member", "people", "resource")):
            try:
                stmt = (
                    select(WorkspaceMember, MemberSkill.skill_name, MemberSkill.skill_level)
                    .outerjoin(MemberSkill, MemberSkill.workspace_member_id == WorkspaceMember.id)
                    .where(WorkspaceMember.workspace_id == workspace_id)
                    .limit(top_k * 3)
                )
                result = await self._session.execute(stmt)
                member_chunks: dict[str, RetrievedChunk] = {}
                for row in result.all():
                    m = row[0]
                    mid = str(m.id)
                    if mid not in member_chunks:
                        name = m.display_name or str(m.user_id)[:8]
                        member_chunks[mid] = RetrievedChunk(
                            entity_type="member",
                            entity_id=mid,
                            content=f"Member: {name} ({m.role})",
                            score=0.7,
                            source=self.name,
                            metadata={"name": name, "role": m.role},
                        )
                    if row[1]:  # skill_name
                        member_chunks[mid].content += f"\n  Skill: {row[1]} ({row[2]})"
                chunks.extend(list(member_chunks.values())[:top_k])
            except Exception as e:
                logger.warning("Structured member/skill retrieval failed: %s", e)

        return chunks[:top_k]
