# Feature: Projects And Project Membership

Last updated: 2026-05-13

## What It Does

- Project list, create, update, delete
- Project metadata such as code, objective summary, deliverable output, methodology, budget, dates, and lead
- Project membership assignment

## How It Works

1. `frontend/src/pages/Projects.tsx` loads workspace projects and workspace members.
2. `frontend/src/pages/projects/CreateProjectModal.tsx` now drives create through a four-step wizard: brief, plan, team, and review.
3. The create flow collects the database-backed planning fields that matter at project setup time: title, code, objective summary, `deliverable_output`, methodology, status, priority, dates, budget, planning hours, and explicit lead.
4. `frontend/src/pages/projects/EditProjectModal.tsx` mirrors that planning shell for updates, including methodology and `deliverable_output`, and applies the same date-order validation before submit.
5. On create, the page posts the project first, then posts additional member assignments for non-lead roles.
6. `services/workspace/domains/project/service.py` now validates date chronology, honors explicit `lead_id`, keeps the creator on the project, and prevents conflicting lead membership behavior.
7. Successful create routes users into the methodology-specific destination: OPPM, Agile, Waterfall, or the hybrid project hub.

## Frontend Files

- `frontend/src/pages/Projects.tsx`
- `frontend/src/pages/projects/CreateProjectModal.tsx`
- `frontend/src/pages/projects/EditProjectModal.tsx`
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
- `projects.methodology` controls the immediate post-create destination.
- `projects.deliverable_output` is collected during create and can be refined again through edit.
- The creator is still kept on the project if lead ownership is reassigned during create.
- The `user_id` field in the project-member add payload is a naming mismatch; the actual working value is a workspace member id.
