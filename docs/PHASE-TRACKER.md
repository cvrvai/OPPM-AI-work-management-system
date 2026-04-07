# Current Phase Tracker

# Phase Tracker

## Task

Fix the OPPM workbook layout so the Owner / Priority area, the Project Completed By header region, and the Project Identity Symbol area align with the classic template.

## Goal

- Restore the classic right-side OPPM layout in generated workbooks.
- Use project-scoped member data for owner columns instead of all workspace members.
- Respect saved OPPM header values where the workbook expects custom text.
- Validate that the frontend and backend still type-check after the changes.

## Plan

1. Inspect the export data assembly and workbook layout constants for the broken right-side sections.
2. Update the exporter to use fixed classic-layout dimensions and populate the right-side legend blocks correctly.
3. Pass OPPM header data and project-scoped members into the export payload.
4. Run targeted validation on the touched files and record any residual gaps.

## Status

- `Completed` inspected the OPPM frontend fill logic and backend exporter.
- `Completed` expanded the AI fill payload with project member ids, owner priorities, timeline entries, and saved OPPM header values.
- `Completed` updated the preview to fill the Project Completed By header, owner A/B/C cells, and timeline identity symbols from live project data.
- `Completed` updated export data assembly to include project-scoped members and saved OPPM header values.
- `Completed` added an assignee-based fallback so Owner / Priority cells fill even when explicit `task_owners` A/B/C records do not exist yet.
- `Completed` added a task-status fallback so Project Identity Symbols use `□` for todo/start, `●` for in-progress, and `■` for completed when no timeline rows exist.
- `Completed` changed Owner / Priority letters to render as plain text instead of colored A/B/C blocks in both the preview and export.
- `Completed` minimized unused owner/member columns in the live OPPM preview so the Owner / Priority area scales down without disappearing.
- `Completed` resized the remaining owner/member columns so the section scales down without truncating the Owner / Priority header when only a few members are present.
- `Completed` replaced the preview-only width hack with real owner-column compaction so the black closing border, Priority box, and Project Identity Symbol box shift left cleanly.
- `Completed` added explicit Left and Right controls in the OPPM top bar so users can horizontally move the FortuneSheet view without relying on the bottom scrollbar.
- `Completed` adjusted preview compaction so non-owner legend text inside removed owner columns is preserved and remapped, restoring the missing Priority and Project Identity Symbol labels.
- `Completed` validated the touched frontend and backend files with the workspace diagnostics tool.

## Files Expected

- `docs/PHASE-TRACKER.md`
- `frontend/src/pages/OPPMView.tsx`
- `services/ai/schemas/oppm_fill.py`
- `services/ai/services/oppm_fill_service.py`
- `services/core/exports/oppm_exporter.py`
- `services/core/services/oppm_service.py`

## Verification

- Workspace diagnostics reported no errors in:
	- `frontend/src/pages/OPPMView.tsx`
	- `services/ai/schemas/oppm_fill.py`
	- `services/ai/services/oppm_fill_service.py`
	- `services/core/services/oppm_service.py`
	- `services/core/exports/oppm_exporter.py`
	- `docs/PHASE-TRACKER.md`

## Notes

- The preview path now uses richer AI fill data so the right-side Owner / Priority and Project Identity Symbol sections can populate from the database.
- The exporter now reads `completed_by_text`, `people_count`, and project-scoped member data, but its overall sheet geometry is still a generated layout rather than a full clone of the bundled Excel template.
- Root cause for the blank Owner / Priority grid: the Priority legend was being derived from project members, but the task grid itself only looked at `task_owners` rows, and the current frontend does not save those rows anywhere.
- Root cause for the misleading Project Identity Symbol fallback: tasks without timeline rows were previously rendered as completed markers only, regardless of their actual task status.
- Owner / Priority letters now inherit the row background and render as plain black text instead of blue highlight blocks.
- The live preview now minimizes unused owner/member columns by updating the sheet config, while the export path already used the actual project member count.
- The remaining visible owner/member columns are now widened proportionally when the member count is small, so the section is reduced without looking cut off.
- The live preview now removes extra owner columns structurally and remaps the right-side merged panels left, which avoids the cramped look from the earlier minimized-column approach.
- The OPPM page now exposes explicit horizontal navigation buttons that call FortuneSheet's built-in scroll API, because the view previously relied only on the internal sheet scrollbar.
- The preview compaction now keeps non-owner text cells that sit inside removed owner columns, which avoids deleting the static Priority and Project Identity Symbol legend labels during the left-shift.
