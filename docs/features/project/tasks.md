# Feature: Tasks, Hierarchy, Dependencies, And Daily Reports

Last updated: 2026-05-01

## What It Does

- Task CRUD within a project
- Main-task and sub-task hierarchy
- Weighted project progress recalculation
- Daily reports and approval flow
- Task dependencies

## How It Works

1. `frontend/src/pages/ProjectDetail.tsx` loads tasks for the selected project.
2. The task tree is represented by `parent_task_id`: `NULL` means main task, non-null means sub-task.
3. `services/workspace/domains/task/service.py` recalculates project progress after task changes.
4. Only the project lead can create tasks.
5. Only the assigned user can submit reports.
6. Only the project lead can approve reports.
7. Task dependencies are stored separately and reattached to task responses.

## Frontend Files

- `frontend/src/pages/ProjectDetail.tsx`

## Backend Files

- `services/workspace/domains/task/router.py`
- `services/workspace/domains/task/service.py`
- `shared/models/task.py`

## Primary Tables

- `tasks`
- `task_reports`
- `task_dependencies`
- `task_assignees`

## Update Notes

- The active product path uses `tasks.assignee_id` for single-assignee ownership.
- `task_assignees` remains in the schema but is not the active UI path.
