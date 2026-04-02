"""
AI Commit Analyzer — Multi-model analysis service.

Supports: Ollama (local), Kimi K2.5, Claude (Anthropic), OpenAI
Analyzes each commit against project tasks and OPPM objectives.
Uses the infrastructure LLM adapter layer for provider abstraction.
"""

import logging
from shared.database import get_db
from infrastructure.llm import get_adapter, call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are an AI code reviewer for a project management system (OPPM — One Page Project Manager).

Analyze this git commit and provide a structured JSON response.

## Commit Information
- **Message**: {commit_message}
- **Files Changed**: {files_changed}
- **Branch**: {branch}
- **Author**: {author}

## Project Tasks (match against these):
{tasks_context}

## Instructions
Return ONLY valid JSON with these fields:
{{
  "task_alignment_score": <0-100, how well this commit aligns with a project task>,
  "code_quality_score": <0-100, estimated code quality based on commit message, files, and scope>,
  "progress_delta": <0-100, estimated progress contribution to the matched task>,
  "summary": "<2-3 sentence summary of what this commit does and its impact>",
  "quality_flags": ["<list of flags: well-structured, clean-code, bug-fix, security-aware, needs-review, minor-issues, major-issues>"],
  "suggestions": ["<list of improvement suggestions, max 3>"],
  "matched_task_id": "<id of the best-matching task, or null>",
  "matched_objective_id": "<id of the matched task's OPPM objective, or null>"
}}
"""


async def analyze_commits(commit_events: list[dict], project_id: str):
    """Analyze a batch of commits using active AI models with fallback."""
    db = get_db()

    # Get project's workspace_id for scoped model lookup
    project = db.table("projects").select("workspace_id").eq("id", project_id).limit(1).execute()
    if not project.data:
        logger.warning("Project %s not found, skipping analysis", project_id)
        return
    workspace_id = project.data[0]["workspace_id"]

    # Get all active AI models for fallback chain
    models_result = (
        db.table("ai_models")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("is_active", True)
        .execute()
    )
    models = models_result.data or []
    if not models:
        return  # No active model configured

    # Get project tasks for context
    tasks = (
        db.table("tasks")
        .select("id, title, description, oppm_objective_id, status, progress")
        .eq("project_id", project_id)
        .execute()
    )
    tasks_context = "\n".join(
        f"- Task ID: {t['id']} | Title: {t['title']} | Objective: {t.get('oppm_objective_id', 'none')} | Status: {t['status']} | Progress: {t['progress']}%"
        for t in (tasks.data or [])
    )

    for commit in commit_events:
        prompt = ANALYSIS_PROMPT.format(
            commit_message=commit.get("commit_message", ""),
            files_changed=", ".join(commit.get("files_changed", [])),
            branch=commit.get("branch", ""),
            author=commit.get("author_github_username", ""),
            tasks_context=tasks_context or "No tasks defined yet.",
        )

        try:
            result = await call_with_fallback(models, prompt, json_mode=True)
            if result:
                analysis_data = {
                    "commit_event_id": commit["id"],
                    "ai_model": "/".join(f"{m['provider']}/{m['model_id']}" for m in models[:1]),
                    "task_alignment_score": result.get("task_alignment_score", 0),
                    "code_quality_score": result.get("code_quality_score", 0),
                    "progress_delta": result.get("progress_delta", 0),
                    "summary": result.get("summary", ""),
                    "quality_flags": result.get("quality_flags", []),
                    "suggestions": result.get("suggestions", []),
                    "matched_task_id": result.get("matched_task_id"),
                    "matched_objective_id": result.get("matched_objective_id"),
                }
                db.table("commit_analyses").insert(analysis_data).execute()

                # Create notifications for workspace members on the project
                members = db.table("project_members").select("user_id").eq("project_id", project_id).execute()
                for member in (members.data or []):
                    db.table("notifications").insert({
                        "user_id": member["user_id"],
                        "workspace_id": workspace_id,
                        "type": "ai_analysis",
                        "title": f"AI analyzed commit {commit.get('commit_hash', '')[:7]}",
                        "message": result.get("summary", ""),
                        "link": "/commits",
                        "metadata": {
                            "quality_score": result.get("code_quality_score", 0),
                            "alignment_score": result.get("task_alignment_score", 0),
                        },
                    }).execute()

                # Auto-update task progress if matched
                matched_task = result.get("matched_task_id")
                progress_delta = result.get("progress_delta", 0)
                if matched_task and progress_delta > 0:
                    task = (
                        db.table("tasks")
                        .select("progress")
                        .eq("id", matched_task)
                        .limit(1)
                        .execute()
                    )
                    if task.data:
                        new_progress = min(100, task.data[0]["progress"] + progress_delta)
                        db.table("tasks").update(
                            {"progress": new_progress}
                        ).eq("id", matched_task).execute()

        except ProviderUnavailableError as e:
            logger.warning("All AI providers unavailable for commit %s: %s", commit.get("id"), e)
        except Exception as e:
            logger.error("AI analysis failed for commit %s: %s", commit.get("id"), e)
