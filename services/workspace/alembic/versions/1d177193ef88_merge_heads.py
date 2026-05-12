"""merge heads

Revision ID: 1d177193ef88
Revises: add_api_key_to_ai_models, add_project_files, add_task_virtual_assignees, merge_agile_waterfall_and_oppm_form_data
Create Date: 2026-05-11 04:34:13.931068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d177193ef88'
down_revision: Union[str, Sequence[str], None] = ('add_api_key_to_ai_models', 'add_project_files', 'add_task_virtual_assignees', 'merge_agile_waterfall_and_oppm_form_data')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
