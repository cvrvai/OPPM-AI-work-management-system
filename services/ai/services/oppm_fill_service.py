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
from shared.models.project import Project
from shared.models.workspace import WorkspaceMember

logger = logging.getLogger(__name__)


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
            select(WorkspaceMember).where(WorkspaceMember.id == project.lead_id).limit(1)
        )
        member = member_result.scalar_one_or_none()
        if member:
            lead_name = member.display_name

    # ── Structured fills (no LLM) ─────────────────────────────
    fills: dict[str, str | None] = {
        "project_name": project.title,
        "project_leader": lead_name,
        "start_date": str(project.start_date) if project.start_date else None,
        "deadline": str(project.deadline) if project.deadline else None,
        "project_objective": project.objective_summary,
        "deliverable_output": project.deliverable_output,
    }

    # If both text fields already have content, skip the LLM call
    if fills["project_objective"] and fills["deliverable_output"]:
        return fills

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

    return fills
