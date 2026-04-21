"""Dashboard schemas."""

from pydantic import BaseModel
from typing import Any


class ProjectProgress(BaseModel):
    project_id: str
    title: str
    progress: int
    status: str


class DashboardStats(BaseModel):
    total_projects: int = 0
    active_projects: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    total_commits_today: int = 0
    avg_quality_score: int = 0
    avg_alignment_score: int = 0
    project_progress: list[Any] = []
