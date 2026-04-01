"""
RAG service — retrieves relevant context from vector store for LLM prompts.

Embeds the user query, performs similarity search in pgvector,
and formats the results into a context string for injection into the system prompt.
"""

import logging

from infrastructure.embedding import generate_embedding
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)

vector_repo = VectorRepository()

# Max characters of RAG context to inject (roughly ~2000 tokens)
MAX_CONTEXT_CHARS = 6000


async def retrieve_context(
    workspace_id: str,
    query: str,
    project_id: str | None = None,
    top_k: int = 10,
) -> str:
    """
    Retrieve relevant context from the vector store for a user query.
    If project_id is provided, results are filtered/boosted for that project.
    Returns a formatted string ready for injection into the system prompt.
    """
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
    """
    Project-scoped retrieval.
    Gets top_k results from the target project + 3 cross-project results.
    """
    query_embedding = await generate_embedding(query)

    # Get all results and split by project
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

    # Compose: all project results + top 3 cross-project
    combined = project_results[:top_k] + other_results[:3]
    # Re-sort by similarity
    combined.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    return _format_results(combined)


def _format_results(results: list[dict]) -> str:
    """Format similarity search results into a context string."""
    if not results:
        return ""

    lines = ["## Retrieved Context (ranked by relevance)"]
    total_chars = 0

    for i, r in enumerate(results, 1):
        entity_type = r.get("entity_type", "unknown")
        content = r.get("content", "")
        similarity = r.get("similarity", 0)
        meta = r.get("metadata") or {}

        # Build a compact summary line
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
