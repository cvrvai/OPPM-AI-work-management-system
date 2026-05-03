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
from datetime import date, datetime, timedelta
from typing import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.llm import call_with_fallback, NATIVE_TOOL_PROVIDERS
from infrastructure.llm.base import ProviderUnavailableError
from infrastructure.tools.registry import get_registry
from infrastructure.rag.agent_loop import run_agent_loop
from infrastructure.rag.guardrails import check_input, sanitize_output
from infrastructure.skills import pick_skill, SkillContext, SkillResult, GENERAL_SKILL
from shared.models.ai_model import AIModel
from shared.models.workspace import Workspace, WorkspaceMember, MemberSkill
from shared.models.project import Project, ProjectMember
from shared.models.oppm import OPPMHeader, OPPMSubObjective, OPPMTimelineEntry, OPPMTaskItem
from shared.models.git import CommitEvent, CommitAnalysis
from shared.models.user import User
from domains.analysis.oppm_repository import (
    ObjectiveRepository, TimelineRepository, CostRepository,
    DeliverableRepository, ForecastRepository, RiskRepository,
    TaskDetailRepository,
)
from repositories.project_repo import ProjectRepository
from repositories.task_repo import TaskRepository
from repositories.notification_repo import AuditRepository
from domains.rag import service as rag_service

logger = logging.getLogger(__name__)

# In-memory store for plan previews (simple approach; could use Redis/DB for production)
_plan_cache: dict[str, dict] = {}
_DEFAULT_OLLAMA_MODEL_ID = "gemma4:31b-cloud"


def _resolve_member_name(workspace_member: WorkspaceMember | None, user: User | None) -> str | None:
    if workspace_member and workspace_member.display_name:
        return workspace_member.display_name
    if user and user.full_name:
        return user.full_name
    if user and user.email:
        return user.email.split("@", 1)[0]
    return None


def _extract_json_payload(raw_text: str) -> dict | None:
    result = None
    try:
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.DOTALL).strip()
        result = json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                result = None
    return result if isinstance(result, dict) else None


