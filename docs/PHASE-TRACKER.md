# OPPM Implementation — Phase Tracker

> Last updated: 2026-04-03

---

## Phase 1 — Make OPPM Grid Editable ✅ COMPLETE

**Goal:** Transform the read-only OPPM view into a fully interactive editor matching the classic OPPM layout.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 1.1 | Fix backend `TimelineEntryUpsert` schema (year/month → week_start) | ✅ | `backend/schemas/oppm.py`, `backend/routers/v1/oppm.py` |
| 1.2 | Fix frontend `OPPMTimelineEntry` type to match DB | ✅ | `frontend/src/types/index.ts` |
| 1.3 | Rewrite OPPMView with clickable StatusDots | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.4 | Inline editing for objective titles + owners | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.5 | Add/delete objectives inline | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.6 | Render timeline entries from API (not computed from tasks) | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.7 | Cost section (CRUD) | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.8 | Deliverables / Forecast / Risk (already working) | ✅ | — |
| 1.9 | Week navigation + current week highlight | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 1.10 | Progress calculation from timeline statuses | ✅ | `frontend/src/pages/OPPMView.tsx` |

### Bug Fixes Applied
- **Backend `TimelineEntryUpsert`**: Was using `year: int` + `month: int`; DB has `week_start DATE`. Changed to `week_start: str` + correct status enum (`planned|in_progress|completed|at_risk|blocked`).
- **Backend OPPM router**: `upsert_timeline_route` was passing year/month payload; now passes week_start correctly.
- **Frontend `OPPMTimelineEntry` type**: Changed from `year/month` to `week_start: string` + correct status union type.

### Architecture Decisions
- **Timeline dots are driven by `oppm_timeline_entries` table**, not computed from tasks. Clicking a dot cycles: empty → planned → in_progress → completed → at_risk → blocked → empty.
- **Objectives are editable inline** — click title to edit, blur/enter to save via `PUT /v1/.../oppm/objectives/{id}`.
- **Objective creation** is a "+ Add objective" row at the bottom of the grid.
- **Objective deletion** via trash icon with confirmation.
- **Cost section** renders below the timeline grid with add/edit/delete.
- **Progress** is auto-calculated: completed cells / total cells per objective.

### API Endpoints Used
```
GET    /v1/workspaces/{ws}/projects/{pid}/oppm/objectives   → objectives with tasks
POST   /v1/workspaces/{ws}/projects/{pid}/oppm/objectives   → create objective
PUT    /v1/workspaces/{ws}/oppm/objectives/{oid}            → update objective
DELETE /v1/workspaces/{ws}/oppm/objectives/{oid}            → delete objective
GET    /v1/workspaces/{ws}/projects/{pid}/oppm/timeline     → all timeline entries
PUT    /v1/workspaces/{ws}/projects/{pid}/oppm/timeline     → upsert single entry
GET    /v1/workspaces/{ws}/projects/{pid}/oppm/costs        → cost summary
POST   /v1/workspaces/{ws}/projects/{pid}/oppm/costs        → create cost
PUT    /v1/workspaces/{ws}/oppm/costs/{cid}                 → update cost
DELETE /v1/workspaces/{ws}/oppm/costs/{cid}                 → delete cost
PUT    /v1/workspaces/{ws}/projects/{pid}                   → update project metadata
```

### Key Frontend Components (in OPPMView.tsx)
- `StatusDot` — clickable circle that cycles status, calls timeline upsert
- `EditableField` — click-to-edit text, saves on blur/enter
- `EditableList` — numbered list editor for deliverables/forecast/risk
- `VerticalLabel` — rotated text cell for bottom section row labels
- `CostSection` — cost table with add/edit/delete rows

---

## Phase 2 — AI Chat Panel ✅ COMPLETE

**Goal:** Add a floating AI chat panel to the OPPM page that can read project context and make OPPM changes via tool calls.

