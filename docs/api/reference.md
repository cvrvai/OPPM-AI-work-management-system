# API Reference

Last updated: 2026-04-09

## Purpose

This file is the practical reference for the public HTTP API currently mounted through `/api`.

It documents the routes that are present in code today, grouped by owning service. It also calls out a few current contract quirks where field naming has not yet been fully normalized.

## Conventions

### Base Path

All frontend requests go through the gateway using `/api`.

Examples:

- `/api/auth/login`
- `/api/v1/workspaces/{workspace_id}/projects`
- `/api/v1/git/webhook`

### Authentication

Most routes require:

```http
Authorization: Bearer <access_token>
```

Token behavior:

- access tokens are validated locally by the backend using `JWT_SECRET`
- the frontend retries once on `401` by calling `POST /api/auth/refresh`
- invite preview and GitHub webhook routes do not use bearer auth

### Authorization

Workspace-scoped routes load `WorkspaceContext` from `workspace_members`.

Role rules:

- read: `owner`, `admin`, `member`, `viewer`
- write: `owner`, `admin`, `member`
- admin-only: `owner`, `admin`
- owner-only: `owner`

### Error Shape

Most error responses use:

```json
{ "detail": "message" }
```

### Success Shape

Delete and simple mutation endpoints often return:

```json
{ "ok": true }
```

### Pagination

The current API is not fully uniform yet.

Current patterns in code:

- projects and tasks accept `page` and `page_size`, but return `{ "items": [...], "total": number }`
- notifications return arrays instead of a paginated wrapper
- several list endpoints accept `limit`

Document against the route behavior that exists today, not the older design target.

## Auth Routes (Workspace Service)

Mounted under `/api/auth/*`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/auth/login` | No | Email/password login. Returns access token, refresh token, and user payload. |
| `POST` | `/api/auth/signup` | No | Registers a user. Returns token pair and user payload. |
| `POST` | `/api/auth/refresh` | No | Exchanges refresh token for a new token pair. |
| `POST` | `/api/auth/signout` | Yes | Signs out current user. Refresh tokens are invalidated; access token blacklist behavior depends on backend signout implementation. |
| `GET` | `/api/auth/me` | Yes | Returns current JWT user info. |
| `PATCH` | `/api/auth/profile` | Yes | Updates `full_name` and/or `password`. |
| `GET` | `/api/v1/auth/me` | Yes | Legacy alias that returns the same current-user payload. |

### Example: Login Request

```json
{
  "email": "admin@example.com",
  "password": "Secret123!"
}
```

### Example: Login Response

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "full_name": "Admin User"
  }
}
```

## Workspace Routes (Workspace Service)

Mounted under `/api/v1/`.