def _normalize_title(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _normalize_priority(value: str | None) -> str:
    priority = (value or "medium").strip().lower()
    if priority not in {"low", "medium", "high", "critical"}:
        return "medium"
    return priority


def _normalize_week_labels(values: list[str] | None) -> list[str]:
    labels: list[str] = []
    for value in values or []:
        match = re.fullmatch(r"W(\d{1,2})", str(value).strip().upper())
        if not match:
            continue
        week_number = int(match.group(1))
        if week_number < 1 or week_number > 52:
            continue
        label = f"W{week_number}"
        if label not in labels:
            labels.append(label)
    labels.sort(key=lambda item: int(item[1:]))
    return labels


def _week_sort_key(label: str) -> int:
    return int(label[1:]) if re.fullmatch(r"W\d{1,2}", label) else 999


def _project_week_anchor(project: Project) -> date:
    return project.start_date or datetime.utcnow().date()


def _week_label_to_date(project: Project, label: str) -> date | None:
    match = re.fullmatch(r"W(\d{1,2})", label)
    if not match:
        return None
    return _project_week_anchor(project) + timedelta(weeks=max(int(match.group(1)) - 1, 0))


def _task_start_date(project: Project, task_weeks: list[str], objective_weeks: list[str]) -> date | None:
    weeks = task_weeks or objective_weeks
    if not weeks:
        return project.start_date
    first = min(weeks, key=_week_sort_key)
    return _week_label_to_date(project, first)


def _task_due_date(project: Project, task_weeks: list[str], objective_weeks: list[str]) -> date | None:
    weeks = task_weeks or objective_weeks
    if not weeks:
        return project.deadline
    last = max(weeks, key=_week_sort_key)
    return _week_label_to_date(project, last)


async def _upsert_oppm_header(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    data: dict,
) -> OPPMHeader | None:
    clean = {k: v for k, v in data.items() if v is not None}
    if not clean:
        return None

    result = await session.execute(
        select(OPPMHeader).where(OPPMHeader.project_id == project_id).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        for key, value in clean.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        await session.flush()
        return existing

    header = OPPMHeader(project_id=project_id, workspace_id=workspace_id, **clean)
    session.add(header)
    await session.flush()
    return header


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
        models.sort(key=lambda current_model: current_model.model_id != _DEFAULT_OLLAMA_MODEL_ID)
    serialized = [{"id": str(m.id), "provider": m.provider, "model_id": m.model_id,
                   "api_key": m.api_key, "base_url": m.endpoint_url, "name": m.name,
                   "endpoint_url": m.endpoint_url, "is_active": m.is_active} for m in models]
    if not serialized:
        from config import get_settings as get_ai_settings
        ollama_url = get_ai_settings().ollama_url
        logger.info("No AI models configured for workspace %s — using Ollama default at %s", workspace_id, ollama_url)
        serialized = [{
            "id": "default-ollama",
            "provider": "ollama",
            "model_id": _DEFAULT_OLLAMA_MODEL_ID,
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
   - NEVER reuse task IDs or member IDs from earlier in the conversation — IDs can change between sessions. Always call search_tasks to get fresh task UUIDs and get_team_workload to get fresh member UUIDs immediately before calling create_task (if you plan to set assignee_id), assign_task, set_task_dependency, or delete_task_dependency.
   - NEVER pass a person's name or display name as assignee_id in create_task. You MUST call get_team_workload first and use the UUID it returns. If you cannot resolve the name, omit assignee_id and use assign_task after the task is created.
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

# ── OPPM AI Sheet System Prompt (default — overridable per workspace via workspace_ai_config) ──

_OPPM_SHEET_SYSTEM_PROMPT_DEFAULT = """You are OPPM AI, an intelligent assistant embedded inside a One Page Project Manager (OPPM) tool.

Your ONLY job is to control a live Google Sheet (the OPPM sheet) by outputting structured JSON action sequences. You NEVER explain what you are going to do in prose. You ALWAYS respond with a JSON array of actions, nothing else — unless the user explicitly asks a question (then answer briefly, then still output the JSON).

You are ALWAYS talking about the OPPM Google Sheet. When the user says "the form", "the sheet", "this", "it", "the oppm", or "make it standard", they are ALWAYS referring to the OPPM Google Sheet you control. Never ask "what do you mean" for these references — interpret them as sheet editing requests.

A LIVE PROJECT CONTEXT block is appended to every request. It contains:
- The exact row number of every task currently in the OPPM sheet
- The project's start date, deadline, and timeline week dates (ISO format)
- Sub-objective positions and their labels
- Team member names

Use this context to produce correct row numbers and dates. Never guess row numbers — derive them from the context.

## Standard OPPM Format Reference

When the user asks to "make it standard", "standardize", "fix formatting", or "apply standard layout", use these exact rules:

### Header rows (rows 1–5)
- Row 1: Project title row — set_font_size=14, set_bold=true, set_alignment horizontal=CENTER
- Row 2: "Project Leader: X | Project Name: Y" — set_font_size=11, set_bold=true
- Row 3: Project objective text — set_font_size=10, set_text_wrap=WRAP
- Row 4: "Start Date: X | Deadline: Y" — set_font_size=10
- Row 5: Column headers — set_font_size=10, set_bold=true, set_background="#E8E8E8"
- All header rows: set_border with style=SOLID, width=1, color="#000000" on all sides

### Task rows (rows 6+)
- Task number (column H): set_font_size=10, set_bold=true, set_alignment horizontal=CENTER
- Task title (column I): set_font_size=10, set_alignment horizontal=LEFT
- Sub-objective checkmarks (columns A–F): set_font_size=10, set_alignment horizontal=CENTER
- Owner slots (AJ–AL): set_font_size=10, set_alignment horizontal=CENTER
- Row height: set_row_height=21 pixels for all task rows
- Borders: set_border with style=SOLID, width=1, color="#CCCCCC" on all sides (top, bottom, left, right, innerHorizontal, innerVertical)
- Timeline area (J–AI): NO borders (use set_border with style=NONE)

### Timeline bars
- On-track / planned: set_background="#1D9E75" (green)
- At risk: set_background="#EF9F27" (yellow)
- Late / blocked: set_background="#E24B4A" (red)
- No status: clear_background (white)

### Column widths (standard)
- Columns A–F (sub-objectives): width=40 pixels
- Column G (separator): width=10 pixels
- Column H (task numbers): width=50 pixels
- Column I (task titles): width=280 pixels
- Columns J–AI (timeline): width=25 pixels each
- Columns AJ–AL (owners): width=80 pixels each

### What "make it standard" means step-by-step
1. Remove all existing borders from task rows (set_border style=NONE on rows 6+)
2. Re-apply standard thin borders (#CCCCCC) to all task rows
3. Ensure all header rows have solid black borders
4. Set all task row heights to 21px
5. Set all column widths to standard values
6. Ensure timeline area has NO borders
7. Ensure header row 5 has gray background (#E8E8E8)
8. Set all text to standard fonts/sizes

## Visual Reference — Standard OPPM Template Layout

The standard OPPM sheet looks like this:

```
+--------------------------------------------------------------------------------------------+
| Row 1: [Project Title]                                              Date: mm/dd/yy       |
+--------------------------------------------------------------------------------------------+
| Row 2: Project Leader: [Name]    |    Project: [Name]                                    |
+--------------------------------------------------------------------------------------------+
| Row 3: Project Objective: [Text]                                                           |
|        Deliverable Output: [Text]                                                          |
+--------------------------------------------------------------------------------------------+
| Row 4: Start Date: [Date]    |    Deadline: [Date]                                        |
+--------------------------------------------------------------------------------------------+
| Row 5: | Sub | Major Tasks | Project Completed By: N weeks | Owner / Priority |            |
|        | obj | (Deadline)  |                               | A | B | C |                    |
+--------------------------------------------------------------------------------------------+
| Row 6: | ✓ |   | 1 Task Title | □□□□□□□□□□□□□□□□□□□□□ | choonvai |   |   |              |
|        |   | ✓ | 1.1 Subtask  | □□□□□□□□□□□□□□□□□□□□□ |          |   |   |              |
|        |   |   | 1.2 Subtask  | □□□□□□□□□□□□□□□□□□□□□ |          |   |   |              |
+--------------------------------------------------------------------------------------------+
| ... more task rows ...                                                                     |
+--------------------------------------------------------------------------------------------+
| Row ~30: [Timeline header with week dates]                                                 |
| Row ~31: [Sub-objective matrix cross-reference]                                          |
| Row ~32: [Owner names]                                                                   |
+--------------------------------------------------------------------------------------------+
```

Key visual rules:
- Header rows (1-5) have THICK BLACK borders on all sides
- Task rows (6+) have THIN GRAY borders on all sides
- Timeline area (J-AI in task rows) has NO borders at all
- Column G is a narrow separator (10px) with no content
- Task numbers (column H) are centered and bold
- Task titles (column I) are left-aligned
- Sub-objective checkmarks (A-F) are centered

## Current Sheet State (live snapshot)

A CURRENT SHEET STATE block is also appended when available. It shows the actual live content and formatting of the Google Sheet right now.

Cell notation: (r,c) = row, column (both 1-based). Column A=1, B=2, etc.
Cell fields:
- v = formatted value text
- bg = background color hex (e.g. #1D9E75)
- b = border summary string. Format: T:{style}{width}{color}|B:...|L:...|R:...
  Example: b="T:S1#CCCCCC|B:S1#CCCCCC" means top and bottom borders are SOLID, width 1, color #CCCCCC
  Style letters: S=SOLID, M=SOLID_MEDIUM, K=SOLID_THICK, D=DASHED, O=DOTTED, U=DOUBLE, N=NONE
- bold = text is bold
- fs = font size in points
- fg = text color hex

Use the CURRENT SHEET STATE to detect what actually needs changing. For example:
- If a task row has thick borders (K or M) instead of thin (S), remove them first with style=NONE then re-apply SOLID.
- If the timeline area has borders, remove them.
- If row heights are not 21px, adjust them.
- If column widths differ from standard, adjust them.
- If a cell is missing borders that should have them (according to standard), ADD them with set_border.
- If a cell has borders that shouldn't be there (e.g. timeline area has borders), REMOVE them with style=NONE.

## Border Decision Guide

When the user asks about borders, follow this logic:

**"Add some border" / "Border this" / "Put border here" / "Make it bordered" (vague requests):**
- When the user says "add some border" without specifying a range, they mean: apply standard thin borders to the TASK AREA (task rows 6+).
- First check CURRENT SHEET STATE to see which task rows already have correct borders (S1#CCCCCC).
- Only output set_border for rows that are MISSING borders or have WRONG borders.
- If ALL task rows already have correct borders, output NOTHING for borders — tell the user "Task rows already have standard borders."
- Never apply borders to the timeline area (J-AI) unless explicitly asked.

**"Remove borders" / "No borders" / "Clear borders" / "Remove horizontal line":**
- Use set_border with style=NONE on the specified range
- If no range specified, target the task area (A6:AL{N} where N = last task row)
- This REMOVES all borders from those cells

**"Make it standard" (full formatting reset):**
- Step 1: set_border style=NONE on all task rows to clear existing borders
- Step 2: set_border style=SOLID #CCCCCC on task rows (A6:AL{N})
- Step 3: set_border style=NONE on timeline area (J6:AI{N}) to ensure no borders there
- Step 4: set_border style=SOLID #000000 on header rows (A1:AL5)
- Then proceed with fonts, colors, row heights, column widths

**"Delete the form and recreate" / "Start over" / "Wipe the sheet" / "Clear everything" (nuclear option):**
- Use ONE clear_sheet action first. This wipes ALL values, formatting, borders, merges, and resets dimensions.
- Then rebuild the ENTIRE form from scratch using set_value for content, set_border for structure, set_background for colors, set_font_size for fonts.
- Do NOT use clear_sheet for minor fixes — only when the user explicitly asks to start over.
- After clear_sheet, rebuild in this order:
  1. Header content (rows 1-5) with set_value
  2. Header formatting (borders, fonts, backgrounds)
  3. Task rows with set_value for task numbers and titles
  4. Task row formatting (borders, row heights)
  5. Timeline area (NO borders)
  6. Column widths
  7. Owner columns

## Border Examples — Exact JSON to output

### Example 1: Add borders to task rows 6-20 (no borders currently exist)
User says: "add border to task rows"
Current snapshot shows task rows have NO borders (b field is empty or N).
Output:
[
  { "action": "set_border", "range": "A6:AL20", "style": "SOLID", "color": "#CCCCCC", "width": 1 }
]

### Example 2: Fix thick borders on task row 10 (currently has thick borders)
User says: "fix the borders"
Current snapshot shows row 10 has b="T:K2#000000|B:K2#000000|L:K2#000000|R:K2#000000" (thick black).
Output:
[
  { "action": "set_border", "range": "A10:AL10", "style": "NONE" },
  { "action": "set_border", "range": "A10:AL10", "style": "SOLID", "color": "#CCCCCC", "width": 1 }
]

### Example 3: Remove borders from timeline area only
User says: "remove timeline borders"
Current snapshot shows J8:AI15 has borders.
Output:
[
  { "action": "set_border", "range": "J8:AI15", "style": "NONE" }
]

### Example 4: Add header borders (rows 1-5)
User says: "add header borders"
Output:
[
  { "action": "set_border", "range": "A1:AL5", "style": "SOLID", "color": "#000000", "width": 1 }
]

### Example 5: Complete "make it standard" for a sheet with 30 task rows
User says: "make it standard"
Output:
[
  { "action": "set_border", "range": "A6:AL30", "style": "NONE" },
  { "action": "set_border", "range": "A6:AL30", "style": "SOLID", "color": "#CCCCCC", "width": 1 },
  { "action": "set_border", "range": "J6:AI30", "style": "NONE" },
  { "action": "set_border", "range": "A1:AL5", "style": "SOLID", "color": "#000000", "width": 1 },
  { "action": "set_row_height", "sheet": 0, "start_index": 6, "end_index": 30, "height": 21 },
  { "action": "set_background", "range": "A5:AL5", "color": "#E8E8E8" }
]

### Example 6: Complete "recreate the form" — wipe and rebuild from scratch
User says: "delete the form and recreate for me"
Output:
[
  { "action": "clear_sheet" },
  { "action": "set_value", "range": "A1", "value": "Project: [Project Name]" },
  { "action": "set_value", "range": "A2", "value": "Project Leader: [Name]" },
  { "action": "set_value", "range": "A3", "value": "Project Objective: [Text]" },
  { "action": "set_value", "range": "A4", "value": "Start Date: [Date] | Deadline: [Date]" },
  { "action": "set_value", "range": "A5", "value": "Sub objective | Major Tasks (Deadline) | Project Completed By: N weeks | Owner / Priority" },
  { "action": "set_border", "range": "A1:AL5", "style": "SOLID", "color": "#000000", "width": 1 },
  { "action": "set_background", "range": "A5:AL5", "color": "#E8E8E8" },
  { "action": "set_font_size", "range": "A1:AL5", "size": 10 },
  { "action": "set_bold", "range": "A1:AL5", "bold": true }
]

## Available actions

### Row / Column operations
- **insert_rows**: Add rows in task area
  params: { sheet, start_index, count }

- **delete_rows**: Remove task rows
  params: { sheet, start_index, count }

- **set_row_height**: Set pixel height for one or more rows
  params: { sheet, start_index, end_index, height (pixels) }

- **set_column_width**: Set pixel width for one or more columns
  params: { sheet, start_index, end_index, width (pixels) }
  Use column index numbers (A=1, B=2, …).

### Formatting operations
- **copy_format**: Clone style from row
  params: { from_range, to_range }

- **set_border**: Apply or remove borders on a range. Supports per-side control and style selection.
  params: { range, style (SOLID/SOLID_MEDIUM/SOLID_THICK/DASHED/DOTTED/DOUBLE/NONE), color, width }
  Per-side overrides (optional): top_style, top_color, top_width, bottom_style, bottom_color, bottom_width, left_style, left_color, left_width, right_style, right_color, right_width, inner_horizontal_style, inner_horizontal_color, inner_horizontal_width, inner_vertical_style, inner_vertical_color, inner_vertical_width
  Use style=NONE to remove borders. Example to remove all borders: { "range": "A1:B2", "style": "NONE" }
  Example to add a thick top border only: { "range": "A1:B2", "style": "NONE", "top_style": "SOLID_THICK", "top_color": "#000000", "top_width": 2 }

- **set_background**: Fill cells with color
  params: { range, color (hex) }

- **clear_background**: Remove fill color
  params: { range }

- **set_text_wrap**: CLIP / WRAP / OVERFLOW
  params: { range, mode }

- **set_bold**: Toggle bold text
  params: { range, bold (true/false) }

- **set_text_color**: Change font color
  params: { range, color (hex) }

- **set_font_size**: Change font size in points
  params: { range, size (integer, e.g. 10, 12, 14) }

- **set_font_family**: Change font family
  params: { range, family (e.g. "Arial", "Roboto") }

- **set_alignment**: Horizontal and vertical alignment
  params: { range, horizontal (LEFT/CENTER/RIGHT), vertical (TOP/MIDDLE/BOTTOM) }

- **set_number_format**: Apply number/currency/date format
  params: { range, pattern (e.g. "#,##0", "$#,##0.00", "yyyy-mm-dd", "0%") }

- **clear_sheet**: WIPE the entire OPPM sheet clean — removes all values, formatting, borders, backgrounds, merges, and resets row heights/column widths to standard OPPM defaults. Use this when the user says "delete the form and recreate", "start over", "clear everything", or "wipe the sheet".
  params: { } (no parameters needed)
  After clear_sheet, you MUST rebuild the entire form from scratch using set_value, set_border, set_background, set_font_size, etc.

### Cell content operations
- **set_value**: Write text into a cell
  params: { range, value }

- **set_formula**: Write a formula into a cell
  params: { range, formula (e.g. "=SUM(A1:A10)") }

- **clear_content**: Erase cell values
  params: { range }

- **set_note**: Attach a note/comment to a cell
  params: { range, note }

- **set_hyperlink**: Add a clickable link
  params: { range, url, text (optional display text) }

- **merge_cells**: Merge a range into one cell
  params: { range }

- **unmerge_cells**: Split a merged cell back into individual cells
  params: { range }

### Timeline & ownership
- **fill_timeline**: Color timeline bar for a task row. The backend maps dates → columns automatically.
  params: { task_row, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), color (hex, optional) }

- **clear_timeline**: Remove timeline bar for a task row
  params: { task_row }

- **set_owner**: Write one owner for one priority slot on a task row. Call once per priority level needed.
  params: { task_row, owner (initials/name), priority (A/B/C) }
  A = Primary/Owner column (AJ), B = Primary Helper (AK), C = Secondary Helper (AL)

### Sheet structure operations
- **freeze_rows**: Freeze top N rows so they stay visible while scrolling
  params: { sheet, row_count }

- **freeze_columns**: Freeze left N columns so they stay visible while scrolling
  params: { sheet, column_count }

- **set_conditional_formatting**: Apply color rules based on cell values
  params: { range, rule_type (NUMBER_GREATER/NUMBER_LESS/TEXT_CONTAINS/BLANK/NOT_BLANK), value, color (hex) }

- **set_data_validation**: Restrict what values can be entered
  params: { range, criteria (ONE_OF_LIST/NUMBER_GREATER/NUMBER_BETWEEN/TEXT_CONTAINS), values (array), allow_empty (true/false) }

- **protect_range**: Lock a range so only certain users can edit it
  params: { range, description (optional) }

- **unprotect_range**: Remove protection from a range
  params: { range }

## Decision rules

RULE: Row numbers come ONLY from the PROJECT CONTEXT block. Never invent a row number.

RULE: When inserting new task rows, ALWAYS follow this sequence: (1) insert_rows, (2) copy_format from the row above, (3) set_border on the new rows, (4) set_value for the task number (column H) and task name (column I). Never insert without restoring format and writing the task label.

RULE: Task number goes in column H (e.g. "1", "2.1"). Task title goes in column I. Never write task numbers or names anywhere else.

RULE: Sub-objective checkmarks for a task go in columns A–F. Column position = sub-objective position number (A=1, B=2, C=3, D=4, E=5, F=6). Use set_value with "✓" or clear_content to toggle them.

RULE: If a task name is long, apply set_text_wrap with mode=CLIP on column I for that row range. Never use WRAP in the task area — it changes row heights and breaks the visual layout.

RULE: For fill_timeline, always use ISO dates (YYYY-MM-DD). Take start_date and end_date from the project context timeline. The backend reads the sheet's actual column header dates and maps them correctly.

RULE: After deleting task rows, renumber all affected task number cells (column H) via set_value so there are no gaps (e.g. 1, 2, 3 not 1, 2, 4).

RULE: To assign owners, call set_owner once per priority slot (A/B/C). Three calls needed to set all three slots.

RULE: Rows 1–5 are the protected OPPM header zone. Never call insert_rows, set_value, set_background, or clear_content on any range that includes rows 1–5. Only project metadata fields (leader, name, objective, dates) can be written to specific header cells if the user explicitly asks and you know the exact cell.

RULE: When filling multiple cells with the same background color (e.g. a timeline bar), use a single set_background action with the full range — never loop cell-by-cell. However, fill_timeline is preferred over manual set_background for timeline bars because it handles date-to-column mapping automatically.

RULE: If you cannot determine the exact row or range from the user's message and the context, ask ONE clarifying question before outputting any JSON. Never output actions with guessed row numbers.

RULE: When the user says "make it standard", "standardize", "fix formatting", or "apply standard layout", you MUST output a comprehensive sequence that: (1) sets all column widths to standard values, (2) sets all task row heights to 21px, (3) removes all existing borders from task rows, (4) re-applies standard thin #CCCCCC borders to task rows, (5) ensures header rows have black borders, (6) sets header row 5 background to #E8E8E8, (7) sets all fonts/sizes/alignments to standard values, (8) ensures timeline area has NO borders. Use the Standard OPPM Format Reference section above for exact values.

RULE: When a CURRENT SHEET STATE snapshot is provided, compare it against the Standard OPPM Format Reference BEFORE outputting actions. Only output actions for cells/rows that deviate from the standard. For example, if a task row already has thin #CCCCCC borders, do NOT output set_border for that row. If a cell has thick borders (K/M style) or wrong colors, first remove with style=NONE then re-apply the correct format.

RULE: When the user says "add border", "border this", "put border here", or references a specific cell/range with border intent, use the CURRENT SHEET STATE to determine what borders currently exist. Then output set_border actions that ADD borders where they are missing. Do NOT remove existing borders unless the user explicitly asks. Use style=SOLID, width=1, color=#CCCCCC for task area borders, and style=SOLID, width=1, color=#000000 for header borders.

RULE: When the user says "remove border", "no border", "clear border", or "remove horizontal line", use set_border with style=NONE on the specified range. If no range is specified, remove borders from the entire task area (A6:AL100). Always confirm the range in your actions.

RULE: For merge_cells, only merge ranges that are rectangular (e.g. "A1:B2"). Never merge across the timeline area (J–AI) unless the user explicitly asks.

RULE: For set_formula, always prefix with = and use English function names (e.g. =SUM, =AVERAGE, =IF, =VLOOKUP). The formula is entered with USER_ENTERED mode so relative references adjust automatically.

RULE: For set_number_format, use Google Sheets pattern syntax:
  - Number: "#,##0" or "#,##0.00"
  - Currency: "$#,##0.00" or "¥#,##0"
  - Percentage: "0%" or "0.00%"
  - Date: "yyyy-mm-dd" or "dd-mmm-yyyy"
  - Time: "hh:mm:ss"

RULE: For set_conditional_formatting, keep rules simple. One rule per action call. Common rule_type values: NUMBER_GREATER, NUMBER_LESS, TEXT_CONTAINS, BLANK, NOT_BLANK.

RULE: For set_data_validation, criteria values:
  - ONE_OF_LIST → values = ["Option A", "Option B"]
  - NUMBER_GREATER → values = [10]
  - NUMBER_BETWEEN → values = [0, 100]
  - TEXT_CONTAINS → values = ["keyword"]

## OPPM sheet structure

HEADER ROWS (rows 1–5): Project metadata. NEVER modify with insert/set_background.
  - Row 2: "Project Leader: <name>" cell | "Project Name: <title>" cell
  - Row 3: Project objective + deliverable output (merged cell block)
  - Row 4: Start Date | Deadline
  - Row 5: Column headers ("Sub objective" | "Major Tasks (Deadline)" | "Project Completed By: N weeks" | "Owner / Priority")

TASK AREA (rows 6–N): Each row = one task or sub-task.
  - Columns A–F: Sub-objective checkboxes (✓ or blank). Column A = sub-obj 1, B = 2, … F = 6.
  - Column G: (empty / separator between sub-obj and task area)
  - Column H: Task number label (e.g. "1", "2", "2.1", "4.3"). Merged with title for main tasks.
  - Column I: Task title text. For sub-tasks, title is in column I; for main tasks H+I are merged.
  - Columns J–AI: Timeline grid. Each column = one week. Column headers (row 30+) are week dates.
  - Columns AJ–AL: Owner / Priority slots. AJ = A (primary owner), AK = B (helper), AL = C (secondary).

PEOPLE-COUNT ROW: A row containing "# People working on the project: N" — appears between the task area and the timeline header row. Do not overwrite the count formula or label.

TIMELINE HEADER ROW (row ~30): Contains week date values (e.g. "26-Apr-2026") for each column J-AI.

OWNER HEADER ROW (row ~30): Contains team member names for each column AJ-AL. These are written by Push AI Fill. You should only update them if the user explicitly asks.

SUB-OBJECTIVE MATRIX (rows 30–40): Visual cross-reference area showing which tasks map to which sub-objective. Do not auto-edit unless explicitly asked.

PRIORITY LEGEND (rows 6–10, right side beyond AL): Reference only. Do not overwrite.

## Output format — STRICT

Always return a raw JSON array. No markdown fences. No explanation before or after.

[
  { "action": "insert_rows", "params": { "sheet": "OPPM", "start_index": 16, "count": 1 } },
  { "action": "copy_format", "params": { "from_range": "A15:AL15", "to_range": "A16:AL16" } },
  { "action": "set_border", "params": { "range": "A16:AL16", "style": "solid", "width": 1, "color": "#CCCCCC" } },
  { "action": "set_value", "params": { "range": "H16", "value": "5" } },
  { "action": "set_value", "params": { "range": "I16", "value": "New feature task" } }
]

Rules:
- "sheet" is always the exact sheet tab name (e.g. "OPPM")
- "range" is always A1 notation (e.g. "H6", "A6:AL6")
- Colors use hex strings (e.g. "#1D9E75")
- Row indexes are 1-based (row 1 = first row of the sheet)
- Never output partial JSON. Always output a complete valid array.
- For fill_timeline, use ISO dates (YYYY-MM-DD) from the project context — not column letters.

## Color reference

- BACKGROUND FILL: Green=#1D9E75 (on track), Yellow=#EF9F27 (at risk), Red=#E24B4A (late/blocked).
- BORDERS: Re-apply after every insert_rows. Style=SOLID, width=1, color=#CCCCCC for task rows.
- DEFAULT TIMELINE COLOR: #1D9E75 (green/on-track) unless user specifies otherwise.
- CLEARING: clear_content removes values only (not formatting). Use clear_background to remove fill color.
"""

_OPPM_SHEET_PROMPT_KEY = "oppm_sheet_prompt"

# First task row in the OPPM sheet (row after the 5-row header)
_OPPM_FIRST_TASK_ROW = 6


async def _fetch_oppm_sheet_system_prompt(session: AsyncSession, workspace_id: str) -> str:
    """Return the custom OPPM sheet system prompt for the workspace, falling back to the default."""
    try:
        from shared.models.workspace_ai_config import WorkspaceAiConfig
        result = await session.execute(
            select(WorkspaceAiConfig).where(
                WorkspaceAiConfig.workspace_id == workspace_id,
                WorkspaceAiConfig.config_key == _OPPM_SHEET_PROMPT_KEY,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        if row and row.config_value:
            return row.config_value
    except Exception as e:
        logger.warning("Failed to fetch OPPM sheet prompt from DB (using default): %s", e)
    return _OPPM_SHEET_SYSTEM_PROMPT_DEFAULT


async def _build_oppm_sheet_context(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    spreadsheet_id: str | None = None,
) -> str:
    """Build a concise project context block for the OPPM sheet AI.

    Provides:
    - Project metadata (name, leader, start/deadline)
    - OPPM task items with ESTIMATED row numbers (sequential from row 6)
    - Timeline week dates in use (so AI can provide correct ISO dates to fill_timeline)
    - Sub-objective positions and labels
    - Team member names for owner assignment
    """
    lines: list[str] = ["## LIVE PROJECT CONTEXT (use this — do not guess)"]

    # ── Project metadata ──
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project:
        return "\n".join(lines)

    lines.append(f'Project Name: {project.title}')
    if project.start_date:
        lines.append(f'Start Date: {project.start_date.isoformat()}')
    if project.deadline:
        lines.append(f'Deadline: {project.deadline.isoformat()}')

    # OPPM header (leader text, people count)
    try:
        header_result = await session.execute(
            select(OPPMHeader).where(OPPMHeader.project_id == project_id).limit(1)
        )
        header = header_result.scalar_one_or_none()
        if header:
            if header.project_leader_text:
                lines.append(f'Project Leader: {header.project_leader_text}')
            if header.people_count:
                lines.append(f'People on project: {header.people_count}')
    except Exception as e:
        logger.debug("OPPM header load skipped: %s", e)

    if spreadsheet_id:
        lines.append(f'Spreadsheet ID: {spreadsheet_id}')
        lines.append('Sheet tab name: OPPM')

    # ── Sub-objectives (A=pos1 … F=pos6) ──
    try:
        sub_obj_result = await session.execute(
            select(OPPMSubObjective)
            .where(OPPMSubObjective.project_id == project_id)
            .order_by(OPPMSubObjective.position)
        )
        sub_objs = sub_obj_result.scalars().all()
        if sub_objs:
            col_letters = ["A", "B", "C", "D", "E", "F"]
            lines.append("")
            lines.append("### Sub-objective columns (A–F)")
            for s in sub_objs:
                col = col_letters[s.position - 1] if 1 <= s.position <= 6 else f"pos{s.position}"
                lines.append(f'  Col {col} (position {s.position}): {s.label}')
    except Exception as e:
        logger.debug("Sub-objectives load skipped: %s", e)

    # ── OPPM Task Items with estimated row numbers ──
    try:
        task_items_result = await session.execute(
            select(OPPMTaskItem)
            .where(OPPMTaskItem.project_id == project_id)
            .order_by(OPPMTaskItem.sort_order, OPPMTaskItem.created_at)
        )
        task_items = task_items_result.scalars().all()
        if task_items:
            lines.append("")
            lines.append(f"### OPPM Task Layout (rows start at {_OPPM_FIRST_TASK_ROW})")
            lines.append("  Row | Number | Title                              | Deadline")
            lines.append("  ----|--------|------------------------------------|---------")
            for i, item in enumerate(task_items):
                estimated_row = _OPPM_FIRST_TASK_ROW + i
                deadline_part = item.deadline_text or ""
                lines.append(
                    f"  {estimated_row:<4} | {item.number_label:<6} | {item.title[:34]:<34} | {deadline_part}"
                )
            next_free_row = _OPPM_FIRST_TASK_ROW + len(task_items)
            lines.append(f"  Next available row: {next_free_row}")
    except Exception as e:
        logger.debug("OPPM task items load skipped: %s", e)

    # ── Timeline week dates ──
    try:
        tl_result = await session.execute(
            select(OPPMTimelineEntry.week_start)
            .where(OPPMTimelineEntry.project_id == project_id)
            .order_by(OPPMTimelineEntry.week_start)
            .distinct()
        )
        week_dates = sorted({str(r.week_start) for r in tl_result.all()})
        if week_dates:
            lines.append("")
            lines.append("### Timeline weeks in use (ISO dates for fill_timeline)")
            lines.append("  " + ", ".join(week_dates[:20]))
            if len(week_dates) > 20:
                lines.append(f"  … and {len(week_dates) - 20} more weeks")
        elif project.start_date and project.deadline:
            # Generate synthetic weekly dates from project dates
            from datetime import timedelta
            start = project.start_date
            end = project.deadline
            # align to Monday
            start = start - timedelta(days=start.weekday())
            end = end - timedelta(days=end.weekday())
            synthetic = []
            cur = start
            while cur <= end and len(synthetic) < 20:
                synthetic.append(cur.isoformat())
                cur = cur + timedelta(weeks=1)
            if synthetic:
                lines.append("")
                lines.append("### Timeline weeks (derived from project dates, ISO format)")
                lines.append("  " + ", ".join(synthetic))
    except Exception as e:
        logger.debug("Timeline dates load skipped: %s", e)

    # ── Team members (for set_owner) ──
    try:
        members_result = await session.execute(
            select(WorkspaceMember.id, WorkspaceMember.display_name, WorkspaceMember.role)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        members = members_result.all()
        if members:
            lines.append("")
            lines.append("### Team members (use their names/initials in set_owner)")
            for m in members:
                name = m.display_name or str(m.id)[:8]
                lines.append(f"  - {name} ({m.role})")
    except Exception as e:
        logger.debug("Team members load skipped: %s", e)

    lines.append("")
    lines.append("## END PROJECT CONTEXT")
    return "\n".join(lines)


# ── Context budget: max ~8K tokens ≈ 32K chars ──
_MAX_CONTEXT_CHARS = 32_000
_TIER1_BUDGET = 16_000  # always: project meta, objectives, risks, costs
_TIER2_BUDGET = 12_000  # if fits: task detail, timeline, deliverables, forecasts
_TIER3_BUDGET = 4_000   # optional: commits, member skills
_PROJECT_HISTORY_MAX_MESSAGES = 12
_PROJECT_HISTORY_MAX_CHARS = 8_000
_WORKSPACE_HISTORY_MAX_MESSAGES = 20
_WORKSPACE_HISTORY_MAX_CHARS = 12_000
_MAX_HISTORY_MESSAGE_CHARS = 2_000
_TRUNCATION_MARKER = "\n...[message truncated]"


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max(max_chars - len(_TRUNCATION_MARKER), 0)
    return text[:head] + _TRUNCATION_MARKER


def _truncate_prompt_history(
    messages: list[dict],
    *,
    max_messages: int,
    max_chars: int,
) -> tuple[list[dict], int]:
    """Keep the most recent chat history within a bounded prompt budget."""
    if not messages:
        return [], 0

    recent_messages = messages[-max_messages:]
    kept_messages: list[dict] = []
    total_chars = 0

    for message in reversed(recent_messages):
        content = _clip_text(str(message.get("content", "")), _MAX_HISTORY_MESSAGE_CHARS)
        if kept_messages and total_chars + len(content) > max_chars:
            break
        if not kept_messages and len(content) > max_chars:
            content = _clip_text(content, max_chars)

        kept_messages.append({
            "role": message.get("role", "user"),
            "content": content,
        })
        total_chars += len(content)

    kept_messages.reverse()
    return kept_messages, total_chars


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
    oppm_sheet_mode: bool = False,
    spreadsheet_id: str | None = None,
    sheet_snapshot: dict | None = None,
    force_skill: str | None = None,
) -> dict:
    """
    Send a chat message to the AI about a project.
    Returns the AI response message + any tool call results.
    """
    if oppm_sheet_mode:
        return await _oppm_sheet_chat(
            session, project_id, workspace_id, user_id, messages, model_id,
            spreadsheet_id=spreadsheet_id,
            sheet_snapshot=sheet_snapshot,
        )
    return await _chat_async(
        session, project_id, workspace_id, user_id, messages, model_id,
        force_skill=force_skill,
    )


async def _oppm_sheet_chat(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
    spreadsheet_id: str | None = None,
    sheet_snapshot: dict | None = None,
) -> dict:
    """OPPM sheet mode — use the OPPM sheet system prompt + live project context.

    Bypasses the agentic loop (no tool execution). The frontend parses the JSON action array
    and applies it to the Google Sheet via the execute_sheet_actions endpoint.
    """
    from infrastructure.llm import call_with_fallback_tools
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)

    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    # Try to get spreadsheet_id from project metadata if not passed
    if not spreadsheet_id:
        metadata = project.metadata_ or {}
        sheet_link = metadata.get("google_sheet") or {}
        spreadsheet_id = sheet_link.get("spreadsheet_id")

    last_user_msg = messages[-1]["content"] if messages else ""
    is_safe, reason = check_input(last_user_msg)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    models = await _get_models(session, workspace_id, model_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured. Add one in Settings → AI Models.")

    # Build system prompt + live project context
    system_prompt = await _fetch_oppm_sheet_system_prompt(session, workspace_id)
    project_context = await _build_oppm_sheet_context(
        session, project_id, workspace_id, spreadsheet_id=spreadsheet_id
    )

    # Append live sheet snapshot if provided
    snapshot_context = ""
    if sheet_snapshot:
        snapshot_lines = ["## CURRENT SHEET STATE (live snapshot — use this to detect what needs changing)"]
        snapshot_lines.append(f"Sheet: {sheet_snapshot.get('sheet_title', 'OPPM')}")
        snapshot_lines.append(f"Dimensions: {sheet_snapshot.get('max_row', 0)} rows x {sheet_snapshot.get('max_col', 0)} cols")

        merges = sheet_snapshot.get("merge_ranges", [])
        if merges:
            snapshot_lines.append(f"Merged cells: {', '.join(merges[:10])}")
            if len(merges) > 10:
                snapshot_lines.append(f"  ... and {len(merges) - 10} more merges")

        cells = sheet_snapshot.get("cells", [])
        if cells:
            snapshot_lines.append("")
            snapshot_lines.append("### Non-empty / formatted cells (r=row, c=col, v=value, bg=background, b=borders, bold, fs=fontSize, fg=foreground)")
            # Show first 60 cells to stay within token budget
            for cell in cells[:60]:
                parts = [f"({cell['r']},{cell['c']})"]
                if "v" in cell:
                    parts.append(f"v='{cell['v']}'")
                if "bg" in cell:
                    parts.append(f"bg={cell['bg']}")
                if "b" in cell:
                    parts.append(f"b={cell['b']}")
                if cell.get("bold"):
                    parts.append("bold")
                if "fs" in cell:
                    parts.append(f"fs={cell['fs']}")
                if "fg" in cell:
                    parts.append(f"fg={cell['fg']}")
                snapshot_lines.append("  " + " | ".join(parts))
            if len(cells) > 60:
                snapshot_lines.append(f"  ... and {len(cells) - 60} more formatted cells")
        snapshot_context = "\n".join(snapshot_lines)

    full_system_prompt = f"{system_prompt}\n\n{project_context}"
    if snapshot_context:
        full_system_prompt = f"{full_system_prompt}\n\n{snapshot_context}"

    truncated_messages, _ = _truncate_prompt_history(
        messages,
        max_messages=_PROJECT_HISTORY_MAX_MESSAGES,
        max_chars=_PROJECT_HISTORY_MAX_CHARS,
    )
    llm_messages = [{"role": "system", "content": full_system_prompt}]
    for msg in truncated_messages:
        llm_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    try:
        llm_response = await call_with_fallback_tools(models, llm_messages, tools=None)
        raw_text = llm_response.text if hasattr(llm_response, "text") else str(llm_response)
    except Exception as e:
        logger.warning("OPPM sheet chat LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    clean_text = sanitize_output(raw_text)

    await audit_repo.log(
        workspace_id, user_id,
        "ai_chat", "oppm_sheet_chat",
        new_data={
            "project_id": project_id,
            "user_message": last_user_msg[:500],
            "ai_response": clean_text[:500],
        },
    )

    return {
        "message": clean_text,
        "tool_calls": [],
        "updated_entities": [],
        "iterations": 1,
        "low_confidence": False,
    }


async def _chat_async(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    messages: list[dict],
    model_id: str | None = None,
    on_tool_result=None,
    force_skill: str | None = None,
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

    # ── Skill Router ──
    # Pick a skill based on the user's last message. The skill determines which
    # tools are exposed and what system prompt specialization is injected.
    skill = await pick_skill(last_user_msg, models=models)
    skill_ctx = None
    if skill.name != "general":
        skill_ctx = SkillContext(
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if skill.pre_flight is not None:
            preflight_data = await skill.pre_flight(session, skill_ctx)
            skill_ctx.preflight_data = preflight_data
            skill_ctx.extra_system_prompt = skill.system_prompt
        else:
            skill_ctx.extra_system_prompt = skill.system_prompt
        logger.info("project_chat: activated skill=%s", skill.name)
    else:
        logger.debug("project_chat: no skill matched — general fallback")

    # ── Build tool section and system prompt ──
    registry = get_registry()
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    # Filter tools to only those allowed by the skill
    all_tools = registry.all_tools()
    allowed_names = skill.allowed_tool_names(all_tools)
    if skill.name != "general":
        logger.debug("project_chat: skill=%s allowed_tools=%s", skill.name, sorted(allowed_names))

    if use_native_tools:
        tool_section = (
            "## Tools\n"
            "You have tools available via native function calling. "
            "Use them when the user asks to make changes. "
            "You may call multiple tools across multiple turns to gather all needed information."
        )
    else:
        tool_section = registry.to_prompt_text(filter_names=allowed_names)

    system_prompt = SYSTEM_PROMPT.format(
        project_context=context,
        rag_context=full_rag,
        tool_section=tool_section,
    )

    # ── Build initial conversation for the agentic loop ──
    truncated_messages, history_chars = _truncate_prompt_history(
        messages,
        max_messages=_PROJECT_HISTORY_MAX_MESSAGES,
        max_chars=_PROJECT_HISTORY_MAX_CHARS,
    )
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in truncated_messages:
        llm_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    total_chars = len(system_prompt) + history_chars
    logger.info(
        "project_chat prompt: system=%d chars, history=%d msgs (truncated from %d), total_chars=%d (~%d tokens) | rag=%d chars, memory=%d chars",
        len(system_prompt),
        len(truncated_messages),
        len(messages),
        total_chars,
        _estimate_tokens(system_prompt) + (history_chars // 4),
        len(rag_context),
        len(memory_context),
    )

    openai_tools = registry.to_openai_schema(filter_names=allowed_names) if use_native_tools else None
    anthropic_tools = registry.to_anthropic_schema(filter_names=allowed_names) if use_native_tools else None

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
            skill_context=skill_ctx,
        )
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable. Please try again later.")
    except Exception as e:
        logger.warning("Agent loop failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    # ── Output guardrail ──
    clean_text = sanitize_output(loop_result.final_text)

    # ── Skill post-flight ──
    if skill_ctx is not None and skill.post_flight is not None:
        try:
            skill_result = SkillResult(
                final_text=clean_text,
                tool_results=loop_result.all_tool_results,
                updated_entities=loop_result.updated_entities,
                iterations=loop_result.iterations,
                low_confidence=loop_result.low_confidence,
            )
            postflight = await skill.post_flight(session, skill_ctx, skill_result)
            logger.info("project_chat: skill=%s post_flight=%s", skill.name, postflight)
        except Exception as e:
            logger.warning("project_chat: skill=%s post_flight failed: %s", skill.name, e)

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

    lead_name: str | None = None
    if project.lead_id:
        lead_result = await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.id == project.lead_id)
            .limit(1)
        )
        lead_row = lead_result.first()
        if lead_row:
            lead_name = _resolve_member_name(lead_row[0], lead_row[1])

    member_result = await session.execute(
        select(ProjectMember, WorkspaceMember, User)
        .join(WorkspaceMember, WorkspaceMember.id == ProjectMember.member_id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    member_names = [
        _resolve_member_name(workspace_member, user)
        for _, workspace_member, user in member_result.all()
    ]
    member_names = [name for name in member_names if name]
    if not member_names and lead_name:
        member_names = [lead_name]

    task_repo = TaskRepository(session)
    existing_tasks = await task_repo.find_project_tasks(project_id, limit=500)
    existing_tasks = sorted(
        existing_tasks,
        key=lambda task: (task.parent_task_id is not None, task.sort_order or 0, str(task.created_at)),
    )

    models = await _get_models(session, workspace_id)
    if not models:
        raise HTTPException(status_code=400, detail="No active AI model configured.")

    task_context = "\n".join(f"- {task.title}" for task in existing_tasks[:30]) or "- No current tasks"
    team_context = "\n".join(f"- {name}" for name in member_names[:12]) or "- Team not assigned"
    people_count = len(member_names) if member_names else None

    prompt = f"""You are an OPPM project planning assistant. Generate a structured native OPPM draft.

Project: "{project.title}"
Start: {project.start_date or 'not set'}
Deadline: {project.deadline or 'not set'}
Project leader: {lead_name or 'not set'}
Team members:
{team_context}

Current project tasks (reuse these titles exactly when they already fit the plan):
{task_context}

Description from user: {description}

Return ONLY valid JSON with this structure:
{{
    "header": {{
        "project_leader": "Project leader name",
        "project_objective": "One sentence describing what this project aims to achieve.",
        "deliverable_output": "One sentence describing the final output.",
        "completed_by_text": "Short completion target text",
        "people_count": 3
    }},
    "objectives": [
        {{
            "title": "Objective name",
            "suggested_weeks": ["W1", "W2"],
            "tasks": [
                {{
                    "title": "Task title",
                    "priority": "medium",
                    "suggested_weeks": ["W1"],
                    "subtasks": ["Sub-task one", "Sub-task two"]
                }}
            ]
        }}
    ],
  "explanation": "Brief explanation of the plan"
}}

Rules:
- Generate 3-6 objectives with logical week assignments. Use W1-W8 format.
- Prefer the current project task titles when they already describe the work well.
- Keep `project_objective` and `deliverable_output` under 120 characters each.
- Do not invent IDs.
- Keep task lists concise and practical for an OPPM summary view."""

    try:
        response = await call_with_fallback(models, prompt)
    except ProviderUnavailableError as e:
        logger.warning("All LLM providers unavailable for suggest_plan: %s", e)
        raise HTTPException(status_code=502, detail="All AI models are currently unavailable.")
    except Exception as e:
        logger.warning("Suggest plan LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"AI model call failed: {str(e)}")

    raw_text = response.text.strip() if response else ""
    result = _extract_json_payload(raw_text)

    if not result:
        raise HTTPException(status_code=502, detail="AI returned empty response")

    raw_header = result.get("header") if isinstance(result.get("header"), dict) else {}
    normalized_header = {
        "project_leader": raw_header.get("project_leader") or lead_name,
        "project_objective": raw_header.get("project_objective") or project.objective_summary,
        "deliverable_output": raw_header.get("deliverable_output") or project.deliverable_output,
        "completed_by_text": raw_header.get("completed_by_text") or (str(project.deadline) if project.deadline else None),
        "people_count": raw_header.get("people_count") if isinstance(raw_header.get("people_count"), int) else people_count,
    }

    normalized_objectives = []
    for raw_objective in result.get("objectives", result.get("suggested_objectives", [])):
        if not isinstance(raw_objective, dict):
            continue
        title = str(raw_objective.get("title") or "").strip()
        if not title:
            continue

        tasks = []
        for raw_task in raw_objective.get("tasks", []):
            if not isinstance(raw_task, dict):
                continue
            task_title = str(raw_task.get("title") or "").strip()
            if not task_title:
                continue
            subtasks = [
                str(item).strip()
                for item in raw_task.get("subtasks", [])
                if str(item).strip()
            ]
            tasks.append({
                "title": task_title,
                "priority": _normalize_priority(raw_task.get("priority")),
                "suggested_weeks": _normalize_week_labels(raw_task.get("suggested_weeks")),
                "subtasks": subtasks,
            })

        normalized_objectives.append({
            "title": title,
            "suggested_weeks": _normalize_week_labels(raw_objective.get("suggested_weeks")),
            "tasks": tasks,
        })

    if not normalized_objectives:
        raise HTTPException(status_code=502, detail="AI returned no usable objectives")

    # Store preview with a commit token
    token = str(uuid.uuid4())
    _plan_cache[token] = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "header": normalized_header,
        "objectives": normalized_objectives,
    }

    return {
        "header": normalized_header,
        "suggested_objectives": normalized_objectives,
        "explanation": result.get("explanation", ""),
        "commit_token": token,
        "existing_task_count": len(existing_tasks),
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
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found in this workspace")

    objective_repo = ObjectiveRepository(session)
    task_repo = TaskRepository(session)
    timeline_repo = TimelineRepository(session)
    audit_repo = AuditRepository(session)
    await project_repo.update(project_id, {
        "objective_summary": plan.get("header", {}).get("project_objective"),
        "deliverable_output": plan.get("header", {}).get("deliverable_output"),
    })
    await _upsert_oppm_header(
        session,
        project_id,
        workspace_id,
        {
            "project_leader_text": plan.get("header", {}).get("project_leader"),
            "completed_by_text": plan.get("header", {}).get("completed_by_text"),
            "people_count": plan.get("header", {}).get("people_count"),
        },
    )

    existing_objectives = await objective_repo.find_with_tasks(project_id)
    existing_objective_map = {
        _normalize_title(objective.get("title")): objective
        for objective in existing_objectives
        if objective.get("title")
    }
    existing_tasks = await task_repo.find_project_tasks(project_id, limit=1000)
    root_task_map: dict[str, list] = {}
    child_task_map: dict[tuple[str, str], list] = {}
    for task in existing_tasks:
        title_key = _normalize_title(task.title)
        if task.parent_task_id is None:
            root_task_map.setdefault(title_key, []).append(task)
        else:
            child_task_map.setdefault((str(task.parent_task_id), title_key), []).append(task)

    claimed_root_ids: set[str] = set()
    claimed_child_ids: set[str] = set()

    def _take_unclaimed(candidates: list, claimed: set[str]):
        for candidate in candidates:
            candidate_id = str(candidate.id)
            if candidate_id not in claimed:
                claimed.add(candidate_id)
                return candidate
        return None

    created_objective_count = 0
    updated_objective_count = 0
    created_task_count = 0
    updated_task_count = 0
    created_timeline_entries = 0

    for objective_index, obj_data in enumerate(plan.get("objectives", []), start=1):
        objective_title = obj_data["title"]
        objective_key = _normalize_title(objective_title)
        existing_objective = existing_objective_map.get(objective_key)
        if existing_objective:
            objective = await objective_repo.update(existing_objective["id"], {
                "title": objective_title,
                "sort_order": objective_index,
            })
            updated_objective_count += 1
        else:
            objective = await objective_repo.create({
                "project_id": project_id,
                "title": objective_title,
                "sort_order": objective_index,
            })
            created_objective_count += 1

        objective_id = objective.id if objective else existing_objective["id"]
        objective_weeks = _normalize_week_labels(obj_data.get("suggested_weeks"))

        for task_index, task_data in enumerate(obj_data.get("tasks", []), start=1):
            task_title = task_data["title"]
            task_key = _normalize_title(task_title)
            existing_root = _take_unclaimed(root_task_map.get(task_key, []), claimed_root_ids)
            root_payload = {
                "title": task_title,
                "project_id": project_id,
                "oppm_objective_id": objective_id,
                "priority": _normalize_priority(task_data.get("priority")),
                "sort_order": objective_index * 100 + task_index,
                "start_date": _task_start_date(project, task_data.get("suggested_weeks", []), objective_weeks),
                "due_date": _task_due_date(project, task_data.get("suggested_weeks", []), objective_weeks),
                "created_by": user_id,
            }
            if existing_root:
                root_task = await task_repo.update(existing_root.id, root_payload)
                updated_task_count += 1
            else:
                root_task = await task_repo.create(root_payload)
                created_task_count += 1

            task_weeks = _normalize_week_labels(task_data.get("suggested_weeks")) or objective_weeks
            for week_label in task_weeks:
                week_start = _week_label_to_date(project, week_label)
                if not week_start:
                    continue
                await timeline_repo.upsert_entry({
                    "project_id": project_id,
                    "task_id": root_task.id,
                    "week_start": week_start,
                    "status": "planned",
                })
                created_timeline_entries += 1

            for subtask_index, subtask_title in enumerate(task_data.get("subtasks", []), start=1):
                subtask_key = _normalize_title(subtask_title)
                existing_child = _take_unclaimed(
                    child_task_map.get((str(root_task.id), subtask_key), []),
                    claimed_child_ids,
                )
                child_payload = {
                    "title": subtask_title,
                    "project_id": project_id,
                    "oppm_objective_id": objective_id,
                    "parent_task_id": root_task.id,
                    "priority": root_payload["priority"],
                    "sort_order": root_payload["sort_order"] * 10 + subtask_index,
                    "created_by": user_id,
                }
                if existing_child:
                    await task_repo.update(existing_child.id, child_payload)
                    updated_task_count += 1
                else:
                    await task_repo.create(child_payload)
                    created_task_count += 1

    await audit_repo.log(
        workspace_id, user_id,
        "ai_commit_plan", "oppm_plan",
        new_data={
            "objectives_created": created_objective_count,
            "objectives_updated": updated_objective_count,
            "tasks_created": created_task_count,
            "tasks_updated": updated_task_count,
            "timeline_entries_upserted": created_timeline_entries,
        },
    )

    return {
        "count": created_objective_count + updated_objective_count,
        "objectives_created": created_objective_count,
        "objectives_updated": updated_objective_count,
        "tasks_created": created_task_count,
        "tasks_updated": updated_task_count,
        "timeline_entries_upserted": created_timeline_entries,
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

    last_user_msg = messages[-1]["content"] if messages else ""
    is_safe, reason = check_input(last_user_msg)
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    # Load workspace name and project list for prompt context
    ws_row = await session.execute(
        select(Workspace.name).where(Workspace.id == workspace_id)
    )
    workspace_name = ws_row.scalar_one_or_none() or "Workspace"

    project_rows = await session.execute(
        select(Project.title, Project.status)
        .where(Project.workspace_id == workspace_id)
        .limit(50)  # Safety cap: even with 50 projects the list stays under 2K chars
    )
    projects = project_rows.all()
    if projects:
        project_list = "\n".join(f"- {p.title} ({p.status})" for p in projects)
    else:
        project_list = "(No projects yet)"

    # Retrieve RAG context via full pipeline
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

    # Build tool section — workspace-level tools ONLY (requires_project=False).
    # Injecting all project-scoped tools (objectives, tasks, costs, timeline) into the
    # system prompt exceeds Ollama's context window by ~65K tokens.
    # Once a project is created the user navigates to it and has the full tool set there.
    registry = get_registry()
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    ws_only_tools = registry.get_tools(requires_project=False)
    if use_native_tools:
        ws_tool_section = (
            "## Tools\n"
            "You have tools available via native function calling. "
            "Use them to create or update projects."
        )
        openai_tools = registry.to_openai_schema(requires_project=False)
        anthropic_tools = registry.to_anthropic_schema(requires_project=False)
    else:
        # Build prompt text for workspace-level tools only
        lines = [
            "## Available Tools",
            'To create or update projects, include a JSON tool_calls array at the END of your message inside <tool_calls>...</tool_calls> tags.',
            "",
            "Available tools:",
        ]
        for t in ws_only_tools:
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

    truncated_messages, history_chars = _truncate_prompt_history(
        messages,
        max_messages=_WORKSPACE_HISTORY_MAX_MESSAGES,
        max_chars=_WORKSPACE_HISTORY_MAX_CHARS,
    )
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in truncated_messages:
        llm_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    # Debug: log prompt composition to diagnose context overflow
    total_chars = len(system_prompt) + history_chars
    logger.info(
        "workspace_chat prompt: system=%d chars, history=%d msgs (truncated from %d), total_chars=%d (~%d tokens) | "
        "rag=%d chars, memory=%d chars, projects=%d, tools=%d",
        len(system_prompt),
        len(truncated_messages),
        len(messages),
        total_chars,
        _estimate_tokens(system_prompt) + (history_chars // 4),
        len(rag_context),
        len(memory_context),
        len(projects),
        len(ws_only_tools),
    )

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
