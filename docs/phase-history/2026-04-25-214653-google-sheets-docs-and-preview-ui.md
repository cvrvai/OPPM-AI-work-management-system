# Current Phase Tracker

## Task
Document Google Sheets Linked Form And Refine Preview UI

## Goal
Document the linked Google Sheet OPPM feature in detail, including live browser preview behavior and backend render fallback, and update the UI so browser preview mode is presented as an intentional frontend experience instead of an error state.

## Plan

### Phase 1: Feature And Docs Audit
- [x] Read the current docs that describe OPPM, Docker, and frontend behavior
- [x] Verify the live implementation in `OPPMView.tsx` and `google_sheets_service.py`
- [x] Identify documentation drift and the current preview-mode UI copy

### Phase 2: UI Refinement
- [x] Make browser preview mode a first-class UI state when backend render is unavailable
- [x] Keep true backend render failures actionable without presenting preview mode as broken

### Phase 3: Documentation Update
- [x] Add a focused OPPM Google Sheets feature document
- [x] Link the new document from the architecture index
- [x] Update the frontend and API references so they reflect the current route and UI behavior

### Phase 4: Validation
- [x] Run focused frontend validation
- [x] Review the updated docs for consistency with the verified code path
- [x] Verify the live page still renders the linked Google Sheet preview

## Status
Complete

## Expected Files
- `frontend/src/pages/OPPMView.tsx`
- `docs/oppm/google-sheets-linked-form.md`
- `docs/ARCHITECTURE.md`
- `docs/API-REFERENCE.md`
- `docs/frontend/FRONTEND-REFERENCE.md`
- `docs/PHASE-TRACKER.md`

## Verification
- Verified that the current page already supports a browser preview fallback and that Google Sheet edits show up on reload through the live Google Sheet URL.
- Verified that backend XLSX render and push depend on Google service-account credentials, while browser preview mode does not.
- `get_errors` reported no issues in `frontend/src/pages/OPPMView.tsx` after the preview-mode UI refinement.
- `npx tsc -p tsconfig.app.json --noEmit` in `frontend` passed after the final UI changes.
- Spot-checked the updated documentation sections in `docs/oppm/google-sheets-linked-form.md`, `docs/API-REFERENCE.md`, `docs/frontend/FRONTEND-REFERENCE.md`, `docs/ARCHITECTURE.md`, and `README.md`.
- The live OPPM page had already been verified to show the linked Google Sheet preview against the running Docker stack earlier in this session.
- A later full page reload dropped the integrated browser back to login because the saved browser refresh token had expired, so the final preview-mode copy change was validated by code and typecheck rather than by a second authenticated browser pass.

## Notes
- Browser preview is a frontend-driven, read-only mode that depends on the user already being signed in to Google in the browser.
- Backend render remains the preferred full-fidelity path when Google credentials are configured, because it converts the sheet into FortuneSheet data inside the app.
- The updated UI now treats browser preview as a normal operating mode when backend render is unavailable, instead of presenting it as a hard failure.