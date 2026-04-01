# OPPM AI — API Reference

> Base URL: `http://localhost:8000/api`
> Authentication: Bearer JWT token from Supabase Auth

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

### `GET /v1/auth/me`
Get current authenticated user info.

**Headers:** `Authorization: Bearer {jwt}`

**Response** `200`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "authenticated"
}
```

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
    "objective_id": "uuid",
    "year": 2025,
    "month": 3,
    "status": "in_progress"
  }
]
```

### `PUT /v1/workspaces/{ws}/projects/{proj}/oppm/timeline`
Upsert a timeline entry.

**Body**
```json
{
  "objective_id": "uuid",
  "year": 2025,
  "month": 3,
  "status": "completed"
}
```

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
