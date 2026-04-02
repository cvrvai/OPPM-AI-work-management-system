# OPPM Implementation — Phase Tracker

> Last updated: 2026-06-01

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
- **Dual write**: Profile save now writes to BOTH Supabase Auth `user_metadata.full_name` AND `workspace_members.display_name` via new PATCH endpoint.
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
- **500 on GET `/ai/models`**: Uncaught Supabase exception when DB is empty. Wrapped in try/except with logger warning.
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
| 6.3 | Deploy `match_documents` pgvector RPC to Supabase | ✅ | `supabase/schema.sql`, Supabase migration |
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
-- Deployed via Supabase migration: recreate_match_documents_rpc
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

## Reference Files
- **OPPM reference JSX**: `task/Oppmeditor · JSX.md` — target UI with StatusDot, InlineEdit, ChatPanel
- **AI API spec**: `task/Oppm api spec.md` — chat, suggest-plan, weekly-summary endpoints
- **AI system prompt**: `task/Oppm ai system prompt.md` — (empty, to be written in Phase 2)
- **DB schema**: `supabase/schema.sql` — all 17 tables
- **Architecture**: `docs/ARCHITECTURE.md`
- **API reference**: `docs/API-REFERENCE.md`
