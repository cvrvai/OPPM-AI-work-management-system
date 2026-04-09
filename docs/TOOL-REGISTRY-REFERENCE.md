# Tool Registry Reference

Last updated: 2026-04-09

## Purpose

This document describes the AI service tool registry in `services/ai/infrastructure/tools/`.

Use this file when you need to add a tool, change a tool's parameters, understand what the agentic loop can call, or debug a tool execution failure.

## Overview

The tool registry holds 21 tools across four categories. Each tool has:

- a unique name
- a description (shown to the LLM)
- a typed parameter schema
- an async handler function
- a flag for whether it requires a `project_id`

Tools are registered once at startup. The registry exposes serialization methods so the same tool definitions can be sent to any LLM provider.

## Registry API

**File:** `services/ai/infrastructure/tools/registry.py`

**Class:** `ToolRegistry`

| Method | Description |
|---|---|
| `register(tool_def)` | Adds a `ToolDefinition` to the registry |
| `get_tool(name)` | Returns the `ToolDefinition` by name, or `None` |
| `get_tools(category)` | Returns all tools, optionally filtered by category |
| `execute(name, args, project_id)` | Runs the handler and returns a `ToolResult` |
| `to_openai_schema()` | Returns a `list[dict]` in OpenAI function-calling format |
| `to_anthropic_schema()` | Returns a `list[dict]` in Anthropic tool-use format |
| `to_prompt_text()` | Returns an XML block for injection into non-native prompts |

**Module-level:** `get_registry()` returns the singleton and auto-imports all tool modules on first call.

---

## Base Types

**File:** `services/ai/infrastructure/tools/base.py`

### `ToolParam`

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Parameter name |
| `type` | `str` | JSON Schema type (`string`, `integer`, `boolean`, `array`, `object`) |
| `description` | `str` | Description shown to the LLM |
| `required` | `bool` | Whether the parameter is required |
| `enum` | `list \| None` | Allowed values |
| `items_type` | `str \| None` | Element type for array parameters |

### `ToolDefinition`

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique tool name |
| `description` | `str` | Tool purpose shown to the LLM |
| `category` | `str` | One of `oppm`, `task`, `cost`, `read` |
| `params` | `list[ToolParam]` | Input parameter schema |
| `handler` | `async callable` | Async function that performs the work |
| `requires_project` | `bool` | Whether a `project_id` must be injected |

### `ToolResult`

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Whether the tool completed without error |
| `result` | `any` | The return value (serializable) |
| `error` | `str \| None` | Error message if `success` is `False` |
| `updated_entities` | `dict` | Entity types modified (e.g., `{"tasks": ["uuid"]}`) |

---

## Tool Catalogue

### Category: `oppm` — OPPM Objective And Timeline Tools

**File:** `services/ai/infrastructure/tools/oppm_tools.py`

#### `create_objective`

Creates a new OPPM objective for the project.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `title` | `string` | yes | Objective text |
| `owner_id` | `string` | no | Workspace member UUID |
| `priority` | `string` | no | `A`, `B`, or `C` |
| `sort_order` | `integer` | no | Display position |

Returns: `{ "id": "uuid", "title": "..." }`

Updated entities: `{ "objectives": ["new_uuid"] }`

---

#### `update_objective`

Updates an existing OPPM objective.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `objective_id` | `string` | yes | UUID of the objective |
| `title` | `string` | no | New title |
| `owner_id` | `string` | no | New owner member UUID |
| `priority` | `string` | no | `A`, `B`, or `C` |

Updated entities: `{ "objectives": ["objective_id"] }`

---

#### `delete_objective`

Deletes an OPPM objective.

| Parameter | Type | Required |
|---|---|---|
| `objective_id` | `string` | yes |

Updated entities: `{ "objectives": ["deleted"] }`

---

#### `set_timeline_status`

Sets the status for a single task in a specific week.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `task_id` | `string` | yes | Task UUID |
| `week_start` | `string` | yes | ISO date (Monday of the week) |
| `status` | `string` | yes | `planned`, `in_progress`, `completed`, `at_risk`, `blocked` |
| `quality` | `string` | no | `good`, `average`, `bad` |
| `notes` | `string` | no | |

Updated entities: `{ "timeline": ["task_id"] }`

---

#### `bulk_set_timeline`

Sets the timeline status for multiple task-week combinations in one call.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `entries` | `array` | yes | List of `{ task_id, week_start, status, quality? }` objects |

Updated entities: `{ "timeline": [affected_task_ids] }`

---

### Category: `task` — Task Management Tools

**File:** `services/ai/infrastructure/tools/task_tools.py`

#### `create_task`

Creates a new task within the project.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `title` | `string` | yes | |
| `description` | `string` | no | |
| `priority` | `string` | no | `low`, `medium`, `high`, `critical` |
| `assignee_id` | `string` | no | User UUID |
| `oppm_objective_id` | `string` | no | Links task to an OPPM objective |
| `due_date` | `string` | no | ISO date |
| `parent_task_id` | `string` | no | Makes this a sub-task |

Updated entities: `{ "tasks": ["new_uuid"] }`

---

#### `update_task`

Updates an existing task.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `task_id` | `string` | yes | |
| `title` | `string` | no | |
| `status` | `string` | no | `todo`, `in_progress`, `completed` |
| `priority` | `string` | no | |
| `progress` | `integer` | no | 0–100 |
| `due_date` | `string` | no | ISO date |

Updated entities: `{ "tasks": ["task_id"] }`

---

#### `delete_task`

Deletes a task.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | `string` | yes |

Updated entities: `{ "tasks": ["deleted"] }`