### Summary of Changes
| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 2.1 | Create `backend/schemas/ai_chat.py` | ✅ | `backend/schemas/ai_chat.py` |
| 2.2 | Create `backend/services/ai_chat_service.py` | ✅ | `backend/services/ai_chat_service.py` |
| 2.3 | Create `backend/services/oppm_tool_executor.py` | ✅ | `backend/services/oppm_tool_executor.py` |
| 2.4 | Create `backend/routers/v1/ai_chat.py` — all endpoints | ✅ | `backend/routers/v1/ai_chat.py` |
| 2.5 | Register AI chat router in v1 init | ✅ | `backend/routers/v1/__init__.py` |
| 2.6 | Create `ChatPanel` React component | ✅ | `frontend/src/components/ChatPanel.tsx` |
| 2.7 | Wire ChatPanel into OPPMView with toggle | ✅ | `frontend/src/pages/OPPMView.tsx` |

### Architecture Decisions
- **Tool calls via XML tags**: LLM returns `<tool_calls>[...]</tool_calls>` JSON blocks. Parsed by regex in `_parse_tool_calls()`.
- **Tool executor pattern**: `oppm_tool_executor.execute_tool()` dispatches tool calls to repository methods via `match/case`.
- **Query invalidation**: ChatPanel tracks `updated_entities` from AI response and invalidates matching React Query keys (e.g., `oppm_objectives` → `oppm-objectives`).
- **Suggest Plan flow**: Two-step — `suggest-plan` returns preview + `commit_token`, `commit` applies the plan.
- **In-memory plan cache**: `_plan_cache` dict stores pending plans. Production would use Redis/DB.

### API Endpoints
```
POST   /v1/workspaces/{ws}/projects/{pid}/ai/chat              → chat with AI
POST   /v1/workspaces/{ws}/projects/{pid}/ai/suggest-plan       → AI plan generation
POST   /v1/workspaces/{ws}/projects/{pid}/ai/suggest-plan/commit → apply suggested plan
GET    /v1/workspaces/{ws}/projects/{pid}/ai/weekly-summary     → AI weekly summary
```

---

## Phase 3 — Task Management Page ✅ COMPLETE

**Goal:** Full task CRUD under each project with create/assign/status transitions.

### Summary of Changes
| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 3.1 | Fix `backend/routers/v1/tasks.py` to match service signatures | ✅ | `backend/routers/v1/tasks.py` |
| 3.2 | Task creation modal (TaskForm component) | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 3.3 | Task edit panel (reuses TaskForm) | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 3.4 | Task status transitions (click chevron to advance) | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 3.5 | Task deletion with confirmation | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 3.6 | TaskCard component with priority badges | ✅ | `frontend/src/pages/ProjectDetail.tsx` |

### Bug Fixes
- **Router-Service signature mismatch**: Router was calling `list_tasks(ws.workspace_id, project_id, ...)` but service expects `list_tasks(project_id=..., status=..., limit=..., offset=...)`. Fixed all 5 route handlers to use correct keyword arguments and pass `user_id` from `ws.user.id`.

### Architecture Decisions
- **TaskCard**: Inline status advancement via chevron button (todo → in_progress → completed → todo).
- **TaskForm**: Shared form component for both create and edit, with modal overlay.
- **Query invalidation**: Both `tasks` and `project` queries invalidated on mutations to update progress.
- **Empty state**: Dashed border placeholder when a status column has no tasks.

---

## Phase 4 — Settings Display Name Fix ✅ COMPLETE

**Goal:** Show real display names instead of UUID fragments everywhere.

### Summary of Changes
| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 4.1 | Add `update_my_display_name` service function | ✅ | `backend/services/workspace_service.py` |
| 4.2 | Add `DisplayNameUpdate` schema | ✅ | `backend/schemas/workspace.py` |
| 4.3 | Add `PATCH /members/me/display-name` endpoint | ✅ | `backend/routers/v1/workspaces.py` |
| 4.4 | Update ProfileSettings to also write workspace_members.display_name | ✅ | `frontend/src/pages/Settings.tsx` |

