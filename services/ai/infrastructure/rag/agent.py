"""
Query classifier — pattern-based routing for RAG retrievers.

Classifies the user query to determine which retrievers to invoke.
No LLM call required — uses keyword matching for low latency.
"""

import re

# Pattern → retriever names mapping (word stems without trailing \b to match plurals)
_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b(objective|goal|okr|milestone)", re.I), ["vector", "keyword"]),
    (re.compile(r"\b(task|todo|ticket|assignee|assign)", re.I), ["vector", "keyword"]),
    (re.compile(r"\b(commit|code|push|pr\b|pull.request|diff|merge|branch)", re.I), ["vector"]),
    (re.compile(r"\b(cost|budget|spend|expense|money|financial)", re.I), ["structured"]),
    (re.compile(r"\b(status|progress|overview|summary|project)", re.I), ["vector", "structured"]),
    (re.compile(r"\b(team|member|who|people|role)", re.I), ["structured", "vector"]),
    (re.compile(r"\b(timeline|schedule|deadline|week|date|plan)", re.I), ["vector", "structured"]),
]


def classify_query(query: str) -> list[str]:
    """Classify a user query and return the list of retriever names to invoke.

    Returns a deduplicated, ordered list of retriever names.
    Falls back to all retrievers if no patterns match.
    """
    matched: list[str] = []
    seen: set[str] = set()

    for pattern, retrievers in _PATTERNS:
        if pattern.search(query):
            for r in retrievers:
                if r not in seen:
                    matched.append(r)
                    seen.add(r)

    # Default: use all retrievers if nothing matched
    if not matched:
        return ["vector", "keyword", "structured"]

    return matched
