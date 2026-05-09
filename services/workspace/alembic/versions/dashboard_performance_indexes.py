"""dashboard_performance_indexes

Revision ID: dashboard_performance_indexes
Revises: oppm_timeline_task_keyed_sort_order
Create Date: 2026-05-09 00:00:00.000000

Changes:
- Add indexes for dashboard stats queries (tasks, repos, commits)
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dashboard_performance_indexes'
down_revision: Union[str, Sequence[str], None] = 'oppm_timeline_task_keyed_sort_order'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index for tasks filtered by project_id + status (dashboard task counting)
    op.execute('CREATE INDEX IF NOT EXISTS ix_tasks_project_id_status ON tasks (project_id, status)')

    # Index for commit_events time-range + repo filter (dashboard commits today)
    op.execute('CREATE INDEX IF NOT EXISTS ix_commit_events_repo_pushed ON commit_events (repo_config_id, pushed_at DESC)')

    # Index for commit_analyses looked up by commit_event_id
    op.execute('CREATE INDEX IF NOT EXISTS ix_commit_analyses_event_id ON commit_analyses (commit_event_id)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_commit_analyses_event_id')
    op.execute('DROP INDEX IF EXISTS ix_commit_events_repo_pushed')
    op.execute('DROP INDEX IF EXISTS ix_tasks_project_id_status')
