"""add_deliverable_output_to_projects

Revision ID: add_deliverable_output_to_projects
Revises: oppm_classic_schema_tables
Create Date: 2026-04-06

Changes:
- Add deliverable_output TEXT column to projects table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_deliverable_output_to_projects'
down_revision: Union[str, Sequence[str], None] = 'oppm_classic_schema_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('deliverable_output', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'deliverable_output')
