# Current Phase Tracker

# Phase Tracker

## Task

Implement the Sub-objective column mapping and vertical merging in the FortuneSheet OPPM form rendering.

## Goal

- Correctly map backend main objectives (`!task.is_sub`) to the dedicated "Sub objective" column.
- Map child sub-tasks to the "Major Tasks" column with proper numbering.
- Apply vertical cell merges dynamically in the `config.merge` schema to span all child tasks of an objective.
- Prevent over-writing or clipping inside the grid.

## Plan

1. During template probing, locate the `^Sub objective` header and record its column range.
2. Group the linear `taskRows` array back into hierarchical blocks (Main Task + its Sub-tasks).
3. For each group, write the Main Task title to `subObjectiveCol` and set its `rowspan` to `children.length + 1`.
4. Add the `mc` (merge configuration) cleanly to the anchor and its covered cells.
5. Write the Sub-tasks directly to `taskCol`/`mainTaskCol` on their respective rows.
6. Ensure existing cell boundaries don't scramble if the Sub-objective column doesn't exist (fallback to old behavior).

## Status

- `Completed` rotated tracker.
- `Completed` detected the Sub objective header and inferred its usable column span.
- `Completed` grouped task rows into objective blocks (`main + children`) before rendering.
- `Completed` mapped main objective titles into Sub objective merged blocks when child rows exist.
- `Completed` preserved fallback behavior: when no Sub objective area exists (or no child rows), main titles stay in Major Tasks.
- `Completed` applied merge anchors/pointers (`config.merge` + `mc`) while clearing stale overlapping merges in the Sub objective task zone.
- `Completed` kept task numbering in the index column and task text in Major Tasks rows.
- `Completed` improved index-column detection so numbering uses the left index column even when placeholder text has changed.
- `Completed` normalized numbering semantics: main tasks use integer indices (`1.`), sub-tasks use decimal indices (`1.1`, `1.2`, ...).
- `Completed` validated TypeScript diagnostics for the touched frontend file.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `frontend/src/pages/OPPMView.tsx`

## Verification
- Workspace diagnostics: no errors in `frontend/src/pages/OPPMView.tsx`.
- Runtime visual validation pending in browser with the user's template and AI Fill action.
