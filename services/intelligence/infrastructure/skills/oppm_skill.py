"""OPPM Skill — specialist agent for filling and updating OPPM forms.

This skill wraps the existing TAOR loop with:
  - a domain-specific system prompt (OPPM methodology rules)
  - filtered tool list (only oppm / task / cost / read categories)
  - pre_flight hook that bulk-loads project context to save tool calls
  - post_flight hook that pushes results to Google Sheets

Usage:
    from infrastructure.skills import SKILL_REGISTRY
    skill = SKILL_REGISTRY.get("oppm")
    ctx = SkillContext(project_id=..., workspace_id=..., user_id=...)
    preflight = await skill.pre_flight(session, ctx)
    # ... run agent loop with skill.system_prompt + filtered tools ...
    result = await skill.post_flight(session, ctx, skill_result)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.skills.base import Skill, SkillContext, SkillResult
from shared.models.project import Project
from shared.models.task import Task, TaskOwner
from shared.models.oppm import (
    OPPMHeader,
    OPPMObjective,
    OPPMSubObjective,
    OPPMTimelineEntry,
    OPPMRisk,
    OPPMForecast,
    ProjectCost,
)
from shared.models.user import User
from shared.models.workspace import WorkspaceMember

logger = logging.getLogger(__name__)

# ── System Prompt ───────────────────────────────────────────────────────────

_OPPM_SYSTEM_PROMPT = """\
You are the OPPM (One Page Project Manager) specialist.

You know Clark Campbell's OPPM methodology — five essential elements:
1. Tasks — major work items (numbered 1-N, plus lettered sub-objective rows A-F)
2. Objectives — strategic goals each task contributes to
3. Timeline — week-by-week date grid with dot markers per task
4. Owners — A/B/C priority letters mapping people to tasks
5. Costs — bar charts in the bottom-right quadrant

Plus two cross-cutting concerns: Risk (bottom rows) and Quality (dot colors).

## STEP 0 — Always start by validating

Before doing anything else, call `validate_oppm`. The result tells you exactly
which fields are missing or broken and which tool to call to fix each one
(every issue includes a `fix_hint`). Use that issue list as your work plan:

- **Repair mode** (when the form is partially populated and the user said
  "fix" / "repair" / "broken"): only address issues from `validate_oppm`. Do
  not regenerate fields that already look right.
- **Fill mode** (empty or near-empty form): work through the priority order
  below, but still call `validate_oppm` first so you know what's already there.

If `validate_oppm` reports `duplicate_sort_order` or `sort_order_gaps`, call
`renumber_oppm_tasks` BEFORE writing timeline / owners / sub-objective links —
otherwise you'll be writing data tied to row numbers the user is about to see
shift.

## When asked to FILL or UPDATE an OPPM, follow this priority order:

1. Generate any missing header text (project_objective, deliverable_output,
   completed_by_text). Keep each under 120 characters.

2. For each task: derive timeline status per week.
   - Task.status = "todo"        → "planned"     (◻)
   - Task.status = "in_progress" → "in_progress" (●)
   - Task.status = "done"        → "completed"   (■)
   - Task overdue + not done     → "at_risk"     (▲)
   - Task with blocker dependency→ "blocked"     (✕)
   Prefer `derive_timeline_from_task_status` (one call) over per-week tool
   calls. Use `bulk_set_timeline` only when you need finer control.

3. Link each task to the sub-objectives it contributes to (max 6, A-F).
   Call `link_task_sub_objectives` with the task_id and a list of positions.

4. Assign owners + priority letters: A=primary, B=primary helper, C=secondary.
   Call `set_task_owner` once per (task, member, priority).

5. Populate risks if the project notes mention risk language.
   Call `upsert_risk` for each risk row.

6. Populate costs if budget data is available.
   Call `upsert_cost` for each cost entry.

7. NEVER invent dates, names, or task titles not present in the input data.

## Variant awareness
If the project metadata contains `oppm_variant = "agile"`, use vision/feature-set
language instead of objective/sub-objective. Default to Traditional otherwise.

## Tool calling discipline
- When the user asks to fill, update, or repair the OPPM, ALWAYS use tools.
  Do NOT describe what you "will do" in text without calling tools.
- Use `derive_timeline_from_task_status` (fill_full_range=true) for the
  one-shot timeline fill. Per-task `bulk_set_timeline` is only for overrides.
- Use `link_task_sub_objectives` to batch-link tasks to sub-objectives.
- After completing all writes, briefly confirm what changed and what (if
  anything) is still missing per the latest validation.

## Border editing rules

When the user asks to modify cell borders (e.g. "make the header row have a
thick bottom border", "add a red border around the risk section", or
"remove the grid lines from the legend"), call `set_sheet_border`.

