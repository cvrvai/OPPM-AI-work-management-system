# Phase Tracker

## Task
Task Form OPPM Coverage And Compact Layout — make the create-task modal expose the full OPPM-relevant task fields and reduce scrolling in both desktop and mobile views.

## Goal
Keep the current task create/edit flow intact while surfacing the remaining OPPM task field that is missing from the form, bringing the most important alignment inputs earlier in the modal, and shrinking the layout so the core form fits with less scrolling.

## Status
| Phase | Status |
|---|---|
| Phase 1: Contract Audit & Tracker Reset | ✅ Completed |
| Phase 2: OPPM Field Coverage | ✅ Completed |
| Phase 3: Compact Task Modal UX | ✅ Completed |
| Phase 4: Validation & Docs | ✅ Completed |

---

## Phase 1: Contract Audit & Tracker Reset ✅

**Completed:** May 13, 2026

### Verified Source Of Truth
- `frontend/src/pages/project-detail/TaskForm.tsx` is the controlling create/edit task modal.
- `frontend/src/pages/ProjectDetail.tsx` strips `sub_objective_ids` and `oppm_owner_assignments` out of the main task create payload and persists them via follow-up OPPM APIs.
- `services/workspace/domains/task/schemas.py` defines the create/update request contracts for task CRUD.
- `shared/models/task.py` is the authoritative task model for persisted task fields.

### Verified Gaps
- The task form already supports OPPM objective linkage, owner assignment, due date, parent task, dependencies, sub-objectives, virtual assignees, and A/B/C owners.
- `project_contribution` exists in the ORM model and create schema but is not currently exposed in the task form UI.
- The modal spends too much height on the guide banner, task-type chooser, section padding, and footer spacing before users reach the core alignment inputs.

### Tracker Reset
- Archived the previous project-create tracker into `docs/phase-history/2026-05-13-024100-task-form-oppm-coverage-and-compactness.md`.
- Started this tracker before task-form implementation changes.

---

## Phase 2: OPPM Field Coverage ✅
**Priority: P0 | Estimated: 1-2 hours | Started: May 13, 2026 | Completed: May 13, 2026**

### Completed
1. Exposed `project_contribution` in the shared task form so create and edit now cover the remaining persisted OPPM task field.
2. Updated the backend task update schema so edits can persist the same contribution field as create.
3. Converted objective, owner, and due date from advisory alignment checks into blocking task-form validation before save.
4. Kept the existing sub-objective, virtual assignee, and A/B/C ownership flows intact.

### Expected Files
- `frontend/src/pages/project-detail/TaskForm.tsx`
- `services/workspace/domains/task/schemas.py`

---

## Phase 3: Compact Task Modal UX ✅
**Priority: P0 | Estimated: 2-3 hours | Completed: May 13, 2026**

### Completed
1. Shrunk the guide banner, task-type chooser, section padding, textarea height, dependency list height, and footer spacing.
2. Moved `Due Date` into the top brief section and surfaced contribution earlier so the key OPPM fields appear sooner.
3. Reduced mobile button and section density so the form wastes less vertical space on small screens.
4. Removed the duplicate in-body OPPM alignment panel and collapsed advanced owners, external assignees, dependencies, and sub-objectives so the modal stays shorter until optional controls are needed.
5. Replaced the remaining footer warning wording with direct required-field guidance so the modal no longer presents missing OPPM fields as a soft alignment message.

### Expected Files
- `frontend/src/pages/project-detail/TaskForm.tsx`

---

## Phase 4: Validation & Docs ✅
**Priority: P1 | Estimated: 1 hour | Completed: May 13, 2026**

### Completed
1. Ran frontend build validation after the task form changes.
2. Ran a narrow Python compile check on the updated task schema.
3. Updated task-facing docs so the implemented create/edit task behavior does not drift.
4. Verified the stricter task-form validation compiles cleanly in the frontend build.

### Verification Result
- `npm run build` from `frontend/`
- `python -m py_compile services/workspace/domains/task/schemas.py`

### Manual Verification Checklist
- [ ] Create an OPPM main task with objective, owner, due date, and project contribution set.
- [ ] Create a sub-task and confirm the selected parent task is preserved.
- [ ] Set A/B/C owners and confirm they persist after create.
- [ ] Confirm the modal fits with less scrolling on desktop and mobile widths.