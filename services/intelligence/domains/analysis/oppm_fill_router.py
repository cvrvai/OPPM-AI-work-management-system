"""AI OPPM Fill router — generates suggested cell values for the OPPM spreadsheet header."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_workspace_context, WorkspaceContext
from shared.database import get_session
from domains.analysis.oppm_fill_schemas import OPPMFillRequest, OPPMFillResponse
from domains.analysis.oppm_fill_service import fill_oppm
from domains.chat.service import _chat_async
from domains.chat.schemas import ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/ai/oppm-fill",
    response_model=OPPMFillResponse,
)
async def oppm_fill_route(
    project_id: str,
    data: OPPMFillRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Use project data + LLM to suggest OPPM spreadsheet header cell values."""
    result = await fill_oppm(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        model_id=data.model_id,
    )
    return OPPMFillResponse(
        fills=result["fills"],
        tasks=result["tasks"],
        members=result["members"],
    )


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/ai/oppm-agent-fill",
    response_model=ChatResponse,
)
async def oppm_agent_fill_route(
    project_id: str,
    data: OPPMFillRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Agentic OPPM fill — uses the OPPM skill to populate the entire form end-to-end.

    This endpoint bypasses the legacy single-LLM-call fill and instead runs the
    full TAOR agent loop with the OPPM skill activated. The skill will:
      1. Bulk-load project context (pre-flight)
      2. Use OPPM tools to write header, timeline, owners, sub-objectives, risks, costs
      3. Push results to Google Sheets (post-flight)
    """
    synthetic_message = {
        "role": "user",
        "content": f"Fill the OPPM form for project {project_id}",
    }
    result = await _chat_async(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        messages=[synthetic_message],
        model_id=data.model_id,
        force_skill="oppm",
    )
    return ChatResponse(
        message=result["message"],
        tool_calls=result["tool_calls"],
        updated_entities=result["updated_entities"],
        iterations=result["iterations"],
        low_confidence=result["low_confidence"],
    )


# ── Streaming variant (SSE) ─────────────────────────────────────────────────
#
# The blocking variant above can run for several minutes on a project with
# many tasks because the agent loop makes multiple LLM calls and tool calls.
# The 120s gateway timeout is not enough. This streaming variant emits a
# `tool_call` SSE event per tool execution (keeping the connection warm and
# giving the user live progress) and a final `message` event with the full
# result. Mirrors the queue pattern in domains/chat/service.chat_stream.


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/ai/oppm-agent-fill/stream",
)
async def oppm_agent_fill_stream_route(
    project_id: str,
    data: OPPMFillRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """SSE-streaming version of oppm-agent-fill.

    Emits:
      - event: tool_call — once per tool execution {tool, input, result, success, error?, updated_entities}
      - event: message   — final agent response {message, tool_calls, updated_entities, iterations, low_confidence}
      - event: error     — fatal {detail, status_code?}
    """
    workspace_id = ws.workspace_id
    user_id = ws.user.id
    model_id = data.model_id
    synthetic_message = {
        "role": "user",
        "content": (
            f"Validate the OPPM form for project {project_id} first (call validate_oppm), "
            "then fix any issues it reports and fill in anything still missing. "
            "If task numbering has duplicates or gaps, call renumber_oppm_tasks before "
            "writing timeline / owners / sub-objective links."
        ),
    }

    queue: asyncio.Queue = asyncio.Queue()

    async def on_tool(record: dict) -> None:
        await queue.put(("tool_call", record))

    async def run() -> None:
        try:
            result = await _chat_async(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
                messages=[synthetic_message],
                model_id=model_id,
                on_tool_result=on_tool,
                force_skill="oppm",
            )
            await session.commit()
            await queue.put(("message", result))
        except HTTPException as exc:
            await session.rollback()
            await queue.put(("error", {"detail": exc.detail, "status_code": exc.status_code}))
        except Exception as exc:
            logger.warning("oppm-agent-fill stream failed: %s", exc)
            await session.rollback()
            await queue.put(("error", {"detail": str(exc)}))
        finally:
            await queue.put(None)

    async def event_generator():
        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, payload = item
                yield _sse(event, payload)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
