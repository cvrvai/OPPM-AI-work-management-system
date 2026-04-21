"""RAG endpoint — query the RAG pipeline for workspace-scoped context retrieval."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_current_user, get_workspace_context
from shared.database import get_session
from schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSource
from services import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/workspaces/{workspace_id}/rag/query", response_model=RAGQueryResponse)
async def rag_query_route(
    body: RAGQueryRequest,
    user=Depends(get_current_user),
    ctx=Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Query the RAG pipeline for relevant context."""
    try:
        result = await rag_service.retrieve_with_rag_pipeline(
            session=session,
            workspace_id=ctx.workspace_id,
            query=body.query,
            user_id=user.id,
            project_id=body.project_id,
            top_k=body.top_k,
        )
    except Exception as e:
        logger.warning("RAG query failed: %s", e)
        raise HTTPException(status_code=502, detail=f"RAG retrieval failed: {e}")

    sources = [
        RAGSource(
            entity_type=s["entity_type"],
            entity_id=s["entity_id"],
            title=s.get("title", ""),
            relevance_score=s["relevance_score"],
            source=s["source"],
        )
        for s in result.sources
    ]

    return RAGQueryResponse(
        context=result.context,
        sources=sources,
        memory_context=result.memory_context,
    )
