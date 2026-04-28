# Current Phase Tracker

## Task
Allow Adding More OPPM Objectives From Task Editor

## Goal
Let users create additional OPPM objectives from the task editor even when one or more objectives already exist, so they can choose or add the right objective without leaving the task flow.

## Plan

### Phase 1: Trace And Scope
- [x] Confirm the current create-objective control only appears when there are zero objectives
- [x] Verify the existing objective API can already create multiple objectives

### Phase 2: Frontend Objective Flow
- [x] Expose an add-another-objective control alongside the existing Linked Objective selector
- [x] Keep the create call on the existing OPPM objective API and auto-select the newly created objective

### Phase 3: Validation
- [x] Run a focused frontend build for the edited slice

## Status
Completed

## Expected Files
- frontend/src/pages/ProjectDetail.tsx
- docs/PHASE-TRACKER.md

## Verification
- frontend/src/pages/ProjectDetail.tsx file diagnostics (pass)
- cd frontend && npm run build (pass)

## Notes
- The user confusion is valid because the current create path disappears once a single objective exists.
- The OPPM objective concept itself already exists in the data model and API; this task is only widening the UI path.