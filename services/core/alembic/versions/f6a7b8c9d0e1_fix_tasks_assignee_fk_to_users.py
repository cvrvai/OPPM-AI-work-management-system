"""fix tasks assignee_id FK to reference users instead of workspace_members

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-04

The frontend stores user UUIDs in assignee_id (user_id, not workspace_member row id).
The old FK pointed to workspace_members.id (PK) which is a different UUID.
This migration corrects it to reference users.id.
"""

from alembic import op

# revision identifiers
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


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
