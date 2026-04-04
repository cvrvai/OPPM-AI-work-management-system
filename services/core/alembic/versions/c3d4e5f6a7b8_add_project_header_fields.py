"""add_project_header_fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-04 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('project_code', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('objective_summary', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('budget', sa.Numeric(14, 2), nullable=False, server_default='0'))
    op.add_column('projects', sa.Column('planning_hours', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('projects', sa.Column('end_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'end_date')
    op.drop_column('projects', 'planning_hours')
    op.drop_column('projects', 'budget')
    op.drop_column('projects', 'objective_summary')
    op.drop_column('projects', 'project_code')
