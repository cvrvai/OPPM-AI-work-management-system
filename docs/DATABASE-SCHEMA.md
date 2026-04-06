# Database Schema Reference

Last updated: 2026-04-06

## Purpose

This is the authoritative reference for every table, column, constraint, and index in the OPPM AI Work Management System database.

The schema is defined by SQLAlchemy ORM models in `shared/models/` and managed through Alembic migrations in `services/core/alembic/`. There are currently **29 tables** across 7 domains.

## Quick Summary

| Domain | Tables | Count |
|---|---|---|
| Identity & Auth | `users`, `refresh_tokens` | 2 |
| Workspace & Membership | `workspaces`, `workspace_members`, `workspace_invites`, `member_skills` | 4 |
| Projects & Execution | `projects`, `project_members`, `tasks`, `task_assignees`, `task_reports`, `task_dependencies`, `task_owners` | 7 |
| OPPM Planning | `oppm_objectives`, `oppm_sub_objectives`, `task_sub_objectives`, `oppm_timeline_entries`, `project_costs`, `oppm_deliverables`, `oppm_forecasts`, `oppm_risks` | 8 |
| GitHub Integration | `github_accounts`, `repo_configs`, `commit_events`, `commit_analyses` | 4 |
| AI & Retrieval | `ai_models`, `document_embeddings` | 2 |
| Notifications & Audit | `notifications`, `audit_log` | 2 |
| **Total** | | **29** |

## Conventions

- All primary keys are `UUID` with `gen_random_uuid()` default
- All tables have `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- Mutable tables additionally have `updated_at TIMESTAMPTZ DEFAULT now()` with `ON UPDATE`
- Workspace-scoped tables have `workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE`
- Enum-like fields use `VARCHAR(N)` with `CHECK` constraints (not PostgreSQL ENUM types)
- Flexible metadata uses `JSONB`

---

## 1. Identity & Auth

### `users`

Local application user accounts.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `email` | `VARCHAR(300)` | NO | | UNIQUE |
| `hashed_password` | `TEXT` | NO | | bcrypt hash |
| `full_name` | `VARCHAR(200)` | YES | | |
| `is_active` | `BOOLEAN` | NO | `true` | |
| `is_verified` | `BOOLEAN` | NO | `false` | |
| `avatar_url` | `TEXT` | YES | | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Indexes:** unique on `email`

---

### `refresh_tokens`

Persisted refresh token hashes for session management.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `user_id` | `UUID` | NO | | FK → (none, not enforced) |
| `token_hash` | `VARCHAR(128)` | NO | | UNIQUE; hashed, never raw |
| `expires_at` | `TIMESTAMPTZ` | NO | | |
| `revoked` | `BOOLEAN` | NO | `false` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `user_id`

**Security note:** Only token hashes are stored, never raw tokens.

---

## 2. Workspace & Membership

### `workspaces`

Tenant boundary. All workspace-scoped data cascades from here.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `name` | `VARCHAR(200)` | NO | | |
| `slug` | `VARCHAR(100)` | NO | | UNIQUE |
| `description` | `TEXT` | YES | `""` | |
| `plan` | `VARCHAR(20)` | NO | `'free'` | CHECK: `free`, `pro`, `enterprise` |
| `settings` | `JSONB` | YES | `{}` | |
| `created_by` | `UUID` | NO | | User who created the workspace |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Constraints:** `ck_workspaces_plan` — plan IN ('free', 'pro', 'enterprise')

---

### `workspace_members`

User membership within a workspace. Central join point for most workspace-scoped references.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `user_id` | `UUID` | NO | | FK → `users(id)` CASCADE |
| `role` | `VARCHAR(20)` | NO | `'member'` | CHECK: `owner`, `admin`, `member`, `viewer` |
| `display_name` | `VARCHAR(200)` | YES | | Workspace-specific display name |
| `avatar_url` | `TEXT` | YES | | |
| `joined_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:**
- `uq_ws_members_ws_user` — UNIQUE(`workspace_id`, `user_id`)
- `ck_ws_members_role` — role IN ('owner', 'admin', 'member', 'viewer')

**Design note:** Many features reference `workspace_members.id` rather than `users.id` directly. This enables per-workspace display names, roles, and multi-tenant isolation.

---

### `workspace_invites`

