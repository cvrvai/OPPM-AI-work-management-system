"""OPPM objective, timeline entry, project cost, sub-objective, deliverable, forecast, risk models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Integer, Date, DateTime, Numeric, ForeignKey, CheckConstraint, UniqueConstraint, PrimaryKeyConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class OPPMObjective(Base):
    __tablename__ = "oppm_objectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="SET NULL"))
    priority: Mapped[str | None] = mapped_column(String(1))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMSubObjective(Base):
    __tablename__ = "oppm_sub_objectives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 6", name="ck_sub_objectives_position"),
        UniqueConstraint("project_id", "position", name="uq_sub_objectives_project_position"),
    )


class TaskSubObjective(Base):
    __tablename__ = "task_sub_objectives"

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    sub_objective_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("oppm_sub_objectives.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("task_id", "sub_objective_id", name="pk_task_sub_objectives"),
    )


class OPPMTimelineEntry(Base):
    __tablename__ = "oppm_timeline_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    quality: Mapped[str | None] = mapped_column(String(10))
    ai_score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'at_risk', 'blocked')", name="ck_timeline_status"),
        CheckConstraint("quality IS NULL OR quality IN ('good', 'average', 'bad')", name="ck_timeline_quality"),
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


class OPPMDeliverable(Base):
    __tablename__ = "oppm_deliverables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMForecast(Base):
    __tablename__ = "oppm_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMRisk(Base):
    __tablename__ = "oppm_risks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rag: Mapped[str] = mapped_column(String(10), default="green", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("rag IN ('green', 'amber', 'red')", name="ck_risks_rag"),
    )


class OPPMTemplate(Base):
    __tablename__ = "oppm_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMHeader(Base):
    """Per-project OPPM form header fields.

    Stores the free-text cells in the OPPM template that are NOT already
    captured on the projects table (objective_summary, deliverable_output,
    start_date, deadline are on projects — no duplication here).
    """
    __tablename__ = "oppm_header"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    # "Project Leader:" text cell (row 2, left) — free text, not a FK
    project_leader_text: Mapped[str | None] = mapped_column(String(200))
    # "Project Completed By: Text" header on the right completion panel
    completed_by_text: Mapped[str | None] = mapped_column(String, nullable=True)
    # "# People working on the project" row
    people_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMTaskItem(Base):
    """Numbered major-task / sub-task rows in the OPPM template.

    These represent the OPPM form's task layout (1., 1.1, 1.2, 2., …)
    and are distinct from the general-purpose tasks table.
    An optional task_id links back to a real task when desired.
    """
    __tablename__ = "oppm_task_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    # NULL → major task;  set → sub-task row
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("oppm_task_items.id", ondelete="CASCADE"), index=True)
    # Optional link to a real task
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"))
    # "1", "1.1", "1.2", "2", "2.3" …
    number_label: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Free-text deadline shown in the "(Deadline)" column of the OPPM template
    deadline_text: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPPMBorderOverride(Base):
    """Cell-level border overrides for FortuneSheet OPPM rendering.

    Stores AI or user edits to cell borders. Applied as a delta layer
    on top of the generated scaffold in oppmSheetBuilder.ts.
    """
    __tablename__ = "oppm_border_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cell_row: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_col: Mapped[int] = mapped_column(Integer, nullable=False)
    side: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    style: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#000000")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("side IN ('top', 'bottom', 'left', 'right')", name="ck_border_override_side"),
        CheckConstraint(
            "style IN ('thin', 'medium', 'thick', 'dashed', 'dotted', 'none')",
            name="ck_border_override_style",
        ),
        UniqueConstraint("project_id", "cell_row", "cell_col", "side", name="uq_border_override_cell_side"),
    )
