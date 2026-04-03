"""
AI Commit Analyzer — Multi-model analysis service.

Supports: Ollama (local), Kimi K2.5, Claude (Anthropic), OpenAI
Analyzes each commit against project tasks and OPPM objectives.
Uses the infrastructure LLM adapter layer for provider abstraction.
"""

import logging
from sqlalchemy import select, update as sa_update
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.ai_model import AIModel
from shared.models.task import Task
from shared.models.git import CommitAnalysis
from shared.models.notification import Notification
from shared.models.project import ProjectMember
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
    factory = get_session_factory()
    async with factory() as session:
        # Get project's workspace_id
        result = await session.execute(
            select(Project.workspace_id).where(Project.id == project_id).limit(1)
        )
        row = result.first()
        if not row:
            logger.warning("Project %s not found, skipping analysis", project_id)
            return
        workspace_id = str(row.workspace_id)

        # Get all active AI models for fallback chain
        result = await session.execute(
            select(AIModel)
            .where(AIModel.workspace_id == workspace_id, AIModel.is_active == True)
        )
        models_orm = result.scalars().all()
        models = [{"id": str(m.id), "provider": m.provider, "model_id": m.model_id,
                    "api_key": m.api_key, "base_url": m.base_url, "name": m.name,
                    "is_active": m.is_active} for m in models_orm]
        if not models:
            return

        # Get project tasks for context
        result = await session.execute(
            select(Task.id, Task.title, Task.description, Task.oppm_objective_id, Task.status, Task.progress)
            .where(Task.project_id == project_id)
        )
        tasks = result.all()
        tasks_context = "\n".join(
            f"- Task ID: {t.id} | Title: {t.title} | Objective: {t.oppm_objective_id or 'none'} | Status: {t.status} | Progress: {t.progress}%"
            for t in tasks
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
                result_data = await call_with_fallback(models, prompt, json_mode=True)
                if result_data:
                    analysis = CommitAnalysis(
                        commit_event_id=commit["id"],
                        ai_model="/".join(f"{m['provider']}/{m['model_id']}" for m in models[:1]),
                        task_alignment_score=result_data.get("task_alignment_score", 0),
                        code_quality_score=result_data.get("code_quality_score", 0),
                        progress_delta=result_data.get("progress_delta", 0),
                        summary=result_data.get("summary", ""),
                        quality_flags=result_data.get("quality_flags", []),
                        suggestions=result_data.get("suggestions", []),
                        matched_task_id=result_data.get("matched_task_id"),
                        matched_objective_id=result_data.get("matched_objective_id"),
                    )
                    session.add(analysis)
                    await session.flush()

                    # Create notifications for project members
                    members_result = await session.execute(
                        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
                    )
                    for member_row in members_result.all():
                        notif = Notification(
                            user_id=str(member_row.user_id),
                            workspace_id=workspace_id,
                            type="ai_analysis",
                            title=f"AI analyzed commit {commit.get('commit_hash', '')[:7]}",
                            message=result_data.get("summary", ""),
                            link="/commits",
                            metadata_={
                                "quality_score": result_data.get("code_quality_score", 0),
                                "alignment_score": result_data.get("task_alignment_score", 0),
                            },
                        )
                        session.add(notif)

                    # Auto-update task progress if matched
                    matched_task = result_data.get("matched_task_id")
                    progress_delta = result_data.get("progress_delta", 0)
                    if matched_task and progress_delta > 0:
                        task_result = await session.execute(
                            select(Task.progress).where(Task.id == matched_task).limit(1)
                        )
                        task_row = task_result.first()
                        if task_row:
                            new_progress = min(100, task_row.progress + progress_delta)
                            await session.execute(
                                sa_update(Task).where(Task.id == matched_task).values(progress=new_progress)
                            )

            except ProviderUnavailableError as e:
                logger.warning("All AI providers unavailable for commit %s: %s", commit.get("id"), e)
            except Exception as e:
                logger.error("AI analysis failed for commit %s: %s", commit.get("id"), e)

        await session.commit()