Pending membership invitations.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `email` | `VARCHAR(300)` | NO | | |
| `role` | `VARCHAR(20)` | NO | `'member'` | CHECK: `admin`, `member`, `viewer` |
| `invited_by` | `UUID` | NO | | User ID of inviter |
| `token` | `VARCHAR(64)` | NO | | UNIQUE; invite acceptance token |
| `expires_at` | `TIMESTAMPTZ` | NO | | |
| `accepted_at` | `TIMESTAMPTZ` | YES | | NULL until accepted |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `ck_ws_invites_role` — role IN ('admin', 'member', 'viewer')

---

### `member_skills`

Skill matrix entries tied to workspace membership.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_member_id` | `UUID` | NO | | FK → `workspace_members(id)` CASCADE |
| `skill_name` | `VARCHAR(100)` | NO | | |
| `skill_level` | `VARCHAR(20)` | NO | | CHECK: `beginner`, `intermediate`, `expert` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `ck_member_skills_level` — skill_level IN ('beginner', 'intermediate', 'expert')

**Indexes:** `ix_member_skills_member_id` on `workspace_member_id`

---

## 3. Projects & Execution

### `projects`

Top-level project record, workspace-scoped.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `title` | `VARCHAR(200)` | NO | | |
| `description` | `TEXT` | YES | `""` | |
| `status` | `VARCHAR(20)` | NO | `'planning'` | CHECK: `planning`, `in_progress`, `completed`, `on_hold`, `cancelled` |
| `priority` | `VARCHAR(10)` | NO | `'medium'` | CHECK: `low`, `medium`, `high`, `critical` |
| `progress` | `INTEGER` | NO | `0` | CHECK: 0–100 |
| `project_code` | `VARCHAR(50)` | YES | | Short project identifier |
| `objective_summary` | `TEXT` | YES | | Strategic summary |
| `budget` | `NUMERIC(14,2)` | NO | `0` | |
| `planning_hours` | `NUMERIC(10,2)` | NO | `0` | |
| `start_date` | `DATE` | YES | | |
| `deadline` | `DATE` | YES | | |
| `end_date` | `DATE` | YES | | |
| `lead_id` | `UUID` | YES | | FK → `workspace_members(id)` SET NULL |
| `metadata` | `JSONB` | YES | `{}` | Flexible metadata |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Constraints:**
- `ck_projects_status` — status IN ('planning', 'in_progress', 'completed', 'on_hold', 'cancelled')
- `ck_projects_priority` — priority IN ('low', 'medium', 'high', 'critical')
- `ck_projects_progress` — progress >= 0 AND progress <= 100

**Indexes:** `workspace_id`

---

### `project_members`

Members assigned to a specific project with a project-level role.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `member_id` | `UUID` | NO | | FK → `workspace_members(id)` CASCADE |
| `role` | `VARCHAR(30)` | NO | `'contributor'` | CHECK: `lead`, `contributor`, `reviewer`, `observer` |
| `joined_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:**
- `uq_project_members` — UNIQUE(`project_id`, `member_id`)
- `ck_project_members_role` — role IN ('lead', 'contributor', 'reviewer', 'observer')

**Indexes:** `project_id`, `member_id`

---

### `tasks`

Actionable work items within a project.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `title` | `VARCHAR(200)` | NO | | |
| `description` | `TEXT` | YES | `""` | |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `oppm_objective_id` | `UUID` | YES | | FK → `oppm_objectives(id)` SET NULL |
| `assignee_id` | `UUID` | YES | | FK → `users(id)` SET NULL |
| `status` | `VARCHAR(20)` | NO | `'todo'` | CHECK: `todo`, `in_progress`, `completed` |
| `priority` | `VARCHAR(10)` | NO | `'medium'` | CHECK: `low`, `medium`, `high`, `critical` |
| `progress` | `INTEGER` | NO | `0` | CHECK: 0–100 |
| `project_contribution` | `INTEGER` | NO | `0` | CHECK: 0–100 |
| `start_date` | `DATE` | YES | | |
| `due_date` | `DATE` | YES | | |
| `created_by` | `UUID` | YES | | User who created the task |
| `completed_at` | `TIMESTAMPTZ` | YES | | |
| `sort_order` | `INTEGER` | NO | `0` | Display order within objective |
| `parent_task_id` | `UUID` | YES | | FK → `tasks(id)` CASCADE; self-ref for sub-tasks |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Constraints:**
- `ck_tasks_status` — status IN ('todo', 'in_progress', 'completed')
- `ck_tasks_priority` — priority IN ('low', 'medium', 'high', 'critical')
- `ck_tasks_progress` — progress >= 0 AND progress <= 100
- `ck_tasks_contribution` — project_contribution >= 0 AND project_contribution <= 100