### Architecture Decisions
- **Dual write**: Profile save writes to both `users.full_name` AND `workspace_members.display_name` via PATCH endpoint.
- **Endpoint design**: `PATCH /workspaces/{ws}/members/me/display-name` — any workspace member can update their own name (no admin check needed).
- **Backend**: `update_my_display_name()` looks up the member record by `user_id + workspace_id`, then updates `display_name` field.

---

## Phase 5 — AI Models UI Redesign + Bug Fixes ✅ COMPLETE

**Goal:** Replace the flat "Add Model" form with a tabbed preset catalog and fix 500 errors on `/ai/models`.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 5.1 | Redesign `AIModelSettings` with tabbed preset catalog | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.2 | Add Ollama Local tab (6 preset models) | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.3 | Add Ollama Cloud tab (8 cloud models incl. kimi-k2.5:cloud) | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.4 | Add OpenAI tab (4 models) and Anthropic tab (3 models) | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.5 | Fix 500 error: provider `'ollama-cloud'` violated DB CHECK constraint | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.6 | Fix duplicate React key warning in preset tabs | ✅ | `frontend/src/pages/Settings.tsx` |
| 5.7 | Add `ALLOWED_PROVIDERS` validation + try/except logging to backend | ✅ | `backend/routers/v1/ai.py` |

### Bug Fixes Applied
- **500 on GET `/ai/models`**: Uncaught DB exception when table is empty. Wrapped in try/except with logger warning.
- **500 on POST `/ai/models` (ollama-cloud)**: Frontend was sending `provider: 'ollama-cloud'` which violated the DB CHECK constraint `('ollama','anthropic','openai','kimi','custom')`. Fixed by using `provider: 'ollama'` for all Ollama-based presets and using unique `id` fields per tab instead.
- **Duplicate React key**: Both Ollama Local and Ollama Cloud tabs used `provider` as the key — now use unique `id` fields (`'ollama-local'`, `'ollama-cloud'`).

### Architecture Decisions
- **`AI_MODEL_PRESETS`** array with `id`, `provider`, `icon`, `label`, `cloudNote?`, `models[]`. Tab keys use `p.id`.
- **`OLLAMA_CLOUD_ENDPOINT`** constant (`https://ollama.com/api`) used for all cloud Ollama models.
- **Backend `ALLOWED_PROVIDERS`** set mirrors DB CHECK constraint — returns 400 (not 500) for unknown providers.
- **Kimi cloud models** routed via the Ollama Cloud tab (Kimi API is Ollama-compatible).

---

## Phase 6 — RAG System + LLM Fallback Chain ✅ COMPLETE

**Goal:** Build a full Retrieval-Augmented Generation pipeline with multi-retriever hybrid search, LLM provider fallback, MCP tool execution, and context-aware AI chat.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 6.1 | LLM fallback chain: `ProviderUnavailableError` + `call_with_fallback()` | ✅ | `backend/infrastructure/llm/base.py`, `ollama.py`, `anthropic.py`, `openai.py`, `kimi.py`, `__init__.py` |
| 6.2 | Update `ai_chat_service.py` + `ai_analyzer.py` to use fallback | ✅ | `backend/services/ai_chat_service.py`, `backend/services/ai_analyzer.py` |
| 6.3 | Deploy `match_documents` pgvector function to PostgreSQL | ✅ | `supabase/schema.sql`, Alembic migration |
| 6.4 | Create RAG infrastructure package | ✅ | `backend/infrastructure/rag/` (7 files) |
| 6.5 | Create MCP tools package | ✅ | `backend/infrastructure/mcp/` (5 files) |
| 6.6 | Rewrite `rag_service.py` with full 4-stage pipeline | ✅ | `backend/services/rag_service.py` |
| 6.7 | Add RAG query endpoint + schemas | ✅ | `backend/routers/v1/rag.py`, `backend/schemas/rag.py` |
| 6.8 | Add MCP tools + call endpoints | ✅ | `backend/routers/v1/mcp.py` |
| 6.9 | Add RAG config vars | ✅ | `backend/config.py` |
| 6.10 | Register rag + mcp routers | ✅ | `backend/routers/v1/__init__.py` |

