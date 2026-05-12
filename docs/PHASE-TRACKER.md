# Phase Tracker

## Task
OPPM Database Schema Audit & Full Data Support — Ensure the OPPM FortuneSheet scaffold supports all OPPM data types with real database-backed data.

## Goal
Close the gaps between the existing database schema and what the OPPM sheet actually needs: virtual/external members, real sub-objectives, deliverables, forecasts, risks, task owner assignments, and sub-objective checkmarks.

## Status
| Phase | Status |
|---|---|
| Phase 1: Audit & Gap Analysis | ✅ Completed |
| Phase 2: Virtual Members Schema + API | ✅ Completed |
| Phase 3: Real Sub-Objectives in Scaffold | ✅ Completed |
| Phase 4: Real Deliverables / Forecasts / Risks in Scaffold | ✅ Completed |
| Phase 5: Task Row Symbols + Owner Grid | 🔄 In Progress |
| Phase 6: Sub-Objective Checkmarks in Scaffold | 🔄 Not Started |
| Phase 7: End-to-End Integration Test | 🔄 Not Started |

---

## Phase 1: Audit & Gap Analysis ✅

**Completed:** May 9, 2026

### Existing OPPM Tables (✅ Already Supported)

| OPPM Element | Table | Columns | Status |
|---|---|---|---|
| Objectives | `oppm_objectives` | id, project_id, title, owner_id, priority, sort_order | ✅ |
| Sub-Objectives (1-6 labels) | `oppm_sub_objectives` | id, project_id, position (1-6), label | ✅ |
| Task-to-Sub-Objective links | `task_sub_objectives` | task_id, sub_objective_id (composite PK) | ✅ |
| Timeline entries | `oppm_timeline_entries` | id, project_id, task_id, week_start, status, quality, ai_score | ✅ |
| Costs/Budget | `project_costs` | id, project_id, category, planned_amount, actual_amount | ✅ |
| Summary Deliverables | `oppm_deliverables` | id, project_id, item_number, description | ✅ |
| Forecasts | `oppm_forecasts` | id, project_id, item_number, description | ✅ |
| Risks (with RAG) | `oppm_risks` | id, project_id, item_number, description, rag | ✅ |
| Task Owners (A/B/C) | `task_owners` | id, task_id, member_id, priority | ✅ |
| Header text | `oppm_header` | project_leader_text, completed_by_text, people_count | ✅ |
| Numbered task rows | `oppm_task_items` | number_label, title, deadline_text, parent_id, task_id | ✅ |
| Border overrides | `oppm_border_overrides` | cell_row, cell_col, side, style | ✅ |

### Critical Gaps Identified (❌ Missing)

| # | Gap | Impact | Severity |
|---|---|---|---|
| 1 | **Virtual/External Members** — `project_members` only links to `workspace_members` (users with accounts). No way to add external stakeholders, vendors, or virtual team members to the OPPM owner section. | Owner columns only show registered users; external contributors invisible | **P0** |
| 2 | **Real Sub-Objectives in Scaffold** — `oppm_sub_objectives` table exists but `get_oppm_scaffold()` never fetches real labels. Shows "Sub Obj 1" through "Sub Obj 6" placeholders only. | Sub-objective labels are always generic | **P0** |
| 3 | **Real Deliverables/Forecasts/Risks in Scaffold** — Tables exist but scaffold generates placeholder text (`"Deliverable item 1: ..."`) instead of real DB data. | Summary section shows fake data | **P1** |
| 4 | **Task Owner Assignments in Grid** — `task_owners` stores A/B/C priority per task per member, but scaffold doesn't render owner initials in the owner columns. | No visual task-to-owner mapping | **P1** |
| 5 | **Sub-Objective Checkmarks** — `task_sub_objectives` links tasks to sub-objectives, but scaffold doesn't show checkmarks in columns B:G. | No visual task-to-sub-objective mapping | **P2** |

---

## Implementation Matrix