### Workspace CRUD

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces` | Yes | Any | Returns workspaces for current user. Current backend response includes `current_user_role`. |
| `POST` | `/api/v1/workspaces` | Yes | Any | Creates a workspace and the creator membership. |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Yes | Member | Returns one workspace. |
| `PUT` | `/api/v1/workspaces/{workspace_id}` | Yes | Admin | Updates workspace metadata. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | Yes | Owner | Deletes the workspace. |

### Members

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/members` | Yes | Member | Lists workspace members. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/members/{member_id}` | Yes | Admin | Updates member role. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/members/{member_id}` | Yes | Admin | Removes a member. |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/members/me/display-name` | Yes | Member | Updates the caller's display name for this workspace only. |
| `GET` | `/api/v1/workspaces/{workspace_id}/members/lookup?email=...` | Yes | Admin | Looks up a user by email for invite and membership flows. |

### Invites

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/invites` | Yes | Admin | Lists pending invites. |
| `POST` | `/api/v1/workspaces/{workspace_id}/invites` | Yes | Admin | Creates an invite. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/invites/{invite_id}` | Yes | Admin | Revokes an invite. |
| `POST` | `/api/v1/workspaces/{workspace_id}/invites/{invite_id}/resend` | Yes | Admin | Resends the invite email. |
| `POST` | `/api/v1/invites/accept` | Yes | Authenticated | Accepts an invite token into the current account. |
| `GET` | `/api/v1/invites/preview/{token}` | No | Public | Returns invite preview metadata. The frontend consumes this from both `/invites/:token` and `/invite/accept/:token`. |

### Member Skills

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/members/{member_id}/skills` | Yes | Member | Lists skills for a workspace member. |
| `POST` | `/api/v1/workspaces/{workspace_id}/members/{member_id}/skills` | Yes | Member | Adds a skill. Members can manage their own skills; admins can manage any member. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/members/{member_id}/skills/{skill_id}` | Yes | Member | Deletes a skill with the same ownership rule as create. |

### Example: Invite Preview Response

The response contract now includes these fields:

```json
{
  "workspace_name": "Acme Workspace",
  "email": "invitee@example.com",
  "role": "member",
  "expires_at": "2026-04-10T12:00:00Z",
  "accepted_at": null,
  "member_count": 7,
  "is_expired": false,
  "is_accepted": false
}
```

## Project Routes (Workspace Service)

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects` | Yes | Member | Query params: `page`, `page_size`, optional `status`. Returns `{ items, total }`. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}` | Yes | Member | Returns one project. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects` | Yes | Write | Creates a project and automatically adds the creator's workspace membership as project `lead`. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}` | Yes | Write | Updates project metadata. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}` | Yes | Write | Deletes the project. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/members` | Yes | Member | Lists project members joined with workspace member info. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/members` | Yes | Write | Adds a project member. See contract note below. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/members/{member_id}` | Yes | Write | Removes a project member. Path parameter is the stored `project_members.member_id` value. |

### Project Fields Used In The Current Product

Important fields on create and update:

- `title`
- `description`
- `project_code`
- `objective_summary`
- `priority`
- `status`
- `budget`
- `planning_hours`
- `start_date`
- `deadline`
- `end_date`
- `lead_id`

### Contract Note: Project Member Add Payload

Current public request schema:

```json
{
  "user_id": "...",
  "role": "contributor"
}
```

Current implementation detail:

- the field is named `user_id`
- the frontend project wizard actually uses `workspace_member.id`
- the backend forwards that value into `project_members.member_id`

Treat this field as a workspace member identifier, even though the public field name says `user_id`.

## Task Routes (Workspace Service)

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/tasks` | Yes | Member | Query params: `project_id`, `status`, `page`, `page_size`. Returns `{ items, total }`. |
| `GET` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}` | Yes | Member | Returns one task. |
| `POST` | `/api/v1/workspaces/{workspace_id}/tasks` | Yes | Write | Creates a task. Only project leads can create tasks. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}` | Yes | Write | Updates a task. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}` | Yes | Write | Deletes a task. |
| `GET` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}/reports` | Yes | Member | Lists daily reports for a task. |
| `POST` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}/reports` | Yes | Member | Creates a daily report entry. Only the task's assignee can submit reports. |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}/reports/{report_id}/approve` | Yes | Write | Approves or revokes approval of a report. Only project leads can approve. Send `{"is_approved": true}` or `{"is_approved": false}`. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/tasks/{task_id}/reports/{report_id}` | Yes | Member | Deletes a report. |

### Task Create/Update Payload

```json
{
  "title": "Kubernetes cluster setup",
  "description": "...",
  "project_id": "uuid",
  "priority": "high",
  "oppm_objective_id": "uuid",
  "assignee_id": "uuid",
  "parent_task_id": "uuid",
  "start_date": "2026-04-01",
  "due_date": "2026-04-15"
}
```

### Current Task Model Notes

- active task statuses are `todo`, `in_progress`, `completed`
- the live product uses `tasks.assignee_id` for single-owner assignment
- `parent_task_id` creates a main-task / sub-task hierarchy (OPPM style)
  - tasks with `parent_task_id = null` are **main tasks**
  - tasks with `parent_task_id = <uuid>` are **sub-tasks** nested under the parent
