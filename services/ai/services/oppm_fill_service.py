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
_DEFAULT_OLLAMA_MODEL_ID = "gemma4:31b-cloud"


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
        models.sort(key=lambda current_model: current_model.model_id != _DEFAULT_OLLAMA_MODEL_ID)

    serialized = [
        {
            "id": str(m.id),
            "provider": m.provider,
            "model_id": m.model_id,
            "api_key": None,
            "base_url": m.endpoint_url,
            "name": m.name,
            "endpoint_url": m.endpoint_url,
            "is_active": m.is_active,
        }
        for m in models
    ]

    if not serialized:
        from config import get_settings as get_ai_settings
        ollama_url = get_ai_settings().ollama_url
        serialized = [
            {
                "id": "default-ollama",
                "provider": "ollama",
                "model_id": _DEFAULT_OLLAMA_MODEL_ID,
                "api_key": None,
                "base_url": ollama_url,
                "endpoint_url": ollama_url,
                "name": "Ollama (default)",
                "is_active": True,
            }
        ]
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

    # ── Build OPPM task list: objectives as main-task rows, root tasks as sub-rows ──
    # Template layout:  Row N   = "X. <Objective title>"  (is_sub=False)
    #                   Row N+1 = "X.1 <Task title>"      (is_sub=True)
    #                   Row N+2 = "X.2 <Task title>"      (is_sub=True)
    # Only the first 3 root tasks per objective are shown (template has 3 sub-rows each).
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

    # Fallback behavior:
    # - If objective-linked tasks are missing, pull from project tasks that are not linked
    #   to any objective (common in board-only task management).
    # - If there are fewer than 4 objectives, synthesize remaining "Task Group" rows
    #   so tasks still appear instead of leaving template placeholders.
    objective_ids = {str(obj.id) for obj in objectives}
    unassigned_root_tasks = sorted(
        [
            task
            for task in all_tasks
            if task.parent_task_id is None
            and (
                task.oppm_objective_id is None
                or str(task.oppm_objective_id) not in objective_ids
            )
        ],
        key=lambda task: (task.sort_order or 0, str(task.created_at)),
    )
    unassigned_cursor = 0

    def _take_unassigned(limit: int) -> list[Task]:
        nonlocal unassigned_cursor
        taken: list[Task] = []
        while unassigned_cursor < len(unassigned_root_tasks) and len(taken) < limit:
            taken.append(unassigned_root_tasks[unassigned_cursor])
            unassigned_cursor += 1
        return taken

    rendered_main_rows = 0

    for obj_idx, obj in enumerate(objectives[:4]):
        # Main task row: the objective itself
        task_items.append({
            "index": str(obj_idx + 1),
            "title": obj.title,
            "deadline": None,
            "status": None,
            "is_sub": False,
            "sub_objective_positions": [],
            "owners": [],
            "timeline": [],
        })
        rendered_main_rows += 1

        # Sub-task rows: first 3 root tasks of this objective (template has 3 sub-rows per main-task slot)
        obj_root = sorted(
            [
                task
                for task in all_tasks
                if str(task.oppm_objective_id) == str(obj.id) and task.parent_task_id is None
            ],
            key=lambda task: (task.sort_order or 0, str(task.created_at)),
        )[:3]

        selected_sub_tasks: list[Task] = list(obj_root)
        if not selected_sub_tasks:
            flat_tasks = sorted(
                [task for task in all_tasks if str(task.oppm_objective_id) == str(obj.id)],
                key=lambda task: (task.sort_order or 0, str(task.created_at)),
            )[:3]
            selected_sub_tasks = list(flat_tasks)

        if len(selected_sub_tasks) < 3:
            selected_sub_tasks.extend(_take_unassigned(3 - len(selected_sub_tasks)))

        for sub_idx, task in enumerate(selected_sub_tasks[:3], 1):
            task_items.append({
                "index": f"{obj_idx + 1}.{sub_idx}",
                "title": task.title,
                "deadline": _fmt(task.due_date),
                "status": task.status,
                "is_sub": True,
                "sub_objective_positions": sub_objective_positions_by_task.get(str(task.id), []),
                "owners": _get_task_owners(task),
                "timeline": timeline_by_task.get(str(task.id), []),
            })

    while rendered_main_rows < 4 and unassigned_cursor < len(unassigned_root_tasks):
        main_idx = rendered_main_rows + 1
        task_items.append({
            "index": str(main_idx),
            "title": f"Task Group {main_idx}",
            "deadline": None,
            "status": None,
            "is_sub": False,
            "sub_objective_positions": [],
            "owners": [],
            "timeline": [],
        })
        rendered_main_rows += 1

        for sub_idx, task in enumerate(_take_unassigned(3), 1):
            task_items.append({
                "index": f"{main_idx}.{sub_idx}",
                "title": task.title,
                "deadline": _fmt(task.due_date),
                "status": task.status,
                "is_sub": True,
                "sub_objective_positions": sub_objective_positions_by_task.get(str(task.id), []),
                "owners": _get_task_owners(task),
                "timeline": timeline_by_task.get(str(task.id), []),
            })

    # If both text fields already have content, skip the LLM call
    if fills["project_objective"] and fills["deliverable_output"]:
        return {"fills": fills, "tasks": task_items, "members": member_items}

    # ── LLM call to generate missing text fields ───────────────
    models = await _get_models(session, workspace_id, model_id)

    prompt = f"""You are an expert project manager using the One Page Project Manager (OPPM) methodology.
Given the project information below, write concise, professional text for the two OPPM header fields.

Project Title: {project.title}
Description: {project.description or "Not provided"}
Start Date: {fills["start_date"] or "Not set"}
Deadline: {fills["deadline"] or "Not set"}
Current Objective: {fills["project_objective"] or "Not set"}
Current Deliverable Output: {fills["deliverable_output"] or "Not set"}

Return ONLY valid JSON with exactly these two keys:
{{
  "project_objective": "One sentence describing what this project aims to achieve.",
  "deliverable_output": "One sentence describing the tangible output/result of this project."
}}

Rules:
- If the current value is already good, return it unchanged.
- Keep each text under 120 characters.
- Be specific and professional."""

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

    return {"fills": fills, "tasks": task_items, "members": member_items}
