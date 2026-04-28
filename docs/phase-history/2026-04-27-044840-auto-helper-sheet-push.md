# Current Phase Tracker

## Task
Implement Explicit OPPM Push Mapping

## Goal
Require a pasted JSON field map for linked Google Sheets pushes, validate and resolve that map before any write, and update only the explicitly mapped OPPM-form cells while preserving the generated Summary, Tasks, and Members tabs.

## Plan

### Phase 1: Contract Freeze
- [x] Define the supported field ids and accepted locator shapes for scalar fields and the optional repeating task anchor
- [x] Reject incomplete, duplicated, ambiguous, and unknown mappings before any write

### Phase 2: Core Contract Plumbing
- [x] Extend the Google Sheets push request schema to require explicit mapping input
- [x] Pass explicit mapping through the OPPM router into the push service and surface mapping diagnostics

### Phase 3: Backend Resolver And Write Path
- [x] Add strict row/column and label-based mapping resolution without fallback inference when manual mapping is supplied
- [x] Abort the whole push before any sheet update when validation fails
- [x] Write OPPM scalar fields and tasks only for explicitly mapped targets; keep Summary, Tasks, and Members generation unchanged after validation succeeds

### Phase 4: Frontend OPPM Controls
- [x] Add pasted JSON mapping state, parsing, allowlist validation, and inline help to the OPPM page
- [x] Disable Push AI Fill when the mapping is missing or invalid
- [x] Send the explicit mapping alongside the AI fill payload and update success/error messaging

### Phase 5: Tests And Validation
- [x] Extend focused backend tests for row/column mapping, label mapping, unknown fields, ambiguous labels, and omitted unmapped fields
- [x] Run targeted backend tests plus frontend lint/build and manual linked-sheet verification

## Status
Completed

## Expected Files
- services/core/schemas/google_sheets.py
- services/core/routers/v1/oppm.py
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- frontend/src/pages/OPPMView.tsx
- docs/PHASE-TRACKER.md

## Verification
- pytest services/core/tests/test_google_sheets_mapping.py (pass, with `PYTHONPATH` set to the workspace root and `services/core` for local imports)
- cd frontend && npm run lint (blocked by pre-existing unused-variable errors in ChatPanel.tsx, GanttChart.tsx, AgileBoard.tsx, and Projects.tsx; no remaining lint error in OPPMView.tsx)
- cd frontend && npm run build (pass)
- Browser OPPM page check: explicit mapping textarea rendered, missing mapping kept Push AI Fill disabled, valid sample mapping changed the UI to “Ready: 4 fields” and enabled the button
- Live push execution through the browser was not completed because the current frontend session is returning 401 responses

## Notes
- Security-sensitive sheet content must not be logged; diagnostics should describe field ids, locator source, and unresolved reasons only.
- Performance target: label-based resolution should reuse one sheet-layout read per push request.
- Scope is limited to the linked Google Sheets push flow; no persistence, OCR, or database changes are included.