**Indexes:** `project_id`, `oppm_objective_id`, `assignee_id`, `ix_tasks_project_sort_order`, `ix_tasks_parent`

**Note:** `assignee_id` references `users(id)`, not `workspace_members(id)`. The active product flow uses this single-assignee field. The `task_assignees` table still exists but is not used by the current UI.

---

### `task_assignees`

Legacy multi-assignee junction table (not actively used).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE |
| `member_id` | `UUID` | NO | | FK → `workspace_members(id)` CASCADE |
| `assigned_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `uq_task_assignees` — UNIQUE(`task_id`, `member_id`)

**Indexes:** `task_id`, `member_id`

**Note:** The current product uses `tasks.assignee_id` for assignment. This table exists in schema but is not part of the active assignment flow.

---

### `task_reports`

Daily or periodic work log entries submitted by task assignees.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE |
| `reporter_id` | `UUID` | NO | | User ID of reporter |
| `report_date` | `DATE` | NO | | |
| `hours` | `FLOAT` | NO | | Hours worked |
| `description` | `TEXT` | YES | `""` | |
| `is_approved` | `BOOLEAN` | NO | `false` | |
| `approved_by` | `UUID` | YES | | User ID of approver |
| `approved_at` | `TIMESTAMPTZ` | YES | | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `task_id`, `reporter_id`

---

### `task_dependencies`

Task dependency graph (task A depends on task B).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE; composite PK |
| `depends_on_task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE; composite PK |

**Primary key:** `pk_task_dependencies` — (`task_id`, `depends_on_task_id`)

**Indexes:** `task_id`, `depends_on_task_id`

---

## 4. OPPM Planning

### `oppm_objectives`

OPPM (One Page Project Manager) objectives linked to a project.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `title` | `VARCHAR(200)` | NO | | |
| `owner_id` | `UUID` | YES | | FK → `workspace_members(id)` SET NULL |
| `priority` | `VARCHAR(1)` | YES | | A, B, or C priority classification |
| `sort_order` | `INTEGER` | NO | `0` | Display order |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `project_id`

---

### `oppm_timeline_entries`

Weekly timeline cells for OPPM tasks.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE |
| `week_start` | `DATE` | NO | | Monday of the week |
| `status` | `VARCHAR(20)` | NO | `'planned'` | CHECK: `planned`, `in_progress`, `completed`, `at_risk`, `blocked` |
| `quality` | `VARCHAR(10)` | YES | | CHECK: `good`, `average`, `bad` |
| `ai_score` | `INTEGER` | YES | | CHECK: 0–100 |
| `notes` | `TEXT` | YES | | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:**
- `ck_timeline_status` — status IN ('planned', 'in_progress', 'completed', 'at_risk', 'blocked')
- `ck_timeline_quality` — quality IS NULL OR quality IN ('good', 'average', 'bad')
- `ck_timeline_ai_score` — ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)
- `uq_timeline_task_week` — UNIQUE(`task_id`, `week_start`)

**Indexes:** `project_id`, `task_id`

**Note:** Timeline is keyed by `task_id` + `week_start` date. The `quality` dimension allows tracking Good/Average/Bad quality per cell.

---

### `project_costs`

Budget tracking line items per project.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `category` | `VARCHAR(100)` | NO | | Cost category label |
| `description` | `TEXT` | YES | `""` | |
| `planned_amount` | `NUMERIC(12,2)` | NO | `0` | |
| `actual_amount` | `NUMERIC(12,2)` | NO | `0` | |
| `period` | `VARCHAR(20)` | YES | | Time period label |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Indexes:** `project_id`

---

### `oppm_sub_objectives`

Strategic alignment columns (1–6) per project. Each objective maps tasks to up to 6 sub-objectives.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `position` | `INTEGER` | NO | | CHECK: 1–6 |
| `label` | `VARCHAR(200)` | NO | | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:**
- `ck_sub_objectives_position` — position BETWEEN 1 AND 6
- `uq_sub_objectives_project_position` — UNIQUE(`project_id`, `position`)

