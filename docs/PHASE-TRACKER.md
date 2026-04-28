# Current Phase Tracker

## Task
Embed live Google Sheets editing in the OPPM page

## Goal
Keep linked OPPM sheets editable inside the website by embedding the real Google Sheets editor in the page, while still avoiding the destructive in-app save-back path.

## Plan

### Phase 1: Confirm editor embedding is feasible
- [x] Verify the real Google Sheets edit URL can load inside the page iframe
- [x] Confirm this gives website-side editing with Google-backed real-time persistence

### Phase 2: Switch the linked-sheet surface
- [x] Replace preview-mode linked-sheet iframe URLs with edit-mode URLs
- [x] Remove the click-through overlay so users can edit directly inside the website
- [x] Keep the backend destructive save endpoint disabled

### Phase 3: Validate
- [x] Run focused frontend validation after the iframe change
- [x] Re-check the live OPPM page to confirm the embedded editor is interactive

## Status
Completed and validated.

## Expected Files
- frontend/src/pages/OPPMView.tsx
- docs/oppm/google-sheets-linked-form.md
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npm run build`
- Live page check on `http://localhost:5173/projects/300aa577-1281-4dd0-ab9f-50032edf13b1/oppm`

## Notes
- The Google Sheets edit URL was verified to load in the page iframe from the live OPPM route.
- This satisfies the user requirement more directly than click-through launch behavior because editing stays inside the website while Google Sheets remains the source of truth.
- The destructive custom save-back route remains disabled to protect the original form structure.
- The live OPPM page now renders the embedded Google Sheets editor directly in the iframe and no longer depends on a click-through overlay for linked-sheet editing.