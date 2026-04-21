# AI System Context

Last verified: 2026-04-10

## Purpose

This is the fastest high-signal reference for future AI-assisted updates.

Read this file first when you need to understand how the current system works, which files own each feature, and how the database is designed. It is meant to reduce broad codebase scanning, not replace code verification when a change affects behavior, contracts, or schema.

## How To Use This File

1. Read the current system snapshot.
2. Jump to the feature section you are changing.
3. Open only the listed source-of-truth files for that feature.
4. If the change affects data shape, also read the database design and schema hotspot sections.
5. If this file and the code disagree, treat the code as the final source of truth and update this file.

## Current System Snapshot

- Product: a workspace-scoped OPPM project management platform with AI assistance, GitHub analysis, and spreadsheet-style planning.
- Frontend: React 19 + Vite 8 + TypeScript 5.9 + Tailwind CSS v4 + TanStack Query + Zustand.
- Backend: FastAPI microservices split across `core`, `ai`, `git`, `mcp`, plus a Python gateway and an nginx gateway.
- Data model: one shared PostgreSQL database and one shared ORM layer in `shared/models/`.
- Auth: local HS256 JWT validation in `shared/auth.py`; refresh tokens persisted in the database.
- Tenancy: workspace model; most business routes are `/api/v1/workspaces/{workspace_id}/...`.
- AI stack: workspace chat, project chat, plan suggestion, weekly summary, OPPM fill, OCR-style OPPM extraction, RAG retrieval, and per-workspace model configuration.
- GitHub stack: GitHub accounts, repo configuration, webhook ingestion, commit storage, commit analysis, developer reports.
- Integration layer: HTTP-exposed MCP tools for project, task, objective, and commit summaries.

## Verified Drift To Keep In Mind

- `CLAUDE.md` still says the system has 23 tables; the canonical count is 29 tables across 7 domains.
- `docs/DATABASE-SCHEMA.md` documents 29 tables, which is consistent with the active ORM models.
- The project-member add payload uses the field name `user_id`, but the working value is a `workspace_members.id` that becomes `project_members.member_id`.
- Workspace responses currently expose `current_user_role`; some frontend code still falls back to `role`.
- The current frontend includes an `Invitations` page and sidebar entry in addition to the invite-accept flow.
- `shared/models/__init__.py` does not list every OPPM table class, but importing `shared.models.oppm` still registers them with SQLAlchemy metadata.

## Feature Reference

### 1. Authentication And Session Bootstrap

What it does:

- Email/password signup and login
- Access-token bootstrap on app load
- Refresh-token retry on `401`
- Signout and profile update

How it works:

1. `frontend/src/App.tsx` calls `authStore.initialize()`.
2. `frontend/src/stores/authStore.ts` reads `access_token` from local storage.
3. If the access token works, `GET /api/auth/me` returns the current user.
4. If the token is expired, `POST /api/auth/refresh` exchanges the refresh token for a new token pair.
5. `frontend/src/lib/api.ts` adds the bearer token to application requests and retries once on `401`.
6. `shared/auth.py` validates JWTs locally with `python-jose` and resolves the authenticated user.

Frontend files:

- `frontend/src/App.tsx`
- `frontend/src/stores/authStore.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/Login.tsx`

Backend files:

- `services/core/routers/auth.py`
- `services/core/routers/v1/auth.py`
- `services/core/services/auth_service.py`
- `shared/auth.py`
- `shared/models/user.py`

Primary tables:

- `users`
- `refresh_tokens`

Update notes:

- Keep JWT validation local unless you intentionally redesign auth across backend and frontend.
- `refresh_tokens` persists token hashes, not raw tokens.

### 2. Workspace Bootstrap, Tenancy, And Authorization

What it does:

- Workspace list and selection
- Workspace CRUD
- Workspace-scoped authorization and role checks

How it works:

1. After auth succeeds, `workspaceStore.fetchWorkspaces()` loads `/api/v1/workspaces`.
2. `frontend/src/stores/workspaceStore.ts` persists the selected workspace in local storage.
3. Most business API calls are built from `/v1/workspaces/{workspace_id}`.
4. `shared/auth.py` resolves `WorkspaceContext` by checking `workspace_members` for the current user and workspace.
5. Role gates are enforced with `get_workspace_context`, `require_write`, `require_admin`, and `require_owner`.

Frontend files:

- `frontend/src/stores/workspaceStore.ts`
- `frontend/src/hooks/useWorkspace.ts`
- `frontend/src/components/workspace/`

Backend files:

- `services/core/routers/v1/workspaces.py`
- `services/core/services/workspace_service.py`
- `shared/auth.py`
- `shared/models/workspace.py`

Primary tables:

- `workspaces`
- `workspace_members`

Update notes:

- `workspace_members.id` is the key membership identifier used by several downstream features.
- Authorization is enforced in the API layer, not with database RLS.

### 3. Team, Invites, And Member Skills

What it does:

- Member listing and role updates
- Invite creation, preview, acceptance, resend, revoke, decline
- Workspace-specific display names
- Member skill matrix

How it works:

1. `frontend/src/pages/Team.tsx` loads workspace members and skill lists.
2. `frontend/src/pages/Settings.tsx` includes workspace-member and invite-management panels.
3. `frontend/src/pages/AcceptInvite.tsx` uses the public preview route and then the authenticated accept route.
4. `frontend/src/pages/Invitations.tsx` loads pending invites for the current user and allows accept or decline.
5. Core workspace routes and services update member roles, invite state, and skills.

Frontend files:

- `frontend/src/pages/Team.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/pages/AcceptInvite.tsx`
- `frontend/src/pages/Invitations.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

Backend files:

- `services/core/routers/v1/workspaces.py`
- `services/core/services/workspace_service.py`
- `shared/models/workspace.py`

Primary tables:

- `workspace_members`
- `workspace_invites`
- `member_skills`

Update notes:

- Workspace display names are stored per membership, not on the user record.
- Invites are authenticated on accept, but preview is public by token.

### 4. Projects And Project Membership

What it does:

- Project list, create, update, delete
- Project metadata such as code, objective summary, budget, dates, and lead
- Project membership assignment

How it works:

1. `frontend/src/pages/Projects.tsx` loads workspace projects and workspace members.
2. On create, the page posts the project first and then best-effort posts selected member assignments.
3. `services/core/services/project_service.py` automatically adds the creator's workspace membership as the project `lead` member.
4. Project detail and OPPM routes use the project id as the feature anchor.

Frontend files:

- `frontend/src/pages/Projects.tsx`
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/OPPMView.tsx`

Backend files:

- `services/core/routers/v1/projects.py`
- `services/core/services/project_service.py`
- `shared/models/project.py`

Primary tables:

- `projects`
- `project_members`

Update notes:

- `projects.lead_id` points to `workspace_members.id`.
- The `user_id` field in the project-member add payload is a naming mismatch; the actual working value is a workspace member id.

### 5. Tasks, Hierarchy, Dependencies, And Daily Reports

What it does:

- Task CRUD within a project
- Main-task and sub-task hierarchy
- Weighted project progress recalculation
- Daily reports and approval flow
- Task dependencies

How it works:

1. `frontend/src/pages/ProjectDetail.tsx` loads tasks for the selected project.
2. The task tree is represented by `parent_task_id`: `NULL` means main task, non-null means sub-task.
3. `services/core/services/task_service.py` recalculates project progress after task changes.
4. Only the project lead can create tasks.
5. Only the assigned user can submit reports.
6. Only the project lead can approve reports.
7. Task dependencies are stored separately and reattached to task responses.

Frontend files:

- `frontend/src/pages/ProjectDetail.tsx`

Backend files:

- `services/core/routers/v1/tasks.py`
- `services/core/services/task_service.py`
- `shared/models/task.py`

Primary tables:

- `tasks`
- `task_reports`
- `task_dependencies`
- `task_assignees`

Update notes:

- The active product path uses `tasks.assignee_id` for single-assignee ownership.
- `task_assignees` remains in the schema but is not the active UI path.

### 6. Structured OPPM Planning Data

What it does:

- OPPM objective list
- Sub-objectives
- Task-to-sub-objective links
- A/B/C owner assignment
- Weekly timeline entries
- Costs, deliverables, forecasts, and risks

How it works:

1. Core OPPM routes under `services/core/routers/v1/oppm.py` expose the structured OPPM data model.
2. Objectives are project-scoped and ordered by `sort_order`.
3. Sub-objectives are a separate project-scoped list with positions `1..6`.
4. Tasks can be linked to multiple sub-objectives.
5. A/B/C ownership is stored in `task_owners` using workspace member ids.
6. Timeline rows link tasks to week starts and status/quality fields.
7. Costs, deliverables, forecasts, and risks are maintained as separate OPPM collections.

