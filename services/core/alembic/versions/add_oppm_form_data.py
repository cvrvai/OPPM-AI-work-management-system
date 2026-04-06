"""add_oppm_form_data

Revision ID: add_oppm_form_data
Revises: add_oppm_templates
Create Date: 2026-04-06 00:00:00.000000

Changes:
- oppm_header: stores per-project OPPM form header fields
  (project_leader_text, completed_by_text, people_count).
  Fields already on the projects table (objective_summary,
  deliverable_output, start_date, deadline) are NOT duplicated.

- oppm_task_items: stores the numbered major-task / sub-task
  hierarchy shown in the OPPM template (1., 1.1, 1.2, 2., …).
  These are OPPM-layout rows, distinct from the general tasks table.
  An optional task_id column lets a row link back to a real task.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'add_oppm_form_data'
down_revision: Union[str, Sequence[str], None] = 'add_deliverable_output_to_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── oppm_header ─────────────────────────────────────────────────
    op.create_table(
        'oppm_header',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('workspace_id', UUID(as_uuid=True),
                  sa.ForeignKey('workspaces.id', ondelete='CASCADE'),
                  nullable=False),
        # "Project Leader:" text cell in the OPPM form (free text, not a FK)
        sa.Column('project_leader_text', sa.String(200)),
        # "Project Completed By: Text" header on the right panel
        sa.Column('completed_by_text', sa.Text),
        # "# People working on the project" row
        sa.Column('people_count', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_oppm_header_workspace_id', 'oppm_header', ['workspace_id'])

    # ── oppm_task_items ─────────────────────────────────────────────
    op.create_table(
        'oppm_task_items',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=True),
                  sa.ForeignKey('workspaces.id', ondelete='CASCADE'),
                  nullable=False),
        # NULL → major task row;  non-NULL → sub-task row
        sa.Column('parent_id', UUID(as_uuid=True),
                  sa.ForeignKey('oppm_task_items.id', ondelete='CASCADE'),
                  nullable=True),
        # Optional link back to a real task in the tasks table
        sa.Column('task_id', UUID(as_uuid=True),
                  sa.ForeignKey('tasks.id', ondelete='SET NULL'),
                  nullable=True),
        # "1", "1.1", "1.2", "2", "2.1" …
        sa.Column('number_label', sa.String(10), nullable=False, server_default=''),
        sa.Column('title', sa.String(500), nullable=False, server_default=''),
        # Free-text deadline shown in the OPPM template "(Deadline)" column
        sa.Column('deadline_text', sa.String(100)),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_oppm_task_items_project_id', 'oppm_task_items', ['project_id'])
    op.create_index('ix_oppm_task_items_workspace_id', 'oppm_task_items', ['workspace_id'])
    op.create_index('ix_oppm_task_items_parent_id', 'oppm_task_items', ['parent_id'])


def downgrade() -> None:
    op.drop_index('ix_oppm_task_items_parent_id')
    op.drop_index('ix_oppm_task_items_workspace_id')
    op.drop_index('ix_oppm_task_items_project_id')
    op.drop_table('oppm_task_items')
    op.drop_index('ix_oppm_header_workspace_id')
    op.drop_table('oppm_header')
