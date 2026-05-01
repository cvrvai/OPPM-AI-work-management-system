"""Schemas for AI OPPM fill endpoint."""

from typing import Optional

from pydantic import BaseModel, Field


class OPPMFillRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id: Optional[str] = None


class OPPMFillTaskItem(BaseModel):
    index: str           # e.g. "1.1" or "1.1.2"
    title: str
    deadline: Optional[str] = None  # ISO date or None
    status: Optional[str] = None
    is_sub: bool
    sub_objective_positions: list[int] = Field(default_factory=list)
    owners: list["OPPMFillTaskOwnerItem"] = Field(default_factory=list)
    timeline: list["OPPMFillTimelineItem"] = Field(default_factory=list)


class OPPMFillTaskOwnerItem(BaseModel):
    member_id: str
    priority: str


class OPPMFillTimelineItem(BaseModel):
    week_start: str
    status: Optional[str] = None
    quality: Optional[str] = None


class OPPMFillMemberItem(BaseModel):
    id: str
    slot: int            # 0-based position in owner columns
    name: str


class OPPMFillResponse(BaseModel):
    fills: dict[str, Optional[str]]
    tasks: list[OPPMFillTaskItem] = Field(default_factory=list)
    members: list[OPPMFillMemberItem] = Field(default_factory=list)
    """
    fills keys: project_name, project_leader, project_leader_member_id,
                start_date, deadline, project_objective,
                deliverable_output, completed_by_text, people_count
    tasks: ordered flat list (main tasks + sub-tasks interleaved)
           with owner priorities and timeline entries per row
    members: project members in owner-column order
    """


OPPMFillTaskItem.model_rebuild()