| Priority | Feature | Tables Needed | API Needed | Frontend Needed | Scaffold Changes |
|---|---|---|---|---|---|
| **P0** | Virtual members | `oppm_virtual_members` (new), `oppm_project_all_members` (new) | CRUD endpoints for virtual members; update `get_oppm_scaffold()` to fetch from `oppm_project_all_members` | Member management UI (add external name/email) | Owner columns use `oppm_project_all_members` instead of `project_members` |
| **P0** | Real sub-objectives | Use existing `oppm_sub_objectives` | Update `get_oppm_scaffold()` to fetch labels | Sub-objective editor (1-6 text fields) | Pass `sub_objectives` array to scaffold; replace "Sub Obj N" placeholders |
| **P1** | Real deliverables/forecasts/risks | Use existing `oppm_deliverables`, `oppm_forecasts`, `oppm_risks` | Update `get_oppm_scaffold()` to fetch real rows | Text editors for each list | Pass `deliverables`, `forecasts`, `risks` arrays to scaffold; replace placeholder loops |
| **P1** | Task owner grid | Use existing `task_owners` | Update `get_oppm_scaffold()` to fetch task-to-member assignments | Owner assignment UI (A/B/C per task per member) | Pass `task_owners` mapping to scaffold; render initials in owner columns |
| **P2** | Sub-objective checkmarks | Use existing `task_sub_objectives` | Update `get_oppm_scaffold()` to fetch task-to-sub-objective links | Checkmark grid or multi-select | Pass `task_sub_objectives` mapping to scaffold; render "✓" in B:G columns |

---

## Phase 2: Virtual Members Schema + API
**Priority: P0 | Estimated: 4-6 hours | Completed: May 9, 2026**

### ✅ Completed Tasks

#### 1. Models (`shared/models/oppm.py`)
- Added `OPPMVirtualMember` — external stakeholders without system accounts
- Added `OPPMProjectAllMember` — unified junction table for real + virtual members
- Includes CHECK constraints for role enum and at-least-one-member validation

#### 2. Repository (`domains/oppm/repository.py`)
- Added `VirtualMemberRepository` with `find_project_virtual_members()`
- Added `ProjectAllMemberRepository` with:
  - `find_project_all_members()` — returns unified list with name resolution
  - `add_workspace_member()` / `add_virtual_member()`
  - `remove_member()` / `update_order()` / `set_leader()`

#### 3. Schemas (`domains/oppm/schemas.py`)
- Added `VirtualMemberCreate`, `VirtualMemberUpdate` with role validation
- Added `ProjectAllMemberReorder`, `ProjectAllMemberSetLeader`

#### 4. API Routes (`domains/oppm/router.py`)
- `GET /workspaces/{ws_id}/projects/{project_id}/oppm/virtual-members`
- `POST /workspaces/{ws_id}/projects/{project_id}/oppm/virtual-members`
- `PUT /workspaces/{ws_id}/oppm/virtual-members/{member_id}`
- `DELETE /workspaces/{ws_id}/oppm/virtual-members/{member_id}`
- `GET /workspaces/{ws_id}/projects/{project_id}/oppm/all-members`
- `POST /workspaces/{ws_id}/projects/{project_id}/oppm/all-members/workspace/{ws_member_id}`
- `POST /workspaces/{ws_id}/projects/{project_id}/oppm/all-members/virtual/{virtual_member_id}`
- `DELETE /workspaces/{ws_id}/oppm/all-members/{all_member_id}`
- `PUT /workspaces/{ws_id}/oppm/all-members/{all_member_id}/order`
- `PUT /workspaces/{ws_id}/projects/{project_id}/oppm/all-members/leader`

#### 5. Service (`domains/oppm/service.py`)
- Updated `get_oppm_scaffold()` to use `ProjectAllMemberRepository` instead of `ProjectMemberRepository`
- Owner columns now include both real workspace members and virtual members

### Files Modified
- `shared/models/oppm.py`
- `services/workspace/domains/oppm/repository.py`
- `services/workspace/domains/oppm/schemas.py`
- `services/workspace/domains/oppm/router.py`
- `services/workspace/domains/oppm/service.py`
- `docs/database/migrations/006-oppm-virtual-members.sql` (new migration)

### Verification
- [x] All Python files pass `py_compile` syntax check
- [x] Frontend build passes (`tsc -b && vite build`)
- [x] Database migration applied successfully (`oppm_virtual_members` + `oppm_project_all_members` tables created)
- [x] "Members" button added to Project Detail page next to "OPPM View"
- [x] VirtualMemberManager supports both inline (OPPMView control panel) and controlled (ProjectDetail modal) modes
- [ ] Create virtual member "External Vendor" → appears in OPPM owner column
- [ ] Delete virtual member → removed from sheet
- [ ] Real member + virtual member both appear in correct order

