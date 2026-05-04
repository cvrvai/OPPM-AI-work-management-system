"""
AI OPPM Fill Service — uses project data + LLM to suggest text values
for key OPPM spreadsheet cells (header fields, objective, deliverable).
"""

import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.llm import call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError
from shared.models.ai_model import AIModel
from shared.models.oppm import OPPMHeader, OPPMObjective, OPPMSubObjective, OPPMTimelineEntry, TaskSubObjective
from shared.models.project import Project, ProjectMember
from shared.models.task import Task, TaskOwner
from shared.models.user import User
from shared.models.workspace import WorkspaceMember

logger = logging.getLogger(__name__)

_FALLBACK_PRIORITY_ORDER = ("A", "B", "C")
_DEFAULT_MODEL_ID = "gemma4:31b-cloud"
_DEFAULT_PROVIDER = "ollama"


def _resolve_member_name(workspace_member: WorkspaceMember | None, user: User | None) -> str | None:
    if workspace_member and workspace_member.display_name:
        return workspace_member.display_name
    if user and user.full_name:
        return user.full_name
    if user and user.email:
        return user.email.split("@", 1)[0]
    return None


async def _get_models(session: AsyncSession, workspace_id: str, model_id: str | None = None) -> list[dict]:
    """Return ordered list of AI models for fallback. Reuses the same logic as ai_chat_service."""
    if model_id:
        primary = await session.execute(
            select(AIModel).where(AIModel.id == model_id, AIModel.workspace_id == workspace_id).limit(1)
        )
        others = await session.execute(
            select(AIModel).where(
                AIModel.workspace_id == workspace_id,
                AIModel.is_active == True,
                AIModel.id != model_id,
            )
        )
        models = list(primary.scalars().all()) + list(others.scalars().all())
    else:
        result = await session.execute(
            select(AIModel).where(AIModel.workspace_id == workspace_id, AIModel.is_active == True)
        )
        models = list(result.scalars().all())
        models.sort(key=lambda current_model: current_model.model_id != _DEFAULT_MODEL_ID)

    serialized = [
        {
            "id": str(m.id),
            "provider": m.provider,
            "model_id": m.model_id,
            "api_key": m.api_key,
            "base_url": m.endpoint_url,
            "name": m.name,
            "endpoint_url": m.endpoint_url,
            "is_active": m.is_active,
        }
        for m in models
    ]
    # Always append Ollama default as final fallback
    from config import get_settings as get_ai_settings
    serialized.append({
        "id": "default-ollama",
        "provider": _DEFAULT_PROVIDER,
        "model_id": _DEFAULT_MODEL_ID,
        "api_key": None,
        "base_url": get_ai_settings().ollama_url,
        "endpoint_url": get_ai_settings().ollama_url,
        "name": "Ollama (fallback)",
        "is_active": True,
    })
    return serialized


