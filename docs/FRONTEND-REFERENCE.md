# Frontend Reference

Last updated: 2026-04-04

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
- `Skeleton.tsx`
  Loading placeholder component.

Use `components/` for reusable UI, not for route-level data orchestration.

### `hooks/`

Small hooks that adapt store behavior to page context.

Current hooks:

- `useChatContext.ts`
  Sets chat context to workspace or project and clears messages when the context changes.
- `useWorkspace.ts`
  Workspace-related helper hook.

### `lib/`

Shared client-side helpers.

Current files:

- `api.ts`
  Central HTTP client wrapper around `fetch`.
- `tokens.ts`
  Token helper utilities.
- `utils.ts`
  Formatting and UI helpers.

Important rule already followed in code:

- pages and components use `api.ts`
- they do not call `fetch` directly for application API traffic

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
  Per-project task board/list, task CRUD, task reports, summary cards.
- `OPPMView.tsx`
  OPPM objectives, timeline, costs, and AI-driven project planning flows.
- `Team.tsx`
  Workspace members and member skills UI.
- `Commits.tsx`
  Commit feed and analysis views.
- `Settings.tsx`
  Profile, members/invites, GitHub integration, and AI model configuration.

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
| `/` | `pages/Dashboard.tsx` | Workspace summary |
| `/projects` | `pages/Projects.tsx` | Project list and project creation wizard |
| `/projects/:id` | `pages/ProjectDetail.tsx` | Task management and per-project summary |
| `/projects/:id/oppm` | `pages/OPPMView.tsx` | Objectives, timeline, costs, AI plan workflows |
| `/team` | `pages/Team.tsx` | Member list and skill matrix |
| `/commits` | `pages/Commits.tsx` | Commit history and analysis UI |
| `/settings` | `pages/Settings.tsx` | Profile, workspace membership, GitHub, AI model config |

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

### Authentication

Start with:

- `stores/authStore.ts`
- `pages/Login.tsx`
- `lib/api.ts`

### Workspace Selection And Shell

Start with:

- `stores/workspaceStore.ts`
- `components/workspace/`
- `components/layout/Layout.tsx`
- `components/layout/Sidebar.tsx`

### Projects

Start with:

- `pages/Projects.tsx`
- `pages/ProjectDetail.tsx`
- `types/index.ts` project and task interfaces

Important current behavior:

- project creation is a two-step modal
- the team assignment step stores workspace member ids but posts them in a field named `user_id`

### OPPM

Start with:

- `pages/OPPMView.tsx`
- `hooks/useChatContext.ts`
- AI routes referenced from the page mutations

### Team And Skills

Start with:

- `pages/Team.tsx`
- skill queries under `/members/{member_id}/skills`

Important current behavior:

- the Team page decides admin behavior from workspace role data
- because of the `role` vs `current_user_role` mismatch, this area is sensitive to contract drift

### Settings

Start with:

- `pages/Settings.tsx`

Settings currently groups four areas:

- profile
- members and invites
- GitHub integration
- AI model configuration

This page is the main aggregation point for workspace administration flows.

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
4. the related backend section in [API-REFERENCE.md](API-REFERENCE.md)
5. the related model notes in [ERD.md](ERD.md)
