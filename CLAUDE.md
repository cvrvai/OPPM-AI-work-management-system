You are working on the **OPPM AI Work Management System** — a multi-tenant, workspace-scoped
project management platform following the One Page Project Manager (OPPM) methodology.

Before making any changes, always read the relevant rules in `.claude/rules/` for the area
you are modifying. These rules are mandatory and must be followed.

## Project Summary
- **Backend**: Python FastAPI 0.115, 4-layer clean architecture (Router → Service → Repository → Infrastructure)
- **Frontend**: React 19 + Vite 8 + TypeScript 5.9 + Tailwind CSS v4 + @tanstack/react-query v5 + Zustand v5
- **Database**: Supabase PostgreSQL with RLS, 17 tables, workspace-scoped
- **Auth**: Supabase Auth + JWT validation via `db.auth.get_user(token)`
- **Multi-tenancy**: Workspace model — all data scoped by `workspace_id`
- **AI**: LLM adapter pattern (Ollama, Kimi, Anthropic, OpenAI)

## Key Commands
- **Backend**: `cd backend && uvicorn main:app --reload --port 8000`
- **Frontend**: `cd frontend && npm run dev`
- **Type check**: `cd frontend && npx tsc -b`
- **Build**: `cd frontend && npm run build`

## Important Notes
- Backend uses `service_role_key` (bypasses RLS). Auth validates via `supabase.auth.get_user(token)`.
- Frontend uses Vite proxy in dev (`/api` → `localhost:8000`). Do NOT set `VITE_API_URL` in dev.
- All v1 API routes are workspace-scoped: `/api/v1/workspaces/:ws_id/...`
- Legacy routes at `/api/...` are kept for backward compatibility.
