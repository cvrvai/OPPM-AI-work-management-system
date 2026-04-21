"""
Query rewriter — LLM-based query expansion for better RAG recall.

Expands vague or conversational queries into richer search strings
before they hit the retrieval pipeline. Falls back silently to the
original query when the LLM is unavailable or returns garbage.
"""

import logging

from infrastructure.llm import call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError

logger = logging.getLogger(__name__)

# Skip rewriting for queries that are already detailed
_MAX_QUERY_LENGTH_FOR_REWRITE = 300

_REWRITE_PROMPT = """\
You are a search query optimizer for a project management system.
Rewrite the following user query to be more specific and searchable.
Expand abbreviations, add relevant synonyms, and make implicit concepts explicit.
Return ONLY the rewritten query — no explanation, no quotes, no punctuation changes.

Project context: {context}
Original query: {query}
Rewritten query:"""


async def rewrite_query(
    query: str,
    models: list[dict],
    *,
    project_title: str = "",
) -> str:
    """Expand a user query for better retrieval recall.

    Returns the rewritten query, or the original if rewriting fails/is skipped.
    """
    # Long queries are already detailed — skip rewriting
    if len(query) > _MAX_QUERY_LENGTH_FOR_REWRITE:
        return query

    # Very short queries (1–2 words) are lookup terms — skip rewriting
    if len(query.split()) <= 2:
        return query

    context = f'"{project_title}"' if project_title else "unspecified project"

    try:
        prompt = _REWRITE_PROMPT.format(query=query, context=context)
        response = await call_with_fallback(models, prompt)
        if not response:
            return query

        rewritten = response.text.strip().strip('"').strip("'").strip()

        # Sanity checks: non-empty, not too long, not a multi-sentence essay
        if rewritten and len(rewritten) <= 500 and "\n" not in rewritten:
            logger.debug(
                "Query rewritten: %r → %r",
                query[:60],
                rewritten[:60],
            )
            return rewritten

    except ProviderUnavailableError:
        pass
    except Exception as exc:
        logger.debug("Query rewriting skipped (%s)", exc)

    return query
