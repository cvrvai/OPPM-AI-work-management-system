"""Workspace schemas — copied from services/core/schemas/workspace.py."""

from pydantic import BaseModel, Field
from typing import Optional
from shared.schemas.common import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class MemberUpdate(BaseModel):
    role: WorkspaceRole


class DisplayNameUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: WorkspaceRole = WorkspaceRole.member


class MemberSkillCreate(BaseModel):
    skill_name: str = Field(min_length=1, max_length=100)
    level: Optional[str] = None