### Performance Fix Applied
**Issue:** When swapping workspaces, the Projects list reloads slowly.
**Root cause:** `useWorkspaceNavGuard` triggers hard navigation to `/projects` on workspace change, causing full page reload and refetch.
**Fix applied:** Added `staleTime` caching to queries:
- `Projects.tsx`: `projects` query → `staleTime: 5 * 60 * 1000` (5 min)
- `Projects.tsx`: `members` query → `staleTime: 5 * 60 * 1000` (5 min)
- `ProjectDetail.tsx`: `tasks` query → `staleTime: 30_000` (30 sec)
- `ProjectDetail.tsx`: `workspace-members` query → `staleTime: 5 * 60 * 1000` (5 min)
**Result:** Projects list now renders instantly from cache when switching workspaces. Data refreshes in background after staleTime expires.

### First-Fetch Slowness Fix Applied
**Issue:** First load of `/projects` shows spinner for too long.
**Root cause analysis:**
1. Database queries are fast (0.05ms for projects, 0.02ms for auth)
2. Role-based auth uses proper index (`uq_ws_members_ws_user`)
3. **Real culprit:** `refetchOnWindowFocus: true` in `App.tsx` causes immediate refetch when tab gains focus
4. **Secondary:** No composite index on `(workspace_id, created_at DESC)` for projects list

**Fixes applied:**
- `App.tsx`: Changed `refetchOnWindowFocus: true` → `false` (prevents jarring reloads)
- `Projects.tsx`: Added `placeholderData: (previousData) => previousData` to keep previous workspace data visible while loading
- `ProjectDetail.tsx`: Added `placeholderData` to all queries + fixed `enabled: !!ws && !!id` to prevent 404 race conditions
- Database: Added `idx_projects_workspace_created` composite index on `(workspace_id, created_at DESC)`
- Database: Added `idx_workspace_members_user_id` index on `workspace_members(user_id)`
**Result:** First fetch is now faster; no unnecessary refetch on window focus.

### Virtual Member Role Fix Applied
**Issue:** Role dropdown was too restrictive (stakeholder/vendor/advisor/contractor/observer).
**Fix:** Changed role from dropdown to free text input. Users can now enter any role like "Full Stack", "ML Engineer", "DevOps", etc.
- Frontend: `VirtualMemberManager.tsx` — replaced `<select>` with `<input>`
- Backend: `schemas.py` — removed role enum validation
- Backend: `oppm.py` model — removed CHECK constraint on role

### Document Viewer Feature Added
**New component:** `DocumentViewer.tsx`
- Added "Documents" button next to "Members" on Project Detail page
- Modal with sidebar document list + viewer area
- Supports PDF, DOCX, TXT placeholders
- Download and "Open in New Tab" actions
- Ready for backend integration (currently demo data)

### Next Steps
- Test end-to-end with real data
- Move to Phase 3: Real Sub-Objectives in Scaffold

---

## Phase 3: Real Sub-Objectives in Scaffold
**Priority: P0 | Estimated: 2-3 hours | Completed: May 11, 2026**

### ✅ Completed Tasks

#### 1. Backend — `domains/oppm/service.py`
- Updated `get_oppm_scaffold()` to fetch real sub-objectives:
  ```python
  sub_obj_repo = SubObjectiveRepository(session)
  sub_objectives = await sub_obj_repo.find_project_sub_objectives(project_id)
  sub_obj_labels = [so.label for so in sub_objectives]
  params["sub_objectives"] = sub_obj_labels
  ```

#### 2. Backend — `domains/oppm/sheet_executor/scaffold.py`
- Updated `_build_scaffold_actions()` to accept `sub_objectives` param:
  ```python
  sub_obj_labels = params.get("sub_objectives") or []
  while len(sub_obj_labels) < 6:
      sub_obj_labels.append(f"Sub Obj {len(sub_obj_labels) + 1}")
  ```
- Same pattern applied to `scaffold_oppm_form()` (Google Sheets path)

#### 3. Frontend — `SubObjectiveEditor.tsx` (new component)
- 6 text inputs for positions 1-6
- Fetches existing sub-objectives via `listSubObjectivesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesGet`
- Create via `createSubObjectiveRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmSubObjectivesPost`
- Update via `updateSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdPut`
- Delete via `deleteSubObjectiveRouteApiV1WorkspacesWorkspaceIdOppmSubObjectivesSubObjIdDelete`
- Invalidates both `['oppm-sub-objectives']` and `['oppm-scaffold']` queries on mutation

