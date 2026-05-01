"""
Reciprocal Rank Fusion (RRF) reranker.

Merges multiple ranked lists into a single ranking using RRF scoring.
Algorithm: score(doc) = sum(1 / (k + rank_i)) across all lists where doc appears.
"""

from collections import defaultdict

from infrastructure.rag.retrievers.base_retriever import RetrievedChunk


def rerank(
    ranked_lists: list[list[RetrievedChunk]],
    top_k: int = 10,
    k: int = 60,
) -> list[RetrievedChunk]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: list of retriever result lists (each pre-sorted by score desc).
        top_k: number of results to return.
        k: RRF constant (default 60 per the original paper).

    Returns:
        top_k chunks sorted by fused RRF score.
    """
    # Accumulate RRF scores by (entity_type, entity_id)
    scores: dict[tuple[str, str], float] = defaultdict(float)
    best_chunk: dict[tuple[str, str], RetrievedChunk] = {}

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list):
            doc_key = (chunk.entity_type, chunk.entity_id)
            rrf_score = 1.0 / (k + rank + 1)
            scores[doc_key] += rrf_score

            # Keep the chunk with the highest original score for dedup
            if doc_key not in best_chunk or chunk.score > best_chunk[doc_key].score:
                best_chunk[doc_key] = chunk

    # Sort by fused score and return top_k
    sorted_keys = sorted(scores.keys(), key=lambda dk: scores[dk], reverse=True)

    results: list[RetrievedChunk] = []
    for doc_key in sorted_keys[:top_k]:
        chunk = best_chunk[doc_key]
        # Override score with the fused RRF score
        results.append(RetrievedChunk(
            entity_type=chunk.entity_type,
            entity_id=chunk.entity_id,
            content=chunk.content,
            score=scores[doc_key],
            source=chunk.source,
            metadata=chunk.metadata,
        ))

    return results
