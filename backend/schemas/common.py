"""Common schemas — enums, pagination, error responses."""

from pydantic import BaseModel
from typing import Generic, TypeVar
from enum import Enum

T = TypeVar("T")


class ProjectStatus(str, Enum):
    planning = "planning"
    in_progress = "in_progress"
    completed = "completed"
    on_hold = "on_hold"
    cancelled = "cancelled"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    completed = "completed"


class WorkspaceRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseModel):
    detail: str


class SuccessResponse(BaseModel):
    ok: bool = True
