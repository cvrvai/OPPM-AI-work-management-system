"""Hybrid retriever — unified facade over vector, keyword, structured, and graph retrievers.

Runs all four retrievers in parallel and merges results using Reciprocal Rank Fusion (RRF).
This is the recommended entry point for the RAG pipeline. It replaces calling retrievers
individually and provides a single, ranked result list.

Usage:
    hybrid = HybridRetriever(session)
    chunks = await hybrid.retrieve(query, workspace_id, top_k=10, project_id=pid)

The retriever selection is still driven by classify_query — graph traversal is only added
when the query signals dependency, workload, or objective patterns, keeping latency low for
simple queries.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.planner.agent import classify_query
from infrastructure.rag.retrievers.base_retriever import BaseRetriever, RetrievedChunk
from infrastructure.rag.retrievers.graph_retriever import GraphRetriever, _needs_graph
from infrastructure.rag.retrievers.keyword_retriever import KeywordRetriever
from infrastructure.rag.retrievers.structured_retriever import StructuredRetriever
from infrastructure.rag.retrievers.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """Fuses vector + keyword + structured + graph retrievers via RRF.

    Graph traversal is added dynamically based on query classification so it
    doesn't add latency to simple questions.
    """

    name = "hybrid"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 10,
        **filters,
    ) -> list[RetrievedChunk]:
        # Decide which base retrievers to use (same logic as rag_service)
        retriever_names = classify_query(query)

        retriever_map: dict[str, BaseRetriever] = {
            "vector": VectorRetriever(self._session),
            "keyword": KeywordRetriever(self._session),
            "structured": StructuredRetriever(self._session),
        }

        tasks: list = []
        active_names: list[str] = []

        for name in retriever_names:
            if name in retriever_map:
                tasks.append(
                    retriever_map[name].retrieve(query, workspace_id, top_k=top_k, **filters)
                )
                active_names.append(name)

        # Add graph retriever when the query signals relational patterns
        if _needs_graph(query):
            tasks.append(
                GraphRetriever(self._session).retrieve(query, workspace_id, top_k=top_k, **filters)
            )
            active_names.append("graph")

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        ranked_lists: list[list[RetrievedChunk]] = []
        for name, result in zip(active_names, results):
            if isinstance(result, list):
                ranked_lists.append(result)
            else:
                logger.warning("HybridRetriever: %s retriever failed: %s", name, result)

        if not ranked_lists:
            return []

        # Deferred import to avoid circular dependency:
        # rag/__init__ → reranker → retrievers/__init__ → hybrid_retriever → reranker (circular)
        from infrastructure.rag.reranker import rerank  # noqa: PLC0415
        return rerank(ranked_lists, top_k=top_k)
