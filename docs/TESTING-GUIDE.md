# Testing Guide

Last updated: 2026-04-06

## Purpose

This guide documents the test and verification paths that actually exist in the repository today.

It covers three levels:

1. fast local checks
2. scripted API and integration checks
3. manual product smoke tests

## Test Inventory

Current test assets in the repo:

- `frontend/package.json`
  - `npm run lint`
  - `npm run build`
- `services/core/tests/test_auth_enforcement.py`
  - focused auth and workspace-membership enforcement test
- `test_api.ps1`
  - host-driven smoke suite through the gateway at `http://localhost:8080/api`
- `test_integration.py`
  - container-network integration smoke script against service hostnames

## Recommended Verification Order

1. run frontend lint and build
2. run targeted backend tests
3. run the gateway API smoke script
4. manually verify the feature area you changed

## Preconditions

### Native Development

Start the services you need:

```powershell
.\start_core.ps1
.\start_ai.ps1
.\start_git.ps1
.\start_mcp.ps1
.\start_gateway.ps1
cd frontend
npm run dev
```

### Docker Development

```powershell
docker compose -f docker-compose.microservices.yml up --build
```

## Fast Checks

### Frontend Lint

```powershell
cd frontend
npm run lint
```

Use this after frontend edits.

### Frontend Build

```powershell
cd frontend
npm run build
```

Use this after frontend edits that might affect route wiring, types, imports, or JSX.

### Core Backend Test

From the repository root:

```powershell
pytest services/core/tests/test_auth_enforcement.py
```

What it is meant to validate:

- unauthenticated requests return `401`
- workspace-scoped endpoints reject authenticated users who are not workspace members

## Scripted Smoke Tests

### Gateway API Smoke Suite

Run from the repository root:

```powershell
.\test_api.ps1
```

What it does:

- signs up or logs in a test user
- exercises auth endpoints
- creates a workspace
- exercises projects, tasks, OPPM, notifications, AI, MCP, and read-only Git routes
- cleans up created data at the end

Important note:

- AI chat endpoints treat `400` or `502` as `SKIP` if no active LLM is available
- this script expects the gateway on `http://localhost:8080`

### Container-Network Integration Script

```powershell
python test_integration.py
```

What it does:

- checks direct service health endpoints
- checks basic auth rejection behavior

Important note:

- this script uses service hostnames like `http://core:8000`
- run it in a Docker/container network context where those names resolve

## Manual Smoke Tests

These are the most useful feature-level checks after code changes.

### 1. Auth

Steps:

1. open `/login`
2. sign up a new account or log in with an existing one
3. reload the page
4. verify you remain authenticated
5. sign out

Expected:

- login succeeds
- refresh survives reload
- signout clears access
- protected routes redirect to `/login` after signout

### 2. Workspace Creation And Selection

Steps:

1. create a new workspace
2. confirm it becomes the selected workspace
3. reload the app
4. switch between available workspaces if more than one exists

Expected:

- workspace appears in selector
- persisted workspace remains selected after reload if still accessible
- all page data updates when workspace changes

### 3. Invite Preview And Acceptance

Steps:

1. open Settings -> Members
2. create an invite for a test email
3. open the invite link in a private window or second session
4. verify preview information renders before login
5. authenticate and accept the invite

Expected:

- preview shows workspace name, role, expiry state, and member count
- acceptance adds the user to the workspace
- workspace appears in the invited user's workspace list

### 4. Team And Member Skills

Steps:

1. open `/team`
2. add one or more skills to your own member record
3. if you are admin, add or remove a skill for another member

Expected:

- skill chips render with correct level styling
- self-management works for own skills
- admin can manage other members' skills
- viewer/member restrictions behave correctly for users without admin rights

### 5. Project Creation Wizard

Steps:

1. open `/projects`
2. create a project through the two-step wizard
3. include project code, objective summary, dates, budget, and planning hours
4. optionally assign team members on step two

Expected:

- project is created
- creator is included as project lead
- assigned members appear in project member list if team step was used
- project detail page opens correctly

### 6. Task Management

Steps:

1. open a project detail page as the project lead
2. create tasks with different priorities and statuses
3. assign a workspace member as owner
4. move tasks across statuses
5. edit and delete a task
6. switch to a non-lead member and verify the Create Task button is hidden

Expected:

- only project leads can create tasks (non-leads see no create button)
- task list updates without full reload
- progress and summary cards update
- assignee name displays correctly
- board and list modes stay consistent

### 7. Task Daily Reports And Approvals

Steps:

1. as a task assignee, submit a daily report on an assigned task
2. as a non-assignee, verify you cannot submit a report (403)
3. as the project lead, approve the report
4. as the project lead, revoke the approval
5. verify non-lead members cannot approve/revoke
6. delete a report

Expected:

- only the assigned user can submit reports
- only project leads can approve/revoke
- approval state updates in real-time without page refresh
- `is_approved`, `approved_by`, and `approved_at` update correctly
- non-authorized actions return 403

### 8. OPPM View

Steps:

1. open `/projects/:id/oppm`
2. create objectives with different A/B/C priorities
3. assign owners to objectives
4. verify tasks auto-fill from linked tasks per objective
5. create or update timeline entries
6. create cost rows
7. verify the X-diagram summary, deliverables, and risk register
8. verify cost bar charts show planned vs actual
9. refresh the page

Expected:

- objectives, timeline, and cost rows persist
- A/B/C priority toggles update correctly
- owner badges display workspace member names
- timeline uses weekly `week_start` dates with SVG status dots
- cost bar charts render planned and actual amounts
- changes remain visible after refresh

### 9. AI Model Configuration

Steps:

1. open Settings -> AI Models
2. add an AI model configuration
3. toggle it active/inactive
4. delete it

Expected:

- model rows persist per workspace
- only allowed providers are accepted
- toggling updates `is_active`

### 10. AI Chat And Weekly Summary

Steps:

1. open workspace chat from the floating button
2. ask a workspace-level question
3. open a project page and ask a project-level question
4. open OPPM or project detail and trigger weekly summary if available

Expected:

- chat context changes between workspace and project views
- messages clear when switching context
- weekly summary returns a response when an active model is available

### 11. Reindex And RAG

Steps:

1. trigger workspace reindex from the AI settings flow
2. wait for completion
3. call the RAG-backed feature path or use API smoke checks

Expected:

- reindex returns a total indexed count
- RAG queries return context and sources

### 12. GitHub Integration

Steps:

1. add a GitHub account in Settings
2. configure a repo against a project
3. send a real or test GitHub push webhook
4. open the Commits view

Expected:

- repo config persists
- webhook rejects invalid signatures
- valid push events are accepted quickly
- commits and analyses appear after background processing

### 13. Notifications

Steps:

1. create activity that should emit notifications
2. open notification UI or call the notifications endpoints
3. mark one notification read
4. mark all read

Expected:

- unread count changes correctly
- read state persists

## Regression Focus Areas

After any change in these areas, run extra checks:

- auth and token refresh
- workspace role enforcement
- invite acceptance
- project member assignment
- task reports approval
- gateway routing to AI, Git, and MCP services
- webhook-to-analysis handoff

## Known Fragile Areas

These are the highest-value areas for manual verification because contract drift has existed here recently:

- workspace role field naming between backend and frontend
- project member add payload naming
- task assignment behavior versus legacy `task_assignees` expectations
- gateway route parity between Python and nginx implementations

## When To Update This Guide

Update this file whenever you:

- add or remove an endpoint
- change a request or response contract
- add a new admin-only flow
- change a major page workflow
- add a new smoke script or automated test
