"""
AI Commit Analyzer — Multi-model analysis service.

Supports: Ollama (local), Kimi K2.5, Claude (Anthropic), OpenAI
Analyzes each commit against project tasks and OPPM objectives.
Uses the infrastructure LLM adapter layer for provider abstraction.
"""

import logging
from database import get_db
from infrastructure.llm import get_adapter

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
    """Analyze a batch of commits using the first active AI model."""
    db = get_db()

    # Get active AI model
    models = (
        db.table("ai_models")
        .select("*")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not models.data:
        return  # No active model configured

    model = models.data[0]

    # Get LLM adapter for this provider
    try:
        adapter_cls = get_adapter(model["provider"])
        adapter = adapter_cls()
    except ValueError:
        logger.warning("Unknown AI provider: %s", model["provider"])
        return

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
            result = await adapter.call_json(
                model["model_id"],
                prompt,
                endpoint_url=model.get("endpoint_url"),
            )
            if result:
                analysis_data = {
                    "commit_event_id": commit["id"],
                    "ai_model": f"{model['provider']}/{model['model_id']}",
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

                # Create notification for the analysis
                db.table("notifications").insert({
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
                        .maybe_single()
                        .execute()
                    )
                    if task.data:
                        new_progress = min(100, task.data["progress"] + progress_delta)
                        db.table("tasks").update(
                            {"progress": new_progress}
                        ).eq("id", matched_task).execute()

        except Exception as e:
            logger.error("AI analysis failed for commit %s: %s", commit.get("id"), e)
