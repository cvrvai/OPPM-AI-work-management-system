"""MCP tools — objective data retrieval."""

import logging
from sqlalchemy import select
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.oppm import OPPMObjective, OPPMTimelineEntry

logger = logging.getLogger(__name__)


async def list_at_risk_objectives(workspace_id: str) -> list[dict]:
    """List objectives that have at_risk or blocked timeline entries."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Project.id).where(Project.workspace_id == workspace_id)
        )
        project_ids = [str(row[0]) for row in result.all()]
        if not project_ids:
            return []

        entries_result = await session.execute(
            select(OPPMTimelineEntry)
            .where(
                OPPMTimelineEntry.project_id.in_(project_ids),
                OPPMTimelineEntry.status.in_(["at_risk", "blocked"]),
            )
        )
        at_risk_entries = list(entries_result.scalars().all())

        if not at_risk_entries:
            return []

        obj_ids = list({str(e.objective_id) for e in at_risk_entries})

        obj_result = await session.execute(
            select(OPPMObjective).where(OPPMObjective.id.in_(obj_ids))
        )
        obj_map = {str(o.id): o for o in obj_result.scalars().all()}

        results = []
        for entry in at_risk_entries:
            obj = obj_map.get(str(entry.objective_id))
            if obj:
                results.append({
                    "objective_id": str(obj.id),
                    "title": obj.title,
                    "project_id": str(obj.project_id),
                    "status": entry.status,
                    "week_start": str(entry.week_start) if entry.week_start else None,
                })

        return results