- the OPPM exporter renders main tasks with bold + grey background and sub-tasks indented underneath
- the database still contains `task_assignees`, but the current frontend and task routes do not use the many-to-many path

## OPPM Routes (Workspace Service)

### Combined OPPM And Spreadsheet Routes

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm` | Yes | Member | Returns the combined OPPM payload for the project, including project metadata, objectives, tasks, members, header, timeline, costs, deliverables, forecasts, risks, and weeks. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/export` | Yes | Member | Exports the current OPPM data as XLSX. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/template` | Yes | Member | Returns a template XLSX for OPPM import or spreadsheet bootstrap workflows. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/import` | Yes | Write | Imports an uploaded XLSX into project OPPM data. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/preview-xlsx` | Yes | Member | Parses an uploaded XLSX into preview JSON without saving. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/import-json` | Yes | Write | Imports structured JSON produced by AI extraction flows. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet` | Yes | Member | Returns saved FortuneSheet JSON for this project, or `404` if no spreadsheet template exists. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet` | Yes | Write | Upserts FortuneSheet JSON for this project. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet` | Yes | Write | Deletes the saved FortuneSheet JSON for this project. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/header` | Yes | Member | Returns OPPM header fields, or `null` if none are stored. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/header` | Yes | Write | Creates or updates OPPM header fields. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/task-items` | Yes | Member | Returns the OPPM task-items tree for this project. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/task-items` | Yes | Write | Full replace of OPPM task-items for the project. |

### Objectives

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives` | Yes | Member |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives` | Yes | Write |
| `PUT` | `/api/v1/workspaces/{workspace_id}/oppm/objectives/{objective_id}` | Yes | Write |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/oppm/objectives/{objective_id}` | Yes | Write |

### Timeline

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline` | Yes | Member | Returns weekly timeline entries. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline` | Yes | Write | Upserts one timeline entry payload. |

### Costs

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/costs` | Yes | Member |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/costs` | Yes | Write |
| `PUT` | `/api/v1/workspaces/{workspace_id}/oppm/costs/{cost_id}` | Yes | Write |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/oppm/costs/{cost_id}` | Yes | Write |

### Google Sheets Linked Form

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet` | Yes | Member | Returns whether a project is linked to a Google Sheet, the linked sheet ID/URL, whether backend Google credentials are configured, and any non-fatal backend configuration warning. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet` | Yes | Write | Stores a Google Sheet URL or spreadsheet ID in project metadata. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet` | Yes | Write | Removes the linked Google Sheet from project metadata. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/push` | Yes | Write | Pushes AI-filled OPPM summary, task, and member data into the linked spreadsheet. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/xlsx` | Yes | Member | Exports the linked Google Sheet as XLSX for in-app FortuneSheet rendering. Requires backend Google credentials and spreadsheet access. |

### OPPM Data Notes

- timeline rows are keyed by `week_start` date, not separate year and month fields
- objective/task linkage is handled through `tasks.oppm_objective_id`
- objectives have an optional `priority` field (single character: `A`, `B`, or `C`)
- costs are project-scoped and tracked independently from tasks
- a linked Google Sheet is stored in `projects.metadata.google_sheet`
- the Google Sheet link-state route should remain readable even when backend Google credentials are missing
- backend Google credentials are required for XLSX export and Push AI Fill, but not for browser preview mode in the frontend
- browser preview mode is a frontend behavior and does not have its own backend route

### Objective Create/Update Fields

- `title` (required on create)
- `owner_id` (workspace member id)
- `priority` (optional, single char: A/B/C)
- `sort_order` (integer)

## Notification Routes (Workspace Service)

User-scoped, not workspace-scoped.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/notifications` | Yes | Query params: `limit`, `unread_only`. |
| `GET` | `/api/v1/notifications/unread-count` | Yes | Returns `{ count }`. |
| `PUT` | `/api/v1/notifications/{notification_id}/read` | Yes | Marks one notification read. |
| `PUT` | `/api/v1/notifications/read-all` | Yes | Marks all notifications read. |
| `DELETE` | `/api/v1/notifications/{notification_id}` | Yes | Deletes one notification. |

## Dashboard Route (Workspace Service)

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/dashboard/stats` | Yes | Member |

