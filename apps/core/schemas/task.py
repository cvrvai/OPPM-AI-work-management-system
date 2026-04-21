"""Task schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from shared.schemas.common import Priority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: str
    parent_task_id: Optional[str] = None
    priority: Priority = Priority.medium
    project_contribution: int = Field(0, ge=0, le=100)
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None
    assignee_id: Optional[str] = None
    depends_on: Optional[List[str]] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    parent_task_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None
    assignee_id: Optional[str] = None
    depends_on: Optional[List[str]] = None


class TaskReportCreate(BaseModel):
    report_date: str  # ISO date string: YYYY-MM-DD
    hours: float = Field(gt=0, le=24)
    description: str = Field(default="", max_length=2000)


class TaskReportApprove(BaseModel):
    is_approved: bool
