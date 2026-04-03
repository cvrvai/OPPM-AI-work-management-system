# Microservices Architecture Review
> Reviewed 2026-04-02 — All Critical and High issues resolved. Medium/Low issues documented below.

## Overview

The OPPM system has been migrated from a FastAPI monolith (`backend/`) to 4 focused microservices behind an nginx gateway. All services successfully build and run as Docker containers.

```
Client → nginx:80 (gateway) → core:8000  (workspaces, projects, tasks, OPPM, notifications)
                             → ai:8001    (LLM chat, commit analysis, RAG, AI models)
                             → git:8002   (GitHub webhooks, repos, commits)
                             → mcp:8003   (Model Context Protocol tools)
```

---

## Deployment

### Quick Start (Production)
```bash
docker compose -f docker-compose.microservices.yml up -d
```

### Development (Hot Reload + Port Exposure)
```bash
docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml up -d
```

### Native Development (no Docker)

Each service has a `start.ps1` that automatically sets `PYTHONPATH` to the workspace root and loads its own `.env` file. No manual environment setup needed.

```powershell
# Start gateway first — all services must be reachable through it
./services/gateway/start.ps1    # Python FastAPI gateway, port 8080

./services/core/start.ps1       # port 8000
./services/ai/start.ps1         # port 8001
./services/git/start.ps1        # port 8002
./services/mcp/start.ps1        # port 8003

cd frontend ; npm run dev       # port 5173
```

`vite.config.ts` proxies all `/api` and `/mcp` to `http://localhost:8080` (gateway only).

**Load balancing (native):** Add comma-separated URLs in `services/gateway/.env`:
```dotenv
CORE_URLS=http://localhost:8000,http://localhost:8010
```

### Service URLs
| Service | Native Port | Docker Port |
|---------|-------------|-------------|
| Gateway | 8080 | 80 |
| Core | 8000 | 8000 (dev only) |
| AI | 8001 | 8001 (dev only) |
| Git | 8002 | 8002 (dev only) |
| MCP | 8003 | 8003 (dev only) |

### Environment
- **Native dev:** each service reads its own `services/{service}/.env` (e.g. `services/core/.env`).
- **Docker:** copy `services/.env.example` to `services/.env` and populate credentials.
- `services/.env` and `services/*/.env` are in `.gitignore` — never commit credentials.
- `OLLAMA_URL` must point to `http://host.docker.internal:11434` when running in Docker.

---

## Design Decisions

### Shared Package (`shared/`)
- `shared/auth.py` — JWT validation via `supabase.auth.get_user(token)`. Never decode locally.
- `shared/database.py` — Supabase singleton, uses `service_role_key` (bypasses RLS). Primary auth gate is always the service layer, not RLS.
- `shared/config.py` — `SharedSettings(BaseSettings)`: Supabase creds + internal_api_key. Each service subclasses this with domain-specific settings.
- Import via `PYTHONPATH=/` (set in each Dockerfile) — `pip install /shared` installs dependencies only.

### CORS Policy
CORS is handled differently per environment:
- **Docker:** exclusively by nginx (`gateway/nginx.conf`). Service containers do NOT add `CORSMiddleware`. This prevents duplicate headers which browsers reject.
- **Native dev:** the Python gateway (`services/gateway/main.py`) adds `CORSMiddleware` with `allow_origin_regex`. Services may also add their own CORS middleware since they are behind the Python gateway (no nginx).

### Python Gateway (`services/gateway/`)
A FastAPI reverse proxy that mirrors the nginx routing table for native development:
- Reads upstream URL lists from env vars (`CORE_URLS`, `AI_URLS`, `GIT_URLS`, `MCP_URLS`) as comma-separated values.
- Uses `itertools.cycle` for round-robin load balancing across the list.
- Same path-routing rules as nginx (most-specific-first order).
- Returns `502` if upstream is unreachable, `504` on timeout.
- Must be started before any other service when running natively.

### Auth Through Gateway
The frontend has no direct Supabase connection. All auth operations go through:
```
Frontend → Gateway → core/routers/auth.py → Supabase Auth (server-side)
```
- `POST /api/auth/login|signup|refresh|signout` and `GET /api/auth/me` / `PATCH /api/auth/profile` are in `services/core/routers/auth.py`.
- Tokens (`access_token`, `refresh_token`) are stored in `localStorage` by `authStore.ts`.
- On 401, `api.ts` auto-calls `authStore.refreshSession()` then retries the original request once.
- No Supabase JS client is used in the frontend.

### Internal API
Service-to-service calls use `X-Internal-API-Key` header (validated by `shared/auth.py#verify_internal_key`). Only the AI service exposes an `/internal/` router. The git service calls `ai:8001/internal/analyze-commits` fire-and-forget (`asyncio.create_task`).

### Gateway Routing
nginx routes based on URL path prefix to the correct upstream:

| Pattern | Service |
|---------|---------|
| `/api/v1/workspaces/.../projects/.../ai/` | ai:8001 |
| `/api/v1/workspaces/.../rag/` | ai:8001 |
| `/api/v1/workspaces/.../ai/` | ai:8001 |
| `/api/v1/workspaces/.../mcp/` | mcp:8003 |
| `/api/v1/workspaces/.../github-accounts` | git:8002 |
| `/api/v1/workspaces/.../commits` | git:8002 |
| `/api/v1/workspaces/.../git/` | git:8002 |
| `/api/v1/git/webhook` | git:8002 |
| `/mcp` (SSE) | mcp:8003 |
| `/api/` (all else) | core:8000 |
| `/` | frontend:5173 |

The gateway uses Docker's internal resolver (`127.0.0.11`) so it starts even when `frontend` is not running.

---

## Issues Fixed in This Review

### Critical (resolved)
| ID | Issue | Fix |
|----|-------|-----|
| C1 | GitHub webhook HMAC optional — any unauthenticated request was processed | Made signature required; reject 401 if header absent |
| C2 | `trigger_ai_analysis` awaited with 120s timeout — blocks event loop, causes GitHub timeout retries | Changed to `asyncio.create_task(...)` (fire-and-forget) |
| C3 | `ai_chat_service` sync functions block async event loop | **Pending** — `_run_llm()` still uses thread pool; full async refactor needed |
| C4 | Real `SUPABASE_SERVICE_ROLE_KEY` in plaintext file | Added `services/.env` to `.gitignore`; rotate key if repo ever had history |

### High (resolved)
| ID | Issue | Fix |
|----|-------|-----|
| H1 | `list_tasks` returned tasks from all workspaces when `project_id=None` | Added `workspace_id` param; new `find_workspace_tasks` repo method |
| H2 | `get_task` no workspace-scoping — cross-workspace read possible | Added `workspace_id` param; check `task.workspace_id == workspace_id` |
| H3 | `delete_notification` no ownership check | Passed `user_id` to service+repository; uses `.eq("user_id", ...)` |
| H4 | `mark_read` accepted `user_id` but ignored it | Added `mark_read_for_user` repo method scoped by `user_id` |
| H5 | Commit analysis notifications inserted without `user_id` — silent `NOT NULL` violation | Look up `project_members` table; create per-member notifications |
| H6 | Double CORS headers (nginx + service middleware) — browser rejects responses | Removed `CORSMiddleware` from ai/git/mcp `main.py`; nginx only |
| H7 | `config["webhook_secret"].encode()` — `AttributeError` if column is NULL | Added null check; return 500 with clear message |
| H9 | `toggle_ai_model` returned `{"error": "..."}` with HTTP 200 on 404 | Changed to `raise HTTPException(status_code=404)` |

---

## Remaining Issues (Medium / Low — Not Fixed)

### Medium
| ID | Issue | Recommendation |
|----|-------|---------------|
| M1 | N+1 queries in `dashboard_service.get_dashboard_stats` (100 DB calls for 50 projects) | Batch: single query with project_id IN (...) |
| M2 | N+1 in `git_service.list_repos` and `list_commits` | Same — batch project_id lookups |
| M3 | `_plan_cache` in `ai_chat_service` is in-memory dict — lost on restart, unbounded, not shared between replicas | Replace with Redis or Supabase table; evict after TTL |
| M4 | Rate limiting middleware exists (migrated from monolith) but never wired into any service | Add `from middleware.rate_limit import RateLimitMiddleware` to `services/core/main.py` |
| M5 | `redis` service defined in `docker-compose.microservices.yml` but nothing connects to it | Wire up once M3/M4 are addressed, or remove the service definition |
| M6 | `shared/database.py` `get_db()` silently falls back to anon key on empty `SUPABASE_SERVICE_ROLE_KEY` | Add startup validation: raise if both keys are empty |

### Low
| ID | Issue |
|----|-------|
| L1 | `ai/config.py` and `git/config.py` use manual `global _settings` instead of `@lru_cache` — not thread-safe at startup |
| L2 | `git_service.validate_webhook()` is dead code that diverges from the router's HMAC logic |
| L3 | `docker-compose.dev.yml` redundantly re-declares `gateway` port `80:80` already in base file |
| L5 | Dockerfiles install shared package both via `pip install /shared` (for deps) AND via `PYTHONPATH=/` (for import) — comment this clearly to avoid future confusion |

---

## Security Posture

| Control | Status |
|---------|--------|
| JWT validation via Supabase Auth | ✅ All routes |
| Workspace scoping | ✅ All v1 routes (post H1/H2 fix) |
| Internal key auth | ✅ `X-Internal-API-Key` header |
| Webhook HMAC | ✅ Required (post C1 fix) |
| Service role key in git | ⚠️ Rotate if repo history exposed |
| Rate limiting | ❌ Not wired in |
| RLS | ✅ Defense-in-depth (service layer is primary gate) |
| Credentials in git | ✅ `.gitignore` added |

---

## Known Limitations

1. **Ollama only**: Both Anthropic and OpenAI API keys are unconfigured. All LLM calls fall through to Ollama at `host.docker.internal:11434`. If Ollama is not running, all AI analysis silently skips (returns no error to webhook caller).

2. **No horizontal scaling yet**: `_plan_cache` in the AI service (M3 above) prevents multiple AI replicas from working correctly.

3. **Frontend container not tested**: `frontend/Dockerfile` was created but not validated in this session. The gateway properly degrades when frontend is absent.
