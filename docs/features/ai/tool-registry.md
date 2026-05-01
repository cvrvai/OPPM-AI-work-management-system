# Feature: Tool Registry And Agentic Loop

Last updated: 2026-05-01

## What It Does

- Registers all AI-callable tools with metadata, parameter schemas, and async handlers
- Exposes tools to LLMs via native function-calling APIs (OpenAI, Anthropic) or via XML-prompt injection (Ollama, Kimi)
- Runs a multi-turn agentic loop so the LLM can chain tool calls before returning a final answer

## How It Works

1. `services/intelligence/infrastructure/tools/registry.py` owns the global `ToolRegistry` singleton.
2. On first call to `get_registry()`, all five tool modules are auto-imported and their tools are registered.
3. For OpenAI and Anthropic, `to_openai_schema()` and `to_anthropic_schema()` serialize the registry to native tool descriptors.
4. For Ollama and Kimi, `to_prompt_text()` converts the registry into a prompt-text tool section that instructs the model to emit `<tool_calls>...</tool_calls>` JSON.
5. `services/intelligence/infrastructure/rag/agent_loop.py` runs the loop:
   - Calls the LLM with the current message history and tool schemas.
   - Parses `tool_calls` from the response (native JSON for OpenAI/Anthropic, JSON inside `<tool_calls>` tags for others).
   - Executes each requested tool via `registry.execute()`.
   - Injects the text results as a new user turn.
   - Deduplicates identical tool retries and can trigger an extra RAG requery when confidence is low.
   - Repeats up to 7 times or until the response contains a confident answer with no tool calls.
   - If the max is hit, makes a final summary call without tools.
6. `AgentLoopResult` carries `final_text`, `all_tool_results`, `updated_entities`, `iterations`, and `low_confidence`.

## Tool Categories

| Category | Count | Key tools |
|---|---|---|
| `oppm` | 5 | `create_objective`, `update_objective`, `delete_objective`, `set_timeline_status`, `bulk_set_timeline` |
| `task` | 5 | `create_task`, `update_task`, `delete_task`, `assign_task`, `set_task_dependency` |
| `cost` | 5 | `update_project_costs`, `create_risk`, `update_risk`, `create_deliverable`, `update_project_metadata` |
| `read` | 6 | `get_project_summary`, `get_task_details`, `search_tasks`, `get_risk_status`, `get_cost_breakdown`, `get_team_workload` |
| `project` | 3 | `create_project`, `list_workspace_projects`, `update_project` |

## Backend Files

- `services/intelligence/infrastructure/tools/__init__.py`
- `services/intelligence/infrastructure/tools/base.py`
- `services/intelligence/infrastructure/tools/registry.py`
- `services/intelligence/infrastructure/tools/oppm_tools.py`
- `services/intelligence/infrastructure/tools/task_tools.py`
- `services/intelligence/infrastructure/tools/cost_tools.py`
- `services/intelligence/infrastructure/tools/read_tools.py`
- `services/intelligence/infrastructure/tools/project_tools.py`
- `services/intelligence/infrastructure/rag/agent_loop.py`
- `services/intelligence/infrastructure/llm/tool_parser.py`
- `services/intelligence/infrastructure/llm/__init__.py`

## Detailed Tool Reference

### Registry API

File: `services/intelligence/infrastructure/tools/registry.py`

Key methods:
- `register(tool)`
- `get_tool(name)`
- `get_tools(category=None, requires_project=None)`
- `execute(name, tool_input, session, project_id, workspace_id, user_id)`
- `to_openai_schema(category=None)`
- `to_anthropic_schema(category=None)`
- `to_prompt_text(category=None)`

### Base Types

File: `services/intelligence/infrastructure/tools/base.py`

**`ToolParam`**
- `name: str`
- `type: str`
- `description: str`
- `required: bool = True`
- `enum: list[str] | None = None`
- `items_type: str | None = None`

**`ToolDefinition`**
- `name: str`
- `description: str`
- `category: str`
- `params: list[ToolParam]`
- `handler: Callable[..., Awaitable[dict[str, Any]]]`
- `requires_project: bool = True`

**`ToolResult`**
- `success: bool`
- `result: Any = None`
- `error: str | None = None`
- `updated_entities: list[str]` — flat list of table/entity groups

