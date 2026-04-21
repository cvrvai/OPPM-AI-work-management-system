"""merge_agile_waterfall_and_oppm_form_data

Revision ID: merge_agile_waterfall_and_oppm_form_data
Revises: add_agile_waterfall_methodology, add_oppm_form_data
Create Date: 2026-04-10

Merges two branches that both diverged from add_deliverable_output_to_projects:
  - add_agile_waterfall_methodology  (agile/waterfall tables + methodology column)
  - add_oppm_form_data               (oppm form data table)
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'merge_agile_waterfall_and_oppm_form_data'
down_revision: Union[str, Sequence[str], None] = (
    'add_agile_waterfall_methodology',
    'add_oppm_form_data',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
