# Phase Tracker

## Task

Build the OPPM view from scratch (no bundled XLSX fallback) and deliver milestone 1 as the black border skeleton: outer frame plus key internal dividers.

## Goal

- Stop relying on `OPPM Template (1).xlsx` for initial OPPM rendering.
- Generate a FortuneSheet sheet model in code.
- Render exact black border geometry for the first milestone:
  - Main outer frame
  - Key internal vertical and horizontal divider lines
  - Right-side legend border blocks
- Keep existing saved `sheet_data` behavior intact.

## Plan

1. Add a frontend sheet builder utility that returns a baseline FortuneSheet sheet with structural borders.
2. Replace default-template auto-load in `OPPMView` with generated baseline when no spreadsheet is stored.
3. Keep reset behavior deterministic by resetting to the generated baseline snapshot.
4. Temporarily gate AI Fill on generated-border-only sheets to avoid incorrect content injection before landmarks are added.
5. Validate TypeScript diagnostics for touched frontend files.

## Status

- `Completed` archived previous tracker into phase history.
- `Completed` added `frontend/src/lib/oppmSheetBuilder.ts` with cell-level black border scaffold generation.
- `Completed` replaced bundled XLSX fallback with generated baseline in `OPPMView` when no `sheet_data` exists.
- `Completed` wired reset baseline to generated/stored snapshot and gated AI Fill for generated border-only sheets.
- `Completed` fixed an existing TypeScript narrowing issue in the Sub objective merge loop (`subObjectiveCol`/`subObjectiveEndCol`).
- `Completed` ran frontend type-check and verified no diagnostics in touched frontend files.
- `Completed` tuned border coordinates for the lower Project Completed By / Owner-Priority section: extended the main frame to row 37 and added lower divider lines for the people-count and rotated header band.
- `Completed` bumped generated layout marker to `border-v2` and added auto-upgrade logic for previously generated `border-v1` sheets.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `frontend/src/lib/oppmSheetBuilder.ts`
- `frontend/src/pages/OPPMView.tsx`

## Verification

- `Completed` `cd frontend && npx tsc -b`
- `Completed` workspace diagnostics: no errors in `frontend/src/lib/oppmSheetBuilder.ts` and `frontend/src/pages/OPPMView.tsx`.
- Pending manual browser checks for border coordinates and persisted reload behavior.

## Notes

- FortuneSheet border rendering remains cell-level (`config.borderInfo` with `rangeType: "cell"`) to avoid range-border clipping issues.
- This phase intentionally excludes full text/merge parity with the uploaded template.