**Indexes:** `ix_oppm_sub_objectives_project` on `project_id`

---

### `task_sub_objectives`

Many-to-many link between tasks and sub-objectives (checkmark grid in OPPM view).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE; composite PK |
| `sub_objective_id` | `UUID` | NO | | FK → `oppm_sub_objectives(id)` CASCADE; composite PK |

**Primary key:** `pk_task_sub_objectives` — (`task_id`, `sub_objective_id`)

---

### `task_owners`

A/B/C priority ownership per task per workspace member (OPPM owner columns).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `task_id` | `UUID` | NO | | FK → `tasks(id)` CASCADE |
| `member_id` | `UUID` | NO | | FK → `workspace_members(id)` CASCADE |
| `priority` | `VARCHAR(1)` | NO | | CHECK: `A`, `B`, `C` |

**Constraints:**
- `ck_task_owners_priority` — priority IN ('A', 'B', 'C')
- `uq_task_owners_task_member` — UNIQUE(`task_id`, `member_id`)

**Indexes:** `ix_task_owners_task` on `task_id`, `ix_task_owners_member` on `member_id`

**Note:** `A` = Primary owner, `B` = Secondary, `C` = Support. Each task-member pair has at most one priority level.

---

### `oppm_deliverables`

Summary deliverable items displayed in the OPPM bottom section.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `item_number` | `INTEGER` | NO | | Display order |
| `description` | `TEXT` | NO | `''` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `ix_oppm_deliverables_project` on `project_id`

---

### `oppm_forecasts`

Forecast items displayed in the OPPM bottom section.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `item_number` | `INTEGER` | NO | | Display order |
| `description` | `TEXT` | NO | `''` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `ix_oppm_forecasts_project` on `project_id`

---

### `oppm_risks`

Risk register items with RAG (Red/Amber/Green) status displayed in the OPPM bottom section.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `item_number` | `INTEGER` | NO | | Display order |
| `description` | `TEXT` | NO | `''` | |
| `rag` | `VARCHAR(10)` | NO | `'green'` | CHECK: `green`, `amber`, `red` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `ck_risks_rag` — rag IN ('green', 'amber', 'red')

**Indexes:** `ix_oppm_risks_project` on `project_id`

---

## 5. GitHub Integration

### `github_accounts`

Stored GitHub account credentials per workspace.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `account_name` | `VARCHAR(100)` | NO | | Display name |
| `github_username` | `VARCHAR(100)` | NO | | |
| `encrypted_token` | `TEXT` | NO | | Encrypted PAT; NEVER returned to frontend |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `workspace_id`

**Security note:** `encrypted_token` must never appear in API responses.

---

### `repo_configs`

Maps a GitHub repository to a project in the system.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `repo_name` | `VARCHAR(200)` | NO | | UNIQUE; `owner/repo` format |
| `project_id` | `UUID` | NO | | FK → `projects(id)` CASCADE |
| `github_account_id` | `UUID` | NO | | FK → `github_accounts(id)` CASCADE |
| `webhook_secret` | `VARCHAR(200)` | NO | | HMAC-SHA256 secret; NEVER returned to frontend |
| `is_active` | `BOOLEAN` | NO | `true` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `project_id`

**Security note:** `webhook_secret` must never appear in API responses.

---

### `commit_events`

Stored push commit metadata from GitHub webhooks.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `repo_config_id` | `UUID` | NO | | FK → `repo_configs(id)` CASCADE |
| `commit_hash` | `VARCHAR(40)` | NO | | Git SHA |
| `commit_message` | `TEXT` | YES | `""` | |
| `author_github_username` | `VARCHAR(100)` | YES | `""` | |
| `branch` | `VARCHAR(200)` | YES | `'main'` | |
| `files_changed` | `TEXT[]` | YES | `[]` | PostgreSQL ARRAY |
| `additions` | `INTEGER` | NO | `0` | Lines added |
| `deletions` | `INTEGER` | NO | `0` | Lines deleted |
| `pushed_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `repo_config_id`, `author_github_username`

---

### `commit_analyses`

AI-generated analysis results for individual commits.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `commit_event_id` | `UUID` | NO | | FK → `commit_events(id)` CASCADE |
| `ai_model` | `VARCHAR(100)` | NO | | Model used for analysis |
| `task_alignment_score` | `INTEGER` | NO | `0` | 0–100 |
| `code_quality_score` | `INTEGER` | NO | `0` | 0–100 |
| `progress_delta` | `INTEGER` | NO | `0` | Estimated progress change |
| `summary` | `TEXT` | YES | `""` | |
| `quality_flags` | `TEXT[]` | YES | `[]` | PostgreSQL ARRAY |
| `suggestions` | `TEXT[]` | YES | `[]` | PostgreSQL ARRAY |
| `matched_task_id` | `UUID` | YES | | FK → `tasks(id)` SET NULL |
| `matched_objective_id` | `UUID` | YES | | FK → `oppm_objectives(id)` SET NULL |
| `analyzed_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `commit_event_id`, `matched_task_id`

