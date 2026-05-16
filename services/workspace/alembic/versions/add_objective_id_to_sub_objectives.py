"""Link sub-objectives to their parent objective

Revision ID: add_objective_id_to_sub_objectives
Revises: add_oppm_project_all_members
Create Date: 2026-05-16

Add objective_id FK to oppm_sub_objectives so each sub-objective belongs
to a specific objective instead of being a flat project-level list.
Removes the old 1-6 position constraint and project-position uniqueness.
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_objective_id_to_sub_objectives'
down_revision = 'add_oppm_project_all_members'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'oppm_sub_objectives',
        sa.Column('objective_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_sub_objectives_objective_id',
        'oppm_sub_objectives', 'oppm_objectives',
        ['objective_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_oppm_sub_objectives_objective_id', 'oppm_sub_objectives', ['objective_id'])

    # Drop old constraints that enforced project-wide 1-6 positions
    op.execute("ALTER TABLE oppm_sub_objectives DROP CONSTRAINT IF EXISTS ck_sub_objectives_position")
    op.execute("ALTER TABLE oppm_sub_objectives DROP CONSTRAINT IF EXISTS uq_sub_objectives_project_position")

    # Change position default so new rows can omit it (use 0 as sentinel)
    op.alter_column('oppm_sub_objectives', 'position', server_default='0', nullable=False)


def downgrade():
    op.drop_index('ix_oppm_sub_objectives_objective_id', table_name='oppm_sub_objectives')
    op.drop_constraint('fk_sub_objectives_objective_id', 'oppm_sub_objectives', type_='foreignkey')
    op.drop_column('oppm_sub_objectives', 'objective_id')
    op.create_unique_constraint('uq_sub_objectives_project_position', 'oppm_sub_objectives', ['project_id', 'position'])
    op.create_check_constraint('ck_sub_objectives_position', 'oppm_sub_objectives', 'position BETWEEN 1 AND 6')
