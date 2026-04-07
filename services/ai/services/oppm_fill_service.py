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
from shared.models.project import Project, ProjectMember
from shared.models.task import Task
from shared.models.oppm import OPPMObjective
from shared.models.user import User
from shared.models.workspace import WorkspaceMember

logger = logging.getLogger(__name__)


def _resolve_member_name(workspace_member: WorkspaceMember | None, user: User | None) -> str | None:
    if workspace_member and workspace_member.display_name:
        return workspace_member.display_name
    if user and user.full_name:
        return user.full_name
    if user and user.email:
        return user.email
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
                "model_id": "kimi-k2.5:cloud",
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
        "project_leader": lead_name,
        "start_date": str(project.start_date) if project.start_date else None,
        "deadline": str(project.deadline) if project.deadline else None,
        "project_objective": project.objective_summary,
        "deliverable_output": project.deliverable_output,
    }

    # ── Load workspace members on this project ─────────────────
    pm_result = await session.execute(
        select(WorkspaceMember, User)
        .join(ProjectMember, ProjectMember.member_id == WorkspaceMember.id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(WorkspaceMember.display_name)
    )
    ws_members = list(pm_result.all())
    member_items = [
        {"slot": i, "name": _resolve_member_name(workspace_member, user) or ""}
        for i, (workspace_member, user) in enumerate(ws_members)
    ]

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

    # ── Build OPPM task list: objectives as main-task rows, root tasks as sub-rows ──
    # Template layout:  Row N   = "X. <Objective title>"  (is_sub=False)
    #                   Row N+1 = "X.1 <Task title>"      (is_sub=True)
    #                   Row N+2 = "X.2 <Task title>"      (is_sub=True)
    # Only the first 3 root tasks per objective are shown (template has 3 sub-rows each).
    task_items: list[dict] = []

    def _fmt(d) -> str | None:
        return d.isoformat() if d else None

    for obj_idx, obj in enumerate(objectives[:4]):
        # Main task row: the objective itself
        task_items.append({
            "index": str(obj_idx + 1),
            "title": obj.title,
            "deadline": None,
            "is_sub": False,
        })
        # Sub-task rows: first 3 root tasks of this objective (template has 3 sub-rows per main-task slot)
        obj_root = sorted(
            [t for t in all_tasks
             if str(t.oppm_objective_id) == str(obj.id) and t.parent_task_id is None],
            key=lambda t: (t.sort_order or 0, str(t.created_at)),
        )[:3]
        for sub_idx, mt in enumerate(obj_root, 1):
            task_items.append({
                "index": f"{obj_idx + 1}.{sub_idx}",
                "title": mt.title,
                "deadline": _fmt(mt.due_date),
                "is_sub": True,
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
