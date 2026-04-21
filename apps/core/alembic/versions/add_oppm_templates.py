"""add_oppm_templates

Revision ID: add_oppm_templates
Revises: oppm_classic_schema_tables
Create Date: 2026-04-06 00:00:00.000000

Changes:
- oppm_templates: stores FortuneSheet-compatible JSON per project
  so users can upload an XLSX and use it as the OPPM form.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'add_oppm_templates'
down_revision: Union[str, Sequence[str], None] = 'oppm_classic_schema_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'oppm_templates',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sheet_data', JSONB, nullable=False),
        sa.Column('file_name', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_oppm_templates_workspace_id', 'oppm_templates', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('ix_oppm_templates_workspace_id')
    op.drop_table('oppm_templates')