### LLM Fallback Chain

- **`ProviderUnavailableError(provider, reason)`** — new exception in `base.py`, raised by all adapters on connect/timeout/5xx errors.
- **`call_with_fallback(models, prompt, *, json_mode)`** in `llm/__init__.py` — iterates models list, skips unavailable providers, raises only if all fail.
- **All 4 adapters** (Ollama, Anthropic, OpenAI, Kimi) catch `httpx.ConnectError`, `httpx.TimeoutException`, and `httpx.HTTPStatusError` (404/502/503/529) → raise `ProviderUnavailableError`.
- **`ai_chat_service`** and **`ai_analyzer`** now use `call_with_fallback` at every LLM call site.

### RAG Pipeline (4 Stages)

```
Query → Classify → Retrieve (parallel) → Rerank (RRF) → Return chunks
```

1. **Query Classifier** (`infrastructure/rag/agent.py`): Pattern-based routing to select retriever combination.
   - objective/goal → vector + keyword
   - task/todo → vector + keyword
   - commit/push → vector only
   - cost/budget → structured only
   - status/progress → vector + structured
   - team/member → structured + vector
   - timeline → vector + structured
   - default → all three

2. **Retrievers** (`infrastructure/rag/retrievers/`):
   - `VectorRetriever` — pgvector cosine similarity via `match_documents` RPC
   - `KeywordRetriever` — ILIKE on `tasks` + `oppm_objectives` tables
   - `StructuredRetriever` — direct DB queries for projects and `project_costs`

3. **Reranker** (`infrastructure/rag/reranker.py`): Reciprocal Rank Fusion (RRF, k=60) merges ranked lists from multiple retrievers.

4. **Memory Loader** (`infrastructure/rag/memory.py`): Injects last 20 `ai_chat` events from `audit_log` as conversation context.

### MCP Tool Registry

5 tools registered in `infrastructure/mcp/tools/`:
- `get_project_status` — project details + task counts by status
- `list_projects` — all workspace projects
- `list_at_risk_objectives` — objectives with `at_risk` or `blocked` timeline entries
- `get_task_summary` — task counts grouped by status
- `summarize_recent_commits` — commit summaries from last N days

### New Database Object
```sql
-- Deployed via Alembic migration: recreate_match_documents_rpc
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding VECTOR(1536),
  match_count INT,
  filter_workspace_id UUID
)
RETURNS TABLE (id UUID, content TEXT, metadata JSONB, similarity FLOAT)
```
Uses `document_embeddings` table (workspace_id, entity_type, entity_id, content, metadata, embedding vector(1536)).

### API Endpoints Added
```
POST   /v1/workspaces/{ws}/rag/query           → RAG retrieval pipeline
GET    /v1/workspaces/{ws}/mcp/tools           → list available MCP tools
POST   /v1/workspaces/{ws}/mcp/call            → execute an MCP tool by name
```

### Architecture Decisions
- **Service layer unchanged externally** — `rag_service.retrieve_with_rag_pipeline()` is additive; legacy `retrieve_context()` / `retrieve_for_workspace()` preserved.
- **Embeddings** use OpenAI `text-embedding-3-small` (1536 dims); falling back to no-op if no API key.
- **MCP tools** are pure functions that accept a `workspace_id` kwarg injected by the router.
- **`document_embeddings` table** is separate from `commit_analyses` — general purpose vector store for any entity type.
- **Config vars added**: `embedding_provider`, `embedding_model`, `embedding_dimension`, `rag_max_context_chars`, `rag_memory_limit`.

---

## Phase 7 — Microservices Migration ✅ COMPLETE

