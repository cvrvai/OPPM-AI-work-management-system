# Database Rules

## Schema Design
- All tables use `UUID` primary keys with `gen_random_uuid()`
- Timestamps: `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at` where applicable
- Workspace-scoped tables must have `workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE`
- Use `VARCHAR(N)` with `CHECK` constraints for enum-like fields (not Postgres ENUMs)
- Use `JSONB` for flexible metadata fields

## Row-Level Security
- Backend uses direct DB owner role — RLS is not enforced in the application layer
- All authorization is handled at the API layer via `require_write` / `require_admin` middleware

## Migrations
- Apply via `psql` or the Supabase MCP `execute_sql` / `apply_migration` tool
- Use `IF NOT EXISTS` / `IF EXISTS` for idempotent DDL
- Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for adding columns to existing tables
- Always add indexes for foreign keys and frequently filtered columns

## Existing Tables (23)
workspaces, workspace_members, workspace_invites, member_skills,
projects, project_members,
tasks, task_assignees, task_reports, task_dependencies,
oppm_objectives, oppm_timeline_entries, project_costs,
github_accounts, repo_configs, commit_events, commit_analyses,
ai_models, document_embeddings,
notifications, audit_log,
users, refresh_tokens

See `docs/DATABASE-SCHEMA.md` for full column-level documentation.
