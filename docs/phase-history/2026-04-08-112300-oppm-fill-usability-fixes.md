# Phase History: OPPM Fill Usability and Truncation Fixes

## Task

Adjust the default OPPM form behavior so users can fill project data more easily while preventing clipping artifacts after Reset + AI Fill.

## Goal

- Improve usability of the default OPPM view without changing the base template structure.
- Preserve original template merges/borders during AI fill to avoid clipped or split legend blocks.
- Reduce layout breakage when task data is filled into the task grid.
- Ensure AI fill still populates task rows when project tasks are not linked to OPPM objectives.
- Validate touched frontend/backend files with workspace diagnostics.

## Plan

1. Inspect current OPPM preview rendering and fill mapping behavior in the frontend page.
2. Remove clipping-prone merge/border rewrite logic from the fill path and preserve template geometry.
3. Keep task and ownership fills mapped to template rows/columns without structural changes.
4. Run diagnostics and capture verification notes.

## Status

- `Completed` rotated previous tracker into phase history and initialized a new active tracker.
- `Completed` added OPPM view scaling controls (`-`, `%`, `+`) with a default reduced scale for easier template navigation.
- `Completed` applied non-destructive preview scaling via CSS transform wrapper so form geometry stays intact.
- `Completed` replaced clipping-prone border/merge/legend rewrite logic with a safe fill-only pipeline that preserves the template layout after Reset + AI Fill.
- `Completed` kept task and owner values filling into existing template cells without column hiding/merge mutation.
- `Completed` added targeted border clipping + title-row merge tuning for the right-side legend blocks, merging their title columns into one span while preserving existing row heights and column widths.
- `Completed` tightened owner-label detection so right-side legend labels are no longer treated as owner name placeholders.
- `Completed` enhanced data fitting with merge-aware text capacity estimation so header values, owner names, and task text stay inside visible cell width.
- `Completed` limited task filling to the template task area and added an overflow summary row (e.g. `+N more tasks`) instead of spilling into lower sections.
- `Completed` added backend fallback mapping in AI fill so unlinked project tasks (no `oppm_objective_id`) are distributed into OPPM sub-task rows.
- `Completed` added synthetic fallback main rows (`Task Group N`) when objective rows are fewer than four and unlinked tasks still exist.
- `Completed` fixed formatting and column distribution bugs where task titles would be clipped under merged boundaries or offset by remaining placeholder texts.
- `Completed` validated touched files with workspace diagnostics.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `frontend/src/pages/OPPMView.tsx`
- `services/ai/services/oppm_fill_service.py`

## Verification

- Workspace diagnostics reported no errors in:
	- `frontend/src/pages/OPPMView.tsx`
	- `services/ai/services/oppm_fill_service.py`
	- `docs/PHASE-TRACKER.md`

## Notes

- User request is focused on making the default form easier to use during fill while avoiding major form breakage.
- Scope for this task is frontend preview behavior in the OPPM view.
- Scaling defaults to 90% on load and can be adjusted between 75% and 100% from the toolbar.
- Root cause for clipping was template-structure mutation during fill (merge filtering, border clipping, and manual legend rebuild), not sheet zoom.
- The current implementation now leaves template geometry untouched and only updates text/symbol values.
- The latest tuning applies merge/border edits only to detected legend title rows (`Priority`, `Project Identity Symbol`) and redraws their outer borders without changing `columnlen` or `rowlen`.
- Fitting now uses a width-based approximation derived from column widths and merge spans, then truncates with `...` when needed.
- Timeline symbols and owner priorities now align with the same visible task rows used for fitted task titles.
- Root cause of the new "task not fill" report was backend task selection relying on objective-linked tasks; projects with board-created tasks lacking `oppm_objective_id` returned sparse task rows.
