"""Task schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from shared.schemas.common import Priority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: str
    priority: Priority = Priority.medium
    project_contribution: int = Field(0, ge=0, le=100)
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None
    assignee_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None
    assignee_id: Optional[str] = None