### Parameters
- cell_range: A1 notation range, e.g. "A1:AL1" (header row), "H6:H10" (task rows),
  or "A30:F35" (bottom section). Single cells like "B5" are also valid.
- borders: Object specifying which sides to modify. Each side is optional:
  { top?: { style, color? }, bottom?: { style, color? },
    left?: { style, color? }, right?: { style, color? } }

### Style values
- "thin"    → style: 1  (default for internal grid lines)
- "medium"  → style: 8  (default for section dividers in OPPM)
- "thick"   → style: 9  (use for emphasis, outer frames, header emphasis)
- "dashed"  → style: 4  (use for temporary / draft / placeholder areas)
- "dotted"  → style: 3  (use for subtle separators)
- "none"    → style: 0  (removes the border on that side)

### Color values
- "#000000" → black (default for structural borders)
- "#CCCCCC" → light gray (subtle dividers, secondary grid)
- "#FF0000" → red (highlighting issues, at-risk markers)
- "#1D9E75" → green (on-track emphasis)
- "#EF9F27" → yellow (warning emphasis)

### Important notes
- Row and column indexes in cell_range are 1-based (A1 = row 0, col 0 internally).
  The tool converts A1 notation to 0-indexed coordinates automatically.
- Only specify the sides you want to CHANGE — unspecified sides are left untouched.
- To REMOVE a border side, set its style to "none".
- After inserting new rows, ALWAYS re-apply borders to maintain visual consistency.
- The OPPM scaffold already has borders; use this tool for ADDITIONAL emphasis
  or CORRECTIONS requested by the user.
- Common patterns:
  * Thick bottom border on header row: `set_sheet_border("A1:AL1", { bottom: { style: "thick" } })`
  * Red frame around risk section: `set_sheet_border("A25:AL28", { top: { style: "thick", color: "#FF0000" }, bottom: { style: "thick", color: "#FF0000" }, left: { style: "thick", color: "#FF0000" }, right: { style: "thick", color: "#FF0000" } })`
  * Remove grid from legend: `set_sheet_border("AJ6:AL10", { top: { style: "none" }, bottom: { style: "none" }, left: { style: "none" }, right: { style: "none" } })`
