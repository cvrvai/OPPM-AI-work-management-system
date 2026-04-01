from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


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


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: Priority = Priority.medium
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    status: ProjectStatus = ProjectStatus.planning


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[Priority] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    start_date: Optional[str] = None
    deadline: Optional[str] = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: str
    priority: Priority = Priority.medium
    project_contribution: int = Field(0, ge=0, le=100)
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    due_date: Optional[str] = None
    oppm_objective_id: Optional[str] = None


class GitAccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    github_username: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=1)


class RepoConfigCreate(BaseModel):
    repo_name: str = Field(min_length=1)
    project_id: str
    github_account_id: str
    webhook_secret: str = Field(min_length=8)


class OPPMObjectiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str
    owner_id: Optional[str] = None
    sort_order: int = 0


class AIModelConfig(BaseModel):
    name: str
    provider: str
    model_id: str
    endpoint_url: Optional[str] = None
    is_active: bool = True
