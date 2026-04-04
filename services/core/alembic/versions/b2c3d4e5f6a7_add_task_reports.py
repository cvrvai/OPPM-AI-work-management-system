"""add_task_reports

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'task_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reporter_id', UUID(as_uuid=True), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Float(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('approved_by', UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_task_reports_task_id', 'task_reports', ['task_id'])
    op.create_index('ix_task_reports_reporter_id', 'task_reports', ['reporter_id'])


def downgrade() -> None:
    op.drop_index('ix_task_reports_reporter_id', table_name='task_reports')
    op.drop_index('ix_task_reports_task_id', table_name='task_reports')
    op.drop_table('task_reports')
