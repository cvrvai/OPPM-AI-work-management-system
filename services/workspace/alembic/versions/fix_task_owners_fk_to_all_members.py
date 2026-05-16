"""Fix task_owners.member_id FK to reference oppm_project_all_members

Revision ID: fix_task_owners_fk_to_all_members
Revises: add_priority_and_owner_to_objectives
Create Date: 2026-05-16

The task_owners table was created with member_id referencing workspace_members(id),
but the model and service layer use oppm_project_all_members.id (which unifies
real workspace members and virtual external members). This migration corrects the
FK so that A/B/C priority assignments work for all member types.
"""

from alembic import op

revision = "fix_task_owners_fk_to_all_members"
down_revision = "add_priority_and_owner_to_objectives"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE task_owners
            DROP CONSTRAINT IF EXISTS task_owners_member_id_fkey
    """)
    op.execute("""
        ALTER TABLE task_owners
            ADD CONSTRAINT task_owners_member_id_fkey
            FOREIGN KEY (member_id)
            REFERENCES oppm_project_all_members(id)
            ON DELETE CASCADE
    """)


def downgrade():
    op.execute("""
        ALTER TABLE task_owners
            DROP CONSTRAINT IF EXISTS task_owners_member_id_fkey
    """)
    op.execute("""
        ALTER TABLE task_owners
            ADD CONSTRAINT task_owners_member_id_fkey
            FOREIGN KEY (member_id)
            REFERENCES workspace_members(id)
            ON DELETE CASCADE
    """)
