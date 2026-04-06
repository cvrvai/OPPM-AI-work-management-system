"""Project and project member models."""

import uuid
from datetime import date, datetime
from sqlalchemy import String, Text, Integer, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planning", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    project_code: Mapped[str | None] = mapped_column(String(50))
    objective_summary: Mapped[str | None] = mapped_column(Text)
    deliverable_output: Mapped[str | None] = mapped_column(Text)
    budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    planning_hours: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="SET NULL"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('planning', 'in_progress', 'completed', 'on_hold', 'cancelled')", name="ck_projects_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_projects_priority"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_projects_progress"),
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), default="contributor", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "member_id", name="uq_project_members"),
        CheckConstraint("role IN ('lead', 'contributor', 'reviewer', 'observer')", name="ck_project_members_role"),
    )