"""

# ── Pre-flight: bulk-load project context ───────────────────────────────────


async def _load_project(session: AsyncSession, project_id: str, workspace_id: str) -> dict[str, Any]:
    result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        ).limit(1)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project {project_id} not found in workspace {workspace_id}")

    lead_name = None
    if project.lead_id:
        member_result = await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.id == project.lead_id)
            .limit(1)
        )
        lead_row = member_result.first()
        if lead_row:
            wm, user = lead_row
            lead_name = wm.display_name or user.full_name or user.email.split("@", 1)[0]

    return {
        "id": str(project.id),
        "title": project.title,
        "description": project.description,
        "start_date": str(project.start_date) if project.start_date else None,
        "deadline": str(project.deadline) if project.deadline else None,
        "lead_id": str(project.lead_id) if project.lead_id else None,
        "lead_name": lead_name,
        "objective_summary": project.objective_summary,
        "deliverable_output": project.deliverable_output,
        "status": project.status,
        "metadata": dict(project.metadata_ or {}),
    }


async def _load_header(session: AsyncSession, project_id: str, workspace_id: str) -> dict[str, Any] | None:
    """Load the OPPMHeader row, if any.

    NOTE: project_objective and deliverable_output live on the projects table,
    NOT on OPPMHeader (see shared/models/oppm.py:132). Don't reach for them
    here — the preflight already pulls them via _load_project.
    """
    result = await session.execute(
        select(OPPMHeader).where(
            OPPMHeader.project_id == project_id,
            OPPMHeader.workspace_id == workspace_id,
        ).limit(1)
    )
    header = result.scalar_one_or_none()
    if not header:
        return None
    return {
        "project_leader_text": header.project_leader_text,
        "completed_by_text": header.completed_by_text,
        "people_count": header.people_count,
    }


async def _load_objectives(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        select(OPPMObjective)
        .where(OPPMObjective.project_id == project_id)
        .order_by(OPPMObjective.sort_order, OPPMObjective.created_at)
    )
    return [
        {
            "id": str(obj.id),
            "title": obj.title,
            "sort_order": obj.sort_order,
        }
        for obj in result.scalars().all()
    ]


async def _load_sub_objectives(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        select(OPPMSubObjective)
        .where(OPPMSubObjective.project_id == project_id)
        .order_by(OPPMSubObjective.position)
    )
    return [
        {
            "id": str(so.id),
            "label": so.label,
            "position": so.position,
        }
        for so in result.scalars().all()
    ]


async def _load_tasks(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.sort_order, Task.created_at)
    )
    tasks = list(result.scalars().all())
    task_ids = [t.id for t in tasks]

    # Load owners
    owners_by_task: dict[str, list[dict]] = {}
    if task_ids:
        owner_result = await session.execute(
            select(TaskOwner.task_id, TaskOwner.member_id, TaskOwner.priority)
            .where(TaskOwner.task_id.in_(task_ids))
        )
        for row in owner_result.all():
            tid = str(row.task_id)
            owners_by_task.setdefault(tid, []).append({
                "member_id": str(row.member_id),
                "priority": row.priority,
            })

    # Load timeline entries
    timeline_by_task: dict[str, list[dict]] = {}
    if task_ids:
        tl_result = await session.execute(
            select(
                OPPMTimelineEntry.task_id,
                OPPMTimelineEntry.week_start,
                OPPMTimelineEntry.status,
                OPPMTimelineEntry.quality,
            )
            .where(OPPMTimelineEntry.task_id.in_(task_ids))
            .order_by(OPPMTimelineEntry.week_start)
        )
        for row in tl_result.all():
            tid = str(row.task_id)
            timeline_by_task.setdefault(tid, []).append({
                "week_start": row.week_start.isoformat(),
                "status": row.status,
                "quality": row.quality,
            })

    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "due_date": str(t.due_date) if t.due_date else None,
            "start_date": str(t.start_date) if t.start_date else None,
            "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
            "sort_order": t.sort_order,
            "owners": owners_by_task.get(str(t.id), []),
            "timeline": timeline_by_task.get(str(t.id), []),
        }
        for t in tasks
    ]


async def _load_members(session: AsyncSession, project_id: str, workspace_id: str) -> list[dict[str, Any]]:
    # Try project members first
    from shared.models.project import ProjectMember
    pm_result = await session.execute(
        select(ProjectMember, WorkspaceMember, User)
        .join(WorkspaceMember, WorkspaceMember.id == ProjectMember.member_id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at, WorkspaceMember.display_name, User.full_name, User.email)
    )
    rows = pm_result.all()
    if not rows:
        # Fall back to all workspace members
        wm_result = await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at, User.full_name, User.email)
        )
        rows = wm_result.all()

    members: list[dict[str, Any]] = []
    for row in rows:
        if len(row) == 3:
            _, wm, user = row
        else:
            wm, user = row
        name = wm.display_name or user.full_name or user.email.split("@", 1)[0]
        members.append({
            "id": str(wm.id),
            "user_id": str(wm.user_id),
            "name": name,
        })
    return members


async def _load_risks(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        select(OPPMRisk).where(OPPMRisk.project_id == project_id)
    )
    return [
        {
            "id": str(r.id),
            "item_number": r.item_number,
            "description": r.description,
            "rag": r.rag,
        }
        for r in result.scalars().all()
    ]


async def _load_costs(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    result = await session.execute(
        select(ProjectCost).where(ProjectCost.project_id == project_id)
    )
    return [
        {
            "id": str(c.id),
            "category": c.category,
            "description": c.description,
            "planned_amount": float(c.planned_amount) if c.planned_amount is not None else None,
            "actual_amount": float(c.actual_amount) if c.actual_amount is not None else None,
            "period": c.period,
        }
        for c in result.scalars().all()
    ]


async def _load_border_overrides(session: AsyncSession, project_id: str) -> list[dict[str, Any]]:
    from domains.analysis.oppm_repository import BorderOverrideRepository
    repo = BorderOverrideRepository(session)
    rows = await repo.find_by_project(project_id)
    return [
        {
            "cell_row": r.cell_row,
            "cell_col": r.cell_col,
            "side": r.side,
            "style": r.style,
            "color": r.color,
        }
        for r in rows
    ]


async def oppm_preflight(session: AsyncSession, ctx: SkillContext) -> dict[str, Any]:
    """Bulk-load all OPPM-relevant data in one shot.

    Returns a dict that is injected into the agent's context as a
    "## Project Snapshot" block so the LLM doesn't waste tool calls re-reading.
    """
    project_id = ctx.project_id
    workspace_id = ctx.workspace_id

    project = await _load_project(session, project_id, workspace_id)
    header = await _load_header(session, project_id, workspace_id)
    objectives = await _load_objectives(session, project_id)
    sub_objectives = await _load_sub_objectives(session, project_id)
    tasks = await _load_tasks(session, project_id)
    members = await _load_members(session, project_id, workspace_id)
    risks = await _load_risks(session, project_id)
    costs = await _load_costs(session, project_id)
    border_overrides = await _load_border_overrides(session, project_id)

    # Build a compact snapshot string for the LLM
    snapshot_lines = [
        f"## Project Snapshot ({date.today().isoformat()})",
        f"Project: {project['title']}",
        f"Leader: {project['lead_name'] or '—'}",
        f"Dates: {project['start_date'] or '?'} → {project['deadline'] or '?'}",
        f"Status: {project['status']}",
        f"Variant: {project['metadata'].get('oppm_variant', 'traditional')}",
        "",
        f"Objectives ({len(objectives)}):",
    ]
    for obj in objectives:
        snapshot_lines.append(f"  - {obj['title']}")

    snapshot_lines.extend([
        "",
        f"Sub-Objectives ({len(sub_objectives)}):",
    ])
    for so in sub_objectives:
        snapshot_lines.append(f"  {so['position']}. {so['label']}")

    snapshot_lines.extend([
        "",
        f"Tasks ({len(tasks)}):",
    ])
    for t in tasks:
        deadline = f" (due {t['due_date']})" if t['due_date'] else ""
        snapshot_lines.append(f"  - {t['title']}{deadline} [{t['status']}]")

    snapshot_lines.extend([
        "",
        f"Team ({len(members)}):",
    ])
    for m in members:
        snapshot_lines.append(f"  - {m['name']} ({m['id']})")

    if risks:
        snapshot_lines.extend(["", f"Risks ({len(risks)}):"])
        for r in risks:
            snapshot_lines.append(f"  - Risk {r['item_number']}: {r['description']} [{r['rag']}]")

    if costs:
        snapshot_lines.extend(["", f"Costs ({len(costs)}):"])
        for c in costs:
            planned = c.get('planned_amount')
            actual = c.get('actual_amount')
            period = c.get('period')
            amount_str = f"planned={planned}" if planned is not None else ""
            if actual is not None:
                amount_str += f" actual={actual}"
            if period:
                amount_str += f" ({period})"
            snapshot_lines.append(f"  - {c['category']}: {amount_str or 'no amount'}")

    if border_overrides:
        snapshot_lines.extend(["", f"Border overrides ({len(border_overrides)}):"])
        for bo in border_overrides[:10]:
            snapshot_lines.append(
                f"  - Cell ({bo['cell_row']},{bo['cell_col']}) {bo['side']}: "
                f"{bo['style']} {bo['color']}"
            )
        if len(border_overrides) > 10:
            snapshot_lines.append(f"  ... and {len(border_overrides) - 10} more")

    snapshot = "\n".join(snapshot_lines)

    return {
        "project": project,
        "header": header,
        "objectives": objectives,
        "sub_objectives": sub_objectives,
        "tasks": tasks,
        "members": members,
        "risks": risks,
        "costs": costs,
        "border_overrides": border_overrides,
        "today": date.today().isoformat(),
        "snapshot_text": snapshot,
    }


# ── Post-flight: push to Google Sheets ──────────────────────────────────────


async def oppm_postflight(
    session: AsyncSession,
    ctx: SkillContext,
    skill_result: SkillResult,
) -> dict[str, Any]:
    """After a successful OPPM skill run, push updated data to Google Sheets.

    Only pushes if the agent actually mutated OPPM-related entities.
    """
    updated = set(skill_result.updated_entities)
    oppm_entities = {
        "oppm_timeline_entries",
        "oppm_header",
        "task_owners",
        "oppm_objectives",
        "oppm_sub_objectives",
        "oppm_risks",
        "oppm_forecasts",
        "project_costs",
        "oppm_border_overrides",
    }
    if not updated & oppm_entities:
        logger.info("OPPM post-flight: no OPPM entities updated — skipping sheet push")
        return {"pushed": False, "reason": "no_oppm_changes"}

    # NOTE: Sheet push is handled by the frontend calling the workspace service
    # directly. The intelligence service does not have access to the workspace
    # service's google_sheets module. Return a marker so the frontend knows
    # the DB writes succeeded and can trigger the push separately.
    logger.info(
        "OPPM post-flight: DB writes complete for project=%s — "
        "frontend should call /oppm/google-sheet/push to sync to Sheets",
        ctx.project_id,
    )
    return {
        "pushed": False,
        "reason": "deferred_to_frontend",
        "note": "Agent fill completed. Call the existing push endpoint to sync to Google Sheets.",
    }


# ── Skill Manifest ──────────────────────────────────────────────────────────

OPPM_SKILL = Skill(
    name="oppm",
    description="Fills, updates, and reasons about One-Page Project Manager forms.",
    triggers=[
        "oppm",
        "one-page",
        "fill the form",
        "auto fill",
        "timeline status",
        "sub-objective",
        "milestone",
        "owner / priority",
        "completed by",
        "risk row",
        "forecast",
        "update the oppm",
        "populate oppm",
    ],
    tool_categories=["oppm", "task", "cost", "read"],
    extra_tool_names=[],
    system_prompt=_OPPM_SYSTEM_PROMPT,
    pre_flight=oppm_preflight,
    post_flight=oppm_postflight,
)
