# Frontend Reference

Last updated: 2026-04-20

## Purpose

This document explains what the frontend currently contains, where each feature lives, and which files you should inspect before making UI changes.

It is written against the current code in `frontend/src/`.

## Stack

- React 19
- Vite 8
- TypeScript 5.9
- Tailwind CSS v4
- TanStack Query v5 for server state
- Zustand v5 for client state
- React Router 7

## Frontend Entry Flow

The frontend boots from `frontend/src/App.tsx`.

Current startup sequence:

1. initialize auth from local storage
2. call `/api/auth/me` if an access token exists
3. attempt `/api/auth/refresh` if the access token is expired
4. fetch workspaces after auth succeeds
5. render protected routes inside `Layout`

Public routes render immediately:

- `/login`
- `/invites/:token`
- `/invite/accept/:token`

Protected routes render inside the main shell:

- `/`
- `/projects`
- `/projects/:id`
- `/projects/:id/oppm`
- `/team`
- `/commits`
- `/settings`

## Folder Map

```text
frontend/
  src/
    App.tsx                App bootstrap, router, ProtectedRoute
    main.tsx               React entry
    index.css              global styles and Tailwind layers
    components/            reusable UI building blocks
    hooks/                 small view-layer hooks
    lib/                   HTTP client and utilities
    pages/                 route-level screens
    stores/                Zustand state containers
    types/                 frontend API/data interfaces
```

## What Each Folder Contains

### `components/`

Shared UI blocks used across pages.

Current important areas:

- `layout/`
  Application shell, sidebar, header, and route outlet layout.
- `workspace/`
  Workspace selector and related workspace shell controls.
- `ChatFAB.tsx`
  Floating entry point for AI chat.
- `ChatPanel.tsx`
  Sliding chat panel used in workspace and project contexts.
- `GanttChart.tsx`
  Gantt-style timeline visualization component.
- `Skeleton.tsx`
  Loading placeholder component.

Use `components/` for reusable UI, not for route-level data orchestration.

### `hooks/`

Small hooks that adapt store behavior to page context.

Current hooks:

- `useChatContext.ts`
  Sets chat context to workspace or project and clears messages when the context changes.
- `useWorkspace.ts`
  Two helpers: `useWorkspaceId()` — throws if no workspace selected; `useWsPath()` — returns `/v1/workspaces/<id>` prefix.
- `useWorkspaceNavGuard.ts`
  Detects workspace changes on project-scoped pages and redirects to `/projects`. Apply this in any page that is keyed to a specific project ID so switching workspace never leaves the user on a stale URL that fires cross-workspace 404s.

### `lib/`

Shared client-side helpers.

Current files:

- `api.ts`
  Central HTTP client wrapper around `fetch`. Handles auth header injection, 401 token refresh, and throws `ApiError` (with `.status` field) for all non-ok responses.
- `tokens.ts`
  Token helper utilities.
- `utils.ts`
  Formatting and UI helpers.

Important rule already followed in code:

- pages and components use `api.ts`
- they do not call `fetch` directly for application API traffic

**`ApiError` class** (in `api.ts`):

All failed responses throw `ApiError` instead of a plain `Error`. This allows TanStack Query's `retry` function to inspect `error.status` and skip retrying 4xx errors entirely.

```typescript
// In App.tsx — never retry client errors (404, 403, 401)
retry: (failureCount, error) => {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 3
}
```

## Local Storage

The frontend stores the following keys in `localStorage`:

| Key | Set by | Purpose |
|---|---|---|
| `access_token` | `authStore.ts` | JWT access token for API authorization. Sent in every request header. |
| `refresh_token` | `authStore.ts` | Long-lived refresh token. Used by `api.ts` on 401 to get a new access token without re-login. |
| `oppm-workspace` | Zustand `persist` middleware | Persists the currently selected workspace across page reloads. |

All three keys are cleared on signout. The workspace key survives reloads but is verified against a fresh workspace list on startup — if the stored workspace no longer exists in the API response, it falls back to the first available workspace.

### `pages/`

Each file is a route-level screen with its own data fetching and mutations.

Current pages:

- `Login.tsx`
  Login and signup flow.
- `AcceptInvite.tsx`
  Public invite preview and accept flow.
- `Dashboard.tsx`
  Workspace dashboard and summary metrics.
- `Projects.tsx`
  Project list, project creation wizard, and project edit/delete actions.
- `ProjectDetail.tsx`
  Per-project task board/list/Gantt, task CRUD with main-task/sub-task hierarchy, task reports, summary cards. Create Task form includes a compact task-type toggle, parent task selector, inline objective creation, A/B/C owner assignment, and early OPPM alignment fields for objective, owner, due date, and contribution. Table view renders tasks hierarchically with visual indentation for sub-tasks.
