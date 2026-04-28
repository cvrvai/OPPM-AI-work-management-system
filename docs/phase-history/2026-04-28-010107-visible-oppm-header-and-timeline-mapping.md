# Current Phase Tracker

## Task
Compact grouped Google Sheet task rows and remove inline deadline text from the visible OPPM task area

## Goal
Make `Push AI Fill` use the grouped OPPM sheet rows more cleanly by packing tasks without unnecessary blank gaps and by moving deadline information out of the visible grouped task labels.

## Plan

### Phase 1: Confirm the presentation gap
- [x] Verify grouped task rows still leave blank white space when a main task has no sub tasks
- [x] Verify grouped task text still includes inline deadlines in the visible OPPM task area

### Phase 2: Patch grouped rendering
- [x] Compact grouped task-row assignment so tasks fill available grouped slots sequentially
- [x] Remove inline deadline text from grouped OPPM task labels while preserving task deadlines for timeline/helper data

### Phase 3: Validate
- [x] Update focused backend tests for the compact grouped layout behavior
- [x] Run the focused Google Sheets mapping tests
- [x] Run a real `Push AI Fill` against the linked workbook and inspect the downloaded OPPM rows

## Status
Completed and validated.

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system" ; $env:PYTHONPATH = (Get-Location).Path ; pytest services/core/tests/test_google_sheets_mapping.py`
- Real `Push AI Fill` call through the frontend API proxy
- Linked-sheet XLSX verification of rows `H6:M17` after the live push
- VS Code error check on touched files

## Notes
- The live workbook now packs the visible task list as `1`, `2`, `2.1`, `2.2`, `2.3`, `3`, `4`, `4.1`, `4.2`, `4.3` without the old empty three-row gaps under root tasks with no children.
- Grouped OPPM task labels no longer include inline deadline text; deadline timing remains available through the timeline/helper-sheet data instead of the main task-text area.