**Goal:** Break the FastAPI monolith into 4 focused microservices behind an nginx reverse proxy for independent scaling, deployment, and development.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 7.1 | Split monolith into 4 services (core/ai/git/mcp) | ✅ | `services/core/`, `services/ai/`, `services/git/`, `services/mcp/` |
| 7.2 | Create `shared/` package for common auth/db/config | ✅ | `shared/auth.py`, `shared/database.py`, `shared/config.py` |
| 7.3 | nginx gateway with dynamic DNS resolver | ✅ | `gateway/nginx.conf` |
| 7.4 | Docker Compose production + dev overlay | ✅ | `docker-compose.microservices.yml`, `docker-compose.dev.yml` |
| 7.5 | Fix nginx 502: static upstream → variable + resolver | ✅ | `gateway/nginx.conf` |
| 7.6 | Remove duplicate CORS middleware from service containers | ✅ | `services/ai/main.py`, `services/git/main.py`, `services/mcp/main.py` |
| 7.7 | Fix GitHub webhook HMAC (make required, not optional) | ✅ | `services/git/routers/v1/git.py` |
| 7.8 | Internal service auth (`X-Internal-API-Key`) | ✅ | `shared/auth.py`, `services/ai/routers/internal/` |
| 7.9 | Create `MICROSERVICES.md` operational guide | ✅ | `MICROSERVICES.md` |
| 7.10 | Create `DEVELOPMENT.md` with native run instructions | ✅ | `DEVELOPMENT.md` |
| 7.11 | Fix `shared/pyproject.toml` for Python 3.11 | ✅ | `shared/pyproject.toml` |

### Architecture

```
Client → nginx:80 (gateway) → core:8000   (workspaces, projects, tasks, OPPM, dashboard)
                             → ai:8001     (LLM chat, RAG, AI analysis, AI models)
                             → git:8002    (GitHub webhooks, commits, repo configs)
                             → mcp:8003    (MCP tool registry + execution)
```

### Key Decisions
- **Shared package**: `pip install -e shared/` in editable mode. Docker uses `ENV PYTHONPATH=/`. Natively: `PYTHONPATH=$(workspace root)` + `uvicorn --app-dir services/<name>`.
- **nginx DNS**: `resolver 127.0.0.11 valid=5s; set $upstream_core http://core:8000; proxy_pass $upstream_core` — re-queries Docker DNS on every request, prevents stale IPs on container restarts.
- **CORS**: Handled exclusively by nginx `add_header Access-Control-Allow-Origin`; services have no `CORSMiddleware`.
- **Internal API**: Git service calls AI service fire-and-forget via `asyncio.create_task(trigger_ai_analysis(...))` to avoid blocking GitHub webhook timeout.

---

## Phase 8 — Production Invite Flow ✅ COMPLETE

**Goal:** Replace the basic invite link with a production-grade flow supporting live email lookup, user-type detection, workspace preview, and invite resend.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 8.1 | DB migration: `lookup_user_by_email` helper (queries users table) | ✅ | Alembic migration `invite_flow_helpers` |
| 8.2 | DB migration: `get_invite_preview` function (public, returns workspace preview) | ✅ | Alembic migration `invite_flow_helpers` |
| 8.3 | DB migration: add `is_new_user BOOLEAN` + `sent_at TIMESTAMPTZ` to `workspace_invites` | ✅ | Alembic migration `invite_flow_helpers` |
| 8.4 | Backend: `lookup_user_by_email` service + endpoint | ✅ | `services/core/services/workspace_service.py`, `routers/v1/workspaces.py` |
| 8.5 | Backend: `get_invite_preview` service + endpoint (public, no auth) | ✅ | `services/core/services/workspace_service.py`, `routers/v1/workspaces.py` |
| 8.6 | Backend: `resend_invite` service + endpoint | ✅ | `services/core/services/workspace_service.py`, `routers/v1/workspaces.py` |
| 8.7 | Backend: update `create_invite` to set `is_new_user` + `sent_at` | ✅ | `services/core/services/workspace_service.py` |
| 8.8 | Frontend: `Settings.tsx` — `MembersSettings` full redesign | ✅ | `frontend/src/pages/Settings.tsx` |
| 8.9 | Frontend: `AcceptInvite.tsx` — workspace preview before accepting | ✅ | `frontend/src/pages/AcceptInvite.tsx` |
| 8.10 | Frontend: `Login.tsx` — invite token handling + auto-accept after sign-in | ✅ | `frontend/src/pages/Login.tsx` |

