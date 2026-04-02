"""MCP tools — objective data retrieval."""

import logging
from shared.database import get_db

logger = logging.getLogger(__name__)


def list_at_risk_objectives(workspace_id: str) -> list[dict]:
    """List objectives that have at_risk or blocked timeline entries."""
    db = get_db()
    projects = (
        db.table("projects")
        .select("id")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    project_ids = [p["id"] for p in (projects.data or [])]
    if not project_ids:
        return []

    at_risk_entries = (
        db.table("oppm_timeline_entries")
        .select("objective_id, status, week_start")
        .in_("project_id", project_ids)
        .in_("status", ["at_risk", "blocked"])
        .execute()
    )

    if not at_risk_entries.data:
        return []

    obj_ids = list({e["objective_id"] for e in at_risk_entries.data})

    objectives = (
        db.table("oppm_objectives")
        .select("id, title, project_id, sort_order")
        .in_("id", obj_ids)
        .execute()
    )

    obj_map = {o["id"]: o for o in (objectives.data or [])}
    results = []
    for entry in at_risk_entries.data:
        obj = obj_map.get(entry["objective_id"])
        if obj:
            results.append({
                "objective_id": obj["id"],
                "title": obj["title"],
                "project_id": obj["project_id"],
                "status": entry["status"],
                "week_start": entry["week_start"],
            })

    return results
