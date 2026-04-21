"""
AI Chat Service — Orchestrates LLM calls with OPPM project context.

Builds a rich system prompt with full project context (objectives, sub-objectives,
tasks with assignees/owners/dependencies, timeline, costs, risks, deliverables,
forecasts, team skills, recent commits), sends user messages to the configured LLM,
and runs an agentic multi-turn tool loop (up to 7 iterations) via the tool registry.

Pipeline: input guardrails → RAG (rewrite → cache → retrieve → RRF) → agent loop
          → output guardrails → response
"""

import json
import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.llm import call_with_fallback, NATIVE_TOOL_PROVIDERS
from infrastructure.llm.base import ProviderUnavailableError
from infrastructure.tools.registry import get_registry
from infrastructure.rag.agent_loop import run_agent_loop
from infrastructure.rag.guardrails import check_input, sanitize_output
from shared.models.ai_model import AIModel
from shared.models.workspace import Workspace, WorkspaceMember, MemberSkill
from shared.models.project import Project
from shared.models.git import CommitEvent, CommitAnalysis
from repositories.oppm_repo import (
    ObjectiveRepository, TimelineRepository, CostRepository,
    DeliverableRepository, ForecastRepository, RiskRepository,
    TaskDetailRepository,
)
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository
from services import rag_service

logger = logging.getLogger(__name__)

# In-memory store for plan previews (simple approach; could use Redis/DB for production)
_plan_cache: dict[str, dict] = {}


async def _get_models(session: AsyncSession, workspace_id: str, model_id: str | None = None) -> list[dict]:
    """Return ordered list of AI models for fallback. Falls back to local Ollama if none configured."""
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
    serialized = [{"id": str(m.id), "provider": m.provider, "model_id": m.model_id,
                   "api_key": None, "base_url": m.endpoint_url, "name": m.name,
                   "endpoint_url": m.endpoint_url, "is_active": m.is_active} for m in models]
    if not serialized:
        from config import get_settings as get_ai_settings
        ollama_url = get_ai_settings().ollama_url
        logger.info("No AI models configured for workspace %s — using Ollama default at %s", workspace_id, ollama_url)
        serialized = [{
            "id": "default-ollama",
            "provider": "ollama",
            "model_id": "kimi-k2.5:cloud",
            "api_key": None,
            "base_url": ollama_url,
            "endpoint_url": ollama_url,
            "name": "Ollama (default)",
            "is_active": True,
        }]
    return serialized

