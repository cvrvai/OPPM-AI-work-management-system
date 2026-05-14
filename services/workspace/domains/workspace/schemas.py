"""Workspace schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from shared.schemas.common import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class MemberUpdate(BaseModel):
    role: WorkspaceRole


class DisplayNameUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: WorkspaceRole = WorkspaceRole.member


class InviteAccept(BaseModel):
    token: str


class EmailLookupResponse(BaseModel):
    exists: bool
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    already_member: bool = False


class InvitePreviewResponse(BaseModel):
    invite_id: str
    workspace_id: str
    workspace_name: str
    workspace_slug: str
    inviter_name: str
    role: str
    expires_at: str
    accepted_at: Optional[str] = None
    member_count: int
    is_expired: bool
    is_accepted: bool


class MemberSkillCreate(BaseModel):
    skill_name: str = Field(min_length=1, max_length=100)
    skill_level: Literal['beginner', 'intermediate', 'expert']


class MemberSyncItem(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: Optional[str] = None
    role: str = "member"


class SyncMembersRequest(BaseModel):
    members: list[MemberSyncItem]