async def fill_oppm(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    model_id: str | None = None,
) -> dict:
    """
    Return suggested OPPM cell fills derived from project data + LLM.

    Structured fields (project_name, project_leader, start_date, deadline) come
    directly from the DB — no tokens spent.  The LLM is called only to generate
    or improve project_objective and deliverable_output.
    """
    # ── Load project ──────────────────────────────────────────
    result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        ).limit(1)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    header_result = await session.execute(
        select(OPPMHeader).where(
            OPPMHeader.project_id == project_id,
            OPPMHeader.workspace_id == workspace_id,
        ).limit(1)
    )
    header = header_result.scalar_one_or_none()

    # ── Load project leader name ───────────────────────────────
    lead_name: str | None = None
    if project.lead_id:
        member_result = await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.id == project.lead_id)
            .limit(1)
        )
        lead_row = member_result.first()
        if lead_row:
            lead_name = _resolve_member_name(lead_row[0], lead_row[1])

    # ── Structured fills (no LLM) ─────────────────────────────
    fills: dict[str, str | None] = {
        "project_name": project.title,
        "project_leader": lead_name or (header.project_leader_text if header else None),
        "project_leader_member_id": str(project.lead_id) if project.lead_id else None,
        "start_date": str(project.start_date) if project.start_date else None,
        "deadline": str(project.deadline) if project.deadline else None,
        "project_objective": project.objective_summary,
        "deliverable_output": project.deliverable_output,
        "completed_by_text": (
            header.completed_by_text
            if header and header.completed_by_text
            else (str(project.deadline) if project.deadline else None)
        ),
        "people_count": None,
    }

    # ── Load project members in owner-column order ─────────────
    pm_result = await session.execute(
        select(ProjectMember, WorkspaceMember, User)
        .join(WorkspaceMember, WorkspaceMember.id == ProjectMember.member_id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at, WorkspaceMember.display_name, User.full_name, User.email)
    )
    member_rows: list[dict[str, str]] = []
    for _, workspace_member, user in pm_result.all():
        member_rows.append({
            "id": str(workspace_member.id),
            "user_id": str(workspace_member.user_id),
            "name": _resolve_member_name(workspace_member, user) or "",
        })

    # If no explicit project members, fall back to all workspace members so the
    # owner columns are populated even for projects that haven't been staffed yet.
    if not member_rows:
        wm_result = await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at, User.full_name, User.email)
        )
        for workspace_member, user in wm_result.all():
            member_rows.append({
                "id": str(workspace_member.id),
                "user_id": str(workspace_member.user_id),
                "name": _resolve_member_name(workspace_member, user) or "",
            })

    lead_member_id = str(project.lead_id) if project.lead_id else None
    ordered_members: list[dict[str, str]] = []
    if lead_member_id:
        lead_member = next((member for member in member_rows if member["id"] == lead_member_id), None)
        if lead_member:
            ordered_members.append(lead_member)
    ordered_members.extend(member for member in member_rows if member["id"] != lead_member_id)
    if lead_member_id and lead_name and not any(member["id"] == lead_member_id for member in ordered_members):
        ordered_members.insert(0, {"id": lead_member_id, "name": lead_name})

    member_items = [
        {"id": member["id"], "slot": i, "name": member["name"]}
        for i, member in enumerate(ordered_members)
    ]
    fallback_owner_by_user_id: dict[str, dict[str, str]] = {}
    for index, member in enumerate(ordered_members):
        user_id = member.get("user_id")
        if not user_id:
            continue
        fallback_owner_by_user_id[user_id] = {
            "member_id": member["id"],
            "priority": _FALLBACK_PRIORITY_ORDER[index] if index < len(_FALLBACK_PRIORITY_ORDER) else "A",
        }
    default_people_count = len(member_items)
    if default_people_count == 0 and lead_name:
        default_people_count = 1
    fills["people_count"] = str(
        header.people_count if header and header.people_count is not None else default_people_count
    )

    # ── Load tasks hierarchically ──────────────────────────────
    # Load objectives for this project (ordered)
    obj_result = await session.execute(
        select(OPPMObjective)
        .where(OPPMObjective.project_id == project_id)
        .order_by(OPPMObjective.sort_order, OPPMObjective.created_at)
    )
    objectives = list(obj_result.scalars().all())

    # Load sub-objectives (for lettered milestone rows)
    so_result = await session.execute(
        select(OPPMSubObjective)
        .where(OPPMSubObjective.project_id == project_id)
        .order_by(OPPMSubObjective.position)
    )
    sub_objectives = list(so_result.scalars().all())

    # Load all tasks for this project
    task_result = await session.execute(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.sort_order, Task.created_at)
    )
    all_tasks = list(task_result.scalars().all())
    task_ids = [task.id for task in all_tasks]

    owners_by_task: dict[str, list[dict[str, str]]] = {str(task_id): [] for task_id in task_ids}
    if task_ids:
        owner_result = await session.execute(
            select(TaskOwner.task_id, TaskOwner.member_id, TaskOwner.priority)
            .where(TaskOwner.task_id.in_(task_ids))
        )
        for row in owner_result.all():
            owners_by_task[str(row.task_id)].append({
                "member_id": str(row.member_id),
                "priority": row.priority,
            })

    timeline_by_task: dict[str, list[dict[str, str | None]]] = {str(task_id): [] for task_id in task_ids}
    if task_ids:
        timeline_result = await session.execute(
            select(
                OPPMTimelineEntry.task_id,
                OPPMTimelineEntry.week_start,
                OPPMTimelineEntry.status,
                OPPMTimelineEntry.quality,
            )
            .where(OPPMTimelineEntry.task_id.in_(task_ids))
            .order_by(OPPMTimelineEntry.week_start)
        )
        for row in timeline_result.all():
            timeline_by_task[str(row.task_id)].append({
                "week_start": row.week_start.isoformat(),
                "status": row.status,
                "quality": row.quality,
             })

    sub_objective_positions_by_task: dict[str, list[int]] = {str(task_id): [] for task_id in task_ids}
    if task_ids:
        sub_objective_result = await session.execute(
            select(TaskSubObjective.task_id, OPPMSubObjective.position)
            .join(OPPMSubObjective, OPPMSubObjective.id == TaskSubObjective.sub_objective_id)
            .where(TaskSubObjective.task_id.in_(task_ids))
            .order_by(OPPMSubObjective.position)
        )
        for row in sub_objective_result.all():
            position = int(row.position)
            if 1 <= position <= 6:
                sub_objective_positions_by_task[str(row.task_id)].append(position)

    # ── Build OPPM task list: flat numbered tasks + lettered sub-objective rows ──
    # Classic OPPM layout:
    #   Rows 1–N   = numbered work tasks (flat list, all root tasks)
    #   Rows A–F   = sub-objective / milestone rows (lettered, below tasks)
    task_items: list[dict] = []

    def _fmt(d) -> str | None:
        return d.isoformat() if d else None

    def _get_task_owners(task: Task) -> list[dict[str, str]]:
        explicit_owners = owners_by_task.get(str(task.id), [])
        if explicit_owners:
            return explicit_owners
        if task.assignee_id:
            fallback_owner = fallback_owner_by_user_id.get(str(task.assignee_id))
            if fallback_owner:
                return [fallback_owner]
        return []

    # Flatten all root tasks into a single numbered list (classic OPPM major tasks)
    root_tasks = sorted(
        [task for task in all_tasks if task.parent_task_id is None],
        key=lambda task: (task.sort_order or 0, str(task.created_at)),
    )

    for idx, task in enumerate(root_tasks, 1):
        task_items.append({
            "index": str(idx),
            "title": task.title,
            "deadline": _fmt(task.due_date),
            "status": task.status,
            "is_sub": False,
            "sub_objective_positions": sub_objective_positions_by_task.get(str(task.id), []),
            "owners": _get_task_owners(task),
            "timeline": timeline_by_task.get(str(task.id), []),
        })

    # Lettered sub-objective rows (A–F) — qualitative milestones from sub-objective labels
    sub_obj_labels = [""] * 6
    for so in sub_objectives:
        pos = int(so.position) - 1
        if 0 <= pos < 6:
            sub_obj_labels[pos] = so.label

    letter_labels = ["A", "B", "C", "D", "E", "F"]
    for i, label in enumerate(sub_obj_labels):
        if not label:
            continue
        task_items.append({
            "index": letter_labels[i],
            "title": label,
            "deadline": None,
            "status": None,
            "is_sub": False,
            "sub_objective_positions": [],
            "owners": [],
            "timeline": [],
        })

    # If all three generated text fields already have content, skip the LLM call
    if fills["project_objective"] and fills["deliverable_output"] and fills["completed_by_text"]:
        return {"fills": fills, "tasks": task_items, "members": member_items}

    # ── LLM call to generate missing text fields ───────────────
    models = await _get_models(session, workspace_id, model_id)

    prompt = f"""You are an OPPM (One Page Project Manager) form-filling assistant.
Read the project data below and return a JSON object with exactly three fields.
Use ONLY the data provided — never invent information not present in the input.

== PROJECT DATA ==
Project Title    : {project.title}
Description      : {project.description or "Not provided"}
Start Date       : {fills["start_date"] or "Not set"}
Deadline         : {fills["deadline"] or "Not set"}
Team size        : {len(member_items)} member(s)
Current Objective: {fills["project_objective"] or "Not set"}
Current Deliverable Output: {fills["deliverable_output"] or "Not set"}
Current Completed-by text : {fills["completed_by_text"] or "Not set"}

Return ONLY valid JSON with exactly these three keys:
{{
  "project_objective":  "One sentence describing what this project aims to achieve.",
  "deliverable_output": "One sentence describing the tangible output/result of this project.",
  "completed_by_text":  "Duration string derived from start_date and deadline, e.g. '8 weeks' or '3 months'. Empty string if dates are missing."
}}

Rules:
- If a current value is already good, return it unchanged.
- Keep each text under 120 characters.
- Be specific and professional.
- completed_by_text: calculate the duration between start_date and deadline; if either is missing, use an empty string.
- Return ONLY the JSON object. No markdown fences, no explanation."""

    import re as _re
    import json as _json

    try:
        response = await call_with_fallback(models, prompt)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable for fill_oppm: %s", e)
        response = None
    except Exception as e:
        logger.warning("fill_oppm LLM call failed: %s", e)
        response = None

    result_json: dict | None = None
    if response:
        raw_text = response.text.strip()
        # Strip markdown fences then parse JSON
        clean = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=_re.DOTALL).strip()
        try:
            result_json = _json.loads(clean)
        except Exception:
            m = _re.search(r'\{[^{}]*"project_objective"[^{}]*\}', raw_text, _re.DOTALL)
            if m:
                try:
                    result_json = _json.loads(m.group())
                except Exception:
                    result_json = None

    if result_json:
        if not fills["project_objective"]:
            fills["project_objective"] = result_json.get("project_objective")
        if not fills["deliverable_output"]:
            fills["deliverable_output"] = result_json.get("deliverable_output")
        if not fills["completed_by_text"]:
            fills["completed_by_text"] = result_json.get("completed_by_text") or None

    return {"fills": fills, "tasks": task_items, "members": member_items}
