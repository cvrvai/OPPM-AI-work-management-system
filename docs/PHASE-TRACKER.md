# OPPM Implementation — Phase Tracker

> Last updated: 2026-04-02

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

## Reference Files
- **OPPM reference JSX**: `task/Oppmeditor · JSX.md` — target UI with StatusDot, InlineEdit, ChatPanel
- **AI API spec**: `task/Oppm api spec.md` — chat, suggest-plan, weekly-summary endpoints
- **AI system prompt**: `task/Oppm ai system prompt.md` — (empty, to be written in Phase 2)
- **DB schema**: `supabase/schema.sql` — all 17 tables
- **Architecture**: `docs/ARCHITECTURE.md`
- **API reference**: `docs/API-REFERENCE.md`
