# OPPM AI — API Reference

> **Base URL (dev):** `http://localhost:8080/api` via Vite proxy → gateway → service
> **Base URL (prod):** `http://your-domain/api` via nginx gateway
> **Authentication:** `Authorization: Bearer {access_token}` on all `/v1/*` routes
> **Dev Note:** Vite proxy routes all `/api` calls to `localhost:8080` (gateway). Do NOT set `VITE_API_URL` in development.
>
> **OPPM applies to any industry** — construction, architecture, finance, healthcare, IT, manufacturing, education, or any other field. All projects share universal elements: objectives, tasks, timelines, budgets, and team members. The AI adapts its vocabulary to the project domain.

---

## Health Check

### `GET /health`
Returns server health status.

**Response** `200`
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

---

## Authentication

All auth endpoints are handled by `core` service via `POST /api/auth/...`. The frontend communicates exclusively through the gateway REST API.

### `POST /api/auth/login`
Sign in with email and password.

**Body**
```json
{ "email": "user@example.com", "password": "secret" }
```

**Response** `200`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600,
  "user": { "id": "uuid", "email": "user@example.com" }
}
```

### `POST /api/auth/signup`
Register a new account.

**Body**
```json
{ "email": "user@example.com", "password": "secret", "full_name": "Jane Doe" }
```

**Response** `201` — same shape as login response.

### `POST /api/auth/refresh`
Exchange a refresh token for a new access token.

**Body**
```json
{ "refresh_token": "eyJ..." }
```

**Response** `200`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600
}
```

### `POST /api/auth/signout`
Invalidate the current session.

**Headers:** `Authorization: Bearer {access_token}`

**Response** `200` `{ "message": "Signed out" }`

### `GET /api/auth/me`
Get the current authenticated user.

**Headers:** `Authorization: Bearer {access_token}`

**Response** `200`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "role": "authenticated"
}
```

### `PATCH /api/auth/profile`
Update display name or user metadata.

**Headers:** `Authorization: Bearer {access_token}`

**Body**
```json
{ "full_name": "New Name" }
```

**Response** `200` — updated user object.

### `GET /v1/auth/me`
Legacy alias for `GET /api/auth/me`. Kept for backward compatibility.

---

## Workspaces

### `GET /v1/workspaces`
List all workspaces the current user belongs to.

**Response** `200`
```json
[
  {
    "id": "uuid",
    "name": "My Team",
    "slug": "my-team",
    "description": "Team workspace",
    "created_by": "uuid",
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

### `POST /v1/workspaces`
Create a new workspace. The creator becomes the owner.

**Body**
```json
{
  "name": "New Workspace",
  "slug": "new-workspace",
  "description": "Optional description"
}
```

**Response** `201`
```json
{ "id": "uuid", "name": "New Workspace", "slug": "new-workspace", ... }
```

### `PUT /v1/workspaces/{workspace_id}`
Update workspace details. **Requires admin role.**

### `DELETE /v1/workspaces/{workspace_id}`
Delete a workspace and all its data. **Requires admin role.**

---

## Workspace Members

### `GET /v1/workspaces/{workspace_id}/members`
List all members of a workspace.

**Response** `200`
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "user_id": "uuid",
    "role": "owner",
    "joined_at": "2025-01-01T00:00:00Z"
  }
]
```

### `PUT /v1/workspaces/{workspace_id}/members/{member_id}`
Update a member's role. **Requires admin role.**

**Body**
```json
{ "role": "admin" }
```

### `DELETE /v1/workspaces/{workspace_id}/members/{member_id}`
Remove a member from the workspace. **Requires admin role.** Cannot remove the last owner.

### `GET /v1/workspaces/{workspace_id}/members/lookup?email={email}`
Look up a workspace member by email address. Useful for invite flows.

**Response** `200`
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "display_name": "Jane Doe",
  "role": "member"
}
```

### `PATCH /v1/workspaces/{workspace_id}/members/me/display-name`
Update the current user's display name within the workspace.

**Body**
```json
{ "display_name": "Jane Doe" }
```

---

## Workspace Invites

### `POST /v1/workspaces/{workspace_id}/invites`
Create an invite link. **Requires admin role.** Token expires in 7 days.

**Body**
```json
{
  "email": "newuser@example.com",
  "role": "member"
}
```

**Response** `201`
```json
{
  "id": "uuid",
  "email": "newuser@example.com",
  "role": "member",
  "token": "invite-token-string",
  "expires_at": "2025-01-08T00:00:00Z"
}
```

