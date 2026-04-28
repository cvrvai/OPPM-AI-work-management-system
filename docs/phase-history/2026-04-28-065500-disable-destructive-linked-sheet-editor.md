# Current Phase Tracker

## Task
Disable destructive linked Google Sheet in-app editing

## Goal
Stop linked OPPM sheets from being edited through the lossy in-app Fortune save path, and switch the page to a direct Google Sheets editing flow where clicking the visible form opens the real linked spreadsheet.

## Plan

### Phase 1: Confirm the destructive path
- [x] Verify the current save flow rebuilds a new spreadsheet from Fortune cell values only
- [x] Verify this strips the original form structure when saved back to Google Sheets

### Phase 2: Replace the interaction model
- [x] Remove linked-sheet in-app save/edit UI from the OPPM page
- [x] Make linked-sheet preview open the real Google Sheet editor directly
- [x] Disable the backend linked-sheet save endpoint so stale clients cannot trigger it

### Phase 3: Validate
- [x] Run focused frontend and backend validation after the change
- [x] Re-check the live OPPM page output and interaction in the authenticated browser session

## Status
Completed and validated.

## Expected Files
- frontend/src/pages/OPPMView.tsx
- services/core/routers/v1/oppm.py
- services/core/services/google_sheets_service.py
- services/core/schemas/google_sheets.py
- docs/oppm/google-sheets-linked-form.md
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npm run build`
- Live page check on `http://localhost:5173/projects/300aa577-1281-4dd0-ab9f-50032edf13b1/oppm`
- Authenticated browser fetch to `POST /api/v1/workspaces/77f3feae-8994-4e06-b39a-cf5df40ff0f3/projects/300aa577-1281-4dd0-ab9f-50032edf13b1/oppm/google-sheet/save` returning `409`

## Notes
- The current backend save path converts Fortune JSON to a brand-new XLSX workbook and uploads it over the linked Google Sheet file, which destroys merges, layout, formulas, and other sheet structure.
- Direct editing should happen in the real Google Sheet, not through a lossy workbook conversion layer.
- For linked sheets, the app should act as a launcher and live preview, not as a second spreadsheet engine.
- The live OPPM page now shows `Edit in Google Sheets` plus a click-to-edit preview overlay instead of the in-app save/editor controls for linked sheets.