---

## 6. AI & Retrieval

### `ai_models`

Workspace-level AI provider configuration.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `name` | `VARCHAR(100)` | NO | | Display name |
| `provider` | `VARCHAR(20)` | NO | | CHECK: `ollama`, `anthropic`, `openai`, `kimi`, `custom` |
| `model_id` | `VARCHAR(100)` | NO | | Provider-specific model identifier |
| `endpoint_url` | `VARCHAR(300)` | YES | | Custom endpoint URL |
| `is_active` | `BOOLEAN` | NO | `true` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `ck_ai_models_provider` — provider IN ('ollama', 'anthropic', 'openai', 'kimi', 'custom')

**Indexes:** `workspace_id`

---

### `document_embeddings`

pgvector storage for RAG retrieval. Stores embedded representations of workspace artifacts.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | NO | | FK → `workspaces(id)` CASCADE |
| `entity_type` | `VARCHAR(50)` | NO | | e.g. `project`, `task`, `objective` |
| `entity_id` | `VARCHAR(100)` | NO | | |
| `content` | `TEXT` | NO | | Text content for embedding |
| `metadata` | `JSONB` | YES | `{}` | |
| `embedding` | `VECTOR(1536)` | YES | | pgvector 1536-dimensional vector |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updates |

**Constraints:** `uq_doc_embeddings_entity` — UNIQUE(`entity_type`, `entity_id`)

**Indexes:** `workspace_id`

**Note:** Requires the `pgvector` PostgreSQL extension. The 1536 dimension matches OpenAI `text-embedding-3-small` output.

---

## 7. Notifications & Audit

### `notifications`

User-facing system notifications.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | YES | | FK → `workspaces(id)` CASCADE |
| `user_id` | `UUID` | YES | | Target user |
| `type` | `VARCHAR(50)` | NO | `'info'` | CHECK: see below |
| `title` | `VARCHAR(300)` | NO | | |
| `message` | `TEXT` | YES | `""` | |
| `is_read` | `BOOLEAN` | NO | `false` | |
| `link` | `VARCHAR(500)` | YES | | Deep link URL |
| `metadata` | `JSONB` | YES | `{}` | |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Constraints:** `ck_notifications_type` — type IN ('info', 'success', 'warning', 'error', 'ai_analysis', 'commit', 'task_update')

**Indexes:** `workspace_id`, `user_id`, `is_read`

---

### `audit_log`

Change history and traceability for all workspace operations.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `workspace_id` | `UUID` | YES | | FK → `workspaces(id)` SET NULL |
| `user_id` | `UUID` | YES | | |
| `action` | `VARCHAR(50)` | NO | | e.g. `create`, `update`, `delete` |
| `entity_type` | `VARCHAR(50)` | NO | | e.g. `project`, `task`, `oppm_objective` |
| `entity_id` | `UUID` | YES | | |
| `old_data` | `JSONB` | YES | | Previous state snapshot |
| `new_data` | `JSONB` | YES | | New state snapshot |
| `ip_address` | `INET` | YES | | Client IP |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

**Indexes:** `workspace_id`, `user_id`

---

## Foreign Key Reference Map

This map shows all foreign key relationships in the system.

