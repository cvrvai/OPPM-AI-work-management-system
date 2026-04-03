# OPPM AI — Feature Testing & Self-Audit Guide

This guide walks you through **every feature** in the OPPM AI Work Management System. Follow each section to confirm the feature works as expected, or to diagnose what is missing.

> **Prerequisites**: All 5 services are running (core:8000, ai:8001, git:8002, mcp:8003, gateway:8080) and the frontend dev server is running on http://localhost:5173.

---

## Table of Contents

1. [Authentication & Registration](#1-authentication--registration)
2. [Workspaces & Members](#2-workspaces--members)
3. [Projects](#3-projects)
4. [OPPM Board (Objectives, Timeline, Costs)](#4-oppm-board-objectives-timeline-costs)
5. [Tasks & Assignees](#5-tasks--assignees)
6. [GitHub Integration](#6-github-integration)
7. [AI Chat & Weekly Summary](#7-ai-chat--weekly-summary)
8. [Notifications](#8-notifications)
9. [Settings & API Keys](#9-settings--api-keys)
10. [Demo Industry Data (seed_demo.ps1)](#10-demo-industry-data)
11. [API Health via Terminal](#11-api-health-via-terminal)

---

## 1. Authentication & Registration

### Register a new account
1. Open http://localhost:5173
2. You should be redirected to `/login`
3. Click **"Sign up"** (or navigate to the register page)
4. Enter email, password (min 8 chars), display name
5. Click **Register**

✓ **Expected**: Redirected to dashboard or workspace selection  
✗ **Failure**: 422 Unprocessable Entity → check password length; 409 Conflict → email already registered

### Log in
1. Go to http://localhost:5173/login
2. Enter credentials and click **Login**

✓ **Expected**: JWT stored, redirected to `/dashboard`  
✗ **Failure**: 401 Unauthorized → wrong credentials; network error → check gateway (port 8080)

### Log out
1. Click user avatar / name in sidebar
2. Click **Sign out**

✓ **Expected**: Redirected to `/login`, JWT cleared from localStorage  

---

## 2. Workspaces & Members

### Create a workspace
1. After login, click **"Create Workspace"** on the workspace selector
2. Enter name and description, submit

✓ **Expected**: Workspace appears in dropdown; you are `owner` role  
✗ **Failure**: 400 name required; 500 → check core service logs

### Switch workspaces
1. Click the workspace name in the top-left menu
2. Select a different workspace from the dropdown

✓ **Expected**: All project/notification data reloads for the selected workspace

### Invite a member
1. Navigate to **Settings** → **Members**
2. Enter an email address and choose a role (member / admin)
3. Click **Send Invite**

✓ **Expected**: Invite row appears with status `pending`; email notification queued  
✗ **Failure**: 404 workspace not found → confirm workspace is selected; 422 → invalid email

### Accept an invite
1. Copy the invite token from the `workspace_invites` table (or from the invite email)
2. Navigate to `http://localhost:5173/invite/accept?token=<TOKEN>`

✓ **Expected**: User joined workspace, redirect to dashboard  
✗ **Failure**: 404 invite not found → token expired or already used

### View members list
1. Go to **Settings** → **Members**

✓ **Expected**: Table lists all members with role, join date  

### Remove a member (admin only)
1. In Members table, click the trash icon next to a member row (admin role required)

✓ **Expected**: Member removed, no longer visible in list; their data remains  

---

## 3. Projects

### Create a project
1. Navigate to **Projects** (sidebar)
2. Click **"New Project"**
3. Fill in title, description, start date, deadline, priority
4. Click Create

✓ **Expected**: Project card appears in grid  
✗ **Failure**: 403 Forbidden → you need `member` or `admin` role in the workspace

### Edit a project
1. On any project card, click the **⋮ kebab menu** (top-right of card)
2. Click **Edit**
3. Change the title, status, or deadline
4. Click **Save Changes**

✓ **Expected**: Card updates immediately without page reload  
✗ **Failure**: Modal doesn't appear → update frontend (this was a recent fix)

### Delete a project
1. On any project card, click the **⋮ kebab menu**
2. Click **Delete**
3. Confirm in the dialog

✓ **Expected**: Project removed from list; all linked objectives, tasks, timeline, and costs are also deleted (cascade)  
✗ **Failure**: 403 → requires `admin` role or project owner

### Search projects
1. Type in the search box on the Projects page

✓ **Expected**: Cards filter in real-time by title (client-side filter)

### Navigate to a project
1. Click anywhere on a project card (excluding the ⋮ menu)

✓ **Expected**: Navigate to `/projects/:id` — Project Detail page

---

## 4. OPPM Board (Objectives, Timeline, Costs)

### Open the OPPM view
1. From the Project Detail page, click **"OPPM View"** button (or navigate to `/projects/:id/oppm`)

✓ **Expected**: Full OPPM spreadsheet with colour columns, timeline dots, cost bar chart

### Add an objective
1. Click the **+ row** at the bottom of the objectives table
2. Type an objective title and press Enter

✓ **Expected**: New row appears with letter A, B, C… counter

### Edit an objective title
1. Click on an objective title cell directly

✓ **Expected**: Inline text editor appears; press Enter or click away to save

### Assign an owner to an objective
1. Click the **Owner/Priority** dropdown cell in an objective row
2. Select a workspace member from the dropdown

✓ **Expected**: Owner name displayed; `owner_id` saved to database  
✗ **Failure**: Dropdown shows only current user → update OPPMView.tsx (this was a recent fix); empty options → no workspace members loaded

### Set timeline status (colour dots)
1. In an objective row, click any week column dot
2. Click repeatedly to cycle through: `planned` (blue) → `in_progress` (yellow) → `completed` (green) → `at_risk` (orange) → `blocked` (red)

✓ **Expected**: Dot colour updates immediately; persisted to backend  
✗ **Failure**: Dot doesn't change → check browser console for 422/500

### Navigate weeks
1. Use the **← / →** arrow buttons above the timeline columns to scroll left/right

✓ **Expected**: Week labels shift; dots for the new date range load

### Edit deliverable text (bottom section)
1. Scroll down to the "Deliverable Output", "Summary Deliverables" rows
2. Click on any cell

✓ **Expected**: `InlineEdit` or `EditableList` editor opens; saves to project `metadata.deliverable_output` / `metadata.summary_deliverables`

### Add a risk with RAG status
1. Find the **"Risks & Issues"** row
2. Click to open the `RiskEditor`
3. Set Red / Amber / Green dot and type risk description
4. Click Save

✓ **Expected**: Risk stored in `project.metadata.risks` array

### Add a project cost
1. Scroll to the Costs section at the bottom of the OPPM board
2. Click **"+ Add Cost"**
3. Enter category, planned amount, actual amount, notes
4. Click Add

✓ **Expected**: New bar chart row appears; totals update

### Edit a cost inline
1. Click on any cost value cell (planned, actual, category, notes)

✓ **Expected**: `InlineEdit` editor appears; saves via `PUT /oppm/costs/:id`

### Delete a cost
1. Click the trash icon on a cost row

✓ **Expected**: Row removed, totals recalculated

---

## 5. Tasks & Assignees

### View tasks on a project
1. Navigate to **Project Detail** (`/projects/:id`)
2. Tasks are shown in the kanban board or list below the project header

✓ **Expected**: Tasks grouped by status (todo / in_progress / done)

### Create a task
1. Click **"+ Add Task"** in a column

✓ **Expected**: Task card appears with title

### Assign a task to a member
1. Open a task
2. Use the assignee picker (shows workspace members)
3. Select a member

✓ **Expected**: Assignee avatar shown on task card; stored in `task_assignees` table

### Update task status
1. Drag a task card between columns (or use the status dropdown in the task edit modal)

✓ **Expected**: Status updates; progress auto-recalculated on parent project

---

## 6. GitHub Integration

### Connect a GitHub account
1. Navigate to **Settings** → **GitHub**
2. Click **"Connect GitHub"** — this will POST to `/v1/workspaces/:id/github/accounts`
3. Enter a Personal Access Token (PAT) with `repo` + `read:org` scopes

✓ **Expected**: GitHub account row appears; username resolved

### Link a repository to a project
1. Go to the project settings or GitHub tab
2. Select a repository from the connected account
3. Link to the project

✓ **Expected**: Repo config saved; webhook endpoint registered

### View commits
1. Navigate to **Commits** page (sidebar)
2. Commits should listed from linked repositories

✓ **Expected**: Commit cards with hash, author, message, timestamp

### Trigger commit analysis (requires AI model)
1. Push a commit to a linked repository (or use a webhook replay tool)
2. The webhook is received at `POST /v1/workspaces/:id/git/webhook`
3. AI analysis runs automatically if an AI model is configured

✓ **Expected**: Commit appears with AI-generated classification (feature/fix/docs/chore) and related task suggestions

---

## 7. AI Chat & Weekly Summary

> **Note**: AI features require an LLM to be configured (Settings → AI Models). Without an LLM, these endpoints return `400 No model available` or `502`.

### Configure an AI model
1. Navigate to **Settings** → **AI Models**
2. Click **"+ Add Model"**
3. Enter provider (ollama/openai/anthropic/kimi), model name, endpoint URL, API key
4. Click Save

✓ **Expected**: Model row appears; test call returns 200

### Chat with the AI assistant
1. Click the **chat FAB** (💬 button, bottom-right of any page)
2. Type a question like: "What is the overall status of this project?"
3. Send

✓ **Expected**: AI response appears with context about the current project or workspace

### Request a weekly summary
1. Send a message: "Give me a weekly summary"  
   OR call `POST /api/v1/workspaces/:id/ai/weekly-summary`

✓ **Expected**: Structured summary of project statuses, objectives progress, and risks  
✗ **Failure**: 400 No model available → configure model first

### Semantic search (RAG)
1. In the chat, ask: "Which projects are at risk?"
2. The AI uses vector embeddings to retrieve and reason over OPPM data

✓ **Expected**: Relevant objectives and projects cited in the response

---

## 8. Notifications

### Receive a notification
Notifications are created automatically when:
- You are invited to a workspace
- A task is assigned to you
- A commit analysis completes on your project

### View notifications
1. Click the bell icon in the top navigation

✓ **Expected**: Dropdown shows unread count badge; list of notification messages

### Mark as read
1. Click a notification

✓ **Expected**: Badge count decrements; notification marked read

### Mark all as read
1. Click **"Mark all as read"** in the notifications panel

✓ **Expected**: All notifications cleared; badge disappears

---

## 9. Settings & API Keys

### Update workspace name / description
1. Navigate to **Settings** → **General**
2. Edit name or description
3. Click Save

✓ **Expected**: Workspace updated; new name visible in sidebar

### Manage AI model configurations
1. Navigate to **Settings** → **AI Models**
2. Add / edit / delete model configurations

✓ **Expected**: Models saved; AI features use the active model

---

## 10. Demo Industry Data

Run the seed script to populate 5 workspaces with real non-software OPPM data:

```powershell
cd "OPPM AI work management system"
.\seed_demo.ps1
```

### Accounts created

| Email | Password | Workspace | Industry |
|---|---|---|---|
| arch@demo.oppm | Demo@12345 | Lakeview Architecture Studio | Architecture & Construction |
| finance@demo.oppm | Demo@12345 | Meridian Capital Management | Finance & Banking |
| health@demo.oppm | Demo@12345 | Metro Health Network | Healthcare |
| mfg@demo.oppm | Demo@12345 | Apex Industrial Solutions | Manufacturing |
| edu@demo.oppm | Demo@12345 | Northgate University | Higher Education |

### Verifying seed data

1. Log in with any demo account at http://localhost:5173
2. Navigate to **Projects** — you should see 2 projects per workspace
3. Open a project and click **OPPM View** — objectives, timeline dots, and costs should all be populated
4. Confirm timelines: completed dots (green) for past phases, in-progress (yellow) for current, planned (blue) for future entries

✓ **Expected per workspace**: 2 projects × 6 objectives × several timeline entries + cost rows

---

## 11. API Health via Terminal

Run these PowerShell checks to verify all services are responding:

```powershell
# Gateway health
Invoke-RestMethod http://localhost:8080/health

# Core service direct
Invoke-RestMethod http://localhost:8000/health

# AI service direct
Invoke-RestMethod http://localhost:8001/health

# Git service direct
Invoke-RestMethod http://localhost:8002/health

# MCP service direct
Invoke-RestMethod http://localhost:8003/health
```

✓ **Expected**: `{ "status": "healthy" }` or `{ "service": "...", "status": "ok" }` from each

### Run the full API test suite

```powershell
cd "OPPM AI work management system"
.\test_api.ps1
```

✓ **Expected**: `48 PASSED / 0 FAILED / 4 SKIP` (AI/LLM tests skipped if no model running)

---

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---|---|---|
| 401 Unauthorized | JWT expired or missing | Log out and log back in |
| 403 Forbidden | Role too low (e.g. viewer tries to write) | Check workspace membership role |
| 404 Not Found | Wrong workspace_id in URL, or resource deleted | Re-select workspace from dropdown |
| 400 No model available | AI endpoint called with no LLM configured | Add a model in Settings → AI Models |
| 502 Bad Gateway | AI or Git service is down | Restart `start_ai.ps1` / `start_git.ps1` |
| OPPM dots not saving | Backend returned 422 | Check `week_start` is `YYYY-MM-DD` format |
| Owner dropdown empty | Workspace members query failed | Check network tab → GET /v1/workspaces/:id/members |
| Projects page shows no edit/delete | Using old frontend | `npm run build` or hot-reload (`npm run dev`) |
