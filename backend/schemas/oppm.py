"""OPPM (One Page Project Manager) schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class OPPMObjectiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str
    owner_id: Optional[str] = None
    sort_order: int = 0


class OPPMObjectiveUpdate(BaseModel):
    title: Optional[str] = None
    owner_id: Optional[str] = None
    sort_order: Optional[int] = None


class TimelineEntryUpsert(BaseModel):
    objective_id: str
    year: int
    month: int
    status: str = "none"  # none | planned | in_progress | completed | delayed


class CostCreate(BaseModel):
    project_id: str
    category: str = Field(min_length=1, max_length=100)
    planned_amount: float = 0
    actual_amount: float = 0
    notes: str = ""


class CostUpdate(BaseModel):
    category: Optional[str] = None
    planned_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    notes: Optional[str] = None
