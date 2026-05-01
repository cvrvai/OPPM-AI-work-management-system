You are working on the **FlowDesk Work Management System** — a multi-tenant, workspace-scoped
project management platform following the One Page Project Manager (OPPM) methodology.

Before making any changes, always read the relevant rules in `.claude/rules/` for the area
you are modifying. These rules are mandatory and must be followed.

## Project Summary
- **Backend**: Python FastAPI 0.115, DDD domain architecture (domains/ with router, service, repository, schemas together)
- **Frontend**: React 19 + Vite 8 + TypeScript 5.9 + Tailwind CSS v4 + @tanstack/react-query v5 + Zustand v5
- **Database**: PostgreSQL (asyncpg) + SQLAlchemy async ORM, 23 tables across 7 domains, workspace-scoped (see `docs/DATABASE-SCHEMA.md`)
- **Auth**: Custom JWT auth (python-jose HS256) — local decode via `JWT_SECRET_KEY`
- **Multi-tenancy**: Workspace model — all data scoped by `workspace_id`
- **AI**: LLM adapter pattern (Ollama, Kimi, Anthropic, OpenAI)

## Key Commands
- **Backend (workspace)**: `cd services/workspace && uvicorn main:app --reload --port 8000`
- **Frontend**: `cd frontend && npm run dev`
- **Type check**: `cd frontend && npx tsc -b`
- **Build**: `cd frontend && npm run build`

## Important Notes
- Backend uses direct DB owner role (no RLS). JWT validated locally via `python-jose` in `shared/auth.py`.
- Frontend uses Vite proxy in dev (`/api` → `localhost:8000`). Do NOT set `VITE_API_URL` in dev.
- All v1 API routes are workspace-scoped: `/api/v1/workspaces/:ws_id/...`
- Legacy routes at `/api/...` are kept for backward compatibility.
