# Database Rules

## Schema Design
- All tables use `UUID` primary keys with `gen_random_uuid()`
- Timestamps: `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at` where applicable
- Workspace-scoped tables must have `workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE`
- Use `VARCHAR(N)` with `CHECK` constraints for enum-like fields (not Postgres ENUMs)
- Use `JSONB` for flexible metadata fields

## Row-Level Security
- All tables have RLS enabled
- Use `is_workspace_member(ws_id)` and `is_workspace_admin(ws_id)` helper functions
- Backend bypasses RLS via `service_role_key` — this is intentional
- Webhook and service-inserted data uses `WITH CHECK (true)` policies

## Migrations
- Apply via Supabase MCP `apply_migration` tool
- Use `IF NOT EXISTS` / `IF EXISTS` for idempotent DDL
- Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for adding columns to existing tables
- Always add indexes for foreign keys and frequently filtered columns

## Existing Tables (17)
workspaces, workspace_members, workspace_invites, projects, project_members,
oppm_objectives, tasks, task_assignees, oppm_timeline_entries, project_costs,
github_accounts, repo_configs, commit_events, commit_analyses, ai_models,
notifications, audit_log
