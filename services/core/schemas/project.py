"""Project schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from shared.schemas.common import ProjectStatus, Priority


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_code: Optional[str] = Field(None, max_length=50)
    objective_summary: Optional[str] = None
    priority: Priority = Priority.medium
    budget: Optional[float] = Field(None, ge=0)
    planning_hours: Optional[float] = Field(None, ge=0)
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    end_date: Optional[str] = None
    lead_id: Optional[str] = None
    status: ProjectStatus = ProjectStatus.planning


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project_code: Optional[str] = Field(None, max_length=50)
    objective_summary: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[Priority] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    budget: Optional[float] = Field(None, ge=0)
    planning_hours: Optional[float] = Field(None, ge=0)
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    end_date: Optional[str] = None
    lead_id: Optional[str] = None
    metadata: Optional[dict] = None


class ProjectMemberAdd(BaseModel):
    user_id: str
    role: str = "member"
