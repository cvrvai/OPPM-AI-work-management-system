"""OPPM objective and timeline tools — migrated from oppm_tool_executor."""

import logging
from datetime import date, timedelta
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from infrastructure.tools.registry import get_registry
from domains.analysis.oppm_repository import (
    ObjectiveRepository,
    TimelineRepository,
    HeaderRepository,
    SubObjectiveRepository,
    TaskSubObjectiveLinkRepository,
    TaskOwnerRepository,
    RiskWriteRepository,
    ForecastWriteRepository,
    CostWriteRepository,
    BorderOverrideRepository,
)
from shared.models.task import Task, TaskOwner
from shared.models.project import Project
from shared.models.oppm import (
    OPPMHeader,
    OPPMSubObjective,
    OPPMTimelineEntry,
    TaskSubObjective,
    OPPMBorderOverride,
)

logger = logging.getLogger(__name__)


# Map Task.status values to OPPMTimelineEntry.status symbols.
#   ☐ planned     · ● in_progress · ■ completed · ▲ at_risk · ✕ blocked
_STATUS_MAP = {
    "todo": "planned",
    "planned": "planned",
    "in_progress": "in_progress",
    "in-progress": "in_progress",
    "doing": "in_progress",
    "done": "completed",
    "completed": "completed",
    "complete": "completed",
    "blocked": "blocked",
}


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def _create_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    resolved_project_id = tool_input.get("project_id") or project_id
    if not resolved_project_id:
        return ToolResult(success=False, error="project_id is required — create a project first")
    data = {
        "project_id": resolved_project_id,
        "title": tool_input["title"],
        "sort_order": tool_input.get("sort_order", 999),
    }
    if tool_input.get("owner_id"):
        data["owner_id"] = tool_input["owner_id"]
    obj = await repo.create(data)
    return ToolResult(
        success=True,
        result={"id": str(obj.id), "title": obj.title, "project_id": str(obj.project_id), "sort_order": obj.sort_order},
        updated_entities=["oppm_objectives"],
    )


async def _update_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    obj_id = tool_input.get("objective_id")
    if not obj_id:
        return ToolResult(success=False, error="objective_id required")
    updates = {k: v for k, v in tool_input.items() if k != "objective_id"}
    obj = await repo.update(obj_id, updates)
    return ToolResult(
        success=True,
        result={"id": str(obj.id), "title": obj.title} if obj else {"updated": True},
        updated_entities=["oppm_objectives"],
    )


async def _delete_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = ObjectiveRepository(session)
    obj_id = tool_input.get("objective_id")
    if not obj_id:
        return ToolResult(success=False, error="objective_id required")
    deleted = await repo.delete(obj_id)
    return ToolResult(success=deleted, result={"deleted": deleted}, updated_entities=["oppm_objectives"])


