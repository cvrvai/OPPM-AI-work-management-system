"""add_member_skills

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'member_skills',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_member_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('workspace_members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('skill_name', sa.String(100), nullable=False),
        sa.Column('skill_level', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("skill_level IN ('beginner', 'intermediate', 'expert')", name='ck_member_skills_level'),
    )
    op.create_index('ix_member_skills_member_id', 'member_skills', ['workspace_member_id'])


def downgrade() -> None:
    op.drop_index('ix_member_skills_member_id', table_name='member_skills')
    op.drop_table('member_skills')
