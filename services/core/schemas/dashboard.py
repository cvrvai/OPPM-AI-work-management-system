"""Dashboard schemas."""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_projects: int = 0
    active_projects: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    total_commits_today: int = 0
    avg_quality_score: int = 0
    avg_alignment_score: int = 0
