"""
RAG service — retrieves relevant context from vector store for LLM prompts.

Provides two pipelines:
1. Legacy: simple embedding → vector search → format (backwards-compatible)
2. Full RAG: classify query → multi-retriever → RRF rerank → memory → format
"""

import asyncio
import logging
from dataclasses import dataclass, field

from infrastructure.embedding import generate_embedding
from infrastructure.rag.agent import classify_query
from infrastructure.rag.memory import load_memory
from infrastructure.rag.reranker import rerank
from infrastructure.rag.retrievers import (
    VectorRetriever,
    KeywordRetriever,
    StructuredRetriever,
)
from infrastructure.rag.retrievers.base_retriever import RetrievedChunk
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)

vector_repo = VectorRepository()

# Max characters of RAG context to inject (roughly ~2000 tokens)
MAX_CONTEXT_CHARS = 6000

# Retriever registry
_RETRIEVERS = {
    "vector": VectorRetriever,
    "keyword": KeywordRetriever,
    "structured": StructuredRetriever,
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
    workspace_id: str,
    query: str,
    user_id: str | None = None,
    project_id: str | None = None,
    top_k: int = 10,
) -> RAGResult:
    """Full RAG pipeline: classify → retrieve → rerank → memory → format."""
    # 1. Load conversation memory (if user_id provided)
    memory_context = ""
    if user_id:
        try:
            memory_context = await load_memory(workspace_id, user_id)
        except Exception as e:
            logger.warning("Memory loading failed: %s", e)

    # 2. Classify query to select retrievers
    retriever_names = classify_query(query)

    # 3. Run selected retrievers in parallel
    filters = {}
    if project_id:
        filters["project_id"] = project_id

    tasks = []
    for name in retriever_names:
        retriever_cls = _RETRIEVERS.get(name)
        if retriever_cls:
            retriever = retriever_cls()
            tasks.append(retriever.retrieve(query, workspace_id, top_k=top_k, **filters))

    ranked_lists: list[list[RetrievedChunk]] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                ranked_lists.append(r)
            elif isinstance(r, Exception):
                logger.warning("Retriever failed: %s", r)

    # 4. Rerank with RRF
    reranked = rerank(ranked_lists, top_k=top_k) if ranked_lists else []

    # 5. If project_id provided, boost project-specific results
    if project_id and reranked:
        project_chunks = []
        other_chunks = []
        for chunk in reranked:
            if chunk.metadata.get("project_id") == project_id:
                project_chunks.append(chunk)
            else:
                other_chunks.append(chunk)
        reranked = project_chunks + other_chunks[:3]

    # 6. Format results
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

    return RAGResult(
        context=context,
        sources=sources,
        memory_context=memory_context,
        chunks=reranked,
    )


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
    workspace_id: str,
    query: str,
    project_id: str | None = None,
    top_k: int = 10,
) -> str:
    """Legacy retrieval — embedding + vector search + format."""
    if project_id:
        return await retrieve_for_project(workspace_id, project_id, query, top_k)
    return await retrieve_for_workspace(workspace_id, query, top_k)


async def retrieve_for_workspace(
    workspace_id: str,
    query: str,
    top_k: int = 15,
) -> str:
    """Cross-project retrieval for workspace-level questions."""
    query_embedding = await generate_embedding(query)
    results = vector_repo.similarity_search(
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )
    return _format_results(results)


async def retrieve_for_project(
    workspace_id: str,
    project_id: str,
    query: str,
    top_k: int = 10,
) -> str:
    """Project-scoped retrieval."""
    query_embedding = await generate_embedding(query)

    all_results = vector_repo.similarity_search(
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
