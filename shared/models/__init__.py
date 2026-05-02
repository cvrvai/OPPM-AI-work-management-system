"""ORM models — import all models so Alembic can discover them."""

from shared.models.user import User, RefreshToken
from shared.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite, MemberSkill
from shared.models.project import Project, ProjectMember
from shared.models.task import Task, TaskAssignee, TaskReport, TaskDependency
from shared.models.oppm import OPPMObjective, OPPMTimelineEntry, ProjectCost, OPPMTemplate, OPPMHeader, OPPMTaskItem
from shared.models.git import GithubAccount, RepoConfig, CommitEvent, CommitAnalysis
from shared.models.ai_model import AIModel
from shared.models.workspace_ai_config import WorkspaceAiConfig
from shared.models.notification import Notification, AuditLog
from shared.models.embedding import DocumentEmbedding
from shared.models.agile import Epic, UserStory, Sprint, Retrospective
from shared.models.waterfall import ProjectPhase, PhaseDocument

__all__ = [
    "User", "RefreshToken",
    "Workspace", "WorkspaceMember", "WorkspaceInvite", "MemberSkill",
    "Project", "ProjectMember",
    "Task", "TaskAssignee", "TaskReport", "TaskDependency",
    "OPPMObjective", "OPPMTimelineEntry", "ProjectCost", "OPPMTemplate", "OPPMHeader", "OPPMTaskItem",
    "GithubAccount", "RepoConfig", "CommitEvent", "CommitAnalysis",
    "AIModel",
    "WorkspaceAiConfig",
    "Notification", "AuditLog",
    "DocumentEmbedding",
    "Epic", "UserStory", "Sprint", "Retrospective",
    "ProjectPhase", "PhaseDocument",
]
