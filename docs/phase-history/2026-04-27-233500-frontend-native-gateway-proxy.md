# Current Phase Tracker

## Task
Fix native gateway health routing

## Goal
Make the Python gateway report its own health correctly and forward `/health/{service}` probes to the backend services' real `/health` endpoints instead of returning local 404s.

## Plan

### Phase 1: Trace the health path
- [x] Confirm why `/health` is returning `404` in native gateway mode
- [x] Confirm why `/health/core` is forwarding to a non-existent backend path

### Phase 2: Patch routing
- [x] Register gateway-owned health routes before the catch-all proxy route
- [x] Add explicit upstream health forwarding for `core`, `ai`, `git`, and `mcp`

### Phase 3: Validate
- [x] Reload the native gateway and verify `/health` returns gateway status
- [x] Verify `/health/core`, `/health/ai`, `/health/git`, and `/health/mcp` return backend health

## Status
Completed and validated.

## Expected Files
- services/gateway/main.py
- docs/PHASE-TRACKER.md

## Verification
- `curl.exe -s http://127.0.0.1:8080/health`
- `curl.exe -s http://127.0.0.1:8080/health/core`
- `curl.exe -s http://127.0.0.1:8080/health/ai`
- `curl.exe -s http://127.0.0.1:8080/health/git`
- `curl.exe -s http://127.0.0.1:8080/health/mcp`

## Notes
- Current native gateway behavior returns `404` for `/health` because the catch-all proxy owns that path before the specific route handler.
- Current `/health/{service}` behavior forwards the prefixed path directly to upstream services, but the backend services expose `/health`, not `/health/{service}`.
- The fix keeps `/health` local to the gateway and forwards `/health/{service}` explicitly to each upstream service's `/health` route.