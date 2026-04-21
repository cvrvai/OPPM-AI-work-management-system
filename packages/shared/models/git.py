"""GitHub integration models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class GithubAccount(Base):
    __tablename__ = "github_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RepoConfig(Base):
    __tablename__ = "repo_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    github_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("github_accounts.id", ondelete="CASCADE"), nullable=False)
    webhook_secret: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitEvent(Base):
    __tablename__ = "commit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repo_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    commit_message: Mapped[str] = mapped_column(Text, default="")
    author_github_username: Mapped[str] = mapped_column(String(100), default="", index=True)
    branch: Mapped[str] = mapped_column(String(200), default="main")
    files_changed: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommitAnalysis(Base):
    __tablename__ = "commit_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commit_events.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False)
    task_alignment_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    code_quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    quality_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    suggestions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    matched_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    matched_objective_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("oppm_objectives.id", ondelete="SET NULL"))
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
