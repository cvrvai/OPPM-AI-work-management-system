"""MCP tools registry — workspace-scoped data retrieval tools."""

from infrastructure.mcp.tools.project_tools import get_project_status, list_projects
from infrastructure.mcp.tools.objective_tools import list_at_risk_objectives
from infrastructure.mcp.tools.task_tools import get_task_summary
from infrastructure.mcp.tools.commit_tools import summarize_recent_commits

TOOL_REGISTRY: dict[str, dict] = {
    "get_project_status": {
        "fn": get_project_status,
        "description": "Get the current status and progress of a project.",
        "params": {"workspace_id": "str", "project_id": "str"},
    },
    "list_projects": {
        "fn": list_projects,
        "description": "List all projects in the workspace.",
        "params": {"workspace_id": "str"},
    },
    "list_at_risk_objectives": {
        "fn": list_at_risk_objectives,
        "description": "List objectives that are at risk or blocked.",
        "params": {"workspace_id": "str"},
    },
    "get_task_summary": {
        "fn": get_task_summary,
        "description": "Get a summary of tasks grouped by status.",
        "params": {"workspace_id": "str", "project_id": "str"},
    },
    "summarize_recent_commits": {
        "fn": summarize_recent_commits,
        "description": "Summarize recent commit activity for a project.",
        "params": {"workspace_id": "str", "project_id": "str", "days": "int"},
    },
}

__all__ = [
    "TOOL_REGISTRY",
    "get_project_status",
    "list_projects",
    "list_at_risk_objectives",
    "get_task_summary",
    "summarize_recent_commits",
]
