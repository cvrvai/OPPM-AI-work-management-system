-- Migration 007: Performance indexes for projects list and workspace auth lookups
-- Addresses slow first-fetch when loading projects after workspace switch

-- Composite index for the common projects list query:
-- SELECT * FROM projects WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
CREATE INDEX IF NOT EXISTS idx_projects_workspace_created
    ON projects(workspace_id, created_at DESC);

-- Index on workspace_members for fast auth lookups by user_id
-- (The unique constraint uq_ws_members_ws_user already covers workspace_id+user_id,
--  but a standalone user_id index helps when looking up all workspaces for a user)
CREATE INDEX IF NOT EXISTS idx_workspace_members_user_id
    ON workspace_members(user_id);
