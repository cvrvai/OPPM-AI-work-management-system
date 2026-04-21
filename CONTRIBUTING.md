# Contributing

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL (local or Docker)
- Redis (local or Docker)

## Local Development Setup

### 1. Clone and configure

```bash
git clone <repo>
cd "OPPM AI work management system"
cp apps/.env.example apps/.env
# Edit apps/.env — set DATABASE_URL, JWT_SECRET_KEY, and optional AI API keys
```

### 2. Install the shared package

```bash
pip install -e packages/shared
```

### 3. Start infrastructure (PostgreSQL + Redis)

```bash
docker compose up -d
```

### 4. Start backend services

Each in its own terminal:

```bash
cd apps/core && uvicorn main:app --reload --port 8000
cd apps/ai   && uvicorn main:app --reload --port 8001
cd apps/git  && uvicorn main:app --reload --port 8002
cd apps/mcp  && uvicorn main:app --reload --port 8003
```

Or use the gateway for unified access:
```bash
cd apps/gateway && uvicorn main:app --reload --port 8080
```

### 5. Start the frontend

```bash
cd frontend && npm install && npm run dev
```

Frontend available at `http://localhost:5173`. Vite proxies `/api` → `http://localhost:8080`.

### 6. Docker Compose (full stack)

```bash
docker compose -f docker-compose.microservices.yml up --build
```

## Repository Layout

See `.claude/rules/project-structure.md` for the authoritative folder structure.

Key directories:
- `apps/` — FastAPI microservices (core, ai, git, mcp, gateway)
- `packages/shared/` — Shared Python package (auth, models, database)
- `frontend/` — React + Vite + TypeScript application
- `infrastructure/nginx/` — Nginx gateway for Docker/production
- `docs/` — Documentation (see `docs/README.md` for index)

## Branch Strategy

- `main` — stable, deployable
- Feature branches: `feature/short-description`
- Bug fixes: `fix/short-description`
- Open a PR against `main` for all changes

## Pull Request Checklist

- [ ] Code follows the 4-layer architecture (Router → Service → Repository → Infrastructure)
- [ ] New endpoints require `get_current_user` and appropriate `require_write` / `require_admin`
- [ ] All workspace-scoped data queries include `workspace_id`
- [ ] No `console.log` or `print()` in production code
- [ ] Frontend API calls go through `lib/api.ts`
- [ ] TypeScript check passes: `cd frontend && npx tsc -b`
- [ ] Backend tests pass: `cd apps/core && python -m pytest tests/ -v`

## Rules

All mandatory coding and architecture rules live in `.claude/rules/`. Read the relevant rule file before modifying any area:

| Area | Rule file |
|---|---|
| API design | `.claude/rules/api-conventions.md` |
| Code style | `.claude/rules/code-style.md` |
| Database | `.claude/rules/database.md` |
| Error handling | `.claude/rules/error-handling.md` |
| Security | `.claude/rules/security.md` |
| Testing | `.claude/rules/testing.md` |
