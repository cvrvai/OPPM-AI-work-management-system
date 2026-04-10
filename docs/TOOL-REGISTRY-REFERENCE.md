# Tool Registry Reference

Last updated: 2026-04-10

## Purpose

This document describes the current AI tool registry in `services/ai/infrastructure/tools/`.

Use it when you add a tool, change a tool contract, or need to understand what the AI service can read or write during the TAOR loop.

## Overview

The registry currently exposes `24` tools across `5` categories:

- `oppm` — 5 tools
- `task` — 5 tools
- `cost` — 5 tools
- `read` — 6 tools
- `project` — 3 tools

The registry is a global singleton created by `get_registry()` in `registry.py`.

On first access it auto-imports:

- `oppm_tools.py`
- `task_tools.py`
- `cost_tools.py`
- `read_tools.py`
- `project_tools.py`

## Registry API

File:

- `services/ai/infrastructure/tools/registry.py`

Key methods:

- `register(tool)`
- `get_tool(name)`
- `get_tools(category=None, requires_project=None)`
- `execute(name, tool_input, session, project_id, workspace_id, user_id)`
- `to_openai_schema(category=None)`
- `to_anthropic_schema(category=None)`
- `to_prompt_text(category=None)`

`execute()` always runs with explicit context:

- `session`
- `project_id`
- `workspace_id`
- `user_id`

## Base Types

File:

- `services/ai/infrastructure/tools/base.py`

### `ToolParam`

- `name: str`
- `type: str`
- `description: str`
- `required: bool = True`
- `enum: list[str] | None = None`
- `items_type: str | None = None`

### `ToolDefinition`

- `name: str`
- `description: str`
- `category: str`
- `params: list[ToolParam]`
- `handler: Callable[..., Awaitable[dict[str, Any]]]`
- `requires_project: bool = True`

### `ToolResult`

- `success: bool`
- `result: Any = None`
- `error: str | None = None`
- `updated_entities: list[str]`

`updated_entities` is a flat list of table/entity groups, for example:

- `projects`
- `tasks`
- `oppm_objectives`
- `oppm_timeline_entries`

## Category: `oppm`

File:

- `services/ai/infrastructure/tools/oppm_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_objective` | Create an OPPM objective | `title`, optional `project_id`, `sort_order`, `owner_id` | `oppm_objectives` |
| `update_objective` | Update title or sort order | `objective_id`, optional fields | `oppm_objectives` |
| `delete_objective` | Delete an objective | `objective_id` | `oppm_objectives` |
| `set_timeline_status` | Set one task-week status | `task_id`, `week_start`, `status`, `notes?` | `oppm_timeline_entries` |
| `bulk_set_timeline` | Set many task-week statuses | `entries[]` | `oppm_timeline_entries` |

## Category: `task`

File:

- `services/ai/infrastructure/tools/task_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_task` | Create a task or sub-task | optional `project_id`, `title`, `description?`, `priority?`, `oppm_objective_id?`, `assignee_id?`, `due_date?`, `project_contribution?`, `start_date?`, `parent_task_id?` | `tasks`, `projects` |
| `update_task` | Update task fields | `task_id`, optional `status`, `progress`, `title`, `priority`, `description`, `due_date` | `tasks`, `projects` |
| `delete_task` | Delete a task | `task_id` | `tasks`, `projects` |
| `assign_task` | Assign a workspace member to a task | `task_id`, `member_id` | `task_assignees`, `tasks` |
| `set_task_dependency` | Create a dependency edge | `task_id`, `depends_on_task_id` | `task_dependencies`, `tasks` |

## Category: `cost`

File:

- `services/ai/infrastructure/tools/cost_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `update_project_costs` | Add a project cost entry | `category`, `planned_amount?`, `actual_amount?`, `description?`, `period?` | `project_costs` |
| `create_risk` | Create a project risk | `description`, `rag?`, `item_number?` | `oppm_risks` |
| `update_risk` | Update an existing risk | `risk_id`, optional `description`, `rag` | `oppm_risks` |
| `create_deliverable` | Create a deliverable | `description`, `item_number?` | `oppm_deliverables` |
| `update_project_metadata` | Update project fields from the cost module | optional `status`, `priority`, `title`, `description`, `start_date`, `deadline`, `budget` | `projects` |

## Category: `read`

File:

- `services/ai/infrastructure/tools/read_tools.py`

These tools are read-only and usually return an empty `updated_entities` list.

| Tool | Purpose | Key params |
|---|---|---|
| `get_project_summary` | Return full project metadata | none |
| `get_task_details` | Return detailed task data including assignees, owners, dependencies, and recent reports | `task_id` |
| `search_tasks` | Filter tasks by status, priority, objective, or keyword | optional `status`, `priority`, `objective_id`, `keyword` |
| `get_risk_status` | Return risks and RAG counts | none |
| `get_cost_breakdown` | Return planned vs actual by category | none |
| `get_team_workload` | Return task count and average progress per member | none |

## Category: `project`

File:

- `services/ai/infrastructure/tools/project_tools.py`

These tools set `requires_project = False` so they can run without an existing project context.

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_project` | Create a new project in the workspace | `title`, optional `description`, `status`, `priority`, `budget`, `start_date`, `deadline` | `projects` |
| `list_workspace_projects` | List workspace projects | none | none |
| `update_project` | Update an existing project | optional `project_id`, `title`, `description`, `status`, `priority`, `budget`, `start_date`, `deadline`, `objective_summary` | `projects` |

## Provider Integration

### Native Providers

OpenAI and Anthropic consume:

- `to_openai_schema()`
- `to_anthropic_schema()`

### Prompt-Based Providers

Ollama and Kimi consume:

- `to_prompt_text()`

Prompt-based usage tells the model to emit a JSON array inside `<tool_calls>...</tool_calls>`.

## Execution Notes

- The registry itself does not enforce authorization. Route dependencies and workspace/project context do that.
- Tool handlers execute directly against the shared database through AI-side repositories.
- Workspace chat currently exposes the full registry.
- Project chat uses the same registry but automatically injects the active `project_id` when a tool does not supply one.

## Adding A New Tool

1. Choose the correct tool module, or add a new one if a new category is justified.
2. Implement an async handler with the standard signature:

```python
async def _my_tool(
    session: AsyncSession,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> ToolResult:
    ...
```

3. Register it with `get_registry().register(ToolDefinition(...))`.
4. Update this document and the high-level architecture docs if the public AI surface changed.

## Related Files

- `services/ai/infrastructure/tools/base.py`
- `services/ai/infrastructure/tools/registry.py`
- `services/ai/infrastructure/tools/oppm_tools.py`
- `services/ai/infrastructure/tools/task_tools.py`
- `services/ai/infrastructure/tools/cost_tools.py`
- `services/ai/infrastructure/tools/read_tools.py`
- `services/ai/infrastructure/tools/project_tools.py`
- `services/ai/infrastructure/rag/agent_loop.py`
