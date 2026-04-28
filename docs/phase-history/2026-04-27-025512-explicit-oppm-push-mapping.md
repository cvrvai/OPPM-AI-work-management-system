# Current Phase Tracker

## Task
Fix Push AI Fill Cell Mapping

## Goal
Ensure Push AI Fill writes OPPM text into the correct rows and columns on linked Google Sheets by resolving live layout coordinates instead of relying on static hard-coded cells.

## Plan

### Phase 1: Baseline and Mapping Contract
- [x] Confirm current hard-coded OPPM write coordinates and task row start behavior in core service
- [x] Define mapping profile fields for labels, value anchors, task column, first task row, and writable bounds

### Phase 2: Runtime Layout Resolver
- [x] Implement resolver that inspects sheet values and metadata to detect anchors from labels and headers
- [x] Support merged-range and shifted-column templates where possible
- [x] Keep classic-coordinate fallback with explicit confidence and safety checks

### Phase 3: OPPM Write Refactor
- [x] Replace fixed OPPM cell writes with resolved mapping profile coordinates
- [x] Skip unsafe writes and return diagnostics instead of writing to uncertain cells
- [x] Keep Summary/Tasks/Members tab writes unchanged

### Phase 4: Diagnostics and Contract Updates
- [x] Add structured mapping diagnostics in service logs and push response metadata
- [x] Update API/schema plumbing if needed for diagnostics payload

### Phase 5: UI and Docs Alignment
- [x] Update OPPM page notice text to match live OPPM-tab write behavior
- [ ] Update linked-form docs and API reference notes for mapping-aware writes

### Phase 6: Validation
- [x] Add/update tests for resolver and mapped writes across shifted and classic layouts
- [ ] Run targeted backend tests for Google Sheets/OPPM paths

## Status
In Progress

## Expected Files
- services/core/services/google_sheets_service.py
- services/core/schemas/google_sheets.py
- services/core/tests/test_google_sheets_mapping.py
- frontend/src/pages/OPPMView.tsx
- docs/oppm/google-sheets-linked-form.md
- docs/API-REFERENCE.md
- docs/PHASE-TRACKER.md

## Verification
- python -m py_compile services/core/services/google_sheets_service.py services/core/schemas/google_sheets.py services/core/tests/test_google_sheets_mapping.py (pass)
- npx tsc -b --pretty false (pass)
- python -m pytest services/core/tests/test_google_sheets_mapping.py (blocked: pytest not installed in current environment)

## Notes
- Security-sensitive sheet content must not be logged; diagnostics should include coordinates, source, confidence, and counts only.
- This change is limited to OPPM tab coordinate resolution and write safety behavior.
