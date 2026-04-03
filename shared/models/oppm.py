"""OPPM objective, timeline entry, and project cost models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Date, DateTime, Numeric, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class OPPMObjective(Base):
    __tablename__ = "oppm_objectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="SET NULL"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMTimelineEntry(Base):
    __tablename__ = "oppm_timeline_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    objective_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("oppm_objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    ai_score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'at_risk', 'blocked')", name="ck_timeline_status"),
        CheckConstraint("ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)", name="ck_timeline_ai_score"),
    )


class ProjectCost(Base):
    __tablename__ = "project_costs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    period: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
