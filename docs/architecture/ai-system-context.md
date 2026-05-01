# AI System Context

Last verified: 2026-05-01

## Purpose

This is the fastest high-signal reference for future AI-assisted updates.

Read this file first when you need to understand how the current system works, which files own each feature, and how the database is designed. It is meant to reduce broad codebase scanning, not replace code verification when a change affects behavior, contracts, or schema.

## How To Use This File

1. Read the current system snapshot.
2. Jump to the feature section you are changing.
3. **Open the canonical feature doc in `docs/features/` for full detail.**
4. Open only the listed source-of-truth files for that feature.
5. If the change affects data shape, also read the database design and schema hotspot sections.
6. If this file and the code disagree, treat the code as the final source of truth and update this file.

## Current System Snapshot

- Product: a workspace-scoped OPPM project management platform with AI assistance, GitHub analysis, and spreadsheet-style planning.
- Frontend: React 19 + Vite 8 + TypeScript 5.9 + Tailwind CSS v4 + TanStack Query + Zustand.
- Backend: FastAPI microservices split across `workspace`, `intelligence`, `integrations`, `automation`, plus a Python gateway and an nginx gateway.
- Data model: one shared PostgreSQL database and one shared ORM layer in `shared/models/`.
- Auth: local HS256 JWT validation in `shared/auth.py`; refresh tokens persisted in the database.
- Tenancy: workspace model; most business routes are `/api/v1/workspaces/{workspace_id}/...`.
- AI stack: workspace chat, project chat, plan suggestion, weekly summary, OPPM fill, OCR-style OPPM extraction, RAG retrieval, and per-workspace model configuration.
- GitHub stack: GitHub accounts, repo configuration, webhook ingestion, commit storage, commit analysis, developer reports.
- Integration layer: HTTP-exposed MCP tools for project, task, objective, and commit summaries.

## Verified Drift To Keep In Mind

- `CLAUDE.md` still says the system has 23 tables; the canonical count is 29 tables across 7 domains.
- `docs/database/schema.md` documents 29 tables, which is consistent with the active ORM models.
- The project-member add payload uses the field name `user_id`, but the working value is a `workspace_members.id` that becomes `project_members.member_id`.
- Workspace responses currently expose `current_user_role`; some frontend code still falls back to `role`.
- The current frontend includes an `Invitations` page and sidebar entry in addition to the invite-accept flow.
- `shared/models/__init__.py` does not list every OPPM table class, but importing `shared.models.oppm` still registers them with SQLAlchemy metadata.

## Feature Reference

Each feature below links to its canonical doc in `docs/features/`. Open that doc for the full flow, file list, tables, and caveats.

| # | Feature | Canonical Doc | Service |
|---|---------|-------------|---------|
| 1 | Authentication And Session Bootstrap | [`features/auth/authentication.md`](../features/auth/authentication.md) | Workspace |
| 2 | Workspace Bootstrap, Tenancy, And Authorization | [`features/workspace/workspaces.md`](../features/workspace/workspaces.md) | Workspace |
| 3 | Team, Invites, And Member Skills | [`features/workspace/team-invites.md`](../features/workspace/team-invites.md) | Workspace |
| 4 | Projects And Project Membership | [`features/project/projects.md`](../features/project/projects.md) | Workspace |
| 5 | Tasks, Hierarchy, Dependencies, And Daily Reports | [`features/project/tasks.md`](../features/project/tasks.md) | Workspace |
| 6 | Structured OPPM Planning Data | [`features/oppm/structured-planning.md`](../features/oppm/structured-planning.md) | Workspace |
| 7 | OPPM Spreadsheet Template, Header, Task Items, Import, Export, And AI Fill | [`features/oppm/spreadsheet-rendering.md`](../features/oppm/spreadsheet-rendering.md) | Workspace + Intelligence |
| 8 | AI Assistant, Plan Suggestion, Weekly Summary, Reindex, RAG, And Model Configuration | [`features/ai/ai-assistant.md`](../features/ai/ai-assistant.md) | Intelligence |
| 9 | GitHub Integration, Commits, And Commit Analysis | [`features/github/github-integration.md`](../features/github/github-integration.md) | Integrations + Intelligence |
| 10 | Dashboard And Notifications | [`features/dashboard/dashboard-notifications.md`](../features/dashboard/dashboard-notifications.md) | Workspace |
| 11 | MCP Tools | [`features/mcp/mcp-tools.md`](../features/mcp/mcp-tools.md) | Automation |
| 12 | Tool Registry And Agentic Loop | [`features/ai/tool-registry.md`](../features/ai/tool-registry.md) | Intelligence |

## Database Schema Design

## Design Principles

- All services share one PostgreSQL database through `shared/database.py` and `shared/models/`.
- Alembic migrations live in `services/workspace/alembic/`.
- UUID primary keys are used throughout.
- Most business data is workspace-scoped and should carry `workspace_id` with cascade delete from `workspaces`.
- `workspace_members` is the central membership pivot for roles, display names, and many downstream references.
- Authorization is enforced in the API layer, not with Postgres RLS.
- Flexible fields use `JSONB`; commit and analysis lists use Postgres arrays; embeddings use `pgvector`.

## Current ORM Table Map

The current ORM model files define 29 active tables across 7 functional domains.

### Identity And Auth

- `users`
- `refresh_tokens`

### Workspace And Membership

- `workspaces`
- `workspace_members`
- `workspace_invites`
- `member_skills`

### Projects And Execution

- `projects`
- `project_members`
- `tasks`
- `task_assignees`
- `task_reports`
- `task_dependencies`
- `task_owners`

### OPPM Planning And Template Storage

