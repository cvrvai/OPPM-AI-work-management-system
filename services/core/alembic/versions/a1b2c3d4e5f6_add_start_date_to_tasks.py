"""add_start_date_to_tasks

Revision ID: a1b2c3d4e5f6
Revises: c856c65cc033
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c856c65cc033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('start_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'start_date')
