# Current Phase Tracker

## Task
Design-first architecture for OPPM linked Google Sheet edit recovery

## Goal
Define the best implementation approach for the OPPM `Edit in App` failure before writing code, with a verified architecture that covers session refresh races, sheet-loading stability, and Fortune Sheet recovery.

## Plan

### Phase 1: Verify current behavior
- [x] Read the core product and architecture docs for auth, OPPM, and Google Sheets behavior
- [x] Verify the owning frontend and backend code paths for refresh, linked-sheet load, and editor entry

### Phase 2: Design the target architecture
- [x] Identify the root causes that should be fixed at the architecture level instead of patching symptoms
- [x] Define the recommended frontend session, OPPM state, and sheet-adapter boundaries

### Phase 3: Document before implementation
- [x] Write the design proposal in the OPPM docs area
- [x] Link the new design doc from the architecture index

## Status
Design documented. Implementation has not started.

## Expected Files
- docs/PHASE-TRACKER.md
- docs/oppm/google-sheet-edit-session-recovery.md
- docs/ARCHITECTURE.md

## Verification
- Verified against current docs plus these source-of-truth files:
  - `frontend/src/lib/api.ts`
  - `frontend/src/stores/authStore.ts`
  - `frontend/src/pages/OPPMView.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/Header.tsx`
  - `services/core/services/auth_service.py`
  - `services/core/services/google_sheets_service.py`
  - `services/core/routers/v1/oppm.py`

## Notes
- No production code changes are included in this phase.
- The current failure spans frontend auth/session handling and the OPPM spreadsheet edit flow.