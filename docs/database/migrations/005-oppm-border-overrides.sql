-- Migration 005: OPPM Border Overrides
-- Stores AI/user cell border edits for FortuneSheet rendering

CREATE TABLE IF NOT EXISTS oppm_border_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    cell_row INTEGER NOT NULL,
    cell_col INTEGER NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('top', 'bottom', 'left', 'right')),
    style VARCHAR(20) NOT NULL CHECK (style IN ('thin', 'medium', 'thick', 'dashed', 'dotted', 'none')),
    color VARCHAR(7) NOT NULL DEFAULT '#000000',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, cell_row, cell_col, side)
);

CREATE INDEX IF NOT EXISTS idx_oppm_border_overrides_project
    ON oppm_border_overrides(project_id);

CREATE INDEX IF NOT EXISTS idx_oppm_border_overrides_project_cell
    ON oppm_border_overrides(project_id, cell_row, cell_col);
