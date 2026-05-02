-- Migration 004: workspace_ai_config table
-- Stores per-workspace AI configuration key-value pairs.
-- Key usage: 'oppm_sheet_prompt' → custom OPPM AI sheet action system prompt.
--
-- Apply via:  psql $DATABASE_URL -f docs/database/migrations/004-workspace-ai-config.sql

CREATE TABLE IF NOT EXISTS workspace_ai_config (
    id            UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id  UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    config_key    VARCHAR(100) NOT NULL,
    config_value  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspace_ai_config_ws_key UNIQUE (workspace_id, config_key)
);

CREATE INDEX IF NOT EXISTS idx_workspace_ai_config_workspace ON workspace_ai_config(workspace_id);