- `OPPMView.tsx`
  Project-scoped linked Google Sheet view for OPPM. Loads saved Google Sheet link state, supports save/unlink/push actions, prefers backend FortuneSheet render when credentials exist, and falls back to live browser preview mode when backend render is unavailable.
- `Team.tsx`
  Workspace members, invite management, and member skills UI.
- `Commits.tsx`
  Commit feed and analysis views.
- `Settings.tsx`
  Profile, workspace settings, GitHub integration, and AI model configuration.

### `stores/`

Client-side state containers.

Current stores:

- `authStore.ts`
  Session bootstrap, login/signup/signout, refresh-session behavior.
- `workspaceStore.ts`
  Workspace list, persisted current workspace, workspace creation.
- `chatStore.ts`
  Chat panel open state, message history, unread counter, context switching.

### `types/`

TypeScript interfaces for API data.

This folder is important but not always the exact backend truth. Some contract drift still exists and should be checked against the backend when debugging integration issues.

## Route Ownership

### App Shell

`Layout.tsx` wraps all protected pages and provides:

- `Sidebar`
- `Header`
- page outlet
- `ChatFAB`
- `ChatPanel`

Important current behavior:

- the sidebar can now fully hide on desktop as well as slide in on mobile
- desktop sidebar visibility is persisted locally so wide-screen workspace layouts can stay focused on dense pages like OPPM

Sidebar navigation currently exposes:

- Dashboard
- Projects
- Team
- Commits
- Settings

### Page Responsibility Map

| Route | File | Primary responsibility |
|---|---|---|
| `/login` | `pages/Login.tsx` | Auth entry point |
| `/invites/:token` | `pages/AcceptInvite.tsx` | Invite preview and acceptance |
| `/invite/accept/:token` | `pages/AcceptInvite.tsx` | Alias route for invite preview and acceptance |
| `/` | `pages/Dashboard.tsx` | Workspace summary |
| `/projects` | `pages/Projects.tsx` | Project list and project creation wizard |
| `/projects/:id` | `pages/ProjectDetail.tsx` | Task management and per-project summary |
| `/projects/:id/oppm` | `pages/OPPMView.tsx` | Linked Google Sheet OPPM view with save/unlink/push actions, backend app render, and browser preview mode |
| `/team` | `pages/Team.tsx` | Member roles, invites, and skill matrix |
| `/commits` | `pages/Commits.tsx` | Commit history and analysis UI |
| `/settings` | `pages/Settings.tsx` | Profile, workspace settings, GitHub, AI model config |

## State Management Pattern

### Auth State

`authStore.ts` owns:

- `user`
- `loading`
- `isAuthenticated`
- `initialize()`
- `signIn()`
- `signUp()`
- `signOut()`
- `refreshSession()`

Important behavior:

- auth bootstrap uses raw `fetch` inside the store, not `api.ts`
- access and refresh tokens are stored in local storage
- signout always clears local tokens even if the backend request fails

### Workspace State

`workspaceStore.ts` owns:

- `workspaces`
- `currentWorkspace`
- persisted workspace selection
- workspace creation
- workspace list refresh

Important behavior:

- the current workspace is persisted across reloads
- after fetching workspaces, the store validates that the persisted workspace still belongs to the current user
- if not, it falls back to the first available workspace

Current contract caveat:

- backend workspace responses include `current_user_role`
- the main `Workspace` frontend type still describes `role`
- some settings code already reads `current_user_role` through loose typing to compensate

### Chat State

`chatStore.ts` owns:

- whether the chat panel is open
- chat message history
- unread count
- workspace vs project context
- current project id and title

`useChatContext()` is called from pages to keep that context aligned with the current route.

## Data Fetching Pattern

The frontend uses TanStack Query for server state.

Common pattern:

1. derive `wsPath` from `currentWorkspace`
2. fetch with `api.get()`
3. mutate with `api.post()`, `api.put()`, `api.patch()`, `api.delete()`
4. invalidate the relevant query keys on success

Typical query keys:

- `['projects', workspaceId]`
- `['project', projectId, workspaceId]`
- `['tasks', projectId, workspaceId]`
- `['members', workspaceId]`
- `['workspace-members', workspaceId]`
- `['member-skills', memberId]`

## Feature Entry Points

Each section below lists the frontend files for a feature. For the full feature flow (backend files, tables, caveats), see the linked canonical doc in `docs/features/`.

### Authentication

Start with:

- `stores/authStore.ts`
- `pages/Login.tsx`
- `lib/api.ts`

Canonical doc: [`features/auth/authentication.md`](../features/auth/authentication.md)

### Workspace Selection And Shell

Start with:

- `stores/workspaceStore.ts`
- `components/workspace/`
- `components/layout/Layout.tsx`
- `components/layout/Sidebar.tsx`

Canonical doc: [`features/workspace/workspaces.md`](../features/workspace/workspaces.md)

### Projects

Start with:

- `pages/Projects.tsx`
- `pages/ProjectDetail.tsx`
- `types/index.ts` project and task interfaces

