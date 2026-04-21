"""Agile domain schemas — epics, user stories, sprints, retrospectives."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ── Epics ──

class EpicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = ""
    status: str = "open"
    priority: str = "medium"
    position: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("open", "in_progress", "done"):
            raise ValueError("status must be open, in_progress, or done")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


class EpicUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    position: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("open", "in_progress", "done"):
            raise ValueError("status must be open, in_progress, or done")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


# ── User Stories ──

class AcceptanceCriterion(BaseModel):
    criterion: str
    met: bool = False


class UserStoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = ""
    epic_id: Optional[str] = None
    sprint_id: Optional[str] = None
    task_id: Optional[str] = None
    acceptance_criteria: list[AcceptanceCriterion] = []
    story_points: Optional[int] = Field(None, ge=0)
    priority: str = "medium"
    status: str = "draft"
    position: int = 0

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("draft", "ready", "in_progress", "done", "rejected"):
            raise ValueError("status must be draft, ready, in_progress, done, or rejected")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


class UserStoryUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    epic_id: Optional[str] = None
    sprint_id: Optional[str] = None
    task_id: Optional[str] = None
    acceptance_criteria: Optional[list[AcceptanceCriterion]] = None
    story_points: Optional[int] = Field(None, ge=0)
    priority: Optional[str] = None
    status: Optional[str] = None
    position: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("draft", "ready", "in_progress", "done", "rejected"):
            raise ValueError("status must be draft, ready, in_progress, done, or rejected")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


class UserStoryReorder(BaseModel):
    story_ids: list[str]


# ── Sprints ──

class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    goal: Optional[str] = None
    sprint_number: int = Field(ge=1)
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            from datetime import date
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("Invalid ISO date format")
        return v


class SprintUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            from datetime import date
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("Invalid ISO date format")
        return v


# ── Retrospectives ──

class ActionItem(BaseModel):
    item: str
    assignee_id: Optional[str] = None
    done: bool = False


class RetrospectiveCreate(BaseModel):
    went_well: list[str] = []
    to_improve: list[str] = []
    action_items: list[ActionItem] = []


class RetrospectiveUpdate(BaseModel):
    went_well: Optional[list[str]] = None
    to_improve: Optional[list[str]] = None
    action_items: Optional[list[ActionItem]] = None