### All 24 Tools

#### Category: `oppm` — `oppm_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_objective` | Create an OPPM objective | `title`, optional `project_id`, `sort_order`, `owner_id` | `oppm_objectives` |
| `update_objective` | Update title or sort order | `objective_id`, optional fields | `oppm_objectives` |
| `delete_objective` | Delete an objective | `objective_id` | `oppm_objectives` |
| `set_timeline_status` | Set one task-week status | `task_id`, `week_start`, `status`, `notes?` | `oppm_timeline_entries` |
| `bulk_set_timeline` | Set many task-week statuses | `entries[]` | `oppm_timeline_entries` |

#### Category: `task` — `task_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_task` | Create a task or sub-task | optional `project_id`, `title`, `description?`, `priority?`, `oppm_objective_id?`, `assignee_id?`, `due_date?`, `project_contribution?`, `start_date?`, `parent_task_id?` | `tasks`, `projects` |
| `update_task` | Update task fields | `task_id`, optional `status`, `progress`, `title`, `priority`, `description`, `due_date` | `tasks`, `projects` |
| `delete_task` | Delete a task | `task_id` | `tasks`, `projects` |
| `assign_task` | Assign a workspace member to a task | `task_id`, `member_id` | `task_assignees`, `tasks` |
| `set_task_dependency` | Create a dependency edge | `task_id`, `depends_on_task_id` | `task_dependencies`, `tasks` |

#### Category: `cost` — `cost_tools.py`

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `update_project_costs` | Add a project cost entry | `category`, `planned_amount?`, `actual_amount?`, `description?`, `period?` | `project_costs` |
| `create_risk` | Create a project risk | `description`, `rag?`, `item_number?` | `oppm_risks` |
| `update_risk` | Update an existing risk | `risk_id`, optional `description`, `rag` | `oppm_risks` |
| `create_deliverable` | Create a deliverable | `description`, `item_number?` | `oppm_deliverables` |
| `update_project_metadata` | Update project fields from the cost module | optional `status`, `priority`, `title`, `description`, `start_date`, `deadline`, `budget` | `projects` |

#### Category: `read` — `read_tools.py` (read-only)

| Tool | Purpose | Key params |
|---|---|---|
| `get_project_summary` | Return full project metadata | none |
| `get_task_details` | Return detailed task data including assignees, owners, dependencies, and recent reports | `task_id` |
| `search_tasks` | Filter tasks by status, priority, objective, or keyword | optional `status`, `priority`, `objective_id`, `keyword` |
| `get_risk_status` | Return risks and RAG counts | none |
| `get_cost_breakdown` | Return planned vs actual by category | none |
| `get_team_workload` | Return task count and average progress per member | none |

#### Category: `project` — `project_tools.py` (`requires_project = False`)

| Tool | Purpose | Key params | Updated entities |
|---|---|---|---|
| `create_project` | Create a new project in the workspace | `title`, optional `description`, `status`, `priority`, `budget`, `start_date`, `deadline` | `projects` |
| `list_workspace_projects` | List workspace projects | none | none |
| `update_project` | Update an existing project | optional `project_id`, `title`, `description`, `status`, `priority`, `budget`, `start_date`, `deadline`, `objective_summary` | `projects` |

### Provider Integration

- **Native providers** (OpenAI, Anthropic): consume `to_openai_schema()` / `to_anthropic_schema()`
- **Prompt-based providers** (Ollama, Kimi): consume `to_prompt_text()` with `<tool_calls>` instructions

### Execution Notes

- The registry itself does not enforce authorization. Route dependencies and workspace/project context do that.
- Tool handlers execute directly against the shared database through AI-side repositories.
- Workspace chat currently exposes the full registry.
- Project chat uses the same registry but automatically injects the active `project_id` when a tool does not supply one.

### Adding A New Tool

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
4. Update this document if the public AI surface changed.

## Update Notes

- To add a new tool, add its `ToolDefinition` to the appropriate module and the registry will pick it up automatically on next import.
- `NATIVE_TOOL_PROVIDERS = {"openai", "anthropic"}` controls which providers use native calling.
- Tool results are always injected as plain-text user messages to stay provider-agnostic.