- `oppm_objectives`
- `oppm_sub_objectives`
- `task_sub_objectives`
- `oppm_timeline_entries`
- `project_costs`
- `oppm_deliverables`
- `oppm_forecasts`
- `oppm_risks`
- `oppm_templates`
- `oppm_header`
- `oppm_task_items`

### GitHub Integration

- `github_accounts`
- `repo_configs`
- `commit_events`
- `commit_analyses`

### AI And Retrieval

- `ai_models`
- `document_embeddings`

### Notifications And Audit

- `notifications`
- `audit_log`

## Relationship Patterns That Matter

- `workspaces` is the tenancy root for most application data.
- `workspace_members` links `users` into a workspace and carries role plus workspace-specific display data.
- `projects` belong to a workspace and often reference `workspace_members.id` for leadership or ownership.
- `project_members` is a scoped subset of workspace members assigned to a project.
- `tasks` belong to projects, not directly to workspaces; workspace scoping is derived through the project.
- `tasks.parent_task_id` creates the main-task and sub-task hierarchy.
- `tasks.assignee_id` points to `users.id`, which is an important exception to the broader `workspace_members.id` pattern.
- `task_dependencies` is a pure relationship table for predecessor links.
- Structured OPPM data is split across objectives, sub-objectives, timeline, costs, deliverables, forecasts, risks, and owner-link tables.
- Spreadsheet OPPM data is split across `oppm_templates`, `oppm_header`, and `oppm_task_items`.
- GitHub data flows from `repo_configs` to `commit_events` to `commit_analyses`.
- Retrieval data is stored in `document_embeddings` and scoped by workspace.
- Notifications are user-scoped with optional workspace context.

## Schema Hotspots And Quirks

- `workspace_members.id` is frequently the correct foreign-key target even when a payload or variable name says `user_id`.
- `tasks.assignee_id` is the live assignment path used by the current frontend.
- `task_assignees` is legacy relative to the current UI but still present in the schema.
- `task_owners` is specific to OPPM A/B/C ownership and is separate from general assignment.
- `refresh_tokens.user_id` is indexed but not declared as a formal foreign key in the current model.
- The OPPM area has both structured planning tables and spreadsheet/template tables; changing only one layer can create partial behavior drift.

## If You Need To Change The Schema

1. Update the relevant ORM model in `shared/models/`.
2. Add or update the Alembic migration in `services/workspace/alembic/versions/`.
3. Update repositories, services, schemas, and route handlers that read or write the field.
4. Update this file and `docs/DATABASE-SCHEMA.md` if the public understanding of the schema changed.
5. Re-check any frontend type definitions if the API contract changed.

## Fast File Map For Future Updates

- Auth and session: `frontend/src/stores/authStore.ts`, `frontend/src/lib/api.ts`, `services/workspace/domains/auth/router.py`, `services/workspace/domains/auth/service.py`, `shared/auth.py`, `shared/models/user.py`
- Workspaces, members, invites: `frontend/src/pages/Team.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/AcceptInvite.tsx`, `frontend/src/pages/Invitations.tsx`, `services/workspace/domains/workspace/router.py`, `services/workspace/domains/workspace/service.py`, `shared/models/workspace.py`
- Projects: `frontend/src/pages/Projects.tsx`, `services/workspace/domains/project/router.py`, `services/workspace/domains/project/service.py`, `shared/models/project.py`
- Tasks and reports: `frontend/src/pages/ProjectDetail.tsx`, `services/workspace/domains/task/router.py`, `services/workspace/domains/task/service.py`, `shared/models/task.py`
- Structured OPPM: `frontend/src/pages/ProjectDetail.tsx`, `services/workspace/domains/oppm/router.py`, `services/workspace/domains/oppm/service.py`, `shared/models/oppm.py`, `shared/models/task.py`
- OPPM spreadsheet and export: `frontend/src/pages/OPPMView.tsx`, `services/workspace/domains/oppm/router.py`, `services/workspace/domains/workspace/export_service.py`, `services/intelligence/domains/analysis/oppm_fill_router.py`, `services/intelligence/domains/analysis/oppm_fill_service.py`, `shared/models/oppm.py`
- AI chat and RAG: `frontend/src/components/ChatPanel.tsx`, `frontend/src/pages/Settings.tsx`, `services/intelligence/domains/chat/router.py`, `services/intelligence/domains/models/router.py`, `services/intelligence/domains/rag/router.py`, `services/intelligence/domains/chat/service.py`, `services/intelligence/domains/rag/service.py`, `services/intelligence/infrastructure/rag/`, `services/intelligence/infrastructure/tools/`, `services/intelligence/infrastructure/llm/`, `shared/models/ai_model.py`, `shared/models/embedding.py`
- GitHub and commits: `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Commits.tsx`, `frontend/src/pages/Dashboard.tsx`, `services/integrations/domains/github/router.py`, `services/integrations/domains/github/service.py`, `services/intelligence/domains/analysis/service.py`, `shared/models/git.py`
- Dashboard and notifications: `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/layout/Header.tsx`, `services/workspace/domains/dashboard/router.py`, `services/workspace/domains/dashboard/service.py`, `services/workspace/domains/notification/router.py`, `services/workspace/domains/notification/service.py`, `shared/models/notification.py`
- MCP tools: `services/automation/domains/registry/router.py`, `services/automation/domains/execution/`

## Source Basis For This File

This file was derived from the current repository documents and then verified against live code in:

- `README.md`
- `DEVELOPMENT.md`
- `docs/ARCHITECTURE.md`
- `docs/API-REFERENCE.md`
- `docs/frontend/FRONTEND-REFERENCE.md`
- `docs/MICROSERVICES-REFERENCE.md`
- `docs/services/README.md`
- `frontend/src/App.tsx`
- key frontend pages and components
- service entry points and route files in `services/`
- ORM model files in `shared/models/`
