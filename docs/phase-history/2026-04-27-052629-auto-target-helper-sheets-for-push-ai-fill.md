# Current Phase Tracker

## Task
Auto-Target Helper Sheets For Push AI Fill

## Goal
Remove the manual JSON mapping step and make Push AI Fill automatically write AI-generated OPPM data into the workbook's stable helper sheets so the visual form updates through its existing formulas.

## Plan

### Phase 1: Auto Profile Design
- [x] Verify the current push path against the helper-sheet layout used by the linked workbook
- [x] Define an automatic workbook profile that targets `OPPM Summary` scalar cells and `OPPM Tasks` task rows without user mapping input

### Phase 2: Backend Auto Write Path
- [x] Make explicit mapping optional or remove it from the push contract
- [x] Detect the helper-sheet profile from existing labels and headers in the workbook
- [x] Write only the stable helper-sheet cells and rows when that profile is present

### Phase 3: Frontend Simplification
- [x] Remove the JSON mapping UI and restore one-click Push AI Fill
- [x] Update notices so the page explains the automatic helper-sheet targeting behavior

### Phase 4: Tests And Validation
- [x] Replace explicit-mapping tests with focused auto-profile helper-sheet tests
- [x] Run targeted backend tests plus frontend build and a browser smoke check

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
- cd frontend && npm run build (pass)
- Browser smoke check: the active dev-session expired and reloaded to `/login`, so only a limited smoke check was possible after the UI change

## Notes
- The working hypothesis is that the linked workbook's `OPPM Summary` and `OPPM Tasks` tabs are the stable write surface and the visual `OPPM` tab is presentation-only.
- Security-sensitive sheet content must not be logged.
- Scope is limited to the linked Google Sheets push flow; no persistence or database changes are included.