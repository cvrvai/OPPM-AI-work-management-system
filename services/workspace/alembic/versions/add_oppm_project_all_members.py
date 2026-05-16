"""Add oppm_project_all_members table

Revision ID: add_oppm_project_all_members
Revises: add_external_identity_to_users
Create Date: 2026-05-16

Unified project team table combining real workspace members and virtual
members for the OPPM owner section. Exactly one of workspace_member_id
or virtual_member_id must be non-null (enforced by CHECK constraint).
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_oppm_project_all_members'
down_revision = 'add_external_identity_to_users'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'oppm_project_all_members',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('workspace_member_id', sa.UUID(), nullable=True),
        sa.Column('virtual_member_id', sa.UUID(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_leader', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_member_id'], ['workspace_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['virtual_member_id'], ['oppm_virtual_members.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            '(workspace_member_id IS NOT NULL) OR (virtual_member_id IS NOT NULL)',
            name='ck_project_all_members_at_least_one',
        ),
        sa.UniqueConstraint('project_id', 'workspace_member_id', name='uq_project_all_members_ws'),
        sa.UniqueConstraint('project_id', 'virtual_member_id', name='uq_project_all_members_virtual'),
    )
    op.create_index('ix_oppm_project_all_members_project_id', 'oppm_project_all_members', ['project_id'])


def downgrade():
    op.drop_index('ix_oppm_project_all_members_project_id', table_name='oppm_project_all_members')
    op.drop_table('oppm_project_all_members')
