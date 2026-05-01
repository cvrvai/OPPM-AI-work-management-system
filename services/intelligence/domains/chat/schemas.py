"""AI Chat schemas — request/response models for the project chat endpoint."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    messages: list[ChatMessage]
    model_id: Optional[str] = None


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
    iterations: int = 1
    low_confidence: bool = False


class SuggestPlanRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


class SuggestedPlanHeader(BaseModel):
    project_leader: Optional[str] = None
    project_objective: Optional[str] = None
    deliverable_output: Optional[str] = None
    completed_by_text: Optional[str] = None
    people_count: Optional[int] = None


class SuggestedPlanTask(BaseModel):
    title: str
    priority: Optional[str] = None
    suggested_weeks: list[str] = []
    subtasks: list[str] = []


class SuggestedObjective(BaseModel):
    title: str
    suggested_weeks: list[str]
    tasks: list[SuggestedPlanTask] = []


class SuggestPlanResponse(BaseModel):
    header: SuggestedPlanHeader = Field(default_factory=SuggestedPlanHeader)
    suggested_objectives: list[SuggestedObjective] = []
    explanation: str = ""
    commit_token: str = ""
    existing_task_count: int = 0


class CommitPlanRequest(BaseModel):
    commit_token: str


class FeedbackRequest(BaseModel):
    """User rating for an AI response — enables future quality improvement."""
    model_config = {"protected_namespaces": ()}
    rating: Literal["up", "down"]
    message_content: str = Field(default="", max_length=2000,
                                 description="The AI message being rated (for context)")
    user_message: str = Field(default="", max_length=2000,
                              description="The user message that prompted the response")
    comment: Optional[str] = Field(default=None, max_length=500,
                                   description="Optional freeform comment")
    model_id: Optional[str] = None


class WeeklySummaryResponse(BaseModel):
    summary: str
    at_risk: list[str] = []
    on_track: list[str] = []
    blocked: list[str] = []
    suggested_actions: list[str] = []


class CapabilitiesResponse(BaseModel):
    has_project: bool = False
    can_execute_tools: bool = False
    indexed_documents: int = 0


class ReindexResponse(BaseModel):
    total_indexed: int = 0


class FileParseResponse(BaseModel):
    """Response from server-side file parsing."""
    filename: str
    content_type: str = ""
    extracted_text: str
    truncated: bool = False
    error: Optional[str] = None
