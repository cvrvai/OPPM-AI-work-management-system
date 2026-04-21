# Current Phase Tracker

## Task
Signup implementation run, full-stack smoke verification, and MCP route reliability fixes

## Goal
Complete end-to-end account creation from the UI, validate cross-service feature paths, and remove blockers discovered during smoke testing (MCP dev proxy mismatch and async MCP tool execution failure).

## Plan
- [x] Bring backend services up with Docker while keeping local Vite frontend running
- [x] Verify core/ai/git/mcp health and frontend proxy readiness
- [x] Create a new account via UI signup flow
- [x] Create first workspace for tenant-scoped testing
- [x] Run full-stack smoke checks across auth, workspace, project, task, OPPM, AI, Git, notifications, and MCP
- [x] Fix MCP tool execution endpoint to await async tools
- [x] Fix Vite dev proxy to route workspace-scoped MCP API paths to port 8003
- [x] Re-run MCP smoke checks through frontend proxy and direct service endpoint
- [x] Summarize outcomes and remaining risks

## Status
Complete

## Files Modified
- `services/mcp/routers/v1/mcp.py`
- `frontend/vite.config.ts`

## Files Archived
- `docs/phase-history/2026-04-20-132200-start-implementation-signup-smoke-mcp-fixes.md`

## Verification Notes
- Signup and workspace bootstrap succeeded through UI.
- Backend containers for postgres, redis, core, ai, git, mcp, and gateway reached healthy/running state.
- Workspace-scoped smoke checks succeeded for auth, workspaces, projects, tasks, OPPM, AI chat, RAG, and Git list routes.
- MCP tool listing and execution both pass through direct service path and frontend proxy path after fixes.
- Gateway `/health` on port 80 still intermittently returns 502 even while proxied auth route `/api/auth/me` returns expected 401 without token.

## Risks
- Gateway health route behavior in docker nginx path may still create false-negative infra alarms.
- Refresh-token rotation can cause old refresh tokens to return 401 in repeated manual smoke calls.

## Outcome
Primary user request is complete: account was created via signup and feature testing was executed across services. Direct DB insertion fallback was not required.