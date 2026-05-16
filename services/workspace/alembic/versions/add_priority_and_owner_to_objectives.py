"""Add priority and owner_id to oppm_objectives

Revision ID: add_priority_and_owner_to_objectives
Revises: add_objective_id_to_sub_objectives
Create Date: 2026-05-16

The ORM model OPPMObjective declares `priority` and `owner_id` columns
that were never added to the DB in the initial schema. This migration
adds them idempotently.
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_priority_and_owner_to_objectives'
down_revision = 'add_objective_id_to_sub_objectives'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE oppm_objectives
            ADD COLUMN IF NOT EXISTS priority VARCHAR(1),
            ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES workspace_members(id) ON DELETE SET NULL
    """)


def downgrade():
    op.execute("""
        ALTER TABLE oppm_objectives
            DROP COLUMN IF EXISTS priority,
            DROP COLUMN IF EXISTS owner_id
    """)
