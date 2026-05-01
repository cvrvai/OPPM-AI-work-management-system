"""add_api_key_to_ai_models

Revision ID: add_api_key_to_ai_models
Revises: oppm_timeline_task_keyed_sort_order
Create Date: 2026-05-01 00:00:00.000000

Changes:
- ai_models: add api_key VARCHAR(500) nullable column for Ollama Cloud auth
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_api_key_to_ai_models'
down_revision: Union[str, Sequence[str], None] = 'oppm_timeline_task_keyed_sort_order'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_models',
        sa.Column('api_key', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('ai_models', 'api_key')
