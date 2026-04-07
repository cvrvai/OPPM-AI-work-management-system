"""Schemas for AI OPPM fill endpoint."""

from pydantic import BaseModel
from typing import Optional


class OPPMFillRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id: Optional[str] = None


class OPPMFillTaskItem(BaseModel):
    index: str           # e.g. "1.1" or "1.1.2"
    title: str
    deadline: Optional[str] = None  # ISO date or None
    is_sub: bool


class OPPMFillMemberItem(BaseModel):
    slot: int            # 0-based position in owner columns
    name: str


class OPPMFillResponse(BaseModel):
    fills: dict[str, Optional[str]]
    tasks: list[OPPMFillTaskItem] = []
    members: list[OPPMFillMemberItem] = []
    """
    fills keys: project_name, project_leader, start_date, deadline,
                project_objective, deliverable_output
    tasks: ordered flat list (main tasks + sub-tasks interleaved)
    members: workspace members for owner column headers
    """
