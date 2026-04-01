"""AI Chat schemas — request/response models for the project chat endpoint."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    messages: list[ChatMessage]
    model_id: Optional[str] = None  # falls back to workspace default


class ToolCallResult(BaseModel):
    tool: str
    input: dict
    result: dict
    success: bool = True
    error: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    tool_calls: list[ToolCallResult] = []
    updated_entities: list[str] = []


class SuggestPlanRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


class SuggestedObjective(BaseModel):
    title: str
    suggested_weeks: list[str]


class SuggestPlanResponse(BaseModel):
    suggested_objectives: list[SuggestedObjective] = []
    explanation: str = ""
    commit_token: str = ""


class CommitPlanRequest(BaseModel):
    commit_token: str


class WeeklySummaryResponse(BaseModel):
    summary: str
    at_risk: list[str] = []
    on_track: list[str] = []
    blocked: list[str] = []
    suggested_actions: list[str] = []