### New API Endpoints

```
GET  /v1/workspaces/{id}/members/lookup?email=  → admin: email lookup (exists, already_member)
GET  /v1/invites/preview/{token}                → public: workspace preview (no auth required)
POST /v1/workspaces/{id}/invites/{invite_id}/resend → admin: regenerate token + resend email
```

### Key UX Changes
- **Settings Members tab**: live debounced email lookup (500ms), color-coded banners (green = has account, amber = new user, red = already member), role picker cards with descriptions + "recommended" badge, dynamic CTA ("Send Sign-Up Invite" vs "Send Invite"), pending invites with `is_new_user`/`is_existing` badges + expiry countdown + **Resend** button.
- **AcceptInvite page**: fetches public workspace preview first — shows name, member count, role, inviter, expiry. Handles expired/accepted/not-found states. Unauthenticated users see "Sign In to Join" → preserves token in query param.
- **Login page**: reads `?invite=token`, shows invite context banner, auto-accepts then navigates after sign-in.

---

## Phase 9 — Dashboard UX Overhaul + Loading Skeletons ✅ COMPLETE

**Goal:** Replace the static fake chart and spinner with real data visualisation and smooth skeleton loading states across the Dashboard.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 9.1 | Backend: add `project_progress` to `DashboardStats` schema | ✅ | `services/core/schemas/dashboard.py` |
| 9.2 | Backend: populate `project_progress` from projects list (no extra DB call) | ✅ | `services/core/services/dashboard_service.py` |
| 9.3 | Frontend: create shared `Skeleton` component | ✅ | `frontend/src/components/Skeleton.tsx` |
| 9.4 | Frontend: add `ProjectProgress` type + update `DashboardStats` | ✅ | `frontend/src/types/index.ts` |
| 9.5 | Frontend: replace fake `AreaChart` with live `BarChart` per project | ✅ | `frontend/src/pages/Dashboard.tsx` |
| 9.6 | Frontend: stat cards with `border-l-4` color accent | ✅ | `frontend/src/pages/Dashboard.tsx` |
| 9.7 | Frontend: skeleton layout for loading state (cards, chart, analysis list) | ✅ | `frontend/src/pages/Dashboard.tsx` |
| 9.8 | Frontend: score pills with semantic background colors | ✅ | `frontend/src/pages/Dashboard.tsx` |
| 9.9 | Frontend: project progress list section with inline progress bars | ✅ | `frontend/src/pages/Dashboard.tsx` |
| 9.10 | Frontend: empty states with icons for chart + analyses panels | ✅ | `frontend/src/pages/Dashboard.tsx` |

### Architecture Decisions
- **Skeleton component**: generic `<Skeleton className="">` using `animate-pulse bg-slate-200`. Each loading section renders a matching shape skeleton rather than a centered spinner.
- **`project_progress` data**: computed in `dashboard_service.py` from the projects list already loaded — no extra DB query.
- **Bar chart**: Recharts `BarChart` with per-bar `Cell` coloring by project status. Custom `ProjectTooltip`. Bars truncated to 10 chars on X-axis.
- **`StatCard`**: `border-l-4` accent (blue/green/violet/amber) gives immediate visual grouping; icon square moved to top-right; value typography enlarged to `text-3xl`.
- **`ScorePill`**: semantic background (emerald ≥80, blue ≥60, amber ≥40, red <40) replaces plain text class colors.

---

## Reference Files
- **OPPM reference JSX**: `task/Oppmeditor · JSX.md` — target UI with StatusDot, InlineEdit, ChatPanel
- **AI API spec**: `task/Oppm api spec.md` — chat, suggest-plan, weekly-summary endpoints
- **AI system prompt**: `task/Oppm ai system prompt.md` — (empty, to be written in Phase 2)
- **DB schema**: `supabase/schema.sql` — reference DDL (canonical schema applied via Alembic)
- **Architecture**: `docs/ARCHITECTURE.md`
- **API reference**: `docs/API-REFERENCE.md`

