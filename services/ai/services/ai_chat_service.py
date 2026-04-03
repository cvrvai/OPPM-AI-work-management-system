"""
AI Chat Service — Orchestrates LLM calls with OPPM project context.

Builds a system prompt with full project context (objectives, timeline, costs, team),
sends user messages to the configured LLM, parses tool calls from the response,
and executes them via the tool executor.
"""

import json
import logging
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.llm import get_adapter, call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError
from shared.models.ai_model import AIModel
from shared.models.workspace import WorkspaceMember
from repositories.oppm_repo import ObjectiveRepository, TimelineRepository, CostRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository
from services.oppm_tool_executor import execute_tool
from services import rag_service

logger = logging.getLogger(__name__)

# In-memory store for plan previews (simple approach; could use Redis/DB for production)
_plan_cache: dict[str, dict] = {}


async def _get_models(session: AsyncSession, workspace_id: str, model_id: str | None = None) -> list[dict]:
    """Return ordered list of AI models for fallback."""
    if model_id:
        primary = await session.execute(
            select(AIModel).where(AIModel.id == model_id, AIModel.workspace_id == workspace_id).limit(1)
        )
        others = await session.execute(
            select(AIModel).where(AIModel.workspace_id == workspace_id, AIModel.is_active == True, AIModel.id != model_id)
        )
        models = list(primary.scalars().all()) + list(others.scalars().all())
    else:
        result = await session.execute(
            select(AIModel).where(AIModel.workspace_id == workspace_id, AIModel.is_active == True)
        )
        models = list(result.scalars().all())
    return [{"id": str(m.id), "provider": m.provider, "model_id": m.model_id,
             "api_key": m.api_key, "base_url": m.base_url, "name": m.name,
             "is_active": m.is_active} for m in models]

SYSTEM_PROMPT = """You are OPPM AI, a project management assistant using the One Page Project Manager (OPPM) methodology.

The OPPM methodology applies to ANY industry — construction, architecture, finance, healthcare, IT, manufacturing, education, or any other field. All projects share universal elements: objectives, tasks, timelines, budgets, and team members.

## Current Project Context
{project_context}

{rag_context}

## Available Tools
When the user wants to make changes, include a JSON tool_calls array at the END of your message inside <tool_calls>...</tool_calls> tags.

Available tools:
- create_objective: {{"title": "...", "sort_order": N}}
- update_objective: {{"objective_id": "...", "title": "..."}}
- set_timeline_status: {{"objective_id": "...", "week_start": "YYYY-MM-DD", "status": "planned|in_progress|completed|at_risk|blocked"}}
- bulk_set_timeline: {{"entries": [{{"objective_id": "...", "week_start": "YYYY-MM-DD", "status": "..."}}]}}
- create_task: {{"title": "...", "description": "...", "priority": "low|medium|high|critical", "oppm_objective_id": "..."}}
- update_task: {{"task_id": "...", "status": "todo|in_progress|completed", "progress": N}}

Example:
<tool_calls>
[{{"tool": "set_timeline_status", "input": {{"objective_id": "abc-123", "week_start": "2026-04-06", "status": "completed"}}}}]
</tool_calls>

## Rules
1. Keep responses concise — max 3 sentences unless explaining a plan.
2. Always reference specific objective IDs and week dates when making changes.
3. If the user asks to update something, use an appropriate tool call.
4. For read-only questions (status, analysis), just respond conversationally.
5. When suggesting multiple changes, use bulk_set_timeline for efficiency.
6. Adapt terminology to the project's domain — use industry-appropriate language when relevant.
"""


