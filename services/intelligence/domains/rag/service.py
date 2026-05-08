"""
RAG service — retrieves relevant context from vector store for LLM prompts.

Provides two pipelines:
1. Legacy: simple embedding → vector search → format (backwards-compatible)
2. Full RAG: rewrite query → classify → multi-retriever → RRF rerank → memory → format
             with optional semantic cache bypass
"""

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.embedding import generate_embedding
from infrastructure.planner.agent import classify_query
from infrastructure.rag.memory import load_memory
from infrastructure.rag.reranker import rerank
from infrastructure.rag.query_rewriter import rewrite_query
from infrastructure.rag.semantic_cache import get_semantic_cache
from infrastructure.rag.retrievers import (
    VectorRetriever,
    KeywordRetriever,
    StructuredRetriever,
    GraphRetriever,
)
from infrastructure.rag.retrievers.graph_retriever import _needs_graph
from infrastructure.rag.retrievers.base_retriever import RetrievedChunk
from domains.rag.vector_repository import VectorRepository

logger = logging.getLogger(__name__)

# Max characters of RAG context to inject (roughly ~2000 tokens)
MAX_CONTEXT_CHARS = 6000

# Retriever registry (now constructed per-call with session)
_RETRIEVER_CLASSES = {
    "vector": VectorRetriever,
    "keyword": KeywordRetriever,
    "structured": StructuredRetriever,
    "graph": GraphRetriever,
}


@dataclass
class RAGResult:
    """Result from the full RAG pipeline."""
    context: str
    sources: list[dict] = field(default_factory=list)
    memory_context: str = ""
    chunks: list[RetrievedChunk] = field(default_factory=list)


# ── Full RAG pipeline ──

