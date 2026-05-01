# Feature: Projects And Project Membership

Last updated: 2026-05-01

## What It Does

- Project list, create, update, delete
- Project metadata such as code, objective summary, budget, dates, and lead
- Project membership assignment

## How It Works

1. `frontend/src/pages/Projects.tsx` loads workspace projects and workspace members.
2. On create, the page posts the project first and then best-effort posts selected member assignments.
3. `services/workspace/domains/project/service.py` automatically adds the creator's workspace membership as the project `lead` member.
4. Project detail and OPPM routes use the project id as the feature anchor.

## Frontend Files

- `frontend/src/pages/Projects.tsx`
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/OPPMView.tsx`

## Backend Files

- `services/workspace/domains/project/router.py`
- `services/workspace/domains/project/service.py`
- `shared/models/project.py`

## Primary Tables

- `projects`
- `project_members`

## Update Notes

- `projects.lead_id` points to `workspace_members.id`.
- The `user_id` field in the project-member add payload is a naming mismatch; the actual working value is a workspace member id.
