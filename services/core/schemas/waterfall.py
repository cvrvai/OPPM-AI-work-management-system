"""Waterfall domain schemas — project phases and phase documents."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


VALID_PHASE_TYPES = ("requirements", "design", "development", "testing", "deployment", "maintenance")
VALID_PHASE_STATUSES = ("not_started", "in_progress", "completed", "approved")
VALID_DOC_TYPES = ("srs", "sdd", "test_plan", "release_notes", "general")


# ── Phases ──

class PhaseUpdate(BaseModel):
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_PHASE_STATUSES:
            raise ValueError(f"status must be one of {VALID_PHASE_STATUSES}")
        return v

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


# ── Phase Documents ──

class PhaseDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: Optional[str] = ""
    document_type: str = "general"

    @field_validator("document_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        if v not in VALID_DOC_TYPES:
            raise ValueError(f"document_type must be one of {VALID_DOC_TYPES}")
        return v


class PhaseDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    content: Optional[str] = None
    document_type: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def validate_doc_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_DOC_TYPES:
            raise ValueError(f"document_type must be one of {VALID_DOC_TYPES}")
        return v
