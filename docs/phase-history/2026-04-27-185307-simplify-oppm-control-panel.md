# Current Phase Tracker

## Task
Reject Unresolved Google Sheets Push Targets

## Goal
Prevent `Push AI Fill` from reporting success when the workbook does not match either the helper-sheet profile or the legacy OPPM layout, so unresolved pushes fail with a clear error before any write occurs.

## Plan

### Phase 1: Trace And Scope
- [x] Confirm the unresolved mapping path still writes helper/export sheets and returns success
- [x] Verify this creates a false-positive success message when the visible OPPM sheet is not actually targeted

### Phase 2: Backend Guard
- [x] Fail fast when helper-sheet detection fails and the legacy OPPM mapping remains unresolved
- [x] Return a clear error message that explains the workbook layout was not recognized

### Phase 3: Regression Coverage
- [x] Add a focused test proving unresolved pushes stop before any sheet write occurs
- [x] Run the targeted backend mapping test suite

## Status
Completed

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- docs/PHASE-TRACKER.md

## Verification
- pytest services/core/tests/test_google_sheets_mapping.py (pass)

## Notes
- Current user symptom: success toast reports `Auto-target: unresolved` with non-zero helper-sheet row counts, but the workbook does not visually update.
- Scope is limited to backend push validation and its focused regression tests.
