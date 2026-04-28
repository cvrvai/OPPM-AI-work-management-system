# Current Phase Tracker

## Task
Clarify Why Push AI Fill Is Disabled

## Goal
Make the OPPM page explain why `Push AI Fill` is greyed out by surfacing the active disable reason near the button and on hover.

## Plan

### Phase 1: Trace And Scope
- [x] Identify the exact disable conditions for `Push AI Fill`
- [x] Confirm the current UI does not attach those reasons to the disabled control itself

### Phase 2: Frontend Disabled-State Messaging
- [x] Compute a single visible disable reason from the existing button conditions
- [x] Show the reason inline and on hover near the disabled button without changing backend behavior

### Phase 3: Validation
- [x] Run a focused frontend build for the edited slice

## Status
Completed

## Expected Files
- frontend/src/pages/OPPMView.tsx
- docs/PHASE-TRACKER.md

## Verification
- frontend/src/pages/OPPMView.tsx file diagnostics (pass)
- cd frontend && npm run build (pass)

## Notes
- The likely disable cases are: missing workspace/project context, loading link state, no linked Google Sheet, backend push not configured, or a push already running.
- Scope is limited to the OPPM page UX; no backend contract changes are required.