---

## Phase 10 — OPPM Compliance Redesign (April 2026)

**Goal:** Align TaskForm and OPPMView with Clark A. Campbell's OPPM standard (5 pillars + Risks/RAG + Summary & Forecast narrative).

### Status: ✅ Complete

| # | Task | Status | Files |
|---|------|--------|-------|
| 10.1 | Add OPPM objective dropdown to TaskForm | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 10.2 | Add Owner assignment dropdown to TaskForm | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 10.3 | Add OPPM compliance hint banner + footer indicator | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 10.4 | Remove non-standard "Project Contribution Weight" field | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 10.5 | Enhance TaskCard with objective (indigo) + owner (slate) badges | ✅ | `frontend/src/pages/ProjectDetail.tsx` |
| 10.6 | Upgrade Risk section with RAG (Green/Amber/Red) status indicators | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 10.7 | Convert Forecast from numbered list to narrative textarea | ✅ | `frontend/src/pages/OPPMView.tsx` |
| 10.8 | Backward-compatible normalization for legacy risk/forecast data | ✅ | `frontend/src/pages/OPPMView.tsx` |

### Key Changes
- **No backend changes** — all endpoints and schemas already supported `oppm_objective_id`, `assignee_id`, JSONB metadata
- **Backward compatible** — existing `string[]` risk data auto-converts to `RiskItem[]`; legacy `string[]` forecast joins to narrative string
- **New inline components**: `RiskEditor` (RAG color selectors per risk), `InlineTextarea` (click-to-edit multi-line)

---

## Phase 11 — API Gateway, Load Balancing & Auth Redesign ✅ COMPLETE

**Goal:** Replace ad-hoc native dev setup with a proper Python gateway for local development, introduce round-robin load balancing, enforce gateway as the single entry point, and route all frontend auth through the backend REST API.

### Summary of Changes

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 11.1 | Create Python gateway service with round-robin load balancer | ✅ | `services/gateway/main.py`, `services/gateway/config.py` |
| 11.2 | Gateway mirrors nginx routing table (most-specific-first) | ✅ | `services/gateway/main.py` |
| 11.3 | Create `start.ps1` for each service (PYTHONPATH + .env auto-load) | ✅ | `services/{gateway,core,ai,git,mcp}/start.ps1` |
| 11.4 | Create per-service `.env` files (replacing shared `services/.env` for native dev) | ✅ | `services/{gateway,core,ai,git,mcp}/.env` |
| 11.5 | Simplify `vite.config.ts` to proxy all traffic to gateway (:8080) | ✅ | `frontend/vite.config.ts` |
| 11.6 | Create `services/core/routers/auth.py` — server-side auth endpoints | ✅ | `services/core/routers/auth.py` |
| 11.7 | Register auth router in `services/core/main.py` | ✅ | `services/core/main.py` |
| 11.8 | Rewrite `authStore.ts` — use REST API with Bearer token (localStorage) | ✅ | `frontend/src/stores/authStore.ts` |
| 11.9 | Update `api.ts` — read `accessToken` from store, auto-retry on 401 | ✅ | `frontend/src/lib/api.ts` |
| 11.10 | Update `App.tsx`, `AcceptInvite.tsx` — `session` → `accessToken` | ✅ | `frontend/src/App.tsx`, `frontend/src/pages/AcceptInvite.tsx` |
| 11.11 | Update `Settings.tsx` — replace profile update with `api.patch('/auth/profile')` | ✅ | `frontend/src/pages/Settings.tsx` |
| 11.12 | Remove unused env vars from `frontend/.env` | ✅ | `frontend/.env` |
| 11.13 | Update `DEVELOPMENT.md` with simplified native run instructions | ✅ | `DEVELOPMENT.md` |

### Architecture Decisions

- **Python gateway** (`services/gateway/main.py`): FastAPI reverse proxy using `httpx.AsyncClient`. Reads `CORE_URLS`, `AI_URLS`, `GIT_URLS`, `MCP_URLS` from `.env` as comma-separated strings, builds `itertools.cycle` iterators for round-robin. Returns `502` on upstream unreachable, `504` on timeout. Must start before all other services in native dev.

