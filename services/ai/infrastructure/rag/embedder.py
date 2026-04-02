"""
Embedding adapter — generates vector embeddings for RAG.

Wraps the existing OpenAI embedding API with provider selection support.
Currently supports: OpenAI text-embedding-3-small (1536 dimensions).
"""

import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
MAX_TOKENS = 8191
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


async def generate_embedding(text: str) -> list[float]:
    """Generate a single embedding vector for the given text."""
    result = await generate_embeddings([text])
    return result[0]


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embedding vectors for a batch of texts."""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured — returning zero vectors")
        return [[0.0] * EMBEDDING_DIMS for _ in texts]

    truncated = [t[: MAX_TOKENS * 4] if len(t) > MAX_TOKENS * 4 else t for t in texts]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENAI_EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": EMBEDDING_MODEL,
                    "input": truncated,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
    except httpx.HTTPStatusError as e:
        logger.warning("OpenAI embedding API error %s: %s", e.response.status_code, e.response.text[:200])
        return [[0.0] * EMBEDDING_DIMS for _ in texts]
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return [[0.0] * EMBEDDING_DIMS for _ in texts]
