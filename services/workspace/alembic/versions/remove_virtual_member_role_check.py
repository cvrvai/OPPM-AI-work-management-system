"""Remove role check constraint from oppm_virtual_members

Revision ID: remove_virtual_member_role_check
Revises: dashboard_performance_indexes
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_virtual_member_role_check'
down_revision = 'dashboard_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the CHECK constraint on oppm_virtual_members.role so any free-text
    # role can be stored (e.g. "Full Stack", "ML Engineer", "DevOps").
    op.execute("ALTER TABLE oppm_virtual_members DROP CONSTRAINT IF EXISTS oppm_virtual_members_role_check")


def downgrade():
    # Re-add the original 5-value CHECK constraint.
    op.execute(
        "ALTER TABLE oppm_virtual_members ADD CONSTRAINT oppm_virtual_members_role_check "
        "CHECK (role IS NULL OR role IN ('stakeholder', 'vendor', 'advisor', 'contractor', 'observer'))"
    )
