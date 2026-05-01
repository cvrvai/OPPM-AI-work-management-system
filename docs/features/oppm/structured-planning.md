# Feature: Structured OPPM Planning Data

Last updated: 2026-05-01

## What It Does

- OPPM objective list
- Sub-objectives
- Task-to-sub-objective links
- A/B/C owner assignment
- Weekly timeline entries
- Costs, deliverables, forecasts, and risks

## How It Works

1. Core OPPM routes under `services/workspace/domains/oppm/router.py` expose the structured OPPM data model.
2. Objectives are project-scoped and ordered by `sort_order`.
3. Sub-objectives are a separate project-scoped list with positions `1..6`.
4. Tasks can be linked to multiple sub-objectives.
5. A/B/C ownership is stored in `task_owners` using workspace member ids.
6. Timeline rows link tasks to week starts and status/quality fields.
7. Costs, deliverables, forecasts, and risks are maintained as separate OPPM collections.

## Frontend Files

- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/components/ChatPanel.tsx`

## Backend Files

- `services/workspace/domains/oppm/router.py`
- `services/workspace/domains/oppm/service.py`
- `shared/models/oppm.py`
- `shared/models/task.py`

## Primary Tables

- `oppm_objectives`
- `oppm_sub_objectives`
- `task_sub_objectives`
- `task_owners`
- `oppm_timeline_entries`
- `project_costs`
- `oppm_deliverables`
- `oppm_forecasts`
- `oppm_risks`

## Update Notes

- This is the structured OPPM layer that the API and analytics use.
- It coexists with the spreadsheet layer described in [`spreadsheet-rendering.md`](spreadsheet-rendering.md).