## AI Routes (Intelligence Service)

### AI Model Configuration

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/ai/models` | Yes | Member | Lists configured models. |
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/models` | Yes | Admin | Adds a model. Allowed providers: `ollama`, `anthropic`, `openai`, `kimi`, `custom`. |
| `PUT` | `/api/v1/workspaces/{workspace_id}/ai/models/{model_id}/toggle` | Yes | Admin | Toggles `is_active`. |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/ai/models/{model_id}` | Yes | Admin | Deletes a model config. |
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/oppm-extract` | Yes | Member | Extracts OPPM JSON from an uploaded image without saving it. |

### Chat And Planning

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/chat` | Yes | Write | Workspace-level chat. The current implementation can execute workspace-scoped tools. |
| `GET` | `/api/v1/workspaces/{workspace_id}/ai/chat/capabilities` | Yes | Member | Returns indexed-document count and capability flags. `can_execute_tools` depends on the caller's workspace role. |
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/reindex` | Yes | Admin | Reindexes workspace data for RAG. |
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/parse-file` | Yes | Member | Extracts text from supported uploaded files. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/chat` | Yes | Write | Project-scoped assistant chat. Response includes `iterations` and `low_confidence` for the TAOR loop result. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan` | Yes | Write | Generates a suggested OPPM plan. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan/commit` | Yes | Write | Commits a previously suggested plan. |
| `GET` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/weekly-summary` | Yes | Member | Generates a project weekly summary. |
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/oppm-fill` | Yes | Member | Returns AI-assisted OPPM spreadsheet fill suggestions. |

### Feedback

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `POST` | `/api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/feedback` | Yes | Member | Submits thumbs-up/down feedback for an AI response. Logged to `audit_log` with `action = "ai_feedback"`. |
| `POST` | `/api/v1/workspaces/{workspace_id}/ai/feedback` | Yes | Member | Workspace-level AI feedback. Same logging contract as project feedback. |

#### Feedback Request Body

```json
{
  "rating": "up",
  "message_content": "The AI response text being rated",
  "user_message": "The user message that prompted the response",
  "comment": "Optional free-text comment",
  "model_id": "uuid of the ai_model record used"
}
```

`rating` must be `"up"` or `"down"`.

### RAG

| Method | Path | Auth | Role |
|---|---|---|---|
| `POST` | `/api/v1/workspaces/{workspace_id}/rag/query` | Yes | Member |

### Internal AI Route

This route exists for service-to-service use and is not meant for frontend traffic:

| Method | Path | Auth |
|---|---|---|
| `POST` | `/internal/analyze-commits` | `X-Internal-API-Key` |

## Git Routes (Integrations Service)

### GitHub Accounts

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/github-accounts` | Yes | Member |
| `POST` | `/api/v1/workspaces/{workspace_id}/github-accounts` | Yes | Admin |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/github-accounts/{account_id}` | Yes | Admin |

### Repo Configs

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/git/repos` | Yes | Member |
| `POST` | `/api/v1/workspaces/{workspace_id}/git/repos` | Yes | Write |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/git/repos/{config_id}` | Yes | Write |

### Commit Data

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/commits` | Yes | Member | Query params: `project_id`, `limit`. |
| `GET` | `/api/v1/workspaces/{workspace_id}/git/report/{project_id}` | Yes | Member | Query param: `days`. |
| `GET` | `/api/v1/workspaces/{workspace_id}/git/recent-analyses` | Yes | Member | Returns recent commit analyses across the workspace. |
| `POST` | `/api/v1/git/webhook` | No bearer auth | HMAC required | GitHub push webhook endpoint. |

### Webhook Security

`POST /api/v1/git/webhook` requires:

- `X-Hub-Signature-256`
- a configured webhook secret on the matched repo config
- GitHub event type `push`

If validation passes, the route accepts quickly and continues processing in a background task.

## MCP Routes (Automation Service)

| Method | Path | Auth | Role |
|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/mcp/tools` | Yes | Member |
| `POST` | `/api/v1/workspaces/{workspace_id}/mcp/call` | Yes | Member |

