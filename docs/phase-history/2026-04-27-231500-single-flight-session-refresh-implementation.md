# Current Phase Tracker

## Task
Implement single-flight frontend session refresh for OPPM editor recovery

## Goal
Eliminate concurrent refresh-token races in the frontend so expired-session page loads do not clear auth state mid-bootstrap and destabilize the OPPM linked Google Sheet editor.

## Plan

### Phase 1: Session coordinator
- [x] Create a shared frontend session client that owns token read/write/clear and refresh behavior
- [x] Ensure refresh requests are single-flight so concurrent `401` handlers wait on the same promise

### Phase 2: Integrate auth surfaces
- [x] Move `frontend/src/lib/api.ts` request helpers onto the shared session client
- [x] Move `frontend/src/stores/authStore.ts` bootstrap and manual refresh onto the same path

### Phase 3: Validate
- [x] Run focused frontend validation for the touched auth/session files
- [x] Check for editor diagnostics in the touched files after the refactor

## Status
Session refresh implementation complete and validated.

## Expected Files
- frontend/src/lib/sessionClient.ts
- frontend/src/lib/api.ts
- frontend/src/stores/authStore.ts
- frontend/src/pages/OPPMView.tsx
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system\frontend" ; npx tsc -b`
- `get_errors` reported no diagnostics in `frontend/src/lib/sessionClient.ts`, `frontend/src/lib/api.ts`, `frontend/src/stores/authStore.ts`, and `frontend/src/pages/OPPMView.tsx`

## Notes
- This phase is intentionally limited to the session-race root cause before touching the OPPM workbook adapter or route state machine.
- As a small adjacent hardening change, `frontend/src/pages/OPPMView.tsx` now routes blank-sheet creation through the shared OPPM sheet builder instead of maintaining a second workbook shape inline.