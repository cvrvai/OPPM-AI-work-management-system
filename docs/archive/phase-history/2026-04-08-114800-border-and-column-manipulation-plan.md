# Current Phase Tracker

# Phase Tracker

## Task

Plan and document the algorithm for manipulating borders, merges, and columns in the OPPM form.

## Goal

- Design a safe and predictable way to adjust the FortuneSheet `.xlsx` layout dynamically.
- Support new functional areas like the "Sub objective" vertical groupings or dynamic resizing of legend blocks.
- Prevent layout breaking when modifying `borderInfo` or `merge` configurations.

## Plan

1. Document the FortuneSheet schemas for `config.columnlen`, `config.colhidden`, `config.merge`, and `config.borderInfo`.
2. Define standard utility patterns for mutating cell borders without destroying overlapping ranges.
3. Design a safe merge/unmerge approach.
4. Record these strategies in `docs/OPPM-ARCHITECTURE.md`.

## Status

- `Completed` rotated tracker.
- `In Progress` writing border/column manipulation plan into architecture docs.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `docs/OPPM-ARCHITECTURE.md`

## Verification
- N/A - Documentation only

## Notes
- `borderInfo` in FortuneSheet is fragile; writing exact cell bounds `(l, r, t, b)` is safer than mutating large `border-all` ranges.
