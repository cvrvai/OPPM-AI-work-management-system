# Current Phase Tracker

## Task
Implement Native OPPM AI Fill MVP

## Goal
Execute the approved MVP in two slices: first clean up the OPPM page header and status area so the linked-sheet mode is easier to scan, then add a native AI draft flow that turns a business brief into previewable OPPM data and commits that draft into the existing project, objective, task, and timeline tables.

## Plan

### Phase 1: OPPM Page Cleanup
- [x] Recompose the top area in `frontend/src/pages/OPPMView.tsx` into clearer status and action sections
- [x] Reduce repeated preview and error messaging across the page states
- [x] Keep linked-sheet actions and current render mode visible without the current dense layout

### Phase 2: AI Draft Contract
- [x] Expand the AI suggest-plan flow to return a richer native OPPM draft
- [x] Reuse the current OPPM fill data shape where practical for header, tasks, members, and timeline output
- [x] Keep preview generation non-destructive before commit

### Phase 3: Native Persistence
- [x] Commit approved AI drafts into project fields, OPPM header data, objectives, tasks, and timeline entries
- [x] Keep native app data as the source of truth and leave Google Sheets as downstream push only

### Phase 4: Frontend Draft UX
- [x] Reuse the current chat-based Suggest Plan flow for preview and apply
- [x] Add a dedicated OPPM-page entry point for generating a draft from a business brief
- [x] Refresh project, objective, task, and timeline queries after commit

### Phase 5: Validation
- [x] Run focused frontend type validation after each UI slice
- [x] Run focused backend validation for draft parsing and commit behavior
- [x] Manually verify the flow using the `3d Enhancement Project` brief

## Status
Completed

## Expected Files
- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/components/ChatPanel.tsx`
- `services/ai/services/ai_chat_service.py`
- `services/ai/schemas/ai_chat.py`
- `docs/PHASE-TRACKER.md`

## Verification
- `npx tsc -p tsconfig.app.json --noEmit`
- `python -m py_compile services\ai_chat_service.py schemas\ai_chat.py`
- Rebuilt and restarted the AI container with `docker compose -f docker-compose.microservices.yml up -d --build ai`
- Live OPPM browser verification on project `300aa577-1281-4dd0-ab9f-50032edf13b1`:
	- Generated a native draft from the brief `Enhancement of existing system to support new business processes`
	- Preview rendered successfully with 4 objectives and 11 existing tasks considered
	- Applied the draft successfully from the UI
	- Commit response reported: objectives `4`, tasks created `22`, tasks updated `11`, timeline rows `11`
	- Direct authenticated API checks after apply confirmed:
		- project `objective_summary` and `deliverable_output` updated
		- OPPM header created with `project_leader_text`, `completed_by_text`, and `people_count`
		- combined OPPM payload returned `10` objectives and `11` timeline entries
		- task list returned `33` project tasks

## Notes
- The first implementation slice starts in `OPPMView.tsx` because it has the clearest user-facing pain point and cheapest validation path.
- The current `suggest_plan()` preview uses an in-memory commit token cache; that is acceptable for the strict MVP but should be treated as follow-up hardening work.
- The live runtime bug `cannot access local variable 'prompt' where it is not associated with a value` was fixed by correcting indentation in `suggest_plan()` and redeploying the AI service.