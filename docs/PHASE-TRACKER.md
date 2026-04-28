# Current Phase Tracker

## Task
Fix Google Sheets OPPM push for grouped main-task and sub-task row layouts

## Goal
Make `Push AI Fill` write main tasks and sub tasks into the actual grouped OPPM row structure used by the linked Google Sheet template, instead of treating the task block as a flat linear list.

## Plan

### Phase 1: Confirm the row-pattern mismatch
- [x] Inspect the current linked Google Sheet layout downloaded from the backend
- [x] Verify the helper `OPPM Tasks` tab has the right root-task and sub-task sequence
- [x] Verify the visible `OPPM` tab uses grouped rows with separate main-task and sub-task slots

### Phase 2: Patch the writer
- [x] Detect grouped task row patterns from the live OPPM sheet layout
- [x] Write main-task titles and sub-task rows into the correct cells for that grouped layout
- [x] Keep the existing linear-row behavior for classic templates that already work
- [x] Stop helper-sheet detection from bypassing the visible `OPPM` tab when its layout is also recognized

### Phase 3: Validate
- [x] Add focused backend tests for grouped OPPM row mapping
- [x] Run targeted validation on the Google Sheets mapping service

## Status
Completed and validated.

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system" ; $env:PYTHONPATH = (Get-Location).Path ; pytest services/core/tests/test_google_sheets_mapping.py`
- Focused downloaded-sheet inspection against the linked Google Sheet layout before and after the live push
- Real `Push AI Fill` call through the frontend API proxy, then linked-sheet XLSX verification of rows `H6:M23`
- VS Code error check on touched files

## Notes
- The linked Google Sheet at `1tAAsDsK5dT35UbfjCyiDpHY3wfPYpx0pC0ftoG6p1Ao` uses a grouped task layout: main rows like `H6:L6`, followed by sub rows with index in column `H` and title merged across `I:L`.
- The original writer treated the task area as a flat linear region, which caused main-task placeholders like `Main task 1` to remain and shifted root-task titles into sub-task rows.
- The live workbook was also taking the helper-sheet path first, so `Push AI Fill` updated `OPPM Summary` and `OPPM Tasks` but skipped the visible `OPPM` tab until the helper-profile branch was changed to write both when possible.