SYSTEM_PROMPT = """You are OPPM AI, a project management assistant using the One Page Project Manager (OPPM) methodology.

The OPPM methodology applies to ANY industry — construction, architecture, finance, healthcare, IT, manufacturing, education, or any other field. All projects share universal elements: objectives, tasks, timelines, budgets, and team members.

## Current Project Context
{project_context}

{rag_context}

{tool_section}

## Methodology Selection Guide
When the user describes a project or asks for a plan, first identify the best methodology fit:
- **Agile / Scrum**: Iterative, time-boxed sprints (1-4 weeks). Best for: software, R&D, evolving requirements. Use Scrum roles (Product Owner, Scrum Master, Dev Team), artifacts (Product Backlog, Sprint Backlog, Increment), and ceremonies (Sprint Planning, Daily Standup, Sprint Review, Retrospective).
- **Waterfall**: Sequential phases (Requirements → Design → Implementation → Testing → Deployment). Best for: construction, manufacturing, regulatory compliance, fixed-scope projects.
- **Hybrid**: Combines Waterfall milestones with Agile sprints within phases. Best for: large-scale projects needing both predictability and flexibility.
- **Kanban**: Continuous flow, WIP limits, visual board. Best for: operations, maintenance, support teams.

Map the chosen methodology onto the OPPM grid:
- Objectives = Milestones / Epics / Deliverables (by methodology)
- Tasks = Work packages / User stories / Activities
- Timeline weeks = Sprint periods / Phase durations

## Structured Response Format
When proposing a new plan, follow this 5-point structure:
1. **Methodology Rationale** — Why this methodology fits the project (1-2 sentences).
2. **Objectives** — Numbered list of OPPM objectives with suggested week ranges.
3. **Key Tasks** — Tasks grouped under each objective with owners, priorities, and dependencies.
4. **Risk Assessment** — Top 3 risks with likelihood and mitigation strategies.
5. **Budget Estimate** — Cost categories (labor, materials, tools) with rough estimates if data is available.

When answering questions (not proposing plans), respond conversationally without this structure.

## Rules
1. Ask clarifying questions when information is ambiguous — NEVER guess at task IDs, dates, or names.
   - If the user references a task or objective by name and it is ambiguous, list the candidates and ask which one.
   - If a date is relative (e.g., "next week", "in 2 days"), confirm the exact date before acting.
   - If the user's request is unclear (e.g., "update the status"), ask: "Which task and what status?"
   - NEVER reuse task IDs or member IDs from earlier in the conversation — IDs can change between sessions. Always call search_tasks to get fresh task UUIDs and get_team_workload to get fresh member UUIDs immediately before calling assign_task, set_task_dependency, or delete_task_dependency.
2. Always reference specific objective IDs and week dates when making changes.
3. **CRITICAL — Tool calls are the ONLY way to make changes.** When the user asks you to assign, create, update, or delete anything, you MUST call the appropriate tool. Describing what you "will do" or "have done" in text WITHOUT calling a tool is FORBIDDEN and will be treated as a failure. The user sees the tool call results in real time — they will know if you did not call a tool.
4. For read-only questions (status, analysis), respond conversationally.
5. When suggesting multiple changes, use bulk_set_timeline for efficiency.
6. After completing any action (create, update, assign), briefly confirm what was done and ask if anything else is needed.
7. Adapt terminology to the project's domain — use industry-appropriate language when relevant.
8. You have read tools (get_task_details, search_tasks, get_risk_status, etc.) — use them when you need more data than what's in the context.
9. You can manage risks (create_risk, update_risk), deliverables (create_deliverable), assign tasks (assign_task), and set dependencies (set_task_dependency).
10. When the user uploads a file (Excel, PDF, Word), analyze its content, summarize what you found, and ask: "Should I create objectives and tasks from this?"
11. When creating from a document, map the structure correctly:
    - Each distinct objective/section in the document → create_objective (do NOT merge separate objectives together)
    - Each objective's main action item → create_task linked to that objective via oppm_objective_id
    - Each bullet point or sub-action under a main item → create_task with parent_task_id set to the main task's ID (this creates a sub-task)
    - Preserve the document's grouping — if the document has 6 sections, create 6 objectives, not fewer
12. When the user asks to create a project and has not already provided these details, ask about them BEFORE calling create_project:
    a. **Methodology** — Ask which fits best. Offer choices with brief descriptions:
       - Agile: iterative sprints, evolving requirements
       - Waterfall: sequential phases, fixed scope
       - Hybrid: milestone structure + sprint execution
       - OPPM: one-page targeted, ideal for focused initiatives
    b. **Objective Summary** — One sentence describing the project outcome.
    c. **Deliverable Output** — What the project produces (report, system, product, etc.).
    d. **Project Code** — Short identifier like PRJ-204 (optional, skip if user says so).
    e. **Planning Hours** — Estimated total effort in hours (optional, skip if unknown).
    If the user provides some of these upfront (in the same message), skip those questions and only ask for the missing ones. If the user says "just create it" or similar, proceed with defaults.
13. **Interactive choices** — When you want to offer the user a fixed set of options, end your message with exactly one line in this format:
    [CHOICES: Option A | Option B | Option C | Type your own...]
    Rules: options are pipe-separated; the last item MUST end with `...` to signal that a free-text input field will appear; do NOT add any text after the closing `]`; use at most 5 options; omit this block entirely when open-ended input is more appropriate.
"""

