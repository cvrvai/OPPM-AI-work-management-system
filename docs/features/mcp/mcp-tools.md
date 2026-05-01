# Feature: MCP Tools

Last updated: 2026-05-01

## What It Does

- Lists AI-consumable MCP tools
- Executes workspace-scoped MCP tool calls over HTTP

## How It Works

1. `services/automation/domains/registry/router.py` lists and executes tools.
2. The router injects the current `workspace_id` into every tool call.
3. Tool implementations live in `services/automation/domains/execution/`.
4. The current registry exposes:
   - `get_project_status`
   - `list_projects`
   - `list_at_risk_objectives`
   - `get_task_summary`
   - `summarize_recent_commits`

## Backend Files

- `services/automation/domains/registry/router.py`
- `services/automation/domains/execution/__init__.py`
- `services/automation/domains/execution/project_tools.py`
- `services/automation/domains/execution/objective_tools.py`
- `services/automation/domains/execution/task_tools.py`
- `services/automation/domains/execution/commit_tools.py`

## Update Notes

- MCP tools are externally callable summaries over existing data, not a second source of truth.