## GraphQL Routes (Intelligence Service)

### Endpoint

| Method | Path | Auth | Role | Notes |
|---|---|---|---|---|
| `GET` | `/api/v1/workspaces/{workspace_id}/graphql` | Yes | Member | GraphQL Playground (schema explorer) |
| `POST` | `/api/v1/workspaces/{workspace_id}/graphql` | Yes | Member | Execute GraphQL queries/mutations |

### Query Operations

#### `weeklyStatusSummary`

Returns weekly project status summary with categorized items.

**Arguments:**
- `projectId: String!` - Project ID
- `workspaceId: String!` - Workspace ID

**Returns:** `WeeklySummaryResult`

```graphql
query {
  weeklyStatusSummary(projectId: "proj-123", workspaceId: "ws-456") {
    summary
    atRisk {
      title
      description
    }
    onTrack {
      title
      description
    }
    blocked {
      title
      description
    }
    suggestedActions {
      title
      description
    }
  }
}
```

#### `suggestOppmPlan`

Suggests OPPM plan based on project description.

**Arguments:**
- `projectId: String!` - Project ID
- `workspaceId: String!` - Workspace ID
- `description: String!` - Project description for planning

**Returns:** `SuggestPlanResult`

```graphql
query {
  suggestOppmPlan(projectId: "proj-123", workspaceId: "ws-456", description: "Build new dashboard feature") {
    suggestedObjectives {
      title
      suggestedWeeks
    }
    explanation
    commitToken
  }
}
```

### Mutation Operations

#### `commitOppmPlan`

Commits a suggested OPPM plan to a project.

**Arguments:**
- `projectId: String!` - Project ID
- `workspaceId: String!` - Workspace ID
- `commitToken: String!` - Token from `suggestOppmPlan` response

**Returns:** `Boolean`

```graphql
mutation {
  commitOppmPlan(projectId: "proj-123", workspaceId: "ws-456", commitToken: "token-abc123")
}
```

### Type Definitions

#### `StatusItem`
```graphql
type StatusItem {
  title: String!
  description: String
}
```

#### `WeeklySummaryResult`
```graphql
type WeeklySummaryResult {
  summary: String!
  atRisk: [StatusItem!]!
  onTrack: [StatusItem!]!
  blocked: [StatusItem!]!
  suggestedActions: [StatusItem!]!
}
```

#### `SuggestedObjective`
```graphql
type SuggestedObjective {
  title: String!
  suggestedWeeks: [String!]!
}
```

#### `SuggestPlanResult`
```graphql
type SuggestPlanResult {
  suggestedObjectives: [SuggestedObjective!]!
  explanation: String!
  commitToken: String!
}
```

### Benefits

GraphQL provides selective field queries, reducing mobile payload by **30-40%** compared to REST endpoints:

- **Before (REST):** Full object returned regardless of needed fields
- **After (GraphQL):** Only requested fields returned

Example: Request only titles without descriptions saves ~40% bandwidth for large result sets.

## Endpoint Ownership Summary

- Core: auth, workspaces, members, invites, projects, tasks, OPPM, notifications, dashboard
- AI: model config, chat, planning, reindex, RAG, internal analysis, **GraphQL**
- Git: GitHub accounts, repo configs, commits, reports, webhook
- MCP: workspace tool discovery and execution

## Contract Notes Worth Remembering

These are the main places where the current API contract deserves extra care:

- workspace list/get responses use `current_user_role` on the backend, while some frontend types still describe `role`
- project member add uses a field named `user_id`, but the working value is a workspace member id
- task APIs currently use single assignee fields even though a `task_assignees` table still exists in the schema
- list endpoints are not yet uniformly paginated
