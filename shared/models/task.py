"""Task and task assignee models."""

import uuid
from datetime import date, datetime
from sqlalchemy import String, Text, Integer, Date, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    oppm_objective_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("oppm_objectives.id", ondelete="SET NULL"), index=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    project_contribution: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'completed')", name="ck_tasks_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_tasks_priority"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_tasks_progress"),
        CheckConstraint("project_contribution >= 0 AND project_contribution <= 100", name="ck_tasks_contribution"),
    )


class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "member_id", name="uq_task_assignees"),
    )
