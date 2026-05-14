# Phase Tracker

## Task
Project Create Flow Refresh — redesign the new-project UX so it captures the real project data model, guides users through methodology-aware setup, and lands them in the right next workspace.

## Goal
Replace the current shell-style create modal with a guided, database-aligned project creation flow that collects all user-meaningful project fields, supports explicit lead selection without breaking current membership behavior, and routes users into OPPM, Agile, Waterfall, or Hybrid follow-up setup.

## Status
| Phase | Status |
|---|---|
| Phase 1: Contract Audit & Tracker Reset | ✅ Completed |
| Phase 2: Backend Create Semantics | ✅ Completed |
| Phase 3: Wizard UX Redesign | ✅ Completed |
| Phase 4: Edit Flow Alignment | ✅ Completed |
| Phase 5: Post-Create Routing | ✅ Completed |
| Phase 6: Docs & Validation | ✅ Completed |

---

## Phase 1: Contract Audit & Tracker Reset ✅

**Completed:** May 13, 2026

### Verified Source Of Truth
- `shared/models/project.py` is the authoritative project field set in code.
- `services/workspace/domains/project/schemas.py` defines current create/update request contracts.
- `services/workspace/domains/project/service.py` currently auto-adds the creator as a project `lead` member during create.
- `frontend/src/pages/projects/CreateProjectModal.tsx` currently omits `deliverable_output` and treats create as a two-step shell flow.
- `frontend/src/pages/Projects.tsx` currently creates the project first and then best-effort posts project-member assignments.

### Verified Gaps
- `deliverable_output` exists in the database/API but is not collected in the current create flow.
- `lead_id` can be sent from the client, but the backend create service does not honor it as the persisted project lead behavior.
- The current UI allows a lead-like role choice in team setup without enforcing single-lead semantics.
- The current create flow does not validate schedule chronology for `start_date`, `deadline`, and `end_date`.
- The current success path stops at project creation instead of routing users into methodology-specific setup pages.

### Tracker Reset
- Archived the previous OPPM scaffold tracker into `docs/phase-history/2026-05-13-000000-oppm-schema-audit-and-full-data-support.md`.
- Started this tracker before implementation changes, per workspace workflow rules.

---

## Phase 2: Backend Create Semantics ✅
**Priority: P0 | Estimated: 1-2 hours | Started: May 13, 2026 | Completed: May 13, 2026**

### Completed
1. Added strict ISO date parsing and chronology validation for `start_date`, `deadline`, and `end_date`.
2. Updated create and update behavior to validate `lead_id` against workspace membership and persist explicit lead ownership correctly.
3. Kept the creator on the project during create while preventing duplicate or conflicting lead membership behavior.
4. Tightened add-member behavior so project membership stays workspace-scoped and single-lead safe.

### Expected Files
- `services/workspace/domains/project/service.py`
- `services/workspace/domains/project/repository.py`
- `services/workspace/domains/project/schemas.py` only if backend validation/messages need schema support

### Verification Target
- Narrow Python syntax validation on the touched backend files immediately after the first code edit.

### Verification Result
- `python -m py_compile services/workspace/domains/project/service.py services/workspace/domains/project/repository.py services/workspace/domains/project/router.py services/workspace/domains/project/schemas.py`

---

## Phase 3: Wizard UX Redesign ✅
**Priority: P0 | Estimated: 4-6 hours | Completed: May 13, 2026**

### Completed
1. Replaced the previous two-step shell modal with a four-step guided wizard: brief, plan, team, and review.
2. Added `deliverable_output`, explicit status selection, methodology-specific next-step guidance, lead selection, and better review context.
3. Added inline client validation for required title and invalid schedule ordering while keeping other planning fields guided instead of fully blocking.
4. Limited team-role assignment during create to contributor, reviewer, and observer, with lead handled as a dedicated selection.

### Expected Files
- `frontend/src/pages/projects/CreateProjectModal.tsx`
- `frontend/src/pages/projects/constants.ts`
- `frontend/src/schemas/project.ts`

---

## Phase 4: Edit Flow Alignment ✅
**Priority: P1 | Estimated: 1-2 hours | Completed: May 13, 2026**

### Completed
1. Updated `frontend/src/pages/projects/EditProjectModal.tsx` so edit now covers the same core planning shell fields as create, including `deliverable_output`, methodology, lead, status, priority, schedule, and resourcing.
2. Added the same client-side schedule ordering rules used in create so invalid date chronology is blocked before submit.
3. Updated the page-level update mutation to surface backend `detail` messages and pass them into the modal, keeping edit failure handling consistent with create.

### Expected Files
- `frontend/src/pages/projects/EditProjectModal.tsx`

---

## Phase 5: Post-Create Routing ✅
**Priority: P1 | Estimated: 1 hour | Completed: May 13, 2026**

### Completed
1. Updated `frontend/src/pages/Projects.tsx` so a newly created project navigates directly to:
   - `oppm` → `projects/:id/oppm`
   - `agile` → `projects/:id/agile`
   - `waterfall` → `projects/:id/waterfall`
   - `hybrid` → `projects/:id`
2. Added explicit API error extraction so failed create requests now surface backend `detail` messages instead of a generic toast only.
3. Kept additional member assignment behavior after create, while surfacing assignment failures separately if they occur.

### Expected Files
- `frontend/src/pages/Projects.tsx`
- optionally destination pages only if a first-run banner is added

---

## Phase 6: Docs & Validation ✅
**Priority: P1 | Estimated: 1-2 hours | Completed: May 13, 2026**

### Completed
1. Updated project feature, API, and schema docs to reflect the current create flow, `deliverable_output`, explicit lead handling, and methodology-aware routing.
2. Ran frontend build validation after the frontend changes landed.
3. Recorded tracker outcomes and left manual verification scenarios available for follow-up testing.

### Verification Result
- `npm run build` from `frontend/`

### Manual Verification Checklist
- [ ] Create an OPPM project with explicit lead override and confirm only one lead member exists.
- [ ] Create an Agile project with only core fields and confirm guided fields do not block creation.
- [ ] Create a Waterfall project and confirm the user reaches the phase setup view.
- [ ] Enter invalid date ordering and confirm both client and server validation reject it.
- [ ] Confirm `deliverable_output` persists and is visible in project data.

---

## Notes
- The implementation should anchor on code, not older summary docs, because service-count and table-count drift already exists across documentation.
- The misleading `user_id` name in the project-member add payload still represents `workspace_members.id`; do not silently break that contract during this task.
- Waterfall already has a phase-initialization service path that should be reused rather than replaced.