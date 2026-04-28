# Current Phase Tracker

## Task
Tighten visible OPPM header-field mapping and remap the date/timeline area for the linked Google Sheet layout

## Goal
Detect the linked workbook's merged summary block and visible timeline layout directly from the sheet so `Push AI Fill` writes header fields into the actual visible OPPM area instead of relying on classic fallback cells.

## Plan

### Phase 1: Confirm the workbook-specific layout
- [x] Inspect the live linked workbook header merges and visible timeline columns
- [x] Verify the visible summary fields live in a merged block instead of standalone label cells

### Phase 2: Patch mapping and writes
- [x] Detect workbook-specific merged summary blocks for project objective, deliverable output, start date, and deadline
- [x] Write the visible summary block into the merged OPPM area
- [x] Tighten the visible timeline/date mapping for the grouped template without regressing helper-sheet output

### Phase 3: Validate
- [x] Add focused backend tests for merged summary-block detection and writing
- [x] Run targeted Google Sheets mapping tests
- [x] Run a live write against the linked workbook and inspect the linked workbook again

## Status
Completed and validated.

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/tests/test_google_sheets_mapping.py
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system" ; $env:PYTHONPATH = (Get-Location).Path ; pytest services/core/tests/test_google_sheets_mapping.py`
- Direct live Google Sheets write probe under the same env-loading logic as `services/core/start.ps1`, which resolved the real workbook mapping and wrote to the linked sheet successfully
- Linked workbook XLSX inspection after the successful direct write, confirming the visible summary block at `H3:AI4` and the compact grouped task rows remain correct

## Notes
- The linked workbook uses `H3:AI4` as one merged summary block containing `Project Objective`, `Deliverable Output`, `Start Date`, and `Deadline` labels.
- The resolved visible OPPM mapping now uses `summary_block_range = H3:AI4` and does not emit null scalar anchors for the summary-block fields, which prevents invalid Google Sheets batch ranges like `'OPPM'!None`.
- The currently running backend process behind `localhost:8000` is stale and did not reload these changes during validation. The current code path itself is verified by the direct write probe, but the local core server should be restarted before relying on the UI `Push AI Fill` button to hit the updated implementation.