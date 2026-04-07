# Phase Tracker

Last updated: 2026-04-07

## Task

Finish the phase-tracker workflow by switching history files from timestamp-only names to timestamp-plus-task-slug names.

## Goal

- Keep the active tracker workflow already added to the repo.
- Improve archive readability with `YYYY-MM-DD-HHMMSS-task-slug.md` filenames.
- Rename the existing archived tracker to a readable slugged filename.
- Update all workflow guidance to use the new naming format.

## Plan

1. Rename the existing archived tracker to include a task slug.
2. Update archive guidance in the history README.
3. Update the custom agent and workspace instructions to require slugged archive names.
4. Validate the updated markdown files.

## Status

- `Completed` existing archived tracker renamed to `docs/phase-history/2026-04-07-135310-phase-tracker-workflow.md`.
- `Completed` history README updated with the slugged archive format.
- `Completed` custom phase-tracker agent and workspace instructions updated.
- `Completed` final validation.

## Files Expected

- `.github/agents/phase-tracker-implementer.agent.md`
- `.github/copilot-instructions.md`
- `docs/PHASE-TRACKER.md`
- `docs/phase-history/README.md`
- `docs/phase-history/2026-04-07-135310-phase-tracker-workflow.md`

## Verification

- Markdown validation passed for the updated agent, workspace instructions, active tracker, history README, and renamed archived tracker.

## Notes

- `docs/PHASE-TRACKER.md` is now the active task tracker.
- Archived tracker files belong only in `docs/phase-history/`.
- Archive names should now use `YYYY-MM-DD-HHMMSS-task-slug.md`.