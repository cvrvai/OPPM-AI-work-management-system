# Phase Tracker

## Task

Copy the target OPPM section part-by-part and make row/column slots scale up/down based on actual data volume.

## Goal

- Rebuild the shown OPPM area to visually match the reference section first.
- Add data-driven compaction so slot grids can shrink from 5 template slots to 1-2 slots when data volume is low.
- Keep the page in scaffold mode (no legacy feature workflows) while iterating layout.

## Plan

1. Extend the scaffold builder to render the requested top/task section with labels and borders closer to the reference.
2. Implement scalable slot partitioning helpers for columns and rows.
3. Apply compaction to sub-objective columns, owner columns, and task rows based on provided data counts.
4. Wire `OPPMView` to call the new builder with sample data (still scaffold-only mode).
5. Validate diagnostics and record verification.

## Status

- `In Progress` archived previous tracker into phase history.
- `Pending` implement scalable section builder.
- `Pending` wire page to new part-by-part scaffold generation.
- `Pending` validate diagnostics.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `frontend/src/lib/oppmSheetBuilder.ts`
- `frontend/src/pages/OPPMView.tsx`

## Verification

- Pending workspace diagnostics for touched files.

## Notes

- This phase focuses only on the shown section and scalable slot behavior; other OPPM areas can be added in subsequent passes.