async def _set_timeline_status(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TimelineRepository(session)
    entry_data = {
        "project_id": project_id,
        "task_id": tool_input["task_id"],
        "week_start": tool_input["week_start"],
        "status": tool_input["status"],
    }
    if tool_input.get("notes"):
        entry_data["notes"] = tool_input["notes"]
    entry = await repo.upsert_entry(entry_data)
    return ToolResult(
        success=True,
        result={"id": str(entry.id), "status": entry.status} if entry else {"updated": True},
        updated_entities=["oppm_timeline_entries"],
    )


async def _bulk_set_timeline(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    repo = TimelineRepository(session)
    results = []
    for entry in tool_input.get("entries", []):
        entry_data = {
            "project_id": project_id,
            "task_id": entry["task_id"],
            "week_start": entry["week_start"],
            "status": entry["status"],
        }
        if entry.get("notes"):
            entry_data["notes"] = entry["notes"]
        results.append(await repo.upsert_entry(entry_data))
    return ToolResult(
        success=True,
        result={"count": len(results)},
        updated_entities=["oppm_timeline_entries"],
    )


# ── Register tools ──

_registry = get_registry()

_registry.register(ToolDefinition(
    name="create_objective",
    description="Create a new OPPM objective for a project. In workspace context, pass the project_id returned by create_project.",
    category="oppm",
    params=[
        ToolParam("title", "string", "Objective title", required=True),
        ToolParam("project_id", "string", "UUID of the target project (required in workspace chat, optional in project chat)", required=False),
        ToolParam("sort_order", "integer", "Display order (1-based)", required=False),
        ToolParam("owner_id", "string", "UUID of the workspace member who owns this objective", required=False),
    ],
    handler=_create_objective,
))

_registry.register(ToolDefinition(
    name="update_objective",
    description="Update an existing OPPM objective's title or sort order",
    category="oppm",
    params=[
        ToolParam("objective_id", "string", "UUID of the objective to update", required=True),
        ToolParam("title", "string", "New title", required=False),
        ToolParam("sort_order", "integer", "New display order", required=False),
    ],
    handler=_update_objective,
))

_registry.register(ToolDefinition(
    name="delete_objective",
    description="Delete an OPPM objective and its associated data",
    category="oppm",
    params=[
        ToolParam("objective_id", "string", "UUID of the objective to delete", required=True),
    ],
    handler=_delete_objective,
))

_registry.register(ToolDefinition(
    name="set_timeline_status",
    description="Set the timeline status for a task in a specific week",
    category="oppm",
    params=[
        ToolParam("task_id", "string", "UUID of the task", required=True),
        ToolParam("week_start", "string", "Week start date (YYYY-MM-DD)", required=True),
        ToolParam("status", "string", "Timeline status", required=True, enum=["planned", "in_progress", "completed", "at_risk", "blocked"]),
        ToolParam("notes", "string", "Optional notes for this timeline entry", required=False),
    ],
    handler=_set_timeline_status,
))

_registry.register(ToolDefinition(
    name="bulk_set_timeline",
    description="Set timeline status for multiple tasks/weeks at once (more efficient than individual calls)",
    category="oppm",
    params=[
        ToolParam("entries", "array", "Array of {task_id, week_start, status, notes?} objects", required=True),
    ],
    handler=_bulk_set_timeline,
))


# ─── New OPPM tools (added for the OPPM agent skill) ────────────────────────

async def _upsert_oppm_header(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    fields = {
        k: v
        for k, v in tool_input.items()
        if k in ("project_leader_text", "completed_by_text", "people_count") and v is not None
    }
    if not fields:
        return ToolResult(success=False, error="At least one field required: project_leader_text, completed_by_text, people_count")
    header = await HeaderRepository(session).upsert(project_id, workspace_id, fields)
    return ToolResult(
        success=True,
        result={"id": str(header.id), **fields},
        updated_entities=["oppm_header"],
    )


async def _upsert_sub_objective(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    position = int(tool_input["position"])
    label = str(tool_input["label"])
    so = await SubObjectiveRepository(session).upsert_at_position(project_id, position, label)
    return ToolResult(
        success=True,
        result={"id": str(so.id), "position": so.position, "label": so.label},
        updated_entities=["oppm_sub_objectives"],
    )


async def _link_task_sub_objectives(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    task_id = tool_input["task_id"]
    sub_objective_ids = tool_input.get("sub_objective_ids") or []
    await TaskSubObjectiveLinkRepository(session).set_links(task_id, sub_objective_ids)
    return ToolResult(
        success=True,
        result={"task_id": task_id, "linked": len(sub_objective_ids)},
        updated_entities=["task_sub_objectives"],
    )


async def _set_task_owner(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    result = await TaskOwnerRepository(session).set_owner(
        task_id=tool_input["task_id"],
        member_id=tool_input["member_id"],
        priority=tool_input["priority"],
    )
    return ToolResult(success=True, result=result, updated_entities=["task_owners"])


async def _upsert_risk(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    fields = {"description": str(tool_input["description"])}
    if "rag" in tool_input and tool_input["rag"]:
        fields["rag"] = tool_input["rag"]
    risk = await RiskWriteRepository(session).upsert(project_id, int(tool_input["item_number"]), fields)
    return ToolResult(
        success=True,
        result={"id": str(risk.id), "item_number": risk.item_number, "description": risk.description, "rag": risk.rag},
        updated_entities=["oppm_risks"],
    )


async def _upsert_forecast(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    forecast = await ForecastWriteRepository(session).upsert(
        project_id,
        int(tool_input["item_number"]),
        {"description": str(tool_input["description"])},
    )
    return ToolResult(
        success=True,
        result={"id": str(forecast.id), "item_number": forecast.item_number, "description": forecast.description},
        updated_entities=["oppm_forecasts"],
    )


async def _upsert_cost(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    fields: dict = {}
    if "description" in tool_input:
        fields["description"] = str(tool_input["description"])
    if "planned_amount" in tool_input:
        fields["planned_amount"] = tool_input["planned_amount"]
    if "actual_amount" in tool_input:
        fields["actual_amount"] = tool_input["actual_amount"]
    cost = await CostWriteRepository(session).upsert_by_category(
        project_id=project_id,
        category=str(tool_input["category"]),
        period=tool_input.get("period"),
        fields=fields,
    )
    return ToolResult(
        success=True,
        result={
            "id": str(cost.id),
            "category": cost.category,
            "period": cost.period,
            "planned_amount": float(cost.planned_amount),
            "actual_amount": float(cost.actual_amount),
        },
        updated_entities=["project_costs"],
    )


async def _derive_timeline_from_task_status(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """For every task in the project, write timeline entries that reflect the task's
    current status — but ONLY for the weeks the task is actually scheduled.

    Each task's range is `[task.start_date, task.due_date]` with project dates as
    fallback. Tasks with no usable range are skipped. Stale entries outside the
    new range are deleted so a re-run doesn't leave dots leaking across the grid.

    Status mapping per week (within the task's range):
      - week > today + task in any status         → planned    ☐
      - week == today + task status               → mapped status
      - week < today + task done                  → completed  ■
      - week < today + task not done + overdue    → at_risk    ▲
      - week < today + task not done              → in_progress●

    `fill_full_range` is accepted for backwards compatibility but is now a no-op:
    we always span the task's own dates.
    """
    project = await session.get(Project, project_id)
    if not project:
        return ToolResult(success=False, error="Project not found")

    today = date.today()
    current_week = _monday(today)

    task_rows = (
        await session.execute(
            select(Task.id, Task.status, Task.start_date, Task.due_date)
            .where(Task.project_id == project_id)
        )
    ).all()
    if not task_rows:
        return ToolResult(success=True, result={"tasks": 0, "entries_written": 0, "entries_deleted": 0})

    project_start = project.start_date
    project_end = project.deadline

    timeline_repo = TimelineRepository(session)
    written = 0
    deleted = 0
    skipped_no_range = 0

    for task_id, raw_status, task_start, task_due in task_rows:
        effective_start = task_start or project_start
        effective_end = task_due or project_end
        if not effective_start or not effective_end or effective_start > effective_end:
            skipped_no_range += 1
            continue

        first_week = _monday(effective_start)
        last_week = _monday(effective_end)
        weeks: list[date] = []
        cursor = first_week
        while cursor <= last_week:
            weeks.append(cursor)
            cursor += timedelta(weeks=1)
        if not weeks:
            continue

        # Drop any existing timeline entries outside the new range so an earlier
        # run that wrote dots across the whole project doesn't leave leftovers.
        del_result = await session.execute(
            delete(OPPMTimelineEntry).where(
                OPPMTimelineEntry.task_id == task_id,
                (OPPMTimelineEntry.week_start < first_week)
                | (OPPMTimelineEntry.week_start > last_week),
            )
        )
        deleted += del_result.rowcount or 0

        mapped = _STATUS_MAP.get((raw_status or "todo").lower(), "planned")
        for week in weeks:
            if week > current_week:
                status = "planned"
            elif week == current_week:
                status = mapped
            else:
                if mapped == "completed":
                    status = "completed"
                elif task_due and task_due < week:
                    status = "at_risk"
                else:
                    status = "in_progress" if mapped != "planned" else "planned"
            await timeline_repo.upsert_entry({
                "project_id": project_id,
                "task_id": str(task_id),
                "week_start": week,
                "status": status,
            })
            written += 1

    return ToolResult(
        success=True,
        result={
            "tasks": len(task_rows),
            "entries_written": written,
            "entries_deleted": deleted,
            "skipped_tasks_without_range": skipped_no_range,
        },
        updated_entities=["oppm_timeline_entries"],
    )


_registry.register(ToolDefinition(
    name="upsert_oppm_header",
    description="Set OPPM free-text header fields (project_leader_text, completed_by_text, people_count). Project_objective and deliverable_output live on the projects table — use update_project for those.",
    category="oppm",
    params=[
        ToolParam("project_leader_text", "string", "Free-text project leader name shown in header", required=False),
        ToolParam("completed_by_text", "string", "Duration string for the 'Project Completed By' header (e.g. '8 weeks')", required=False),
        ToolParam("people_count", "integer", "Number of people working on the project", required=False),
    ],
    handler=_upsert_oppm_header,
))


_registry.register(ToolDefinition(
    name="upsert_sub_objective",
    description="Create or rename one of the 6 lettered (A–F) sub-objective milestone rows. position must be 1-6 (1=A, 2=B, …, 6=F).",
    category="oppm",
    params=[
        ToolParam("position", "integer", "1-6 corresponding to letter A-F", required=True),
        ToolParam("label", "string", "Sub-objective text shown in the lettered row", required=True),
    ],
    handler=_upsert_sub_objective,
))


_registry.register(ToolDefinition(
    name="link_task_sub_objectives",
    description="Replace the set of sub-objectives a task contributes to. Pass an empty list to clear all links. Each ✓ in the sub-objective columns of the OPPM corresponds to one link.",
    category="oppm",
    params=[
        ToolParam("task_id", "string", "UUID of the task", required=True),
        ToolParam("sub_objective_ids", "array", "Array of sub-objective UUIDs the task contributes to (empty list clears all)", required=True, items_type="string"),
    ],
    handler=_link_task_sub_objectives,
))


_registry.register(ToolDefinition(
    name="set_task_owner",
    description="Assign a workspace member to a task with a priority letter. A=Primary owner, B=Primary helper, C=Secondary helper. These letters appear in the OPPM 'Owner / Priority' column.",
    category="oppm",
    params=[
        ToolParam("task_id", "string", "UUID of the task", required=True),
        ToolParam("member_id", "string", "UUID of the workspace member", required=True),
        ToolParam("priority", "string", "Priority letter", required=True, enum=["A", "B", "C"]),
    ],
    handler=_set_task_owner,
))


_registry.register(ToolDefinition(
    name="upsert_risk",
    description="Create or update one of the OPPM risk rows shown at the bottom of the form.",
    category="oppm",
    params=[
        ToolParam("item_number", "integer", "Risk row number (1-based)", required=True),
        ToolParam("description", "string", "Risk description", required=True),
        ToolParam("rag", "string", "RAG status", required=False, enum=["green", "amber", "red"]),
    ],
    handler=_upsert_risk,
))


_registry.register(ToolDefinition(
    name="upsert_forecast",
    description="Create or update one row of the OPPM Summary & Forecast quadrant.",
    category="oppm",
    params=[
        ToolParam("item_number", "integer", "Forecast row number (1-based)", required=True),
        ToolParam("description", "string", "Forecast text", required=True),
    ],
    handler=_upsert_forecast,
))


_registry.register(ToolDefinition(
    name="upsert_cost",
    description="Create or update a cost line in the OPPM Costs quadrant. Upsert key is (category, period). Pass period=null for non-periodic costs.",
    category="oppm",
    params=[
        ToolParam("category", "string", "Cost category (e.g. 'Engineering', 'Cloud')", required=True),
        ToolParam("planned_amount", "number", "Planned cost amount", required=False),
        ToolParam("actual_amount", "number", "Actual cost amount to date", required=False),
        ToolParam("description", "string", "Optional free-text description", required=False),
        ToolParam("period", "string", "Optional period label (e.g. 'Q1', '2026-05')", required=False),
    ],
    handler=_upsert_cost,
))


_registry.register(ToolDefinition(
    name="derive_timeline_from_task_status",
    description=(
        "Bulk-fill the OPPM timeline dots from each task's status, scoped to the "
        "task's own [start_date, due_date] range (project dates as fallback). "
        "Tasks with no usable range are skipped. Stale entries outside the new "
        "range are deleted, so re-running this is safe. This is the right tool "
        "to call after any task date or status change."
    ),
    category="oppm",
    params=[
        ToolParam(
            "fill_full_range",
            "boolean",
            "Deprecated / ignored — kept for backwards compatibility. The tool always uses each task's own date range.",
            required=False,
        ),
    ],
    handler=_derive_timeline_from_task_status,
))


# ─── Validation & repair tools ──────────────────────────────────────────────
#
# These let the agent detect a broken/incomplete OPPM and propose fixes.
# `validate_oppm` is read-only — call it first. `renumber_oppm_tasks` rewrites
# Task.sort_order so the auto-derived numbers (1, 2, 3, …) form a contiguous
# sequence again.


async def _validate_oppm(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    project = await session.get(Project, project_id)
    if not project:
        return ToolResult(success=False, error="Project not found")

    issues: list[dict] = []

    def add(severity: str, code: str, field: str, message: str, fix_hint: str | None = None) -> None:
        entry = {"severity": severity, "code": code, "field": field, "message": message}
        if fix_hint:
            entry["fix_hint"] = fix_hint
        issues.append(entry)

    # ── Header / project metadata ──
    if not (project.objective_summary or "").strip():
        add("error", "missing_objective", "project.objective_summary",
            "Project objective is empty.",
            "Call update_project with a one-sentence objective_summary.")
    if not (project.deliverable_output or "").strip():
        add("error", "missing_deliverable", "project.deliverable_output",
            "Deliverable output is empty.",
            "Call update_project with a one-sentence deliverable_output.")
    if not project.start_date:
        add("error", "missing_start_date", "project.start_date",
            "Start date is not set.",
            "Call update_project with a start_date.")
    if not project.deadline:
        add("error", "missing_deadline", "project.deadline",
            "Deadline is not set.",
            "Call update_project with a deadline.")
    if project.start_date and project.deadline and project.start_date > project.deadline:
        add("error", "invalid_dates", "project.dates",
            f"start_date ({project.start_date}) is after deadline ({project.deadline}).",
            "Fix start_date or deadline via update_project.")

    header_row = (await session.execute(
        select(OPPMHeader).where(OPPMHeader.project_id == project_id).limit(1)
    )).scalar_one_or_none()
    if header_row is None or not (header_row.completed_by_text or "").strip():
        add("warning", "missing_completed_by", "oppm_header.completed_by_text",
            "OPPM header 'Completed By' text is empty.",
            "Call upsert_oppm_header with a duration string like '8 weeks'.")
    if header_row is None or header_row.people_count is None or header_row.people_count <= 0:
        add("warning", "missing_people_count", "oppm_header.people_count",
            "OPPM header people_count is not set.",
            "Call upsert_oppm_header with people_count.")

    # ── Sub-objectives ──
    sub_objs = (await session.execute(
        select(OPPMSubObjective)
        .where(OPPMSubObjective.project_id == project_id)
        .order_by(OPPMSubObjective.position)
    )).scalars().all()
    seen_positions = [so.position for so in sub_objs]
    for pos in seen_positions:
        if not (1 <= pos <= 6):
            add("error", "sub_objective_out_of_range", "oppm_sub_objectives.position",
                f"Sub-objective at position {pos} is outside 1-6.")
    if len(sub_objs) > 0 and len(sub_objs) < 6:
        missing = [p for p in range(1, 7) if p not in seen_positions]
        add("warning", "sub_objectives_incomplete", "oppm_sub_objectives",
            f"Only {len(sub_objs)}/6 sub-objective rows defined. Missing positions: {missing}.",
            "Call upsert_sub_objective for each missing position (1=A … 6=F).")
    if len(sub_objs) == 0:
        add("warning", "no_sub_objectives", "oppm_sub_objectives",
            "No sub-objective rows (A–F) defined.",
            "Call upsert_sub_objective for positions 1–6.")

    # ── Tasks: numbering / contiguity / status ──
    tasks = (await session.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.sort_order, Task.created_at)
    )).scalars().all()
    if not tasks:
        add("error", "no_tasks", "tasks",
            "Project has no tasks. The OPPM cannot be filled without at least one task.",
            "Create tasks via create_task before running fill.")

    root_tasks = [t for t in tasks if t.parent_task_id is None]
    sort_orders = [t.sort_order for t in root_tasks]
    duplicate_orders = sorted({s for s in sort_orders if sort_orders.count(s) > 1})
    if duplicate_orders:
        add("warning", "duplicate_sort_order", "tasks.sort_order",
            f"Duplicate sort_order values among root tasks: {duplicate_orders}. "
            "Numbering in the sheet will collide.",
            "Call renumber_oppm_tasks to rebuild sort_order from 1..N contiguously.")
    # Non-contiguous root sort_order (gaps > 1) — purely cosmetic but suggests drift
    if len(root_tasks) >= 2:
        seq = sorted({s for s in sort_orders})
        gaps = [(seq[i], seq[i + 1]) for i in range(len(seq) - 1) if seq[i + 1] - seq[i] > 1]
        if gaps:
            add("info", "sort_order_gaps", "tasks.sort_order",
                f"Root task sort_order has gaps (showing first 3): {gaps[:3]}.",
                "Run renumber_oppm_tasks to compact numbering.")

    # ── Owners: every root task should have at least one A-priority owner ──
    if root_tasks:
        owners_rows = (await session.execute(
            select(TaskOwner.task_id, TaskOwner.priority)
            .where(TaskOwner.task_id.in_([t.id for t in root_tasks]))
        )).all()
        owners_by_task: dict[str, list[str]] = {}
        for row in owners_rows:
            owners_by_task.setdefault(str(row.task_id), []).append(row.priority)
        no_owner = [t for t in root_tasks if not owners_by_task.get(str(t.id))]
        no_a_owner = [
            t for t in root_tasks
            if owners_by_task.get(str(t.id)) and "A" not in owners_by_task[str(t.id)]
        ]
        if no_owner:
            sample = [t.title[:40] for t in no_owner[:3]]
            add("warning", "tasks_without_owner", "task_owners",
                f"{len(no_owner)} task(s) have no owner. Sample: {sample}",
                "Call set_task_owner with priority='A' for each.")
        if no_a_owner:
            sample = [t.title[:40] for t in no_a_owner[:3]]
            add("warning", "tasks_missing_primary", "task_owners",
                f"{len(no_a_owner)} task(s) have B/C owners but no A (Primary). Sample: {sample}",
                "Promote one owner to priority='A' via set_task_owner.")

    # ── Sub-objective links ──
    if sub_objs and root_tasks:
        link_rows = (await session.execute(
            select(TaskSubObjective.task_id)
            .where(TaskSubObjective.task_id.in_([t.id for t in root_tasks]))
        )).all()
        linked_task_ids = {str(r.task_id) for r in link_rows}
        unlinked = [t for t in root_tasks if str(t.id) not in linked_task_ids]
        if unlinked:
            sample = [t.title[:40] for t in unlinked[:3]]
            add("info", "tasks_without_sub_objective", "task_sub_objectives",
                f"{len(unlinked)} task(s) are not linked to any sub-objective. Sample: {sample}",
                "Call link_task_sub_objectives for each.")

    # ── Timeline coverage ──
    if root_tasks:
        tl_rows = (await session.execute(
            select(OPPMTimelineEntry.task_id)
            .where(OPPMTimelineEntry.task_id.in_([t.id for t in root_tasks]))
        )).all()
        tasks_with_timeline = {str(r.task_id) for r in tl_rows}
        no_timeline = [t for t in root_tasks if str(t.id) not in tasks_with_timeline]
        if no_timeline:
            sample = [t.title[:40] for t in no_timeline[:3]]
            add("warning", "tasks_without_timeline", "oppm_timeline_entries",
                f"{len(no_timeline)} task(s) have no timeline entries. Sample: {sample}",
                "Call derive_timeline_from_task_status (fill_full_range=true).")

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")
    info_count = sum(1 for i in issues if i["severity"] == "info")

    return ToolResult(
        success=True,
        result={
            "is_valid": error_count == 0,
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
            "issues": issues,
            "task_count": len(tasks),
            "root_task_count": len(root_tasks),
        },
    )


_registry.register(ToolDefinition(
    name="validate_oppm",
    description=(
        "Inspect the OPPM form and return a list of issues (errors, warnings, info). "
        "ALWAYS call this first when asked to fix or repair an OPPM. Each issue has a "
        "fix_hint describing which tool to call. Read-only — does not modify any data."
    ),
    category="oppm",
    params=[],
    handler=_validate_oppm,
))


async def _renumber_oppm_tasks(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Rebuild Task.sort_order so root tasks get 1..N (in current order) and
    sub-tasks get 1..M within each parent. Stable: preserves the existing order
    determined by current (sort_order, created_at).

    The OPPM form derives task numbers from this order — flat root index for
    main tasks, and "{parent_index}.{sub_index}" for sub-tasks. After running
    this, gaps and duplicates in the visible numbering are gone.
    """
    tasks = (await session.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.sort_order, Task.created_at)
    )).scalars().all()
    if not tasks:
        return ToolResult(success=True, result={"updated": 0, "root_tasks": 0})

    by_id = {t.id: t for t in tasks}
    root_tasks = [t for t in tasks if t.parent_task_id is None]
    children_by_parent: dict = {}
    for t in tasks:
        if t.parent_task_id is not None and t.parent_task_id in by_id:
            children_by_parent.setdefault(t.parent_task_id, []).append(t)

    # Stable ordering already applied by query; assign sequential sort_order.
    updated = 0
    for idx, root in enumerate(root_tasks, start=1):
        if root.sort_order != idx:
            await session.execute(
                update(Task).where(Task.id == root.id).values(sort_order=idx)
            )
            updated += 1
        kids = children_by_parent.get(root.id, [])
        for sub_idx, child in enumerate(kids, start=1):
            if child.sort_order != sub_idx:
                await session.execute(
                    update(Task).where(Task.id == child.id).values(sort_order=sub_idx)
                )
                updated += 1

    # Tasks whose parent_task_id points to a missing/foreign row — leave alone
    # but report so the agent can decide whether to delete or re-parent them.
    orphans = [
        t for t in tasks
        if t.parent_task_id is not None and t.parent_task_id not in by_id
    ]

    return ToolResult(
        success=True,
        result={
            "updated": updated,
            "root_tasks": len(root_tasks),
            "orphans": len(orphans),
        },
        updated_entities=["tasks"],
    )


_registry.register(ToolDefinition(
    name="renumber_oppm_tasks",
    description=(
        "Rebuild Task.sort_order so root tasks number 1..N and sub-tasks number "
        "1..M within their parent (preserving current order). Use this to fix "
        "duplicate or gap-ridden task numbering in the OPPM. No-op when "
        "numbering is already contiguous."
    ),
    category="oppm",
    params=[],
    handler=_renumber_oppm_tasks,
))


# ─── Border editing tool ─────────────────────────────────────────────────────

_STYLE_MAP = {
    "thin": 1,
    "hair": 2,
    "dotted": 3,
    "dashed": 4,
    "medium_dash_dot": 5,
    "medium": 8,
    "double": 7,
    "thick": 9,
    "medium_dashed": 10,
    "slant_dash_dot": 11,
    "none": 0,
}

_SIDE_MAP = {"top": "t", "bottom": "b", "left": "l", "right": "r"}


def _parse_a1_range(range_str: str) -> tuple[int, int, int, int]:
    """Convert A1 notation like 'A1:AL10' to 0-indexed (r1, r2, c1, c2).
    Supports single cells ('B5') and ranges ('A1:D4')."""
    import re

    def _col_to_index(col: str) -> int:
        idx = 0
        for ch in col.upper():
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx - 1  # 0-indexed

    def _parse_cell(cell: str) -> tuple[int, int]:
        m = re.match(r"^([A-Z]+)(\d+)$", cell.upper().strip())
        if not m:
            raise ValueError(f"Invalid cell reference: {cell}")
        return int(m.group(2)) - 1, _col_to_index(m.group(1))

    if ":" in range_str:
        start, end = range_str.split(":", 1)
        r1, c1 = _parse_cell(start.strip())
        r2, c2 = _parse_cell(end.strip())
        return min(r1, r2), max(r1, r2), min(c1, c2), max(c1, c2)
    else:
        r, c = _parse_cell(range_str.strip())
        return r, r, c, c


async def _set_sheet_border(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    """Apply border overrides to a cell range in the OPPM FortuneSheet.

    Parameters:
      - cell_range: A1 notation, e.g. "A1:AL1" or "H6"
      - borders: dict of sides to modify, each with { style, color? }
        e.g. { "bottom": { "style": "thick", "color": "#000000" } }
    """
    range_str = tool_input.get("cell_range", "")
    borders_spec = tool_input.get("borders", {})
    if not range_str or not borders_spec:
        return ToolResult(success=False, error="cell_range and borders are required")

    try:
        r1, r2, c1, c2 = _parse_a1_range(range_str)
    except ValueError as e:
        return ToolResult(success=False, error=f"Invalid cell_range: {e}")

    repo = BorderOverrideRepository(session)
    written = 0
    cleared = 0

    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            for side_key, side_spec in borders_spec.items():
                side = side_key.lower()
                if side not in _SIDE_MAP:
                    continue
                style = (side_spec.get("style") or "thin").lower()
                color = side_spec.get("color") or "#000000"
                if style == "none":
                    # Delete override for this side
                    stmt = (
                        delete(OPPMBorderOverride)
                        .where(
                            OPPMBorderOverride.project_id == project_id,
                            OPPMBorderOverride.cell_row == r,
                            OPPMBorderOverride.cell_col == c,
                            OPPMBorderOverride.side == side,
                        )
                    )
                    result = await session.execute(stmt)
                    cleared += result.rowcount or 0
                else:
                    await repo.upsert(
                        project_id=project_id,
                        workspace_id=workspace_id,
                        cell_row=r,
                        cell_col=c,
                        side=side,
                        style=style,
                        color=color,
                        created_by=user_id,
                    )
                    written += 1

    await session.flush()
    return ToolResult(
        success=True,
        result={
            "range": range_str,
            "rows": r2 - r1 + 1,
            "cols": c2 - c1 + 1,
            "overrides_written": written,
            "overrides_cleared": cleared,
        },
        updated_entities=["oppm_border_overrides"],
    )


_registry.register(ToolDefinition(
    name="set_sheet_border",
    description="Apply or remove cell borders in the OPPM FortuneSheet. Use A1 notation for cell_range. Styles: thin, medium, thick, dashed, dotted, none. Colors are hex strings (e.g. #000000). Only the specified sides are modified — others are left untouched.",
    category="oppm",
    params=[
        ToolParam("cell_range", "string", "A1 notation range, e.g. 'A1:AL1' or 'H6'", required=True),
        ToolParam("borders", "object", "Dict of sides: { top?: {style, color?}, bottom?: {...}, left?: {...}, right?: {...} }. Use style='none' to remove a side.", required=True),
    ],
    handler=_set_sheet_border,
))
