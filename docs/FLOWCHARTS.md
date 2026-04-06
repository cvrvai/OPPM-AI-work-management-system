# Flowcharts

Last updated: 2026-04-06

## Purpose

These flowcharts describe the major runtime paths in the current implementation.

They are intentionally based on the code paths that exist now, not on older architecture plans.

## 1. App Bootstrap And Auth Refresh

```mermaid
flowchart TD
    A[Browser loads React app] --> B[App.tsx initialize]
    B --> C{Has local access token?}
    C -- No --> D[Render public routes]
    C -- Yes --> E[fetchWorkspaces after auth init]
    D --> F[User goes to login or invite page]
    E --> G[Protected routes render]

    G --> H[User makes API request]
    H --> I{API returns 401?}
    I -- No --> J[Use response]
    I -- Yes --> K[POST /api/auth/refresh]
    K --> L{Refresh succeeds?}
    L -- Yes --> M[Store new tokens]
    M --> N[Retry original request once]
    L -- No --> O[Clear tokens]
    O --> P[ProtectedRoute redirects to /login]
```

## 2. Workspace Invite Acceptance

```mermaid
flowchart TD
    A[User opens /invites/:token] --> B[Frontend calls GET /api/v1/invites/preview/:token]
    B --> C{Preview valid?}
    C -- No --> D[Show invalid or expired state]
    C -- Yes --> E[Show workspace name, role, member count]
    E --> F{User authenticated?}
    F -- No --> G[User logs in or signs up]
    G --> H[POST /api/v1/invites/accept]
    F -- Yes --> H[POST /api/v1/invites/accept]
    H --> I[Core service validates token and membership rules]
    I --> J[workspace_members row created]
    J --> K[Invite marked accepted]
    K --> L[Frontend refreshes workspace list]
```

## 3. Project Creation Wizard

```mermaid
flowchart TD
    A[User opens New Project modal] --> B[Step 1 project info]
    B --> C[Title, code, objective summary, schedule, budget, lead]
    C --> D[Step 2 team assignment]
    D --> E[Select workspace members and project roles]
    E --> F[POST /api/v1/workspaces/:ws/projects]
    F --> G[Core creates project]
    G --> H[Creator workspace membership added as project lead]
    H --> I{Additional team members selected?}
    I -- No --> J[Invalidate project queries]
    I -- Yes --> K[Frontend loops POST /projects/:project_id/members]
    K --> L[Backend stores project_members rows]
    L --> J[Invalidate project queries]
```

## 4. Task Report Approval Flow

```mermaid
flowchart TD
    A[Member opens project detail page] --> B[Create task report]
    B --> C[POST /api/v1/workspaces/:ws/tasks/:task_id/reports]
    C --> D[task_reports row created]
    D --> E[Write-enabled user reviews report]
    E --> F[PATCH /reports/:report_id/approve]
    F --> G[Core updates is_approved and approved_by]
    G --> H[UI refreshes task reports]
```

## 5. GitHub Webhook To Commit Analysis

```mermaid
flowchart TD
    A[Developer pushes to GitHub] --> B[GitHub sends POST /api/v1/git/webhook]
    B --> C[Git service locates repo_config by repository full name]
    C --> D[Validate X-Hub-Signature-256 with webhook secret]
    D --> E{Signature valid and push event?}
    E -- No --> F[Reject or ignore request]
    E -- Yes --> G[Return accepted response quickly]
    G --> H[Background task stores commit_events]
    H --> I[Git service calls AI /internal/analyze-commits]
    I --> J[AI service analyzes commits against project context]
    J --> K[commit_analyses rows stored]
    K --> L[Frontend can fetch recent analyses and reports]
```

## 6. AI Chat And RAG Retrieval

```mermaid
flowchart TD
    A[User sends AI message] --> B{Workspace chat or project chat?}
    B -- Workspace --> C[POST /api/v1/workspaces/:ws/ai/chat]
    B -- Project --> D[POST /api/v1/workspaces/:ws/projects/:project_id/ai/chat]
    C --> E[AI service loads workspace context]
    D --> F[AI service loads project context]
    E --> G[Optional retrieval pipeline]
    F --> G[Optional retrieval pipeline]
    G --> H[Structured queries + embeddings + audit memory]
    H --> I[LLM selection from active ai_models]
    I --> J[Response returned to frontend]
```

## 7. Workspace Reindex Flow

```mermaid
flowchart TD
    A[Admin triggers reindex] --> B[POST /api/v1/workspaces/:ws/ai/reindex]
    B --> C[AI document indexer walks workspace data]
    C --> D[Projects, tasks, objectives, costs, members, commits gathered]
    D --> E[Embeddings generated]
    E --> F[document_embeddings upserted]
    F --> G[Capabilities endpoint reflects updated index count]
```

## 8. Gateway Routing Decision

```mermaid
flowchart TD
    A[Incoming /api request] --> B{Path matches AI pattern?}
    B -- Yes --> C[Forward to AI service]
    B -- No --> D{Path matches Git pattern?}
    D -- Yes --> E[Forward to Git service]
    D -- No --> F{Path matches MCP pattern?}
    F -- Yes --> G[Forward to MCP service]
    F -- No --> H[Forward to Core service]
```

## Notes

- Native development uses the Python gateway in `services/gateway/`.
- Docker deployments use nginx rules in `gateway/nginx.conf`.
- Those routing rules must stay aligned.
- The internal AI analysis route is not part of the public frontend API surface.
