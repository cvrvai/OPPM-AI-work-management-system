# API Conventions

## Route Structure
- All new endpoints under `/api/v1/`
- Workspace-scoped: `/api/v1/workspaces/{workspace_id}/resource`
- User-scoped (no workspace): `/api/v1/notifications`
- All routes require `get_current_user` dependency
- Write operations require `require_write` or `require_admin` from workspace middleware

## Request/Response
- Use Pydantic schemas for all request bodies (in `schemas/` package)
- Return plain dicts from services (FastAPI serializes automatically)
- Paginated responses: `{ "items": [...], "total": int, "page": int, "page_size": int }`
- Errors: `HTTPException(status_code=N, detail="message")`

## Naming
- Router files: `routers/v1/{resource}.py`
- Route functions: `{verb}_{resource}_route` (e.g., `list_projects_route`)
- Service functions: `{verb}_{resource}` (e.g., `create_project`)
- Repository methods: `find_*`, `create`, `update`, `delete`

## Auth Flow
- `get_current_user` → validates JWT via `supabase.auth.get_user(token)` → returns `CurrentUser`
- `get_workspace_context` → checks `workspace_members` table → returns `WorkspaceContext` with role
- Never decode JWT locally; always validate via Supabase Auth API
