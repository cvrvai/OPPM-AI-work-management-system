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
from infrastructure.llm import get_adapter
from database import get_db
from repositories.oppm_repo import ObjectiveRepository, TimelineRepository, CostRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository
from services.oppm_tool_executor import execute_tool

logger = logging.getLogger(__name__)

objective_repo = ObjectiveRepository()
timeline_repo = TimelineRepository()
cost_repo = CostRepository()
project_repo = ProjectRepository()
audit_repo = AuditRepository()

# In-memory store for plan previews (simple approach; could use Redis/DB for production)
_plan_cache: dict[str, dict] = {}

SYSTEM_PROMPT = """You are OPPM AI, a project management assistant specialized in the One Page Project Manager (OPPM) methodology.

## Current Project Context
{project_context}

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
"""


def _build_project_context(project_id: str, workspace_id: str) -> str:
    """Build a text representation of the current project state for the LLM."""
    project = project_repo.find_by_id(project_id)
    if not project:
        return "Project not found."

    objectives = objective_repo.find_with_tasks(project_id)
    timeline = timeline_repo.find_project_timeline(project_id)
    costs = cost_repo.get_cost_summary(project_id)

    # Build timeline lookup
    tl_map: dict[str, dict[str, str]] = {}
    for entry in timeline:
        oid = entry["objective_id"]
        if oid not in tl_map:
            tl_map[oid] = {}
        tl_map[oid][entry["week_start"]] = entry["status"]

    # Get workspace members
    db = get_db()
    members = db.table("workspace_members").select("user_id, display_name, email, role").eq("workspace_id", workspace_id).execute()
    member_list = members.data or []

    lines = [
        f'Project: "{project["title"]}"',
        f'Description: {project.get("description", "—")}',
        f'Status: {project["status"]} | Progress: {project.get("progress", 0)}%',
        f'Start: {project.get("start_date", "—")} | Deadline: {project.get("deadline", "—")}',
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
        name = m.get("display_name") or m.get("email") or m["user_id"][:8]
        lines.append(f'- {name} ({m["role"]})')

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


def chat(
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
    # Verify project
    project = project_repo.find_by_id(project_id)
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    # Get active model
    db = get_db()
    if model_id:
        model_result = db.table("ai_models").select("*").eq("id", model_id).eq("workspace_id", workspace_id).limit(1).execute()
    else:
        model_result = db.table("ai_models").select("*").eq("workspace_id", workspace_id).eq("is_active", True).limit(1).execute()

    if not model_result.data:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    model = model_result.data[0]

    # Build context and prompt
    context = _build_project_context(project_id, workspace_id)
    system_prompt = SYSTEM_PROMPT.format(project_context=context)

    # Build full prompt for adapter (combine system + conversation)
    conversation = f"System: {system_prompt}\n\n"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        conversation += f"{role.capitalize()}: {content}\n\n"
    conversation += "Assistant: "

    # Call LLM
    try:
        adapter_cls = get_adapter(model["provider"])
        adapter = adapter_cls()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown AI provider: {model['provider']}")

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context already — use run_coroutine_threadsafe
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                response = pool.submit(
                    asyncio.run,
                    adapter.call(model["model_id"], conversation, endpoint_url=model.get("endpoint_url"))
                ).result()
        else:
            response = asyncio.run(
                adapter.call(model["model_id"], conversation, endpoint_url=model.get("endpoint_url"))
            )
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    # Parse tool calls
    clean_text, tool_calls_raw = _parse_tool_calls(response.text)

    # Execute tool calls
    tool_results = []
    all_updated = set()
    for tc in tool_calls_raw:
        tool_name = tc.get("tool", "")
        tool_input = tc.get("input", {})
        result = execute_tool(tool_name, tool_input, project_id, workspace_id, user_id)
        tool_results.append({
            "tool": tool_name,
            "input": tool_input,
            "result": result.get("result", {}),
            "success": result["success"],
            "error": result.get("error"),
        })
        all_updated.update(result.get("updated_entities", []))

    # Log the chat interaction
    audit_repo.log(
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


def suggest_plan(
    project_id: str,
    workspace_id: str,
    user_id: str,
    description: str,
) -> dict:
    """Ask AI to generate an OPPM plan from a description. Returns a preview."""
    project = project_repo.find_by_id(project_id)
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    db = get_db()
    model_result = db.table("ai_models").select("*").eq("workspace_id", workspace_id).eq("is_active", True).limit(1).execute()
    if not model_result.data:
        raise HTTPException(status_code=400, detail="No active AI model configured.")

    model = model_result.data[0]

    prompt = f"""You are an OPPM project planning assistant. Generate a structured project plan.

Project: "{project['title']}"
Start: {project.get('start_date', 'not set')}
Deadline: {project.get('deadline', 'not set')}
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
        adapter_cls = get_adapter(model["provider"])
        adapter = adapter_cls()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown AI provider: {model['provider']}")

    import asyncio
    try:
        result = asyncio.run(
            adapter.call_json(model["model_id"], prompt, endpoint_url=model.get("endpoint_url"))
        )
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


def commit_plan(
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
    created_objectives = []

    for i, obj_data in enumerate(plan.get("objectives", [])):
        obj = objective_repo.create({
            "project_id": project_id,
            "title": obj_data["title"],
            "sort_order": i + 1,
        })
        created_objectives.append(obj)

        # Create timeline entries for suggested weeks
        project = project_repo.find_by_id(project_id)
        start_date = project.get("start_date")
        if start_date:
            from datetime import timedelta
            from dateutil.parser import parse as parse_date
            base = parse_date(start_date)
            for week_label in obj_data.get("suggested_weeks", []):
                week_num = int(week_label.replace("W", "")) - 1
                week_start = base + timedelta(weeks=week_num)
                timeline_repo.upsert_entry({
                    "project_id": project_id,
                    "objective_id": obj["id"],
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "status": "planned",
                })

    audit_repo.log(
        workspace_id, user_id,
        "ai_commit_plan", "oppm_plan",
        new_data={"objectives_created": len(created_objectives)},
    )

    return {
        "created_objectives": created_objectives,
        "count": len(created_objectives),
    }


def weekly_summary(
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> dict:
    """Generate a weekly status summary using AI."""
    project = project_repo.find_by_id(project_id)
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    context = _build_project_context(project_id, workspace_id)

    db = get_db()
    model_result = db.table("ai_models").select("*").eq("workspace_id", workspace_id).eq("is_active", True).limit(1).execute()
    if not model_result.data:
        raise HTTPException(status_code=400, detail="No active AI model configured.")

    model = model_result.data[0]

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
        adapter_cls = get_adapter(model["provider"])
        adapter = adapter_cls()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown AI provider: {model['provider']}")

    import asyncio
    try:
        result = asyncio.run(
            adapter.call_json(model["model_id"], prompt, endpoint_url=model.get("endpoint_url"))
        )
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
