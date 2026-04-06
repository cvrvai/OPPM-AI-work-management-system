"""oppm_classic_schema_tables

Revision ID: oppm_classic_schema_tables
Revises: oppm_timeline_task_keyed_sort_order
Create Date: 2026-04-07 00:00:00.000000

Changes:
- oppm_sub_objectives: 1-6 strategic alignment columns per project
- task_sub_objectives: many-to-many linking tasks to sub-objectives
- task_owners: A/B/C priority per task per member
- tasks.parent_task_id: self-referencing FK for sub-task hierarchy
- oppm_timeline_entries.quality: Good/Average/Bad quality dimension
- oppm_deliverables: summary deliverable items per project
- oppm_forecasts: forecast items per project
- oppm_risks: risk items per project with RAG status
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'oppm_classic_schema_tables'
down_revision: Union[str, Sequence[str], None] = 'oppm_timeline_task_keyed_sort_order'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sub-objectives (1-6 strategic alignment columns)
    op.create_table(
        'oppm_sub_objectives',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('position BETWEEN 1 AND 6', name='ck_sub_objectives_position'),
        sa.UniqueConstraint('project_id', 'position', name='uq_sub_objectives_project_position'),
    )
    op.create_index('ix_oppm_sub_objectives_project', 'oppm_sub_objectives', ['project_id'])

    # Task ↔ Sub-objective links
    op.create_table(
        'task_sub_objectives',
        sa.Column('task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sub_objective_id', UUID(as_uuid=True), sa.ForeignKey('oppm_sub_objectives.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('task_id', 'sub_objective_id', name='pk_task_sub_objectives'),
    )

    # Task owners with A/B/C priority per member
    op.create_table(
        'task_owners',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('member_id', UUID(as_uuid=True), sa.ForeignKey('workspace_members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('priority', sa.String(1), nullable=False),
        sa.CheckConstraint("priority IN ('A', 'B', 'C')", name='ck_task_owners_priority'),
        sa.UniqueConstraint('task_id', 'member_id', name='uq_task_owners_task_member'),
    )
    op.create_index('ix_task_owners_task', 'task_owners', ['task_id'])
    op.create_index('ix_task_owners_member', 'task_owners', ['member_id'])

    # Parent task reference for sub-task hierarchy
    op.add_column('tasks', sa.Column('parent_task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True))
    op.create_index('ix_tasks_parent', 'tasks', ['parent_task_id'])

    # Quality on timeline entries
    op.add_column('oppm_timeline_entries', sa.Column('quality', sa.String(10), nullable=True))
    op.create_check_constraint('ck_timeline_quality', 'oppm_timeline_entries', "quality IS NULL OR quality IN ('good', 'average', 'bad')")

    # Summary deliverables
    op.create_table(
        'oppm_deliverables',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_number', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_oppm_deliverables_project', 'oppm_deliverables', ['project_id'])

    # Forecasts
    op.create_table(
        'oppm_forecasts',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_number', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_oppm_forecasts_project', 'oppm_forecasts', ['project_id'])

    # Risks
    op.create_table(
        'oppm_risks',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_number', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, server_default='', nullable=False),
        sa.Column('rag', sa.String(10), server_default='green', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("rag IN ('green', 'amber', 'red')", name='ck_risks_rag'),
    )
    op.create_index('ix_oppm_risks_project', 'oppm_risks', ['project_id'])


def downgrade() -> None:
    op.drop_table('oppm_risks')
    op.drop_table('oppm_forecasts')
    op.drop_table('oppm_deliverables')
    op.drop_constraint('ck_timeline_quality', 'oppm_timeline_entries')
    op.drop_column('oppm_timeline_entries', 'quality')
    op.drop_index('ix_tasks_parent', 'tasks')
    op.drop_column('tasks', 'parent_task_id')
    op.drop_table('task_owners')
    op.drop_table('task_sub_objectives')
    op.drop_table('oppm_sub_objectives')