Frontend files:

- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/components/ChatPanel.tsx`

Backend files:

- `services/core/routers/v1/oppm.py`
- `services/core/services/oppm_service.py`
- `shared/models/oppm.py`
- `shared/models/task.py`

Primary tables:

- `oppm_objectives`
- `oppm_sub_objectives`
- `task_sub_objectives`
- `task_owners`
- `oppm_timeline_entries`
- `project_costs`
- `oppm_deliverables`
- `oppm_forecasts`
- `oppm_risks`

Update notes:

- This is the structured OPPM layer that the API and analytics use.
- It coexists with the spreadsheet layer described next.

### 7. OPPM Spreadsheet Template, Header, Task Items, Import, Export, And AI Fill

What it does:

- Spreadsheet-style OPPM editing in the UI
- Saved FortuneSheet JSON per project
- XLSX template import/export
- Per-project OPPM header fields
- OPPM task-numbering rows separate from general tasks
- AI-assisted spreadsheet fill
- OCR-style image extraction to OPPM JSON

How it works:

1. `frontend/src/pages/OPPMView.tsx` loads `/oppm/spreadsheet` for the current project.
2. If no saved spreadsheet exists, the frontend loads the bundled default XLSX template, converts it to FortuneSheet JSON, and saves it back to the backend.
3. Spreadsheet persistence is handled by `oppm_templates` through `PUT /oppm/spreadsheet`.
4. Additional free-text form data lives in `oppm_header`.
5. Numbered OPPM task rows live in `oppm_task_items`, which are distinct from the general `tasks` table.
6. `GET /oppm/export` renders a current XLSX export from structured data.
7. `POST /oppm/import`, `POST /oppm/preview-xlsx`, and `POST /oppm/import-json` handle spreadsheet and OCR import paths.
8. `POST /projects/{project_id}/ai/oppm-fill` returns suggested cell values derived from project data plus AI.
9. `POST /ai/oppm-extract` uses a vision model to produce structured JSON without saving it directly.

Frontend files:

- `frontend/src/pages/OPPMView.tsx`

Backend files:

- `services/core/routers/v1/oppm.py`
- `services/core/services/export_service.py`
- `services/ai/routers/v1/oppm_fill.py`
- `services/ai/routers/v1/ai.py`
- `services/ai/services/oppm_fill_service.py`
- `shared/models/oppm.py`

Primary tables:

- `oppm_templates`
- `oppm_header`
- `oppm_task_items`
- plus the structured OPPM tables above

Update notes:

- This is the highest-coupling area in the system.
- When changing OPPM behavior, check both the structured OPPM API and the spreadsheet/template path.

### 8. AI Assistant, Plan Suggestion, Weekly Summary, Reindex, RAG, And Model Configuration

What it does:

- Workspace chat with RAG plus workspace-scoped tool execution for write-capable members
- Project chat with agentic tool loop — up to 7 LLM iterations, executing registry tools to read or write project data
- Input guardrails (injection detection, length limit) and output guardrails (sensitive data scrub)
- LLM-based query rewriting before retrieval for better recall
- Semantic cache (Redis, cosine ≥ 0.92, TTL 300 s) to skip re-retrieval on repeated questions
- Tool registry with 24 tools across five categories: oppm (5), task (5), cost (5), read (6), project (3)
- Native LLM function calling for OpenAI and Anthropic; XML-prompt-based tool execution for Ollama and Kimi
- Suggested project plans (generate + commit)
- Weekly project summaries
- OPPM fill assistance
- Server-side file parsing and OPPM image extraction
- Workspace reindexing for retrieval
- RAG query endpoint
- Per-workspace AI model configuration
- User feedback (thumbs up/down) logged to `audit_log`

How it works:

1. `frontend/src/components/ChatPanel.tsx` opens in workspace or project context.
2. Workspace chat posts to `/ai/chat`:
   - The route now requires write access because the implementation can execute tools.
   - RAG context and memory are loaded across the workspace.
   - The full tool registry is exposed so the assistant can create or update workspace/project data, including creating a project before adding objectives or tasks.
3. Project chat posts to `/projects/{project_id}/ai/chat`:
   - Input guardrail checks message for injection patterns and length.
   - Query rewriting expands vague queries into richer search terms (skipped for queries > 300 chars or ≤ 2 words).
   - RAG pipeline: semantic cache lookup → classify → parallel vector + keyword + structured retrieval → RRF rerank → project boost → cache store.
   - Full project context (objectives, tasks, risks, costs, team, commits) is loaded using tiered windowing.
   - Agentic tool loop runs up to 7 iterations: LLM call → parse tool calls → execute via registry → inject results as next user turn → optionally requery on low confidence → repeat until confident answer or max iterations.
   - Output guardrail scrubs sensitive patterns before the response is returned.
   - Response includes `message`, `tool_calls`, `updated_entities`, `iterations`, and `low_confidence`.
4. Users can submit feedback via `POST /projects/{id}/ai/feedback` or `POST /workspaces/{ws}/ai/feedback`.
5. Project quick actions call `suggest-plan`, `suggest-plan/commit`, `weekly-summary`, and `oppm-fill`.
6. File and image helpers call `parse-file` and `oppm-extract` on the AI service.
7. Admins manage `ai_models` from `frontend/src/pages/Settings.tsx`.
8. `POST /ai/reindex` rebuilds retrieval data for the workspace.
9. `POST /rag/query` runs the RAG pipeline against workspace data and memory context.

Frontend files:

- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/pages/Settings.tsx`