### `POST /v1/invites/accept`
Accept an invite by token.

**Body**
```json
{ "token": "invite-token-string" }
```

### `GET /v1/invites/preview/{token}` *(no auth required)*
Fetch a public preview of the workspace invitation before accepting.

**Response** `200`
```json
{
  "workspace_name": "Acme Corp",
  "workspace_description": "...",
  "member_count": 12,
  "role": "member",
  "inviter_name": "Alice",
  "expires_at": "2025-01-08T00:00:00Z",
  "is_expired": false,
  "is_used": false
}
```

**Errors:** `404` invite not found · `410` invite expired or already used

### `POST /v1/workspaces/{workspace_id}/invites/{invite_id}/resend`
Regenerate an invite token and resend the invitation email. **Requires admin role.**

**Response** `200`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "token": "new-token-string",
  "expires_at": "2025-01-15T00:00:00Z"
}
```

---

## Projects

### `GET /v1/workspaces/{workspace_id}/projects`
List workspace projects. Supports pagination.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Items per page |
| `status` | string | — | Filter by status |

**Response** `200`
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 50
}
```

### `POST /v1/workspaces/{workspace_id}/projects`
Create a project. **Requires write access.**

**Body**
```json
{
  "title": "Project Alpha",
  "description": "Description",
  "status": "planning",
  "priority": "high",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30"
}
```

### `GET /v1/workspaces/{workspace_id}/projects/{project_id}`
Get project details.

### `PUT /v1/workspaces/{workspace_id}/projects/{project_id}`
Update project. **Requires write access.**

### `DELETE /v1/workspaces/{workspace_id}/projects/{project_id}`
Delete project. **Requires write access.**

---

## Project Members

### `GET /v1/workspaces/{workspace_id}/projects/{project_id}/members`
List project team members.

### `POST /v1/workspaces/{workspace_id}/projects/{project_id}/members`
Add a workspace member to a project. **Requires write access.**

**Body**
```json
{
  "workspace_member_id": "uuid",
  "role": "member"
}
```

---

## Tasks

### `GET /v1/workspaces/{workspace_id}/tasks`
List tasks. Supports filtering by project.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `project_id` | uuid | Filter by project |
| `status` | string | Filter by status |
| `assignee_id` | uuid | Filter by assignee |

### `POST /v1/workspaces/{workspace_id}/tasks`
Create a task. **Requires write access.** Automatically recalculates project progress.

**Body**
```json
{
  "project_id": "uuid",
  "title": "Implement feature X",
  "description": "Details...",
  "status": "todo",
  "priority": "high",
  "weight": 5,
  "assignee_id": "uuid",
  "oppm_objective_id": "uuid",
  "due_date": "2025-03-15"
}
```

### `PUT /v1/workspaces/{workspace_id}/tasks/{task_id}`
Update task. Triggers project progress recalculation.

### `DELETE /v1/workspaces/{workspace_id}/tasks/{task_id}`
Delete task. Triggers project progress recalculation.

---

## OPPM Objectives

### `GET /v1/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives`
List OPPM objectives for a project, ordered by `sort_order`.

### `POST /v1/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives`
Create an objective. **Requires write access.**

**Body**
```json
{
  "title": "Launch MVP",
  "description": "Release minimum viable product",
  "owner_id": "uuid",
  "sort_order": 1
}
```

### `PUT /v1/workspaces/{ws}/projects/{proj}/oppm/objectives/{obj_id}`
Update an objective.

### `DELETE /v1/workspaces/{ws}/projects/{proj}/oppm/objectives/{obj_id}`
Delete an objective.

---

## OPPM Timeline

### `GET /v1/workspaces/{ws}/projects/{proj}/oppm/timeline`
Get all timeline entries for a project's objectives.

