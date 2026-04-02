"""
Document indexer — converts entities to text and stores embeddings for RAG.

Each index_* function builds a natural-language text representation of the entity,
generates an embedding, and upserts it into the vector store.

All functions are async and designed to be called via fire-and-forget
(asyncio.create_task) so they don't block API responses.
"""

import logging
from typing import Any

from infrastructure.embedding import generate_embedding
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)

vector_repo = VectorRepository()


# ── Entity indexing functions ──


async def index_project(project: dict, workspace_id: str) -> None:
    """Index a project entity."""
    text = (
        f'Project: "{project.get("title", "")}"\n'
        f'Description: {project.get("description", "")}\n'
        f'Status: {project.get("status", "unknown")} | Priority: {project.get("priority", "medium")}\n'
        f'Progress: {project.get("progress", 0)}%\n'
        f'Start: {project.get("start_date", "not set")} | Deadline: {project.get("deadline", "not set")}'
    )
    metadata = {
        "title": project.get("title"),
        "status": project.get("status"),
        "priority": project.get("priority"),
        "progress": project.get("progress"),
    }
    await _do_index(workspace_id, "project", project["id"], text, metadata)


async def index_objective(objective: dict, workspace_id: str, project_id: str) -> None:
    """Index an OPPM objective."""
    text = (
        f'Objective: "{objective.get("title", "")}"\n'
        f'Sort Order: {objective.get("sort_order", 0)}\n'
        f'Description: {objective.get("description", "")}'
    )
    metadata = {
        "project_id": project_id,
        "title": objective.get("title"),
        "sort_order": objective.get("sort_order"),
    }
    await _do_index(workspace_id, "objective", objective["id"], text, metadata)


async def index_task(task: dict, workspace_id: str) -> None:
    """Index a task."""
    text = (
        f'Task: "{task.get("title", "")}"\n'
        f'Status: {task.get("status", "todo")} | Priority: {task.get("priority", "medium")}\n'
        f'Progress: {task.get("progress", 0)}%\n'
        f'Description: {task.get("description", "")}\n'
        f'Due: {task.get("due_date", "not set")}'
    )
    metadata = {
        "project_id": task.get("project_id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "priority": task.get("priority"),
        "progress": task.get("progress"),
    }
    await _do_index(workspace_id, "task", task["id"], text, metadata)


async def index_cost(cost: dict, workspace_id: str, project_id: str) -> None:
    """Index a cost entry."""
    text = (
        f'Cost: {cost.get("category", "")}\n'
        f'Planned: {cost.get("planned_amount", 0)} | Actual: {cost.get("actual_amount", 0)}\n'
        f'Currency: {cost.get("currency", "USD")}\n'
        f'Notes: {cost.get("notes", "")}'
    )
    metadata = {
        "project_id": project_id,
        "category": cost.get("category"),
        "planned_amount": cost.get("planned_amount"),
        "actual_amount": cost.get("actual_amount"),
    }
    await _do_index(workspace_id, "cost", cost["id"], text, metadata)


async def index_commit_analysis(analysis: dict, workspace_id: str) -> None:
    """Index a commit analysis result."""
    text = (
        f'Commit Analysis\n'
        f'Summary: {analysis.get("summary", "")}\n'
        f'Quality Score: {analysis.get("quality_score", 0)}/100\n'
        f'Alignment Score: {analysis.get("alignment_score", 0)}/100\n'
        f'Progress Delta: {analysis.get("progress_delta", 0)}'
    )
    if analysis.get("suggestions"):
        text += f'\nSuggestions: {", ".join(analysis["suggestions"])}'
    metadata = {
        "commit_event_id": analysis.get("commit_event_id"),
        "quality_score": analysis.get("quality_score"),
        "alignment_score": analysis.get("alignment_score"),
    }
    await _do_index(workspace_id, "commit_analysis", analysis["id"], text, metadata)


async def index_member(member: dict, workspace_id: str) -> None:
    """Index a workspace member."""
    name = member.get("display_name") or member.get("email") or member.get("user_id", "")[:8]
    text = (
        f'Team Member: {name}\n'
        f'Role: {member.get("role", "member")}'
    )
    metadata = {
        "display_name": name,
        "role": member.get("role"),
        "user_id": member.get("user_id"),
    }
    await _do_index(workspace_id, "member", member["id"], text, metadata)


async def remove_entity(entity_type: str, entity_id: str) -> None:
    """Remove an embedding when an entity is deleted."""
    try:
        vector_repo.delete_embedding(entity_type, entity_id)
    except Exception as e:
        logger.warning("Failed to remove embedding for %s/%s: %s", entity_type, entity_id, e)


# ── Bulk reindex ──


async def reindex_workspace(workspace_id: str) -> dict:
    """Re-index all entities in a workspace. Returns stats."""
    from repositories.project_repo import ProjectRepository
    from repositories.oppm_repo import ObjectiveRepository, CostRepository
    from repositories.task_repo import TaskRepository
    from shared.database import get_db

    project_repo = ProjectRepository()
    objective_repo = ObjectiveRepository()
    cost_repo = CostRepository()
    task_repo = TaskRepository()
    db = get_db()

    total = 0

    # Projects
    projects = project_repo.find_all(filters={"workspace_id": workspace_id}, limit=500)
    for p in projects:
        await index_project(p, workspace_id)
        total += 1

        # Objectives per project
        objectives = objective_repo.find_with_tasks(p["id"])
        for obj in objectives:
            await index_objective(obj, workspace_id, p["id"])
            total += 1

        # Costs per project
        cost_data = cost_repo.get_cost_summary(p["id"])
        for c in cost_data.get("items", []):
            await index_cost(c, workspace_id, p["id"])
            total += 1

        # Tasks per project
        tasks = task_repo.find_project_tasks(p["id"], limit=500)
        for t in tasks:
            await index_task(t, workspace_id)
            total += 1

    # Workspace members
    members = db.table("workspace_members").select("*").eq("workspace_id", workspace_id).execute()
    for m in (members.data or []):
        await index_member(m, workspace_id)
        total += 1

    logger.info("Reindexed %d entities for workspace %s", total, workspace_id)
    return {"total_indexed": total}


# ── Internal ──


async def _do_index(
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    text: str,
    metadata: dict[str, Any],
) -> None:
    """Generate embedding and upsert into vector store."""
    try:
        embedding = await generate_embedding(text)
        vector_repo.upsert_embedding(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=text,
            metadata=metadata,
            embedding=embedding,
        )
    except Exception as e:
        logger.warning("Failed to index %s/%s: %s", entity_type, entity_id, e)