Backend files:

- `services/ai/routers/v1/ai_chat.py`
- `services/ai/routers/v1/ai.py`
- `services/ai/routers/v1/rag.py`
- `services/ai/services/ai_chat_service.py`
- `services/ai/services/rag_service.py`
- `services/ai/services/document_indexer.py`
- `services/ai/infrastructure/rag/agent_loop.py`
- `services/ai/infrastructure/rag/query_rewriter.py`
- `services/ai/infrastructure/rag/guardrails.py`
- `services/ai/infrastructure/rag/semantic_cache.py`
- `services/ai/infrastructure/tools/registry.py`
- `services/ai/infrastructure/tools/oppm_tools.py`
- `services/ai/infrastructure/tools/task_tools.py`
- `services/ai/infrastructure/tools/cost_tools.py`
- `services/ai/infrastructure/tools/read_tools.py`
- `services/ai/infrastructure/tools/project_tools.py`
- `services/ai/infrastructure/llm/tool_parser.py`
- `services/ai/infrastructure/file_parser.py`
- `shared/models/ai_model.py`
- `shared/models/embedding.py`

Primary tables:

- `ai_models`
- `document_embeddings`
- `audit_log` — feedback and memory context

Update notes:

- AI model configuration is workspace-scoped.
- RAG and chat behavior depend on indexed workspace data, not just live tables.
- `GET /ai/chat/capabilities` now reflects write-capable tool access via `can_execute_tools` based on the caller's workspace role.
- See [AI-PIPELINE-REFERENCE.md](ai/AI-PIPELINE-REFERENCE.md) for the full pipeline step sequence.
- See [TOOL-REGISTRY-REFERENCE.md](ai/TOOL-REGISTRY-REFERENCE.md) for the tool registry and all 24 tools.
- Feedback is written to `audit_log` with `action = "ai_feedback"` and `metadata` containing rating, comment, and related message content.

### 9. GitHub Integration, Commits, And Commit Analysis

What it does:

- GitHub account registration
- Repo configuration per project
- Webhook ingestion
- Commit storage
- AI commit analysis
- Recent analysis feed and developer reports

How it works:

1. `frontend/src/pages/Settings.tsx` manages GitHub accounts and repo configs.
2. `frontend/src/pages/Commits.tsx` loads commits and attached AI analysis.
3. GitHub sends push events to `POST /api/v1/git/webhook`.
4. The git service looks up an active repo config by `repository.full_name`.
5. It validates `X-Hub-Signature-256` using the stored webhook secret.
6. It stores commit events and triggers background AI analysis.
7. The AI service writes analysis results that are shown in the commits feed and dashboard.

Frontend files:

- `frontend/src/pages/Settings.tsx`
- `frontend/src/pages/Commits.tsx`
- `frontend/src/pages/Dashboard.tsx`

Backend files:

- `services/git/routers/v1/git.py`
- `services/git/services/git_service.py`
- `services/ai/routers/internal.py`
- `services/ai/services/ai_analyzer.py`
- `shared/models/git.py`

Primary tables:

- `github_accounts`
- `repo_configs`
- `commit_events`
- `commit_analyses`

Update notes:

- Never expose `encrypted_token` or `webhook_secret` in responses.
- Webhook routing and HMAC verification must remain aligned across the git service and deployment gateway.

### 10. Dashboard And Notifications

What it does:

- Workspace dashboard stats
- Recent AI commit analysis on the dashboard
- User notifications in the header dropdown

How it works:

1. `frontend/src/pages/Dashboard.tsx` loads workspace stats from `/dashboard/stats`.
2. The dashboard service aggregates projects, tasks, repos, commits, and recent analyses.
3. `frontend/src/components/layout/Header.tsx` loads `/v1/notifications` and `/v1/notifications/unread-count`.
4. Header actions mark individual notifications read, mark all read, or delete notifications.

Frontend files:

- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/layout/Header.tsx`

Backend files:

- `services/core/routers/v1/dashboard.py`
- `services/core/services/dashboard_service.py`
- `services/core/routers/v1/notifications.py`
- `services/core/services/notification_service.py`
- `shared/models/notification.py`

Primary tables:

- `notifications`
- `audit_log`
- plus projects, tasks, repo configs, commits, and analyses for dashboard aggregation

Update notes:

- Notifications are user-scoped routes, not workspace-scoped routes.

### 11. MCP Tools

What it does:

- Lists AI-consumable MCP tools
- Executes workspace-scoped MCP tool calls over HTTP

How it works:

1. `services/mcp/routers/v1/mcp.py` lists and executes tools.
2. The router injects the current `workspace_id` into every tool call.
3. Tool implementations live in `services/mcp/infrastructure/mcp/tools/`.
4. The current registry exposes:
   - `get_project_status`
   - `list_projects`
   - `list_at_risk_objectives`
   - `get_task_summary`
   - `summarize_recent_commits`

Backend files:

- `services/mcp/routers/v1/mcp.py`
- `services/mcp/infrastructure/mcp/tools/__init__.py`
- `services/mcp/infrastructure/mcp/tools/project_tools.py`
- `services/mcp/infrastructure/mcp/tools/objective_tools.py`
- `services/mcp/infrastructure/mcp/tools/task_tools.py`
- `services/mcp/infrastructure/mcp/tools/commit_tools.py`

Update notes:

- MCP tools are externally callable summaries over existing data, not a second source of truth.

### 12. Tool Registry And Agentic Loop

What it does:

- Registers all AI-callable tools with metadata, parameter schemas, and async handlers
- Exposes tools to LLMs via native function-calling APIs (OpenAI, Anthropic) or via XML-prompt injection (Ollama, Kimi)
- Runs a multi-turn agentic loop so the LLM can chain tool calls before returning a final answer

How it works:

1. `services/ai/infrastructure/tools/registry.py` owns the global `ToolRegistry` singleton.
2. On first call to `get_registry()`, all five tool modules are auto-imported and their tools are registered.
3. For OpenAI and Anthropic, `to_openai_schema()` and `to_anthropic_schema()` serialize the registry to native tool descriptors.
4. For Ollama and Kimi, `to_prompt_text()` converts the registry into a prompt-text tool section that instructs the model to emit `<tool_calls>...</tool_calls>` JSON.
5. `services/ai/infrastructure/rag/agent_loop.py` runs the loop:
   - Calls the LLM with the current message history and tool schemas.
   - Parses `tool_calls` from the response (native JSON for OpenAI/Anthropic, JSON inside `<tool_calls>` tags for others).
   - Executes each requested tool via `registry.execute()`.
   - Injects the text results as a new user turn.
   - Deduplicates identical tool retries and can trigger an extra RAG requery when confidence is low.
   - Repeats up to 7 times or until the response contains a confident answer with no tool calls.
   - If the max is hit, makes a final summary call without tools.
6. `AgentLoopResult` carries `final_text`, `all_tool_results`, `updated_entities`, `iterations`, and `low_confidence`.

Tool categories:

| Category | Count | Key tools |
|---|---|---|
| `oppm` | 5 | `create_objective`, `update_objective`, `delete_objective`, `set_timeline_status`, `bulk_set_timeline` |
| `task` | 5 | `create_task`, `update_task`, `delete_task`, `assign_task`, `set_task_dependency` |
| `cost` | 5 | `update_project_costs`, `create_risk`, `update_risk`, `create_deliverable`, `update_project_metadata` |
| `read` | 6 | `get_project_summary`, `get_task_details`, `search_tasks`, `get_risk_status`, `get_cost_breakdown`, `get_team_workload` |
| `project` | 3 | `create_project`, `list_workspace_projects`, `update_project` |

Backend files:

- `services/ai/infrastructure/tools/__init__.py`
- `services/ai/infrastructure/tools/base.py`
- `services/ai/infrastructure/tools/registry.py`
- `services/ai/infrastructure/tools/oppm_tools.py`
- `services/ai/infrastructure/tools/task_tools.py`
- `services/ai/infrastructure/tools/cost_tools.py`
- `services/ai/infrastructure/tools/read_tools.py`
- `services/ai/infrastructure/tools/project_tools.py`
- `services/ai/infrastructure/rag/agent_loop.py`
- `services/ai/infrastructure/llm/tool_parser.py`
- `services/ai/infrastructure/llm/__init__.py`

Update notes:

- To add a new tool, add its `ToolDefinition` to the appropriate module and the registry will pick it up automatically on next import.
- `NATIVE_TOOL_PROVIDERS = {"openai", "anthropic"}` controls which providers use native calling.
- Tool results are always injected as plain-text user messages to stay provider-agnostic.
- See [TOOL-REGISTRY-REFERENCE.md](ai/TOOL-REGISTRY-REFERENCE.md) for full tool parameter schemas and handler contracts.

## Database Schema Design

## Design Principles

- All services share one PostgreSQL database through `shared/database.py` and `shared/models/`.
- Alembic migrations live in `services/core/alembic/`.
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
2. Add or update the Alembic migration in `services/core/alembic/versions/`.
3. Update repositories, services, schemas, and route handlers that read or write the field.
4. Update this file and `docs/DATABASE-SCHEMA.md` if the public understanding of the schema changed.
5. Re-check any frontend type definitions if the API contract changed.

## Fast File Map For Future Updates

- Auth and session: `frontend/src/stores/authStore.ts`, `frontend/src/lib/api.ts`, `services/core/routers/auth.py`, `services/core/services/auth_service.py`, `shared/auth.py`, `shared/models/user.py`
- Workspaces, members, invites: `frontend/src/pages/Team.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/AcceptInvite.tsx`, `frontend/src/pages/Invitations.tsx`, `services/core/routers/v1/workspaces.py`, `services/core/services/workspace_service.py`, `shared/models/workspace.py`
- Projects: `frontend/src/pages/Projects.tsx`, `services/core/routers/v1/projects.py`, `services/core/services/project_service.py`, `shared/models/project.py`
- Tasks and reports: `frontend/src/pages/ProjectDetail.tsx`, `services/core/routers/v1/tasks.py`, `services/core/services/task_service.py`, `shared/models/task.py`
- Structured OPPM: `frontend/src/pages/ProjectDetail.tsx`, `services/core/routers/v1/oppm.py`, `services/core/services/oppm_service.py`, `shared/models/oppm.py`, `shared/models/task.py`
- OPPM spreadsheet and export: `frontend/src/pages/OPPMView.tsx`, `services/core/routers/v1/oppm.py`, `services/core/services/export_service.py`, `services/ai/routers/v1/oppm_fill.py`, `services/ai/services/oppm_fill_service.py`, `shared/models/oppm.py`
- AI chat and RAG: `frontend/src/components/ChatPanel.tsx`, `frontend/src/pages/Settings.tsx`, `services/ai/routers/v1/ai_chat.py`, `services/ai/routers/v1/ai.py`, `services/ai/routers/v1/rag.py`, `services/ai/services/ai_chat_service.py`, `services/ai/services/rag_service.py`, `services/ai/infrastructure/rag/`, `services/ai/infrastructure/tools/`, `services/ai/infrastructure/llm/`, `shared/models/ai_model.py`, `shared/models/embedding.py`
- GitHub and commits: `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Commits.tsx`, `frontend/src/pages/Dashboard.tsx`, `services/git/routers/v1/git.py`, `services/git/services/git_service.py`, `services/ai/services/ai_analyzer.py`, `shared/models/git.py`
- Dashboard and notifications: `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/layout/Header.tsx`, `services/core/routers/v1/dashboard.py`, `services/core/services/dashboard_service.py`, `services/core/routers/v1/notifications.py`, `services/core/services/notification_service.py`, `shared/models/notification.py`
- MCP tools: `services/mcp/routers/v1/mcp.py`, `services/mcp/infrastructure/mcp/tools/`

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
