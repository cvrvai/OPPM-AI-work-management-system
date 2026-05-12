"""add_project_files

Revision ID: add_project_files
Revises: add_agile_waterfall_methodology
Create Date: 2026-05-11

Changes:
- Create project_files table for project-level file uploads
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_project_files'
down_revision: Union[str, Sequence[str], None] = 'add_agile_waterfall_methodology'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_name VARCHAR(300) NOT NULL,
            original_name VARCHAR(300) NOT NULL,
            file_size BIGINT NOT NULL DEFAULT 0,
            content_type VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
            storage_path TEXT NOT NULL,
            uploaded_by UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_files_workspace_id ON project_files (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_files_project_id ON project_files (project_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_files")