async def retrieve_with_rag_pipeline(
    session: AsyncSession,
    workspace_id: str,
    query: str,
    user_id: str | None = None,
    project_id: str | None = None,
    top_k: int = 10,
    models: list[dict] | None = None,
    project_title: str = "",
) -> RAGResult:
    """Full RAG pipeline: rewrite → embed → cache? → classify → retrieve → RRF → memory → format."""

    # 1. Load conversation memory (if user_id provided)
    memory_context = ""
    if user_id:
        try:
            memory_context = await load_memory(session, workspace_id, user_id, project_id=project_id)
        except Exception as e:
            logger.warning("Memory loading failed: %s", e)

    # 2. Query rewriting — expand vague queries for better recall
    effective_query = query
    if models:
        try:
            effective_query = await rewrite_query(query, models, project_title=project_title)
        except Exception as e:
            logger.debug("Query rewriting skipped: %s", e)

    # 3. Generate embedding for cache lookup and vector retrieval
    query_embedding: list[float] | None = None
    try:
        query_embedding = await generate_embedding(effective_query)
    except Exception as e:
        logger.debug("Embedding generation failed (continuing without): %s", e)

    # 4. Semantic cache lookup
    if query_embedding:
        cache = get_semantic_cache()
        cached_context = await cache.lookup(
            query_embedding,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if cached_context is not None:
            return RAGResult(
                context=cached_context,
                sources=[],
                memory_context=memory_context,
                chunks=[],
            )

    # 5. Classify query to select retrievers
    retriever_names = classify_query(effective_query)

    # Add graph retriever for relational/dependency queries
    if _needs_graph(effective_query) and "graph" not in retriever_names:
        retriever_names.append("graph")

    # 6. Run selected retrievers in parallel
    filters = {}
    if project_id:
        filters["project_id"] = project_id

    tasks = []
    for name in retriever_names:
        retriever_cls = _RETRIEVER_CLASSES.get(name)
        if retriever_cls:
            retriever = retriever_cls(session)
            tasks.append(retriever.retrieve(effective_query, workspace_id, top_k=top_k, **filters))

    ranked_lists: list[list[RetrievedChunk]] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                ranked_lists.append(r)
            elif isinstance(r, Exception):
                logger.warning("Retriever failed: %s", r)

    # 7. Rerank with RRF
    reranked = rerank(ranked_lists, top_k=top_k) if ranked_lists else []

    # 8. Boost project-specific results to the top
    if project_id and reranked:
        project_chunks = []
        other_chunks = []
        for chunk in reranked:
            if chunk.metadata.get("project_id") == project_id:
                project_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        reranked = project_chunks + other_chunks[:3]

    # 9. Format results
    context = _format_chunks(reranked)
    sources = [
        {
            "entity_type": c.entity_type,
            "entity_id": c.entity_id,
            "title": c.metadata.get("title", ""),
            "relevance_score": round(c.score, 4),
            "source": c.source,
        }
        for c in reranked
    ]

    result = RAGResult(
        context=context,
        sources=sources,
        memory_context=memory_context,
        chunks=reranked,
    )

    # 10. Store in semantic cache for future similar queries
    if query_embedding and context:
        cache = get_semantic_cache()
        await cache.store(
            query_embedding,
            context,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    return result


async def requery(
    session: AsyncSession,
    workspace_id: str,
    gap_phrase: str,
    project_id: str | None = None,
    user_id: str | None = None,
    top_k: int = 8,
) -> str:
    """Lightweight mid-loop RAG re-query for a specific knowledge gap phrase.

    Called by the TAOR agentic loop when the LLM's confidence is low and
    it has identified a concrete gap in its knowledge. Returns a context
    string (max 3000 chars) ready for injection into the conversation.
    """
    try:
        result = await retrieve_with_rag_pipeline(
            session,
            workspace_id,
            gap_phrase,
            user_id=user_id,
            project_id=project_id,
            top_k=top_k,
        )
        # Trim to half the normal budget to avoid context overload mid-loop
        ctx = result.context
        if len(ctx) > 3000:
            ctx = ctx[:3000] + "\n... [additional context truncated]"
        return ctx
    except Exception as exc:
        logger.warning("requery failed for gap '%s': %s", gap_phrase[:80], exc)
        return ""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into a context string for the LLM prompt."""
    if not chunks:
        return ""

    lines = ["## Retrieved Context (ranked by relevance)"]
    total_chars = 0

    for i, chunk in enumerate(chunks, 1):
        title = chunk.metadata.get("title") or chunk.metadata.get("category") or ""
        status = chunk.metadata.get("status", "")
        extra = f" — {status}" if status else ""

        line = f"{i}. [{chunk.entity_type.capitalize()}] {title}{extra} (score: {chunk.score:.3f}, via {chunk.source})"
        detail = chunk.content.strip()
        entry = f"{line}\n   {detail}\n"

        if total_chars + len(entry) > MAX_CONTEXT_CHARS:
            break

        lines.append(entry)
        total_chars += len(entry)

    return "\n".join(lines)


# ── Legacy pipeline (backwards-compatible) ──

async def retrieve_context(
    session: AsyncSession,
    workspace_id: str,
    query: str,
    project_id: str | None = None,
    top_k: int = 10,
) -> str:
    """Legacy retrieval — embedding + vector search + format."""
    if project_id:
        return await retrieve_for_project(session, workspace_id, project_id, query, top_k)
    return await retrieve_for_workspace(session, workspace_id, query, top_k)


async def retrieve_for_workspace(
    session: AsyncSession,
    workspace_id: str,
    query: str,
    top_k: int = 15,
) -> str:
    """Cross-project retrieval for workspace-level questions."""
    vector_repo = VectorRepository(session)
    query_embedding = await generate_embedding(query)
    results = await vector_repo.similarity_search(
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )
    return _format_results(results)


async def retrieve_for_project(
    session: AsyncSession,
    workspace_id: str,
    project_id: str,
    query: str,
    top_k: int = 10,
) -> str:
    """Project-scoped retrieval."""
    vector_repo = VectorRepository(session)
    query_embedding = await generate_embedding(query)

    all_results = await vector_repo.similarity_search(
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        top_k=top_k + 5,
    )

    project_results = []
    other_results = []
    for r in all_results:
        meta = r.get("metadata") or {}
        if meta.get("project_id") == project_id or r.get("entity_type") == "member":
            project_results.append(r)
        else:
            other_results.append(r)

    combined = project_results[:top_k] + other_results[:3]
    combined.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    return _format_results(combined)


def _format_results(results: list[dict]) -> str:
    """Format similarity search results into a context string (legacy format)."""
    if not results:
        return ""

    lines = ["## Retrieved Context (ranked by relevance)"]
    total_chars = 0

    for i, r in enumerate(results, 1):
        entity_type = r.get("entity_type", "unknown")
        content = r.get("content", "")
        similarity = r.get("similarity", 0)
        meta = r.get("metadata") or {}

        title = meta.get("title") or meta.get("category") or meta.get("display_name") or ""
        status = meta.get("status", "")
        extra = f" — {status}" if status else ""

        line = f"{i}. [{entity_type.capitalize()}] {title}{extra} (relevance: {similarity:.2f})"
        detail = content.strip()
        entry = f"{line}\n   {detail}\n"

        if total_chars + len(entry) > MAX_CONTEXT_CHARS:
            break

        lines.append(entry)
        total_chars += len(entry)

    return "\n".join(lines)