```
users.id
  ← workspace_members.user_id
  ← tasks.assignee_id
  
workspaces.id
  ← workspace_members.workspace_id
  ← workspace_invites.workspace_id
  ← projects.workspace_id
  ← github_accounts.workspace_id
  ← ai_models.workspace_id
  ← document_embeddings.workspace_id
  ← notifications.workspace_id
  ← audit_log.workspace_id

workspace_members.id
  ← member_skills.workspace_member_id
  ← projects.lead_id
  ← project_members.member_id
  ← task_assignees.member_id
  ← task_owners.member_id
  ← oppm_objectives.owner_id

projects.id
  ← project_members.project_id
  ← tasks.project_id
  ← oppm_objectives.project_id
  ← oppm_sub_objectives.project_id
  ← oppm_timeline_entries.project_id
  ← project_costs.project_id
  ← oppm_deliverables.project_id
  ← oppm_forecasts.project_id
  ← oppm_risks.project_id
  ← repo_configs.project_id

tasks.id
  ← tasks.parent_task_id (self-ref)
  ← task_assignees.task_id
  ← task_owners.task_id
  ← task_sub_objectives.task_id
  ← task_reports.task_id
  ← task_dependencies.task_id
  ← task_dependencies.depends_on_task_id
  ← oppm_timeline_entries.task_id
  ← commit_analyses.matched_task_id

oppm_objectives.id
  ← tasks.oppm_objective_id
  ← commit_analyses.matched_objective_id

oppm_sub_objectives.id
  ← task_sub_objectives.sub_objective_id

github_accounts.id
  ← repo_configs.github_account_id

repo_configs.id
  ← commit_events.repo_config_id

commit_events.id
  ← commit_analyses.commit_event_id
```

---

## Migration History

Migrations are managed by Alembic in `services/core/alembic/versions/`.

| Revision | Description |
|---|---|
| `c856c65cc033` | Initial schema — creates all 17 core tables with pgvector extension |
| `a1b2c3d4e5f6` | Add `start_date` column to `tasks` |
| `b2c3d4e5f6a7` | Create `task_reports` table |
| `c3d4e5f6a7b8` | Add project header fields (`project_code`, `objective_summary`, `budget`, `planning_hours`, `end_date`) |
| `d4e5f6a7b8c9` | Create `member_skills` table |
| `e5f6a7b8c9d0` | Create `task_dependencies` table |
| `f6a7b8c9d0e1` | Fix `tasks.assignee_id` FK from workspace_members → users |
| `g7b8c9d0e1f2` | Add `tasks.sort_order`; rename `oppm_timeline_entries.objective_id` → `task_id`, re-key FK to tasks, add unique constraint |
| `h8c9d0e1f2g3` | Classic OPPM schema — create `oppm_sub_objectives`, `task_sub_objectives`, `task_owners`, `oppm_deliverables`, `oppm_forecasts`, `oppm_risks`; add `tasks.parent_task_id`, `oppm_timeline_entries.quality` |

Additional DDL applied via Supabase:
- Performance indexes on high-traffic tables (see `supabase/migrations/20260403_add_performance_indexes.sql`)

---

## Modeling Notes

### Workspace Members as Central Join Point

Many features route through `workspace_members` rather than `users` directly:
- `projects.lead_id` → `workspace_members.id`
- `project_members.member_id` → `workspace_members.id`
- `oppm_objectives.owner_id` → `workspace_members.id`
- `member_skills.workspace_member_id` → `workspace_members.id`

This is correct for multi-tenant isolation where the same user can have different roles and display names across workspaces.

### Task Assignment Model

The current product uses single-assignee via `tasks.assignee_id` (→ `users.id`). The `task_assignees` junction table exists in schema but is not used by the active UI flow.

### OPPM Objective-Task Linkage

Tasks link to objectives via `tasks.oppm_objective_id`. The OPPM view reads objectives with their linked tasks in a single query.

### Security-Sensitive Columns

These columns must never be returned in API responses:
- `github_accounts.encrypted_token`
- `repo_configs.webhook_secret`
- `users.hashed_password`
- `refresh_tokens.token_hash`

### Extension Guidelines

When adding new tables:
1. Use `workspace_id` for workspace-scoped data
2. Prefer `workspace_members.id` over `users.id` for role-sensitive references
3. Add CHECK constraints for enum-like VARCHAR fields
4. Add indexes for foreign keys and frequently filtered columns
5. Use `IF NOT EXISTS` / `IF EXISTS` for idempotent DDL
6. Keep migrations in `services/core/alembic/versions/`
7. Update this document and [ERD.md](ERD.md) with every schema change
