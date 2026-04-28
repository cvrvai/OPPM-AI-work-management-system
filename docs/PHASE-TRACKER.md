# Current Phase Tracker

## Task
Organize the startup helper and fix native microservice startup

## Goal
Move the main startup logic into `deploy/scripts/start-all.ps1`, keep `start-all.ps1` at the repo root as the stable entrypoint, and make native mode launch the full local stack: gateway, core, ai, git, mcp, and the frontend using the gateway-based proxy.

## Plan

### Phase 1: Tracker handoff
- [x] Archive the previous task tracker into `docs/phase-history/`
- [x] Create a new tracker for the startup fix

### Phase 2: Startup script organization
- [x] Move the main script body under `deploy/scripts/`
- [x] Keep the root `start-all.ps1` as a thin compatibility wrapper

### Phase 3: Native startup behavior
- [x] Start the Python gateway before the frontend
- [x] Start the missing `mcp` service in native mode
- [x] Use the native frontend command that proxies through `http://127.0.0.1:8080`
- [x] Align the tunnel target with the native gateway instead of the git service directly
- [x] Keep failed service windows open and write launcher logs under `logs/dev-startup/`

### Phase 4: Validation
- [ ] Validate PowerShell script syntax for both startup files
- [ ] Run the updated root entrypoint and confirm it launches the intended services

## Status
In progress - Phase 4 validation

## Expected Files
- `start-all.ps1`
- `deploy/scripts/start-all.ps1`
- `docs/PHASE-TRACKER.md`

## Verification
- [ ] PowerShell parse check for `start-all.ps1`
- [ ] PowerShell parse check for `deploy/scripts/start-all.ps1`
- [ ] Manual startup run opens gateway/core/ai/git/mcp/frontend processes in native mode
- [ ] Failed child service launch leaves its window open with an error and writes to `logs/dev-startup/*.log`

## Notes
- The frontend native dev path should use the gateway on port `8080`; the old startup path launched `npm run dev` and could leave the UI running without the gateway proxy.
- The previous root script also omitted `services/gateway/start.ps1` and `services/mcp/start.ps1`, which is why the stack was incomplete in native mode.