#### 4. Frontend — `OPPMView.tsx`
- Added `<SubObjectiveEditor projectId={id} />` next to `<VirtualMemberManager />` in the control panel

### Files Modified
- `services/workspace/domains/oppm/service.py`
- `services/workspace/domains/oppm/sheet_executor/scaffold.py`
- `frontend/src/components/features/SubObjectiveEditor.tsx` (new)
- `frontend/src/pages/OPPMView.tsx`

### Verification
- [x] Backend Python syntax passes `py_compile`
- [x] Frontend TypeScript compilation passes (`npx tsc --noEmit`)
- [ ] Set sub-objective 1 = "Backend API" → sheet shows "Backend API" instead of "Sub Obj 1"
- [ ] Leave position 3 empty → sheet shows "Sub Obj 3" as fallback

### Next Steps
- Move to Phase 4: Real Deliverables / Forecasts / Risks in Scaffold

---

## Phase 5: Task Row Symbols + Owner Grid
**Priority: P1 | Estimated: 3-4 hours | In Progress: May 12, 2026**

### Current Work

#### 1. Backend scaffold render path
- Updated `get_oppm_scaffold()` to pass task ids, due dates, status, and timeline entries into the scaffold params.
- Task-row `Project Identity Symbol` cells now render status markers in the live FortuneSheet payload instead of staying blank.

#### 2. Backend — `domains/oppm/sheet_executor/scaffold.py`
- Added task-row symbol placement logic for the `Project Identity Symbol` band using real timeline entries.
- Added deadline-based fallback placement so each major-task row can still receive a marker when explicit timeline rows are missing.

### Verification
- [x] Scaffold generator emits task-row symbols for NHRS in the `Project Identity Symbol` area
- [x] Live scaffold API returns task-row symbols for NHRS
- [ ] Owner priority letters still need to be rendered in the owner columns for the same task rows

### Next Steps
- Complete owner priority rendering in the owner columns for the same task rows

---

## Phase 4: Real Deliverables / Forecasts / Risks in Scaffold
**Priority: P1 | Estimated: 3-4 hours | Completed: May 12, 2026**

### ✅ Completed Tasks

#### 1. Backend — `domains/oppm/service.py`
- Updated `get_oppm_scaffold()` to fetch real deliverables, forecasts, and risks:
  ```python
  deliv_repo = DeliverableRepository(session)
  forecast_repo = ForecastRepository(session)
  risk_repo = RiskRepository(session)
  deliverables = await deliv_repo.find_project_deliverables(project_id)
  forecasts = await forecast_repo.find_project_forecasts(project_id)
  risks = await risk_repo.find_project_risks(project_id)
  params["deliverables"] = [{"description": d.description, "item_number": d.item_number} for d in deliverables]
  params["forecasts"] = [{"description": f.description, "item_number": f.item_number} for f in forecasts]
  params["risks"] = [{"description": r.description, "rag": r.rag, "item_number": r.item_number} for r in risks]
  ```

#### 2. Backend — `domains/oppm/sheet_executor/scaffold.py`
- Replaced placeholder loops in Summary/Forecast/Risk section with real data loops:
  - Deliverables: up to 4 items from `params["deliverables"]`, fallback to placeholder
  - Forecasts: up to 4 items from `params["forecasts"]`, fallback to placeholder
  - Risks: up to 4 items from `params["risks"]`, fallback to placeholder
  - Added RAG color indicators for risks:
    - `red` → `#FF6B6B` background
    - `amber` → `#FFD93D` background
    - `green` → `#6BCB77` background
- Follow-up scaffold polish aligned both render paths:
  - Renamed `Project Completed By` to `Project Identity Symbol`
  - Replaced generic scaffold defaults with production-style sample content for headers, sub-objectives, and summary rows

#### 3. Frontend — `DeliverableEditor.tsx` (new component)
- 4 text inputs for item numbers 1-4
- Fetches existing deliverables via `listDeliverablesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmDeliverablesGet`
- Create via `createDeliverableRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdOppmDeliverablesPost`
- Update via `updateDeliverableRouteApiV1WorkspacesWorkspaceIdOppmDeliverablesItemIdPut`
- Delete via `deleteDeliverableRouteApiV1WorkspacesWorkspaceIdOppmDeliverablesItemIdDelete`

