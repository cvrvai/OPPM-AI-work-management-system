"""oppm_timeline_task_keyed_sort_order

Revision ID: oppm_timeline_task_keyed_sort_order
Revises: fix_tasks_assignee_fk_to_users
Create Date: 2026-04-06 00:00:00.000000

Changes:
- tasks: add sort_order INTEGER NOT NULL DEFAULT 0
- oppm_timeline_entries: rename objective_id -> task_id, re-key FK to tasks
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'oppm_timeline_task_keyed_sort_order'
down_revision: Union[str, Sequence[str], None] = 'fix_tasks_assignee_fk_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tasks.sort_order
    op.add_column('tasks', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_tasks_project_sort_order', 'tasks', ['project_id', 'sort_order'])

    # oppm_timeline_entries: rename objective_id → task_id
    op.execute('TRUNCATE TABLE oppm_timeline_entries')
    op.drop_constraint('oppm_timeline_entries_objective_id_fkey', 'oppm_timeline_entries', type_='foreignkey')
    op.drop_index('ix_oppm_timeline_entries_objective_id', table_name='oppm_timeline_entries')
    op.alter_column('oppm_timeline_entries', 'objective_id', new_column_name='task_id')
    op.create_foreign_key(
        'oppm_timeline_entries_task_id_fkey',
        'oppm_timeline_entries', 'tasks',
        ['task_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint('uq_timeline_task_week', 'oppm_timeline_entries', ['task_id', 'week_start'])
    op.create_index('ix_oppm_timeline_entries_task_id', 'oppm_timeline_entries', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_oppm_timeline_entries_task_id', table_name='oppm_timeline_entries')
    op.drop_constraint('uq_timeline_task_week', 'oppm_timeline_entries', type_='unique')
    op.drop_constraint('oppm_timeline_entries_task_id_fkey', 'oppm_timeline_entries', type_='foreignkey')
    op.alter_column('oppm_timeline_entries', 'task_id', new_column_name='objective_id')
    op.create_index('ix_oppm_timeline_entries_objective_id', 'oppm_timeline_entries', ['objective_id'])
    op.create_foreign_key(
        'oppm_timeline_entries_objective_id_fkey',
        'oppm_timeline_entries', 'oppm_objectives',
        ['objective_id'], ['id'],
        ondelete='CASCADE',
    )
    op.drop_index('ix_tasks_project_sort_order', table_name='tasks')
    op.drop_column('tasks', 'sort_order')
