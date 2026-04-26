# Current Phase Tracker

## Task
Frontend Env-Based Proxy Communication

## Goal
Make the frontend use env-based configuration for backend communication during development so native `npm run dev` can target either the Docker gateway or direct service ports without editing source code.

## Plan

### Phase 1: Proxy Source Of Truth
- [x] Confirm how Vite currently decides API proxy targets
- [x] Confirm whether frontend `.env` is currently loaded into the proxy config
- [x] Confirm the currently reachable backend entry point for the user's running Docker stack

### Phase 2: Implementation
- [x] Load frontend env files in `vite.config.ts`
- [x] Prefer an env-provided proxy base when present
- [x] Set the local frontend env to use the Docker gateway for the current workflow

### Phase 3: Validation
- [x] Validate the updated Vite config
- [x] Validate that the env-based proxy resolves to the gateway instead of `127.0.0.1:8000`

## Status
Complete

## Expected Files
- `frontend/vite.config.ts`
- `frontend/.env`
- `docs/PHASE-TRACKER.md`

## Verification
- Confirmed `core` is healthy in Docker but only exposed internally, while `gateway` is reachable on `localhost:80`.
- Confirmed the native Vite dev server currently hardcodes `127.0.0.1:8000` when no env proxy base is loaded.
- `get_errors` reported no issues in `frontend/vite.config.ts` and `frontend/.env` after the change.
- `node -e "const { loadEnv } = require('vite'); ..."` in `frontend` resolved `API_PROXY_BASE` to `http://127.0.0.1:80` from `frontend/.env`.
- Running `npm run dev` in `frontend` and requesting `http://localhost:5174/api/auth/me` returned `401`, confirming the proxy now reaches the backend through the gateway instead of failing with `502`.

## Notes
- The shortest stable local path is `API_PROXY_BASE=http://127.0.0.1:80` so the native frontend talks to the Docker gateway.
- This keeps frontend source code unchanged across Docker and native frontend workflows.