**Response** `200`
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "objective_id": "uuid",
    "week_start": "2025-03-10",
    "status": "in_progress",
    "ai_score": null,
    "notes": null
  }
]
```

### `PUT /v1/workspaces/{ws}/projects/{proj}/oppm/timeline`
Upsert a single timeline entry (create or update by project+objective+week).

**Body**
```json
{
  "objective_id": "uuid",
  "week_start": "2025-03-10",
  "status": "completed"
}
```

**Status values:** `planned` | `in_progress` | `completed` | `at_risk` | `blocked`

---

## OPPM Costs

### `GET /v1/workspaces/{ws}/projects/{proj}/oppm/costs`
Get project cost entries.

### `POST /v1/workspaces/{ws}/projects/{proj}/oppm/costs`
Add a cost entry. **Requires write access.**

**Body**
```json
{
  "category": "Development",
  "description": "Frontend contractor",
  "planned_amount": 5000,
  "actual_amount": 4800,
  "currency": "USD"
}
```

---

## Git Integration

### `GET /v1/workspaces/{workspace_id}/github-accounts`
List GitHub accounts connected to the workspace.

### `POST /v1/workspaces/{workspace_id}/github-accounts`
Connect a GitHub account. **Requires admin role.**

**Body**
```json
{
  "account_name": "my-org",
  "github_username": "octocat",
  "token": "ghp_xxx..."
}
```

### `GET /v1/workspaces/{workspace_id}/repo-configs`
List repository configurations.

### `POST /v1/workspaces/{workspace_id}/repo-configs`
Link a repository to a project.

**Body**
```json
{
  "repo_name": "owner/repo",
  "project_id": "uuid",
  "github_account_id": "uuid"
}
```

### `GET /v1/workspaces/{workspace_id}/commits`
List recent commits with AI analyses.

### `GET /v1/workspaces/{workspace_id}/git/repos`
List repositories configured in this workspace.

### `GET /v1/workspaces/{workspace_id}/git/recent-analyses`
List the most recent AI commit analyses (last 20 by default).

### `GET /v1/workspaces/{workspace_id}/git/report/{project_id}`
Get a formatted AI-generated Git activity report for a specific project. Summarises commit frequency, author activity, and alignment with OPPM objectives.

**Response** `200`
```json
{
  "project_id": "uuid",
  "period_days": 30,
  "total_commits": 47,
  "authors": ["alice", "bob"],
  "avg_quality_score": 82.4,
  "avg_alignment_score": 71.1,
  "summary": "The team has been actively working on the Authentication module...",
  "top_objectives_referenced": ["Login & Registration", "Security Hardening"]
}
```

### `POST /v1/git/webhook`
GitHub webhook endpoint. Validates HMAC signature. Rate limited (30 req/min).

**Headers:** `X-Hub-Signature-256: sha256=...`, `X-GitHub-Event: push`

---

## AI Models

### `GET /v1/workspaces/{workspace_id}/ai/models`
List configured AI models for the workspace.

### `POST /v1/workspaces/{workspace_id}/ai/models`
Add an AI model configuration. **Requires admin role.**

**Body**
```json
{
  "name": "Local Ollama",
  "provider": "ollama",
  "model_id": "llama3.2",
  "endpoint_url": "http://localhost:11434",
  "is_active": true
}
```

### `PUT /v1/workspaces/{workspace_id}/ai/models/{model_id}/toggle`
Toggle a model's `is_active` state. **Requires admin role.**

**Response** `200` — updated model object.

**Provider constraint:** `provider` must be one of `ollama`, `anthropic`, `openai`, `kimi`, `custom`. Invalid values return `400`.

**Ollama cloud models** should use `provider: "ollama"` with `endpoint_url` pointing to the cloud endpoint (e.g., `https://ollama.com/api`). The `model_id` identifies the cloud model.

---

## AI Chat

> All AI chat endpoints require at least one **active** AI model configured for the workspace.
> Returns `400 No active AI model configured` when no active model is found.
> Returns `502 All AI models are currently unavailable` when the LLM server is unreachable.

### `POST /v1/workspaces/{workspace_id}/ai/chat`
Workspace-level chat with AI (no project context).

**Body**
```json
{
  "messages": [
    { "role": "user", "content": "What projects are in progress?" }
  ],
  "model_id": "uuid"
}
```

**Response** `200`
```json
{
  "message": "There are 3 active projects...",
  "tool_calls": [],
  "updated_entities": []
}
```

### `POST /v1/workspaces/{workspace_id}/projects/{project_id}/ai/chat`
Chat with AI in the context of a specific project. Automatically injects project state (objectives, timeline, costs, team).

**Body**
```json
{
  "messages": [
    { "role": "user", "content": "What tasks are overdue?" }
  ],
  "model_id": "uuid"
}
```

**Response** `200`
```json
{
  "message": "There are 3 overdue tasks: ...",
  "tool_calls": [
    { "tool": "update_task", "input": { "task_id": "uuid", "status": "completed" } }
  ],
  "applied_tool_calls": true,
  "updated_entities": ["tasks"]
}
```