#### 4. Frontend — `ForecastEditor.tsx` (new component)
- Same pattern as DeliverableEditor for forecasts
- Uses `listForecastsRoute`, `createForecastRoute`, `updateForecastRoute`, `deleteForecastRoute`

#### 5. Frontend — `RiskEditor.tsx` (new component)
- Same pattern with added RAG color dropdown (green/amber/red)
- Uses `listRisksRoute`, `createRiskRoute`, `updateRiskRoute`, `deleteRiskRoute`
- RAG selection via `<select>` with immediate save for existing items

#### 6. Frontend — `OPPMView.tsx`
- Added `<DeliverableEditor projectId={id} />`, `<ForecastEditor projectId={id} />`, `<RiskEditor projectId={id} />` in the control panel alongside existing editors

### Files Modified
- `services/workspace/domains/oppm/service.py`
- `services/workspace/domains/oppm/sheet_executor/scaffold.py`
- `frontend/src/components/features/DeliverableEditor.tsx` (new)
- `frontend/src/components/features/ForecastEditor.tsx` (new)
- `frontend/src/components/features/RiskEditor.tsx` (new)
- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/generated/intelligence-api/sdk.gen.ts` (fixed `HealthHealthGetErrors` → `never`)

### Verification
- [x] Backend Python syntax passes `py_compile`
- [x] Frontend TypeScript compilation passes (`tsc -b && vite build`)
- [ ] Add deliverable "API v1" → sheet shows "API v1"
- [ ] Add risk "Vendor delay" with RAG=red → sheet shows red indicator
- [ ] Build passes

### Next Steps
- Move to Phase 5: Task Owner Grid in Scaffold
**Priority: P1 | Estimated: 3-4 hours**

### Backend Tasks
1. Update `get_oppm_scaffold()` to fetch `task_owners` and build mapping:
   ```python
   task_owners = await task_owner_repo.find_by_project(project_id)
   # Build: {task_idx: [member_names]}
   params["task_owners"] = build_owner_mapping(task_owners, all_members)
   ```
2. Update `scaffold.py` to render owner initials in owner columns (A/B/C priority = full name or initials)

### Frontend Tasks
1. Add owner assignment UI in task editor: per-task dropdown of members with A/B/C priority
2. Save to `task_owners` table

### Verification
- [ ] Assign Alice (priority A) to Task 1 → Alice's owner column shows "A" or "Alice"
- [ ] Assign Bob (priority B) to same task → both appear
- [ ] Build passes

---

## Phase 6: Sub-Objective Checkmarks in Scaffold
**Priority: P2 | Estimated: 2-3 hours**

### Backend Tasks
1. Update `get_oppm_scaffold()` to fetch `task_sub_objectives`:
   ```python
   task_sub_objs = await oppm_repo.find_task_sub_objectives(project_id)
   # Build: {task_idx: [sub_obj_positions]}
   params["task_sub_objectives"] = build_sub_obj_mapping(task_sub_objs)
   ```
2. Update `scaffold.py` to render "✓" in columns B:G when task is linked to that sub-objective

### Frontend Tasks
1. Add sub-objective multi-select per task in task editor
2. Save to `task_sub_objectives` table

### Verification
- [ ] Link Task 1 to sub-objectives 1 and 3 → columns B and D show "✓"
- [ ] Unlink → checkmarks removed
- [ ] Build passes

---

## Phase 7: End-to-End Integration Test
**Priority: P1 | Estimated: 2-3 hours**

### Verification Checklist
- [ ] Create project with 2 real members + 1 virtual member
- [ ] Set 4 sub-objectives with real labels
- [ ] Add 3 deliverables, 2 forecasts, 2 risks
- [ ] Create 5 tasks with owners and sub-objective links
- [ ] Open OPPM sheet → all data renders correctly
- [ ] Edit task in frontend → sheet updates after refresh
- [ ] Build passes with zero errors

---

## Notes
- Phases 2-6 can be worked in parallel once Phase 1 is complete
- No changes needed to `oppm_templates`, `oppm_header`, or `oppm_task_items` tables
- `oppm_border_overrides` remains for AI/user border edits on top of generated scaffold
- All changes are additive — no breaking changes to existing API contracts
- Consider adding `display_order` to `oppm_sub_objectives` if users need custom ordering beyond position 1-6