async def _build_project_context(session: AsyncSession, project_id: str, workspace_id: str) -> str:
    """Build a text representation of the current project state for the LLM."""
    project_repo = ProjectRepository(session)
    objective_repo = ObjectiveRepository(session)
    timeline_repo = TimelineRepository(session)
    cost_repo = CostRepository(session)

    project = await project_repo.find_by_id(project_id)
    if not project:
        return "Project not found."

    objectives = await objective_repo.find_with_tasks(project_id)
    timeline = await timeline_repo.find_project_timeline(project_id)
    costs = await cost_repo.get_cost_summary(project_id)

    # Build timeline lookup
    tl_map: dict[str, dict[str, str]] = {}
    for entry in timeline:
        oid = str(entry.objective_id)
        if oid not in tl_map:
            tl_map[oid] = {}
        tl_map[oid][str(entry.week_start)] = entry.status

    # Get workspace members
    result = await session.execute(
        select(WorkspaceMember.user_id, WorkspaceMember.display_name, WorkspaceMember.email, WorkspaceMember.role)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    member_list = result.all()

    lines = [
        f'Project: "{project.title}"',
        f'Description: {project.description or "—"}',
        f'Status: {project.status} | Progress: {project.progress or 0}%',
        f'Start: {project.start_date or "—"} | Deadline: {project.deadline or "—"}',
        f'Today: {datetime.now().strftime("%Y-%m-%d")}',
        "",
        "## Objectives & Timeline",
    ]

    for obj in objectives:
        tl = tl_map.get(obj["id"], {})
        tl_str = ", ".join(f"{k}: {v}" for k, v in sorted(tl.items())) or "no timeline entries"
        task_count = len(obj.get("tasks", []))
        lines.append(f'- [{obj["id"]}] "{obj["title"]}" (tasks: {task_count})')
        lines.append(f'  Timeline: {tl_str}')

    if not objectives:
        lines.append("  No objectives defined yet.")

    lines.append("")
    lines.append(f"## Costs: Planned={costs['total_planned']}, Actual={costs['total_actual']}")

    lines.append("")
    lines.append("## Team Members")
    for m in member_list:
        name = m.display_name or m.email or str(m.user_id)[:8]
        lines.append(f'- {name} ({m.role})')

    return "\n".join(lines)


def _parse_tool_calls(text: str) -> tuple[str, list[dict]]:
    """Extract tool_calls JSON from the LLM response and return clean text + parsed calls."""
    import re
    match = re.search(r"<tool_calls>\s*(.*?)\s*</tool_calls>", text, re.DOTALL)
    if not match:
        return text.strip(), []

    clean_text = text[:match.start()].strip()
    try:
        calls = json.loads(match.group(1))
        if isinstance(calls, list):
            return clean_text, calls
    except json.JSONDecodeError:
        logger.warning("Failed to parse tool_calls JSON from LLM response")

    return clean_text, []


async def chat(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
) -> dict:
    """
    Send a chat message to the AI about a project.
    Returns the AI response message + any tool call results.
    """
    return await _chat_async(session, project_id, workspace_id, user_id, messages, model_id)


async def _chat_async(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
) -> dict:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    models = await _get_models(session, workspace_id, model_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    context = await _build_project_context(session, project_id, workspace_id)

    last_user_msg = messages[-1]["content"] if messages else ""
    try:
        rag_result = await rag_service.retrieve_with_rag_pipeline(
            session, workspace_id, last_user_msg, user_id=user_id, project_id=project_id,
        )
        rag_context = rag_result.context
        memory_context = rag_result.memory_context
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        rag_context = ""
        memory_context = ""

    full_rag = rag_context
    if memory_context:
        full_rag = f"{memory_context}\n\n{rag_context}"

    system_prompt = SYSTEM_PROMPT.format(project_context=context, rag_context=full_rag)

    conversation = f"System: {system_prompt}\n\n"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        conversation += f"{role.capitalize()}: {content}\n\n"
    conversation += "Assistant: "

    try:
        response = await call_with_fallback(models, conversation)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable. Please try again later.")
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    clean_text, tool_calls_raw = _parse_tool_calls(response.text)

    tool_results = []
    all_updated = set()
    for tc in tool_calls_raw:
        tool_name = tc.get("tool", "")
        tool_input = tc.get("input", {})
        result = await execute_tool(session, tool_name, tool_input, project_id, workspace_id, user_id)
        tool_results.append({
            "tool": tool_name,
            "input": tool_input,
            "result": result.get("result", {}),
            "success": result["success"],
            "error": result.get("error"),
        })
        all_updated.update(result.get("updated_entities", []))

    await audit_repo.log(
        workspace_id, user_id,
        "ai_chat", "chat",
        new_data={
            "project_id": project_id,
            "user_message": messages[-1]["content"] if messages else "",
            "ai_response": clean_text[:500],
            "tool_calls_count": len(tool_results),
        },
    )

    return {
        "message": clean_text,
        "tool_calls": tool_results,
        "updated_entities": list(all_updated),
    }


async def suggest_plan(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    description: str,
) -> dict:
    """Ask AI to generate an OPPM plan from a description. Returns a preview."""
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    models = await _get_models(session, workspace_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured.")

    prompt = f"""You are an OPPM project planning assistant. Generate a structured project plan.

Project: "{project.title}"
Start: {project.start_date or 'not set'}
Deadline: {project.deadline or 'not set'}
Description from user: {description}

Return ONLY valid JSON with this structure:
{{
  "objectives": [
    {{"title": "Objective name", "suggested_weeks": ["W1", "W2"]}}
  ],
  "explanation": "Brief explanation of the plan"
}}

Generate 3-7 objectives with logical week assignments. Use W1-W8 format."""

    try:
        result = await call_with_fallback(models, prompt, json_mode=True)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable for suggest_plan: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable.")
    except Exception as e:
        logger.warning("Suggest plan LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    if not result:
        raise HTTPException(status_code=502, detail="AI returned empty response")

    # Store preview with a commit token
    token = str(uuid.uuid4())
    _plan_cache[token] = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "objectives": result.get("objectives", []),
    }

    return {
        "suggested_objectives": result.get("objectives", []),
        "explanation": result.get("explanation", ""),
        "commit_token": token,
    }


async def commit_plan(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    commit_token: str,
) -> dict:
    """Commit a previously suggested plan — actually creates objectives and timeline entries."""
    plan = _plan_cache.pop(commit_token, None)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or already committed. Generate a new plan.")

    if plan["workspace_id"] != workspace_id or plan["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to commit this plan")

    project_id = plan["project_id"]
    objective_repo = ObjectiveRepository(session)
    timeline_repo = TimelineRepository(session)
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    created_objectives = []

    for i, obj_data in enumerate(plan.get("objectives", [])):
        obj = await objective_repo.create({
            "project_id": project_id,
            "title": obj_data["title"],
            "sort_order": i + 1,
        })
        created_objectives.append(obj)

        project = await project_repo.find_by_id(project_id)
        start_date = str(project.start_date) if project and project.start_date else None
        if start_date:
            from datetime import timedelta
            from dateutil.parser import parse as parse_date
            base = parse_date(start_date)
            for week_label in obj_data.get("suggested_weeks", []):
                week_num = int(week_label.replace("W", "")) - 1
                week_start = base + timedelta(weeks=week_num)
                await timeline_repo.upsert_entry({
                    "project_id": project_id,
                    "objective_id": str(obj.id),
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "status": "planned",
                })

    await audit_repo.log(
        workspace_id, user_id,
        "ai_commit_plan", "oppm_plan",
        new_data={"objectives_created": len(created_objectives)},
    )

    return {
        "created_objectives": created_objectives,
        "count": len(created_objectives),
    }


async def weekly_summary(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> dict:
    """Generate a weekly status summary using AI."""
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    models = await _get_models(session, workspace_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured.")

    context = await _build_project_context(session, project_id, workspace_id)

    prompt = f"""Analyze this OPPM project and provide a weekly status summary.

{context}

Return ONLY valid JSON:
{{
  "summary": "2-3 sentence status summary",
  "at_risk": ["list of objective IDs that are at risk"],
  "on_track": ["list of objective IDs on track"],
  "blocked": ["list of objective IDs that are blocked"],
  "suggested_actions": ["list of 2-3 specific actions to take"]
}}"""

    try:
        result = await call_with_fallback(models, prompt, json_mode=True)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable for weekly_summary: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable.")
    except Exception as e:
        logger.warning("Weekly summary LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    if not result:
        return {
            "summary": "Unable to generate summary — no response from AI.",
            "at_risk": [],
            "on_track": [],
            "blocked": [],
            "suggested_actions": [],
        }

    return {
        "summary": result.get("summary", ""),
        "at_risk": result.get("at_risk", []),
        "on_track": result.get("on_track", []),
        "blocked": result.get("blocked", []),
        "suggested_actions": result.get("suggested_actions", []),
    }


# ── Workspace-level chat (no project context, no tools) ──

WORKSPACE_SYSTEM_PROMPT = """You are OPPM AI, a project management assistant for the workspace.

The OPPM methodology applies universally — to architecture, construction, finance, healthcare, IT, manufacturing, research, education, and any other field. Objectives, tasks, timelines, and budgets are universal project concepts.

You can answer questions about projects, tasks, objectives, costs, and team members
across the entire workspace.

{rag_context}

## Rules
1. Keep responses concise — max 3 sentences unless explaining analysis.
2. You do NOT have access to tools. You cannot make changes.
3. For modification requests, tell the user to open the specific project page.
4. Provide data-driven answers using the retrieved context above.
5. Adapt to the domain/industry of the projects being discussed.
"""


async def workspace_chat(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
) -> dict:
    """
    Workspace-level chat — answers cross-project questions using RAG.
    No tool execution (tools are project-scoped).
    """
    models = await _get_models(session, workspace_id, model_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    # Retrieve RAG context via full pipeline
    last_user_msg = messages[-1]["content"] if messages else ""
    try:
        rag_result = await rag_service.retrieve_with_rag_pipeline(
            session, workspace_id, last_user_msg, user_id=user_id, top_k=15,
        )
        rag_context = rag_result.context
        memory_context = rag_result.memory_context
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        rag_context = ""
        memory_context = ""

    full_rag = rag_context
    if memory_context:
        full_rag = f"{memory_context}\n\n{rag_context}"

    system_prompt = WORKSPACE_SYSTEM_PROMPT.format(rag_context=full_rag)

    conversation = f"System: {system_prompt}\n\n"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        conversation += f"{role.capitalize()}: {content}\n\n"
    conversation += "Assistant: "

    # Call LLM with fallback chain
    try:
        response = await call_with_fallback(models, conversation)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable. Please try again later.")
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    audit_repo = AuditRepository(session)
    await audit_repo.log(
        workspace_id, user_id,
        "ai_chat", "workspace_chat",
        new_data={
            "user_message": last_user_msg[:200],
            "ai_response": response.text[:500],
        },
    )

    return {
        "message": response.text.strip(),
        "tool_calls": [],
        "updated_entities": [],
    }