### `POST /v1/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan`
Generate an AI-driven OPPM plan preview (does NOT apply changes).

**Body**
```json
{
  "description": "A 5-story office tower construction project in downtown"
}
```

### `POST /v1/workspaces/{workspace_id}/projects/{project_id}/ai/suggest-plan/commit`
Apply a previously generated plan by `commit_token`.

**Body**
```json
{ "commit_token": "uuid" }
```

### `GET /v1/workspaces/{workspace_id}/projects/{project_id}/ai/weekly-summary`
Get an AI-generated weekly status summary for the project.

### `GET /v1/workspaces/{workspace_id}/ai/chat/capabilities`
Returns available AI features and whether an active LLM model is configured.

**Response** `200`
```json
{
  "chat": true,
  "weekly_summary": true,
  "commit_analysis": true,
  "rag": true,
  "active_model": "llama3.2",
  "provider": "ollama"
}
```

### `POST /v1/workspaces/{workspace_id}/ai/reindex`
Trigger a background re-embedding of all workspace data (projects, objectives, tasks, commits) into the vector store. Useful after bulk imports or migrations.

**Response** `202` Accepted
```json
{ "message": "Reindex started", "entity_count": 142 }
```

---

## RAG

### `POST /v1/workspaces/{workspace_id}/rag/query`
Run the RAG retrieval pipeline for a query.  Returns ranked context chunks and conversation memory.

**Body**
```json
{
  "query": "Which objectives are at risk?",
  "project_id": "uuid",
  "top_k": 10
}
```

**Response** `200`
```json
{
  "chunks": [
    {
      "entity_type": "objective",
      "entity_id": "uuid",
      "content": "Launch MVP — status: at_risk",
      "score": 0.87,
      "source": "vector",
      "metadata": {}
    }
  ],
  "memory": [
    { "role": "user", "content": "What tasks are overdue?" },
    { "role": "assistant", "content": "There are 3 overdue tasks..." }
  ],
  "retriever_used": ["vector", "keyword"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Natural language question |
| `project_id` | uuid? | Optional project scope filter |
| `top_k` | int | Max chunks to return (default: 10) |

---

## MCP Tools

### `GET /v1/workspaces/{workspace_id}/mcp/tools`
List all available MCP tools for the workspace.

**Response** `200`
```json
[
  {
    "name": "get_project_status",
    "description": "Get status and task counts for a project",
    "parameters": { "project_id": "uuid" }
  },
  {
    "name": "list_projects",
    "description": "List all workspace projects",
    "parameters": {}
  },
  {
    "name": "list_at_risk_objectives",
    "description": "List objectives with at_risk or blocked timeline entries",
    "parameters": {}
  },
  {
    "name": "get_task_summary",
    "description": "Get task counts grouped by status",
    "parameters": {}
  },
  {
    "name": "summarize_recent_commits",
    "description": "Summarize commits from the last N days",
    "parameters": { "project_id": "uuid?", "days": 7 }
  }
]
```

### `POST /v1/workspaces/{workspace_id}/mcp/call`
Execute an MCP tool by name. `workspace_id` is injected automatically.

**Body**
```json
{
  "tool": "get_project_status",
  "params": { "project_id": "uuid" }
}
```

**Response** `200` — tool-specific JSON result.

---

## Notifications

### `GET /v1/notifications`
List notifications for the current user (across all workspaces).

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `unread_only` | bool | false | Only unread |

### `PUT /v1/notifications/{notification_id}/read`
Mark a notification as read.

### `DELETE /v1/notifications/{notification_id}`
Delete a single notification permanently.

**Response** `204` No Content

### `PUT /v1/notifications/read-all`
Mark all notifications as read.

---

## Dashboard

### `GET /v1/workspaces/{workspace_id}/dashboard/stats`
Get aggregated dashboard statistics for a workspace.

**Response** `200`
```json
{
  "total_projects": 12,
  "active_projects": 8,
  "total_tasks": 156,
  "completed_tasks": 89,
  "total_commits": 342,
  "recent_commits": [...],
  "project_progress": [
    { "project_id": "uuid", "title": "Alpha", "progress": 75 }
  ]
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request / validation error |
| `401` | Missing or invalid JWT |
| `403` | Insufficient permissions (wrong workspace role) |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
