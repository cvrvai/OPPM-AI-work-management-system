"""
OPPM Tool Executor for AI service — Routes AI tool calls to the correct repo methods.
Used by the AI chat service when the LLM wants to make changes.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.oppm_repo import ObjectiveRepository, TimelineRepository, CostRepository
from repositories.task_repo import TaskRepository
from repositories.project_repo import ProjectRepository
from repositories.notification_repo import AuditRepository

logger = logging.getLogger(__name__)


async def execute_tool(
    session: AsyncSession,
    tool_name: str,
    tool_input: dict,
    project_id: str,
    workspace_id: str,
    user_id: str,
) -> dict:
    """Routes AI tool calls to the correct repository method."""
    objective_repo = ObjectiveRepository(session)
    timeline_repo = TimelineRepository(session)
    cost_repo = CostRepository(session)
    task_repo = TaskRepository(session)
    audit_repo = AuditRepository(session)

    try:
        match tool_name:

            case "create_objective":
                data = {
                    "project_id": project_id,
                    "title": tool_input["title"],
                    "sort_order": tool_input.get("sort_order", 999),
                }
                if tool_input.get("owner_id"):
                    data["owner_id"] = tool_input["owner_id"]
                result = await objective_repo.create(data)
                updated = ["oppm_objectives"]

            case "update_objective":
                result = await objective_repo.update(tool_input["objective_id"], {
                    k: v for k, v in tool_input.items() if k != "objective_id"
                })
                updated = ["oppm_objectives"]

            case "set_timeline_status":
                entry_data = {
                    "project_id": project_id,
                    "task_id": tool_input["task_id"],
                    "week_start": tool_input["week_start"],
                    "status": tool_input["status"],
                }
                if tool_input.get("notes"):
                    entry_data["notes"] = tool_input["notes"]
                result = await timeline_repo.upsert_entry(entry_data)
                updated = ["oppm_timeline_entries"]

            case "bulk_set_timeline":
                results = []
                for entry in tool_input.get("entries", []):
                    entry_data = {
                        "project_id": project_id,
                        "task_id": entry["task_id"],
                        "week_start": entry["week_start"],
                        "status": entry["status"],
                    }
                    if entry.get("notes"):
                        entry_data["notes"] = entry["notes"]
                    results.append(await timeline_repo.upsert_entry(entry_data))
                result = {"count": len(results), "entries": results}
                updated = ["oppm_timeline_entries"]

            case "create_task":
                data = {
                    "project_id": project_id,
                    "title": tool_input["title"],
                    "created_by": user_id,
                }
                for f in ("description", "priority", "due_date", "oppm_objective_id", "assignee_id", "project_contribution"):
                    if f in tool_input:
                        data[f] = tool_input[f]
                result = await task_repo.create(data)
                updated = ["tasks", "projects"]

            case "update_task":
                task_id = tool_input.pop("task_id", None)
                if not task_id:
                    return {"success": False, "error": "task_id required", "updated_entities": []}
                result = await task_repo.update(task_id, tool_input)
                updated = ["tasks", "projects"]

            case "update_project_costs":
                data = {"project_id": project_id}
                for f in ("category", "planned_amount", "actual_amount", "notes"):
                    if f in tool_input:
                        data[f] = tool_input[f]
                result = await cost_repo.create(data)
                updated = ["project_costs"]

            case _:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "updated_entities": [],
                }

        await audit_repo.log(
            workspace_id, user_id,
            f"ai_tool:{tool_name}", tool_name,
            new_data=tool_input,
        )

        return {
            "success": True,
            "result": result,
            "updated_entities": updated,
        }

    except Exception as e:
        logger.warning("Tool execution error %s: %s", tool_name, e)
        return {
            "success": False,
            "error": str(e),
            "updated_entities": [],
        }
