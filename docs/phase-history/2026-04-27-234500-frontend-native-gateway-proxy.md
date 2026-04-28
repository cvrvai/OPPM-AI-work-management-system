# Current Phase Tracker

## Task
Align frontend dev proxy defaults with the native gateway

## Goal
Make `npm run dev` work with the documented native development flow by defaulting the frontend proxy to the Python gateway on port `8080`, while keeping explicit scripts for Docker gateway and direct per-service proxying.

## Plan

### Phase 1: Trace the proxy source
- [x] Confirm which frontend config owns the dev proxy base
- [x] Verify the current default points local Vite traffic at port `80`

### Phase 2: Align dev entry points
- [x] Make the local frontend default target the native gateway on port `8080`
- [x] Add explicit scripts for Docker gateway mode and direct service proxy mode
- [x] Update the development guide so the commands match the actual proxy behavior

### Phase 3: Validate
- [x] Run a focused frontend build or type check after the config change
- [x] Confirm the dev proxy no longer defaults to `127.0.0.1:80`

## Status
Completed and validated.

## Expected Files
- frontend/.env
- frontend/package.json
- DEVELOPMENT.md
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npm run build`
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npm run dev -- --port 5174`
- `curl.exe -i http://127.0.0.1:5174/api/auth/me`

## Notes
- The controlling config is `frontend/vite.config.ts`, which uses `API_PROXY_BASE` / `VITE_API_PROXY_BASE` when present.
- The original local default in `frontend/.env` pinned `API_PROXY_BASE=http://127.0.0.1:80`, which conflicted with the native gateway started by `./services/gateway/start.ps1` on port `8080`.
- `DEVELOPMENT.md` already tells users to run `npm run dev` in native mode, so the frontend defaults need to match that documented path.
- The validation request returned `401 Missing authentication token`, which confirms Vite reached the backend through the configured proxy instead of failing with `ECONNREFUSED 127.0.0.1:80`.