Important current behavior:

- project creation is a two-step modal
- the team assignment step stores workspace member ids but posts them in a field named `user_id`
- create and edit flows now use the same wider modal rhythm as the task editor for denser setup without cramped form spacing

Canonical doc: [`features/project/projects.md`](../features/project/projects.md)

### Task Permissions

The task system enforces role-based permissions:

- only project leads can create tasks
- only the assigned user can submit daily reports
- only project leads can approve/revoke report approvals
- approval status updates use optimistic UI via `setQueryData`

Canonical doc: [`features/project/tasks.md`](../features/project/tasks.md)

### Task Hierarchy

Tasks support a parent/sub-task hierarchy via `parent_task_id`:

- **Main tasks** have `parent_task_id = null` — these are top-level deliverables
- **Sub-tasks** have `parent_task_id` referencing a main task
- The Create Task form provides:
  - A compact **task-type toggle** (Main Task / Sub-Task) at the top for quick selection
  - Early OPPM alignment inputs for **Objective**, **Owner**, **Due Date**, and **Contribution**
  - A **Parent Task** dropdown in the Ownership section
  - Inline **objective creation**, **A/B/C owner assignment**, **dependencies**, and **sub-objective** selection
- The table view renders tasks hierarchically with `└` indentation for sub-tasks
- The board (Kanban) view renders all tasks flat grouped by status

Canonical doc: [`features/project/tasks.md`](../features/project/tasks.md)

### OPPM

Start with:

- `pages/OPPMView.tsx`
- `hooks/useChatContext.ts`
- AI routes referenced from the page mutations

Important current behavior:

- the page is now centered on a **linked Google Sheet** per project instead of the older default scaffold path
- it loads link state from the core `oppm/google-sheet` routes using React Query
- **Save Link** stores a Google Sheet URL or spreadsheet ID in project metadata
- **Unlink** removes the saved project-level Google Sheet reference
- **Push AI Fill** calls the AI fill route and writes the generated OPPM summary, task, and member data into Google Sheets tabs
- when backend Google credentials are configured, the page fetches linked-sheet XLSX bytes and renders them through FortuneSheet
- when backend app render is unavailable, the page switches to **browser preview mode** and embeds the live Google Sheet preview in an `iframe`
- browser preview mode is read-only inside the app, but it is the reason Google Sheet edits can appear after reload
- the current page surfaces backend configuration warnings without crashing the route or breaking the rest of the page

Canonical docs:
- [`features/oppm/spreadsheet-rendering.md`](../features/oppm/spreadsheet-rendering.md) — Spreadsheet, templates, AI fill
- [`features/oppm/google-sheets-integration.md`](../features/oppm/google-sheets-integration.md) — Google Sheets linking
- [`features/oppm/structured-planning.md`](../features/oppm/structured-planning.md) — Structured OPPM data

### Team And Skills

Start with:

- `pages/Team.tsx`
- `pages/Settings.tsx` for the exported `WorkspaceMembersPanel`
- skill queries under `/members/{member_id}/skills`

Important current behavior:

- the Team page is now the home for member role changes, invite management, and skill management
- the member and invite panel is shared from `Settings.tsx` but rendered on Team
- admin behavior resolves from `current_user_role` first and falls back to `role` for compatibility

Canonical doc: [`features/workspace/team-invites.md`](../features/workspace/team-invites.md)

### Settings

Start with:

- `pages/Settings.tsx`

Settings currently groups four areas:

- profile
- workspace settings
- GitHub integration
- AI model configuration

Important current behavior:

- workspace membership and invites were moved out of Settings and into Team
- the workspace tab contains the owner-only workspace deletion flow and general workspace summary controls

### AI Chat

Start with:

- `components/ChatFAB.tsx`
- `components/ChatPanel.tsx`
- `stores/chatStore.ts`
- `hooks/useChatContext.ts`

## API Client Behavior

`lib/api.ts` is the frontend network contract layer.

It does three important things:

- injects `Authorization` automatically from local storage
- retries once on `401` by calling `/api/auth/refresh`
- throws `Error(detail)` for non-OK responses

Any new frontend API integration should go through this file.

## Current Frontend Risks

These are the main integration issues worth knowing before editing:

- workspace role naming is not fully normalized between backend and frontend
- project member assignment uses a misleading request field name: `user_id` currently carries a workspace member id
- task assignment is single-assignee in the live UI even though the database still has a legacy multi-assignee table
- some auth flows are implemented directly in the store rather than fully through the shared `api.ts` wrapper

## Recommended Change Strategy

Before editing a feature, read files in this order:

1. the route page in `pages/`
2. any supporting store in `stores/`
3. `lib/api.ts`
4. the related backend section in [API-REFERENCE.md](../API-REFERENCE.md)
5. the related model notes in [ERD.md](../ERD.md)
