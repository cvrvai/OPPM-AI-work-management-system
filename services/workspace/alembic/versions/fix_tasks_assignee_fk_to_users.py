"""fix tasks assignee_id FK to reference users instead of workspace_members

Revision ID: fix_tasks_assignee_fk_to_users
Revises: add_task_dependencies
Create Date: 2026-04-04

The frontend stores user UUIDs in assignee_id (user_id, not workspace_member row id).
The old FK pointed to workspace_members.id (PK) which is a different UUID.
This migration corrects it to reference users.id.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fix_tasks_assignee_fk_to_users'
down_revision: Union[str, Sequence[str], None] = 'add_task_dependencies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the incorrect FK that references workspace_members.id
    op.drop_constraint('tasks_assignee_id_fkey', 'tasks', type_='foreignkey')
    # Add corrected FK referencing users.id
    op.create_foreign_key(
        'tasks_assignee_id_fkey',
        'tasks',
        'users',
        ['assignee_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('tasks_assignee_id_fkey', 'tasks', type_='foreignkey')
    op.create_foreign_key(
        'tasks_assignee_id_fkey',
        'tasks',
        'workspace_members',
        ['assignee_id'],
        ['id'],
        ondelete='SET NULL',
    )