- **`start.ps1` pattern**: Each script uses `$PSScriptRoot` (immune to CWD) to set `PYTHONPATH` to workspace root and call `Set-Location $PSScriptRoot` before uvicorn. Reads its own `.env` via `Get-Content` + regex parse into `[System.Environment]::SetEnvironmentVariable`. No global shell setup needed.

- **Per-service `.env`**: Each `services/{name}/.env` contains only that service's credentials. `services/gateway/.env` only has upstream URLs. `pydantic-settings` resolves `.env` relative to CWD (= `$PSScriptRoot`).

- **Auth through gateway**: The frontend `authStore` stores `access_token` and `refresh_token` in `localStorage`. `api.ts` reads `accessToken` from the store for every request. On `401`, it calls `authStore.refreshSession()` then retries once. All auth is handled server-side via `auth_service.py`.

- **`git/.env` routing**: `AI_SERVICE_URL=http://localhost:8080` — the git service routes AI analysis calls through the gateway, not directly to `ai:8001`.

### Auth Endpoints Added (`services/core/routers/auth.py`)

```
POST   /api/auth/login       → signInWithPassword(email, password) → {access_token, refresh_token, user}
POST   /api/auth/signup      → signUp(email, password, full_name)  → {access_token, refresh_token, user}
POST   /api/auth/refresh     → refreshSession(refresh_token)       → {access_token, refresh_token}
POST   /api/auth/signout     → signOut()                           → {message}
GET    /api/auth/me          → getUser(access_token)               → {id, email, full_name, role}
PATCH  /api/auth/profile     → updateUser({data: {full_name}})     → updated user object
```

### New Auth Flow

```
Browser → Vite (:5173) → gateway (:8080) → core (:8000) → auth_service.py (local JWT)
```

---

> **⚠️ Path Note for Phases 1–6**: These phases were written during the monolith era when all backend code lived in `backend/`. After Phase 7 (Microservices Migration), the code was reorganised into `services/core/`, `services/ai/`, `services/git/`, `services/mcp/`, and `shared/`. File paths in Phases 1–6 that reference `backend/` are historical and no longer reflect the current structure.

---

## Phase 12 — Backlog (Planned)

Items identified for the next development cycle:

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 12.1 | Project edit/delete in frontend | ✅ Done | Edit modal + delete dialog with kebab menu added to `Projects.tsx` |
| 12.2 | Owner picker uses workspace members | ✅ Done | OPPM objective owner dropdown loads `GET /members` |
| 12.3 | Industry demo seed data | ✅ Done | `seed_demo.ps1` — 5 industries, 10 projects |
| 12.4 | User-facing testing guide | ✅ Done | `docs/TESTING-GUIDE.md` |
| 12.5 | Public API endpoint security (rate limiting on all non-webhook public routes) | High | Currently only webhook has rate limiting |
| 12.6 | Email sending (SMTP / SendGrid) for invites and notifications | High | Currently notifications are stored only; no email delivery |
| 12.7 | Task drag-and-drop between status columns | Medium | `@dnd-kit/core` or similar |
| 12.8 | Real-time notifications (WebSocket / SSE) | Medium | Currently polling; add `GET /notifications/stream` SSE endpoint |
| 12.9 | Alembic migrations for all services | Medium | Currently applied manually; add `alembic upgrade head` to Docker entrypoint |
| 12.10 | Project member management UI (add/remove from project team) | Medium | Backend endpoints exist; no frontend UI |
| 12.11 | Commits page — project filter + pagination | Low | Currently shows all commits unfiltered |
| 12.12 | AI weekly summary scheduled job (cron) | Low | Currently on-demand only |
| 12.13 | MCP protocol compliance audit | Low | Validate against MCP 1.0 spec |
| 12.14 | Git service report endpoint UI (`GET /git/report/:project_id`) | Low | Backend route exists; no frontend component |

