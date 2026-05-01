# Feature: Workspace Bootstrap, Tenancy, And Authorization

Last updated: 2026-05-01

## What It Does

- Workspace list and selection
- Workspace CRUD
- Workspace-scoped authorization and role checks

## How It Works

1. After auth succeeds, `workspaceStore.fetchWorkspaces()` loads `/api/v1/workspaces`.
2. `frontend/src/stores/workspaceStore.ts` persists the selected workspace in local storage.
3. Most business API calls are built from `/v1/workspaces/{workspace_id}`.
4. `shared/auth.py` resolves `WorkspaceContext` by checking `workspace_members` for the current user and workspace.
5. Role gates are enforced with `get_workspace_context`, `require_write`, `require_admin`, and `require_owner`.

## Frontend Files

- `frontend/src/stores/workspaceStore.ts`
- `frontend/src/hooks/useWorkspace.ts`
- `frontend/src/components/workspace/`

## Backend Files

- `services/workspace/domains/workspace/router.py`
- `services/workspace/domains/workspace/service.py`
- `shared/auth.py`
- `shared/models/workspace.py`

## Primary Tables

- `workspaces`
- `workspace_members`

## Update Notes

- `workspace_members.id` is the key membership identifier used by several downstream features.
- Authorization is enforced in the API layer, not with database RLS.
