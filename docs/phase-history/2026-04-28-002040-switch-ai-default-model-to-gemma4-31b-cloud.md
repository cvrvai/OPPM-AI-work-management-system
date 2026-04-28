# Current Phase Tracker

## Task
Make AI-driven Google Sheet push place OPPM task data into the correct form cells

## Goal
Use the existing OPPM project structure to write task rows, sub-objective markers, timeline symbols, and owner priorities into the live Google Sheet in the same layout the exported classic OPPM template expects.

## Plan

### Phase 1: Confirm the placement gap
- [x] Verify the current Google Sheets push path only writes header fields and a flat task label column on the OPPM sheet
- [x] Confirm the classic exporter already contains the full task-row placement rules for sub-objectives, timeline, and owners

### Phase 2: Patch the Google Sheets writer
- [x] Enrich the AI fill task payload with sub-objective positions used by the classic OPPM form
- [x] Reuse classic layout rules to resolve task-row placement for task text, sub-objectives, owners, timeline cells, and people-count text
- [x] Keep summary/tasks/members helper tabs working as fallback diagnostics

### Phase 3: Validate
- [x] Run focused backend tests for Google Sheets mapping and task placement
- [x] Run file-level error checks on the touched backend files

## Status
Completed and validated.

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system" ; $env:PYTHONPATH = (Get-Location).Path ; pytest services/core/tests/test_google_sheets_mapping.py`
- VS Code error check on `services/ai/schemas/oppm_fill.py`, `services/ai/services/oppm_fill_service.py`, `services/core/schemas/google_sheets.py`, `services/core/services/google_sheets_service.py`, `services/core/tests/test_google_sheets_mapping.py`

## Notes
- The write-path decision is in the core Google Sheets service, not in the AI fill route.
- The AI fill payload now carries sub-objective positions alongside owner and timeline data so the core writer can place each task row into the live OPPM form without guessing.
- The classic exporter remains the local source of truth for sheet geometry, and the Google Sheets writer now mirrors its visible task-row regions instead of only writing a single task-label column.
