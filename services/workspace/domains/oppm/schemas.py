"""OPPM (One Page Project Manager) schemas."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ── Objectives ──

class OPPMObjectiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: Optional[str] = None
    owner_id: Optional[str] = None
    priority: Optional[str] = None
    sort_order: int = 0


class OPPMObjectiveUpdate(BaseModel):
    title: Optional[str] = None
    owner_id: Optional[str] = None
    priority: Optional[str] = None
    sort_order: Optional[int] = None


# ── Sub-Objectives ──

class SubObjectiveCreate(BaseModel):
    objective_id: Optional[str] = None
    position: Optional[int] = None
    label: str = Field(min_length=1, max_length=200)


class SubObjectiveUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    position: Optional[int] = None


class TaskSubObjectiveSet(BaseModel):
    """Set sub-objective alignment for a task (list of sub_objective_ids)."""
    sub_objective_ids: list[str]


# ── Task Owners (A/B/C per task per member) ──

class TaskOwnerSet(BaseModel):
    member_id: str
    priority: str = Field(pattern=r'^[ABC]$')

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("A", "B", "C"):
            raise ValueError("priority must be A, B, or C")
        return v


class TaskOwnerRemove(BaseModel):
    member_id: str


# ── Timeline ──

class TimelineEntryUpsert(BaseModel):
    task_id: str
    week_start: str
    status: str = "planned"
    quality: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str | None) -> str | None:
        if v is not None and v not in ("good", "average", "bad"):
            raise ValueError("quality must be good, average, or bad")
        return v


# ── Costs ──

class CostCreate(BaseModel):
    project_id: Optional[str] = None
    category: str = Field(min_length=1, max_length=100)
    planned_amount: float = 0
    actual_amount: float = 0
    description: str = ""


class CostUpdate(BaseModel):
    category: Optional[str] = None
    planned_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    description: Optional[str] = None


# ── Deliverables ──

class DeliverableCreate(BaseModel):
    item_number: int = Field(ge=1)
    description: str = ""


class DeliverableUpdate(BaseModel):
    item_number: Optional[int] = None
    description: Optional[str] = None


# ── Forecasts ──

class ForecastCreate(BaseModel):
    item_number: int = Field(ge=1)
    description: str = ""


class ForecastUpdate(BaseModel):
    item_number: Optional[int] = None
    description: Optional[str] = None


# ── Risks ──

class RiskCreate(BaseModel):
    item_number: int = Field(ge=1)
    description: str = ""
    rag: str = "green"

    @field_validator("rag")
    @classmethod
    def validate_rag(cls, v: str) -> str:
        if v not in ("green", "amber", "red"):
            raise ValueError("rag must be green, amber, or red")
        return v


class RiskUpdate(BaseModel):
    item_number: Optional[int] = None
    description: Optional[str] = None
    rag: Optional[str] = None

    @field_validator("rag")
    @classmethod
    def validate_rag(cls, v: str | None) -> str | None:
        if v is not None and v not in ("green", "amber", "red"):
            raise ValueError("rag must be green, amber, or red")
        return v


# ── Virtual Members ──

class VirtualMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=300)
    role: Optional[str] = Field(None, max_length=50)


class VirtualMemberUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=300)
    role: Optional[str] = Field(None, max_length=50)


class ProjectAllMemberReorder(BaseModel):
    """Reorder a unified member entry by its all-member id."""
    display_order: int = Field(ge=0)


class ProjectAllMemberSetLeader(BaseModel):
    all_member_id: str


# ── OPPM Header ──

class OPPMHeaderUpsert(BaseModel):
    project_leader_text: Optional[str] = Field(None, max_length=200)
    completed_by_text: Optional[str] = None
    people_count: Optional[int] = Field(None, ge=0)


# ── OPPM Task Items ──

class OPPMTaskItemPayload(BaseModel):
    number_label: Optional[str] = Field(None, max_length=10)
    title: Optional[str] = Field(None, max_length=500)
    deadline_text: Optional[str] = Field(None, max_length=100)
    task_id: Optional[str] = None
    children: list["OPPMTaskItemPayload"] = []


OPPMTaskItemPayload.model_rebuild()


class OPPMTaskItemsReplace(BaseModel):
    items: list[OPPMTaskItemPayload]


# ── Sheet Actions (OPPM AI sheet control) ──

class SheetActionParams(BaseModel):
    """Flexible params dict for a sheet action — validated loosely so the LLM output passes through."""
    model_config = {"extra": "allow"}


class SheetAction(BaseModel):
    """A single sheet action. Supports both nested params {action, params} and flat {action, range, value}."""
    model_config = {"extra": "allow"}
    action: str = Field(min_length=1, max_length=50)
    params: dict = Field(default_factory=dict)


class SheetActionsRequest(BaseModel):
    actions: list[SheetAction] = Field(min_length=1)


class SheetActionResult(BaseModel):
    action: str
    success: bool
    error: Optional[str] = None


class SheetActionsResponse(BaseModel):
    results: list[SheetActionResult]
    success_count: int
    error_count: int


# ── AI Config (workspace-level prompt overrides) ──

class OppmSheetPromptResponse(BaseModel):
    config_key: str = "oppm_sheet_prompt"
    prompt: str
    is_default: bool


class OppmSheetPromptUpsert(BaseModel):
    prompt: str = Field(min_length=50, max_length=32000)
