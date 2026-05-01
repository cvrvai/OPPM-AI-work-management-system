"""add_agile_waterfall_methodology

Revision ID: add_agile_waterfall_methodology
Revises: add_deliverable_output_to_projects
Create Date: 2026-04-10

Changes:
- Add methodology column to projects table
- Create epics table
- Create sprints table
- Create user_stories table (depends on epics + sprints)
- Create retrospectives table (depends on sprints)
- Create project_phases table
- Create phase_documents table (depends on project_phases)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_agile_waterfall_methodology'
down_revision: Union[str, Sequence[str], None] = 'add_deliverable_output_to_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── methodology column on projects ──
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS methodology VARCHAR(20) NOT NULL DEFAULT 'oppm'
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_projects_methodology'
            ) THEN
                ALTER TABLE projects
                ADD CONSTRAINT ck_projects_methodology
                CHECK (methodology IN ('agile', 'waterfall', 'hybrid', 'oppm'));
            END IF;
        END
        $$;
    """)

    # ── epics ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS epics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'open'
                CONSTRAINT ck_epics_status CHECK (status IN ('open', 'in_progress', 'done')),
            priority VARCHAR(10) NOT NULL DEFAULT 'medium'
                CONSTRAINT ck_epics_priority CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_epics_workspace_id ON epics (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_epics_project_id ON epics (project_id)")

    # ── sprints ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS sprints (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            goal TEXT,
            sprint_number INTEGER NOT NULL,
            start_date DATE,
            end_date DATE,
            status VARCHAR(20) NOT NULL DEFAULT 'planning'
                CONSTRAINT ck_sprints_status CHECK (status IN ('planning', 'active', 'completed', 'cancelled')),
            velocity INTEGER CONSTRAINT ck_sprints_velocity CHECK (velocity IS NULL OR velocity >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sprints_workspace_id ON sprints (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sprints_project_id ON sprints (project_id)")

    # ── user_stories (references epics + sprints) ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_stories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            epic_id UUID REFERENCES epics(id) ON DELETE SET NULL,
            sprint_id UUID REFERENCES sprints(id) ON DELETE SET NULL,
            task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
            title VARCHAR(300) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            acceptance_criteria JSONB NOT NULL DEFAULT '[]',
            story_points INTEGER CONSTRAINT ck_user_stories_points CHECK (story_points IS NULL OR story_points >= 0),
            priority VARCHAR(10) NOT NULL DEFAULT 'medium'
                CONSTRAINT ck_user_stories_priority CHECK (priority IN ('low', 'medium', 'high', 'critical')),
            status VARCHAR(20) NOT NULL DEFAULT 'draft'
                CONSTRAINT ck_user_stories_status CHECK (status IN ('draft', 'ready', 'in_progress', 'done', 'rejected')),
            position INTEGER NOT NULL DEFAULT 0,
            created_by UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_stories_workspace_id ON user_stories (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_stories_project_id ON user_stories (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_stories_epic_id ON user_stories (epic_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_stories_sprint_id ON user_stories (sprint_id)")

    # ── retrospectives ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS retrospectives (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            sprint_id UUID NOT NULL UNIQUE REFERENCES sprints(id) ON DELETE CASCADE,
            went_well JSONB NOT NULL DEFAULT '[]',
            to_improve JSONB NOT NULL DEFAULT '[]',
            action_items JSONB NOT NULL DEFAULT '[]',
            created_by UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrospectives_workspace_id ON retrospectives (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrospectives_project_id ON retrospectives (project_id)")

    # ── project_phases ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_phases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            phase_type VARCHAR(30) NOT NULL
                CONSTRAINT ck_project_phases_type CHECK (
                    phase_type IN ('requirements', 'design', 'development', 'testing', 'deployment', 'maintenance')
                ),
            status VARCHAR(20) NOT NULL DEFAULT 'not_started'
                CONSTRAINT ck_project_phases_status CHECK (
                    status IN ('not_started', 'in_progress', 'completed', 'approved')
                ),
            position INTEGER NOT NULL,
            start_date DATE,
            end_date DATE,
            gate_approved_by UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
            gate_approved_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_project_phases_project_type UNIQUE (project_id, phase_type)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_phases_workspace_id ON project_phases (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_phases_project_id ON project_phases (project_id)")

    # ── phase_documents ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS phase_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            phase_id UUID NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            title VARCHAR(300) NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            document_type VARCHAR(50) NOT NULL DEFAULT 'general',
            version INTEGER NOT NULL DEFAULT 1
                CONSTRAINT ck_phase_documents_version CHECK (version >= 1),
            created_by UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_phase_documents_workspace_id ON phase_documents (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_phase_documents_project_id ON phase_documents (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_phase_documents_phase_id ON phase_documents (phase_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS phase_documents")
    op.execute("DROP TABLE IF EXISTS project_phases")
    op.execute("DROP TABLE IF EXISTS retrospectives")
    op.execute("DROP TABLE IF EXISTS user_stories")
    op.execute("DROP TABLE IF EXISTS sprints")
    op.execute("DROP TABLE IF EXISTS epics")
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_projects_methodology")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS methodology")
