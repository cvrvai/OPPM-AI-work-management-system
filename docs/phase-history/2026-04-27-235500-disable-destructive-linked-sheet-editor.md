# Current Phase Tracker

## Task
Keep linked Google Sheets on browser preview until edit mode

## Goal
Stop the OPPM page from auto-rendering linked Google Sheets through the Fortune workbook path in browse mode, so users see the stable Google browser preview until they explicitly click `Edit in App`.

## Plan

### Phase 1: Trace the browse-mode render path
- [x] Confirm the linked-sheet effect auto-loads XLSX in normal browse mode
- [x] Verify the non-edit render tree falls through to the Fortune `Workbook` when `sheetData` exists

### Phase 2: Patch the preview behavior
- [x] Keep linked sheets in browser preview mode by default
- [x] Reserve Fortune workbook loading/rendering for explicit edit-mode entry

### Phase 3: Validate
- [x] Run a focused frontend build after the OPPM page change
- [ ] Re-check the live OPPM page output after the patch when tooling allows

## Status
Code patched and build-validated. Authenticated live-page confirmation is still limited by the available browser tooling.

## Expected Files
- frontend/src/pages/OPPMView.tsx
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npm run build`
- Live page check on `http://localhost:5173/projects/300aa577-1281-4dd0-ab9f-50032edf13b1/oppm`

## Notes
- The current page visibly shows a malformed in-app workbook state (`A1:NaN`) while the top-right button still says `Edit in App`, which means browse mode is incorrectly falling through to the Fortune renderer.
- `frontend/src/pages/OPPMView.tsx` currently sets `sheetLoadState('ready')` after any successful XLSX-to-Fortune transform, even outside edit mode.
- The safer default is the browser preview iframe; the Fortune workbook should only be opened when the user explicitly asks to edit.
- A focused frontend build passed after the patch.
- The attachment-backed browser screenshot did not provide a reliable post-patch authenticated rerender path, so a manual page refresh is still needed to confirm the visual result in-session.