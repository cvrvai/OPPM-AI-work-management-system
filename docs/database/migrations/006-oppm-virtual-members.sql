-- Migration 006: OPPM Virtual Members & Unified Project Members
-- Adds support for external stakeholders without system accounts
-- and a unified view of real + virtual members for OPPM owner columns.

-- ─── Virtual Members ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS oppm_virtual_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(300),
    role VARCHAR(50) CHECK (role IS NULL OR role IN ('stakeholder', 'vendor', 'advisor', 'contractor', 'observer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oppm_virtual_members_project
    ON oppm_virtual_members(project_id);

-- ─── Unified Project Members (real + virtual) ────────────────

CREATE TABLE IF NOT EXISTS oppm_project_all_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_member_id UUID REFERENCES workspace_members(id) ON DELETE CASCADE,
    virtual_member_id UUID REFERENCES oppm_virtual_members(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_leader BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_project_all_members_at_least_one CHECK (
        (workspace_member_id IS NOT NULL) OR (virtual_member_id IS NOT NULL)
    ),
    UNIQUE (project_id, workspace_member_id),
    UNIQUE (project_id, virtual_member_id)
);

CREATE INDEX IF NOT EXISTS idx_oppm_project_all_members_project
    ON oppm_project_all_members(project_id);

CREATE INDEX IF NOT EXISTS idx_oppm_project_all_members_order
    ON oppm_project_all_members(project_id, display_order);
