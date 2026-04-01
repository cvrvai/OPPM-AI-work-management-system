"""Project schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from schemas.common import ProjectStatus, Priority


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
    metadata: Optional[dict] = None


class ProjectMemberAdd(BaseModel):
    user_id: str
    role: str = "member"  # lead | member | viewer
