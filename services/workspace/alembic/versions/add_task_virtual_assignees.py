"""Add task_virtual_assignees table for external member assignment

Revision ID: add_task_virtual_assignees
Revises: remove_virtual_member_role_check
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_task_virtual_assignees'
down_revision = 'remove_virtual_member_role_check'
branch_labels = None
depends_on = None


def upgrade():
    # Create oppm_virtual_members if it was not created by an earlier migration
    # (the original CREATE TABLE migration was removed during a refactor).
    op.execute("""
        CREATE TABLE IF NOT EXISTS oppm_virtual_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            role VARCHAR(100),
            email VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_oppm_virtual_members_workspace
        ON oppm_virtual_members (workspace_id)
    """)

    op.create_table(
        'task_virtual_assignees',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=False),
        sa.Column('virtual_member_id', sa.UUID(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['virtual_member_id'], ['oppm_virtual_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'virtual_member_id', name='uq_task_virtual_assignees')
    )
    op.create_index(op.f('ix_task_virtual_assignees_task_id'), 'task_virtual_assignees', ['task_id'], unique=False)
    op.create_index(op.f('ix_task_virtual_assignees_virtual_member_id'), 'task_virtual_assignees', ['virtual_member_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_task_virtual_assignees_virtual_member_id'), table_name='task_virtual_assignees')
    op.drop_index(op.f('ix_task_virtual_assignees_task_id'), table_name='task_virtual_assignees')
    op.drop_table('task_virtual_assignees')