# ── Context budget: max ~8K tokens ≈ 32K chars ──
_MAX_CONTEXT_CHARS = 32_000
_TIER1_BUDGET = 16_000  # always: project meta, objectives, risks, costs
_TIER2_BUDGET = 12_000  # if fits: task detail, timeline, deliverables, forecasts
_TIER3_BUDGET = 4_000   # optional: commits, member skills


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


async def _build_project_context(session: AsyncSession, project_id: str, workspace_id: str) -> str:
    """Build a rich text representation of the current project state for the LLM.

    Loads ALL OPPM data: objectives, sub-objectives, tasks (with assignees,
    owners, dependencies, priorities, due dates), timeline, costs (breakdown),
    deliverables, forecasts, risks, team members (with skills), and recent commits.

    Uses tiered context windowing to stay within token budget.
    """
    project_repo = ProjectRepository(session)
    objective_repo = ObjectiveRepository(session)
    timeline_repo = TimelineRepository(session)
    cost_repo = CostRepository(session)
    deliverable_repo = DeliverableRepository(session)
    forecast_repo = ForecastRepository(session)
    risk_repo = RiskRepository(session)
    task_detail_repo = TaskDetailRepository(session)

    project = await project_repo.find_by_id(project_id)
    if not project:
        return "Project not found."

    # ── Load all data sources concurrently ──
    objectives = await objective_repo.find_with_tasks(project_id)
    sub_objectives = await objective_repo.find_sub_objectives(project_id)
    task_sub_obj_links = await objective_repo.find_task_sub_objective_links(project_id)
    timeline = await timeline_repo.find_project_timeline(project_id)
    costs = await cost_repo.get_cost_summary(project_id)
    cost_breakdown = await cost_repo.get_cost_breakdown(project_id)
    deliverables = await deliverable_repo.find_by_project(project_id)
    forecasts = await forecast_repo.find_by_project(project_id)
    risks = await risk_repo.find_by_project(project_id)
    assignees_map = await task_detail_repo.find_assignees(project_id)
    owners_map = await task_detail_repo.find_owners(project_id)
    deps_map = await task_detail_repo.find_dependencies(project_id)

    # Build timeline lookup: task_id → week → status
    tl_map: dict[str, dict[str, str]] = {}
    for entry in timeline:
        tid = str(entry.task_id)
        if tid not in tl_map:
            tl_map[tid] = {}
        tl_map[tid][str(entry.week_start)] = entry.status

    # Build sub-objective lookup: id → label
    sub_obj_labels = {s["id"]: s["label"] for s in sub_objectives}

    # Get workspace members with skills
    members_result = await session.execute(
        select(WorkspaceMember.id, WorkspaceMember.user_id, WorkspaceMember.display_name, WorkspaceMember.role)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    member_list = members_result.all()

    skills_result = await session.execute(
        select(MemberSkill.workspace_member_id, MemberSkill.skill_name, MemberSkill.skill_level)
        .join(WorkspaceMember, WorkspaceMember.id == MemberSkill.workspace_member_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    skills_map: dict[str, list[str]] = {}
    for row in skills_result.all():
        mid = str(row.workspace_member_id)
        skills_map.setdefault(mid, []).append(f"{row.skill_name}({row.skill_level})")

    # Get recent commits (last 5) for this project
    commit_lines: list[str] = []
    try:
        from shared.models.git import RepoConfig
        stmt = (
            select(CommitEvent, CommitAnalysis.summary, CommitAnalysis.task_alignment_score)
            .outerjoin(CommitAnalysis, CommitAnalysis.commit_event_id == CommitEvent.id)
            .join(RepoConfig, RepoConfig.id == CommitEvent.repo_config_id)
            .where(RepoConfig.project_id == project_id)
            .order_by(CommitEvent.pushed_at.desc())
            .limit(5)
        )
        commit_result = await session.execute(stmt)
        for row in commit_result.all():
            evt = row[0]
            summary = row[1] or ""
            alignment = row[2]
            msg = (evt.commit_message or "")[:80]
            line = f'  - "{msg}" by {evt.author_github_username or "?"}'
            if summary:
                line += f" | AI: {summary[:100]}"
            if alignment is not None:
                line += f" | alignment: {alignment}%"
            commit_lines.append(line)
    except Exception as e:
        logger.debug("Commit loading skipped: %s", e)

    # ── TIER 1: Always include (project meta, objectives, risks, cost totals) ──
    tier1: list[str] = [
        f'Project: "{project.title}"',
        f'Description: {project.description or "—"}',
        f'Status: {project.status} | Progress: {project.progress or 0}%',
        f'Budget: {project.budget or "—"} | Planning hours: {project.planning_hours or "—"}',
        f'Start: {project.start_date or "—"} | Deadline: {project.deadline or "—"}',
        f'Today: {datetime.now().strftime("%Y-%m-%d")}',
    ]

    if sub_objectives:
        tier1.append("")
        tier1.append("## Sub-Objectives (strategic alignment columns)")
        for s in sub_objectives:
            tier1.append(f'  {s["position"]}. {s["label"]}')

    tier1.append("")
    tier1.append("## Objectives & Tasks")

    for obj in objectives:
        task_count = len(obj.get("tasks", []))
        tier1.append(f'- [{obj["id"]}] "{obj["title"]}" (tasks: {task_count})')
        for task in obj.get("tasks", []):
            tid = str(task["id"])
            tl = tl_map.get(tid, {})
            tl_str = ", ".join(f"{k}: {v}" for k, v in sorted(tl.items())) or "no entries"

            # Enriched task info
            parts = [f'Task [{tid}] "{task["title"]}"']
            parts.append(f'status: {task["status"]}')
            parts.append(f'priority: {task["priority"]}')
            if task.get("progress"):
                parts.append(f'progress: {task["progress"]}%')
            if task.get("due_date"):
                parts.append(f'due: {task["due_date"]}')

            # Assignees
            task_assignees = assignees_map.get(tid)
            if task_assignees:
                parts.append(f'assignees: {", ".join(task_assignees)}')

            # Owners (A/B/C)
            task_owners = owners_map.get(tid)
            if task_owners:
                owner_strs = [f'{o["name"]}({o["priority"]})' for o in task_owners]
                parts.append(f'owners: {", ".join(owner_strs)}')

            # Sub-objective alignment
            task_sub_objs = task_sub_obj_links.get(tid)
            if task_sub_objs:
                aligned = [sub_obj_labels.get(sid, sid) for sid in task_sub_objs]
                parts.append(f'aligned-to: {", ".join(aligned)}')

            # Dependencies
            task_deps = deps_map.get(tid)
            if task_deps:
                parts.append(f'depends-on: {", ".join(task_deps)}')

            parts.append(f'timeline: {tl_str}')

            # Description (truncated)
            desc = task.get("description", "")
            if desc and len(desc) > 5:
                parts.append(f'desc: {desc[:200]}')

            tier1.append(f'  - {" | ".join(parts)}')

    if not objectives:
        tier1.append("  No objectives defined yet.")

    # Risks (always include — critical for project management)
    if risks:
        tier1.append("")
        tier1.append("## Risks")
        for r in risks:
            tier1.append(f'  {r["number"]}. [{r["rag"].upper()}] {r["description"]}')

    # Cost totals
    tier1.append("")
    tier1.append(f"## Costs: Planned={costs['total_planned']}, Actual={costs['total_actual']}, Variance={costs['variance']}")

    # ── TIER 2: Include if fits (cost breakdown, deliverables, forecasts, team) ──
    tier2: list[str] = []

    if cost_breakdown:
        tier2.append("")
        tier2.append("## Cost Breakdown")
        for cb in cost_breakdown:
            tier2.append(f'  - {cb["category"]}: planned={cb["planned"]}, actual={cb["actual"]}')

    if deliverables:
        tier2.append("")
        tier2.append("## Deliverables")
        for d in deliverables:
            tier2.append(f'  {d["number"]}. {d["description"]}')

    if forecasts:
        tier2.append("")
        tier2.append("## Forecasts")
        for f in forecasts:
            tier2.append(f'  {f["number"]}. {f["description"]}')

    tier2.append("")
    tier2.append("## Team Members")
    for m in member_list:
        mid = str(m.id)
        name = m.display_name or str(m.user_id)[:8]
        skills = skills_map.get(mid)
        if skills:
            tier2.append(f'- {name} ({m.role}) — skills: {", ".join(skills)}')
        else:
            tier2.append(f'- {name} ({m.role})')

    # ── TIER 3: Optional (commits) ──
    tier3: list[str] = []
    if commit_lines:
        tier3.append("")
        tier3.append("## Recent Commits")
        tier3.extend(commit_lines)

    # ── Assemble with budget ──
    tier1_text = "\n".join(tier1)
    tier2_text = "\n".join(tier2)
    tier3_text = "\n".join(tier3)

    combined = tier1_text
    omitted: list[str] = []

    if len(combined) + len(tier2_text) <= _MAX_CONTEXT_CHARS:
        combined += tier2_text
    else:
        omitted.append("cost breakdown, deliverables, forecasts, team skills")

    if len(combined) + len(tier3_text) <= _MAX_CONTEXT_CHARS:
        combined += tier3_text
    else:
        if commit_lines:
            omitted.append("recent commits")

    if omitted:
        combined += f"\n\n## Note\nOmitted due to context limits: {', '.join(omitted)}. Ask about these topics for details."

    return combined


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
    on_tool_result=None,
) -> dict:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    # ── Input guardrail ──
    last_user_msg = messages[-1]["content"] if messages else ""
    is_safe, reason = check_input(last_user_msg)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    models = await _get_models(session, workspace_id, model_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    context = await _build_project_context(session, project_id, workspace_id)

    # ── RAG pipeline (includes query rewriting + semantic cache) ──
    try:
        rag_result = await rag_service.retrieve_with_rag_pipeline(
            session,
            workspace_id,
            last_user_msg,
            user_id=user_id,
            project_id=project_id,
            models=models,
            project_title=project.title or "",
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

    # ── Build tool section and system prompt ──
    registry = get_registry()
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    if use_native_tools:
        tool_section = (
            "## Tools\n"
            "You have tools available via native function calling. "
            "Use them when the user asks to make changes. "
            "You may call multiple tools across multiple turns to gather all needed information."
        )
    else:
        tool_section = registry.to_prompt_text()

    system_prompt = SYSTEM_PROMPT.format(
        project_context=context,
        rag_context=full_rag,
        tool_section=tool_section,
    )

    # ── Build initial conversation for the agentic loop ──
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        llm_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    openai_tools = registry.to_openai_schema() if use_native_tools else None
    anthropic_tools = registry.to_anthropic_schema() if use_native_tools else None

    # Closure that re-runs RAG for a knowledge gap phrase mid-loop
    async def _rag_requery(gap_phrase: str) -> str:
        return await rag_service.requery(
            session,
            workspace_id,
            gap_phrase,
            project_id=project_id,
            user_id=user_id,
        )

    # ── TAOR agentic loop (Think → Act → Observe → Retry) ──
    try:
        loop_result = await run_agent_loop(
            models,
            llm_messages,
            registry,
            session=session,
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
            openai_tools=openai_tools,
            anthropic_tools=anthropic_tools,
            rag_requery=_rag_requery,
            on_tool_result=on_tool_result,
        )
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable. Please try again later.")
    except Exception as e:
        logger.warning("Agent loop failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    # ── Output guardrail ──
    clean_text = sanitize_output(loop_result.final_text)

    await audit_repo.log(
        workspace_id, user_id,
        "ai_chat", "chat",
        new_data={
            "project_id": project_id,
            "user_message": last_user_msg[:500],
            "ai_response": clean_text[:500],
            "tool_calls_count": len(loop_result.all_tool_results),
            "agent_iterations": loop_result.iterations,
        },
    )

    return {
        "message": clean_text,
        "tool_calls": loop_result.all_tool_results,
        "updated_entities": loop_result.updated_entities,
        "iterations": loop_result.iterations,
        "low_confidence": loop_result.low_confidence,
    }


async def chat_stream(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream AI chat as Server-Sent Events.

    Yields SSE-formatted strings:
      - ``event: tool_call`` — once per tool execution, with updated_entities list
      - ``event: message`` — final response (same payload as the blocking ``chat()``)
      - ``event: error`` — on fatal error
    """
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    # Validate input + build context using the same pipeline as chat()
    # We call _chat_async_stream which is just _chat_async with on_tool_result wired up
    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    async def on_tool(record: dict) -> None:
        await queue.put(("tool_call", record))

    async def run() -> None:
        try:
            result = await _chat_async(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
                messages=messages,
                model_id=model_id,
                on_tool_result=on_tool,
            )
            # Explicitly commit here — StreamingResponse background task lifecycle
            # may not align with get_session's yield cleanup timing.
            await session.commit()
            await queue.put(("message", result))
        except HTTPException as exc:
            await session.rollback()
            await queue.put(("error", {"detail": exc.detail, "status_code": exc.status_code}))
        except Exception as exc:
            logger.warning("chat_stream background task failed: %s", exc)
            await session.rollback()
            await queue.put(("error", {"detail": str(exc)}))
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(run())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield _sse(event, data)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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
        response = await call_with_fallback(models, prompt)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable for suggest_plan: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable.")
    except Exception as e:
        logger.warning("Suggest plan LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    # Extract JSON from the text response (model may wrap it in ```json ... ``` blocks)
    raw_text = response.text.strip() if response else ""
    result = None
    try:
        # Strip markdown code fences if present
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.DOTALL).strip()
        result = json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        # Last resort: find first {...} block
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

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
    audit_repo = AuditRepository(session)
    created_objectives = []

    for i, obj_data in enumerate(plan.get("objectives", [])):
        obj = await objective_repo.create({
            "project_id": project_id,
            "title": obj_data["title"],
            "sort_order": i + 1,
        })
        created_objectives.append(obj)

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

WORKSPACE_SYSTEM_PROMPT = """You are OPPM AI, a project management assistant for the workspace "{workspace_name}".

The OPPM methodology applies universally — to architecture, construction, finance, healthcare, IT, manufacturing, research, education, and any other field. Objectives, tasks, timelines, and budgets are universal project concepts.

You can answer questions about projects, tasks, objectives, costs, and team members
across the entire workspace.

## Projects in this workspace
{project_list}

{rag_context}

## Rules
1. Ask clarifying questions when required information is missing — NEVER guess or create with incomplete data.
   - If asked to create a project but the title is unclear, ask: "What should the project be titled?"
   - If a deadline is relative (e.g., "1 week", "next Friday"), calculate and confirm: "That would be [date] — is that correct?"
   - If a file is uploaded without explicit instruction, summarize what you extracted and ask: "Should I create a project from this? What title should I use?"
   - If the user's intent covers multiple projects, ask which one to act on.
2. You CAN create projects, objectives, and tasks using the available tools.
3. After creating a project, immediately use the returned project ID to create objectives and tasks from the uploaded document or user description.
4. When creating from a document, extract ALL objectives and key tasks — do not stop at the project shell.
   - Each distinct section or numbered item in the document → create_objective (keep them separate, do NOT merge similar sections)
   - Each objective's main action → create_task linked via oppm_objective_id
   - Each bullet point or sub-action under a main item → create_task with parent_task_id set to the main task's UUID (creates sub-task)
   - Preserve the document's original grouping structure faithfully
5. After completing any action (create, update), briefly summarize what was done and ask: "Is there anything else you need?"
6. Provide data-driven answers using the retrieved context above.
7. Adapt to the domain/industry of the projects being discussed.
8. When comparing projects, reference their names and key metrics (objectives count, status, budget).
"""


async def workspace_chat(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
) -> dict:
    """
    Workspace-level chat — cross-project questions with workspace-scoped tool execution.
    Supports creating/updating projects and listing workspace data via the TAOR loop.
    """
    models = await _get_models(session, workspace_id, model_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    # Load workspace name and project list for prompt context
    ws_row = await session.execute(
        select(Workspace.name).where(Workspace.id == workspace_id)
    )
    workspace_name = ws_row.scalar_one_or_none() or "Workspace"

    project_rows = await session.execute(
        select(Project.title, Project.status).where(Project.workspace_id == workspace_id)
    )
    projects = project_rows.all()
    if projects:
        project_list = "\n".join(f"- {p.title} ({p.status})" for p in projects)
    else:
        project_list = "(No projects yet)"

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

    # Build tool section — expose ALL tools so the AI can create projects, objectives, and tasks
    registry = get_registry()
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    # Expose all tools (workspace + project-scoped) so the AI can populate a full project
    all_tools = registry.get_tools()
    if use_native_tools:
        ws_tool_section = (
            "## Tools\n"
            "You have tools available via native function calling. "
            "Use them to create projects, then use the returned project ID to create objectives and tasks."
        )
        openai_tools = registry.to_openai_schema()
        anthropic_tools = registry.to_anthropic_schema()
    else:
        # Build prompt text for all tools
        lines = [
            "## Available Tools",
            'To create or update projects/objectives/tasks, include a JSON tool_calls array at the END of your message inside <tool_calls>...</tool_calls> tags.',
            "",
            "Available tools:",
        ]
        for t in all_tools:
            param_parts = []
            for p in t.params:
                if p.enum:
                    val = f'"{"|".join(p.enum)}"'
                elif p.type == "string":
                    val = '"..."'
                elif p.type in ("integer", "number"):
                    val = "N"
                else:
                    val = "..."
                marker = "" if p.required else " (optional)"
                param_parts.append(f'"{p.name}": {val}{marker}')
            params_str = ", ".join(param_parts)
            lines.append(f"- {t.name}: {{{{{params_str}}}}}")
            lines.append(f"  Description: {t.description}")
        lines += ["", "Example:", "<tool_calls>", '[{{"tool": "create_project", "input": {{"title": "My Project"}}}}]', "</tool_calls>"]
        ws_tool_section = "\n".join(lines)
        openai_tools = None
        anthropic_tools = None

    system_prompt = WORKSPACE_SYSTEM_PROMPT.format(
        workspace_name=workspace_name,
        project_list=project_list,
        rag_context=full_rag,
    ) + f"\n\n{ws_tool_section}"

    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        llm_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    async def _rag_requery(gap_phrase: str) -> str:
        return await rag_service.requery(session, workspace_id, gap_phrase, user_id=user_id)

    audit_repo = AuditRepository(session)

    try:
        loop_result = await run_agent_loop(
            models,
            llm_messages,
            registry,
            session=session,
            project_id="",   # No specific project at workspace level
            workspace_id=workspace_id,
            user_id=user_id,
            openai_tools=openai_tools or None,
            anthropic_tools=anthropic_tools or None,
            rag_requery=_rag_requery,
        )
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable. Please try again later.")
    except Exception as e:
        logger.warning("Workspace agent loop failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    clean_text = sanitize_output(loop_result.final_text)

    await audit_repo.log(
        workspace_id, user_id,
        "ai_chat", "workspace_chat",
        new_data={
            "user_message": last_user_msg[:200],
            "ai_response": clean_text[:500],
            "tool_calls_count": len(loop_result.all_tool_results),
            "agent_iterations": loop_result.iterations,
        },
    )

    return {
        "message": clean_text,
        "tool_calls": loop_result.all_tool_results,
        "updated_entities": loop_result.updated_entities,
        "iterations": loop_result.iterations,
        "low_confidence": loop_result.low_confidence,
    }
