"""RAG request/response schemas."""

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    project_id: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class RAGSource(BaseModel):
    entity_type: str
    entity_id: str
    title: str
    relevance_score: float
    source: str


class RAGQueryResponse(BaseModel):
    context: str
    sources: list[RAGSource]
    memory_context: str = ""