---

#### `assign_task`

Assigns a user to a task.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `task_id` | `string` | yes | |
| `assignee_id` | `string` | yes | User UUID |

Updated entities: `{ "tasks": ["task_id"] }`

---

#### `set_task_dependency`

Adds or removes a dependency between two tasks.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `task_id` | `string` | yes | The dependent task |
| `depends_on_task_id` | `string` | yes | The prerequisite task |
| `action` | `string` | yes | `add` or `remove` |

Updated entities: `{ "tasks": ["task_id"] }`

---

### Category: `cost` — Project Cost And Risk Tools

**File:** `services/ai/infrastructure/tools/cost_tools.py`

#### `update_project_costs`

Creates or updates a project cost line item.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `category` | `string` | yes | Cost category label |
| `planned_amount` | `number` | no | |
| `actual_amount` | `number` | no | |
| `description` | `string` | no | |
| `period` | `string` | no | Time period label |

Updated entities: `{ "costs": ["project_id"] }`

---

#### `create_risk`

Creates a new risk entry for the project.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `description` | `string` | yes | |
| `impact` | `string` | no | `low`, `medium`, `high` |
| `likelihood` | `string` | no | `low`, `medium`, `high` |
| `mitigation` | `string` | no | |

Updated entities: `{ "risks": ["new_uuid"] }`

---

#### `update_risk`

Updates an existing risk.

| Parameter | Type | Required |
|---|---|---|
| `risk_id` | `string` | yes |
| `description` | `string` | no |
| `impact` | `string` | no |
| `likelihood` | `string` | no |
| `mitigation` | `string` | no |

Updated entities: `{ "risks": ["risk_id"] }`

---

#### `create_deliverable`

Creates a deliverable entry for the project.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `description` | `string` | yes | |
| `item_number` | `integer` | no | Display order |

Updated entities: `{ "deliverables": ["new_uuid"] }`

---

#### `update_project`

Updates top-level project fields.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `status` | `string` | no | `planning`, `in_progress`, `completed`, `on_hold`, `cancelled` |
| `priority` | `string` | no | `low`, `medium`, `high`, `critical` |
| `progress` | `integer` | no | 0–100 |
| `description` | `string` | no | |

Updated entities: `{ "project": ["project_id"] }`

---

### Category: `read` — Read-Only Query Tools

**File:** `services/ai/infrastructure/tools/read_tools.py`

These tools never write to the database. Updated entities will always be `{}`.

#### `get_project_summary`

Returns a structured summary of the project: title, status, progress, budget, lead, active objectives, overdue tasks.

| Parameter | Type | Required |
|---|---|---|
| `project_id` | `string` | yes |

---

#### `get_task_details`

Returns full detail for a single task: title, status, assignee, sub-tasks, dependencies, progress, timeline entries.

| Parameter | Type | Required |
|---|---|---|
| `task_id` | `string` | yes |

---

#### `search_tasks`

Searches tasks by title or description substring.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `project_id` | `string` | yes | Injected from context |
| `query` | `string` | yes | Search term |
| `status` | `string` | no | Filter by status |

Returns a list of matching tasks with title, status, assignee, and due date.

---

#### `get_risk_status`

Returns all risks for the project with impact, likelihood, and mitigation.

| Parameter | Type | Required |
|---|---|---|
| `project_id` | `string` | yes |

---

#### `get_cost_breakdown`

Returns the cost breakdown for the project: all line items with planned vs actual.

| Parameter | Type | Required |
|---|---|---|
| `project_id` | `string` | yes |

---

#### `get_team_workload`

Returns all team members assigned to the project with their tasks, assigned hours, and skill tags.

| Parameter | Type | Required |
|---|---|---|
| `project_id` | `string` | yes |

---

## How To Add A New Tool

1. Choose the appropriate module (`oppm_tools.py`, `task_tools.py`, `cost_tools.py`, `read_tools.py`) or create a new category module.

2. Define a `ToolDefinition`:

```python
from services.ai.infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult
from services.ai.infrastructure.tools.registry import get_registry

async def _my_tool_handler(project_id: str, param_a: str) -> ToolResult:
    # ... implementation ...
    return ToolResult(success=True, result={"key": "value"}, updated_entities={"tasks": []})

MY_TOOL = ToolDefinition(
    name="my_tool",
    description="Brief description shown to the LLM",
    category="task",
    params=[
        ToolParam(name="param_a", type="string", description="...", required=True),
    ],
    handler=_my_tool_handler,
    requires_project=True,
)
```

3. Register it at the bottom of the module:

```python
get_registry().register(MY_TOOL)
```

4. The registry auto-imports all tool modules on first `get_registry()` call, so no further wiring is needed.

5. Update this document with the new tool's parameter table.

---

## Schema Serialization Examples

### OpenAI Format

```json
{
  "type": "function",
  "function": {
    "name": "create_task",
    "description": "Creates a new task within the project.",
    "parameters": {
      "type": "object",
      "properties": {
        "title": { "type": "string", "description": "..." },
        "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] }
      },
      "required": ["title"]
    }
  }
}
```

### Anthropic Format

```json
{
  "name": "create_task",
  "description": "Creates a new task within the project.",
  "input_schema": {
    "type": "object",
    "properties": { ... },
    "required": ["title"]
  }
}
```

### XML Prompt Format (Ollama / Kimi)

```xml
<tools>
  <tool>
    <name>create_task</name>
    <description>Creates a new task within the project.</description>
    <parameters>
      <parameter name="title" type="string" required="true">Task title</parameter>
    </parameters>
  </tool>
</tools>
```
