# Feature: Google Sheet Edit Session Recovery

Last updated: 2026-05-01

## What It Does

- Defines the recommended fix architecture for OPPM linked Google Sheet issues
- Addresses visible text dropping, Fortune Sheet runtime errors, and repeated `401` responses during "Edit in App"

## Current Issues

1. **Frontend requests refresh tokens independently**
   - `frontend/src/lib/api.ts` retries `401` responses by calling `POST /api/auth/refresh` inside each request helper.
   - `frontend/src/stores/authStore.ts` separately implements refresh behavior during bootstrap and manual session refresh.

2. **Backend refresh tokens rotate on every successful refresh**
   - `services/workspace/domains/auth/service.py` revokes the old refresh token and issues a new one on each refresh.
   - This can cause race conditions when multiple requests fail simultaneously.

3. **OPPM page mixes too many concerns**
   - `frontend/src/pages/OPPMView.tsx` background-loads linked-sheet XLSX, handles `Edit in App`, and contains an inline blank-sheet generator.
   - A reusable sheet builder exists in `frontend/src/lib/oppmSheetBuilder.ts`, but the page does not use a single adapter boundary.

## Recommended Architecture

### Phase 1: Auth Coordination
- Centralize token refresh in `api.ts` with a single in-flight promise.
- Queue concurrent requests during refresh instead of firing multiple refresh calls.

### Phase 2: Sheet Adapter Boundary
- Extract all sheet creation/normalization logic into `oppmSheetBuilder.ts`.
- Make `OPPMView.tsx` a thin coordinator that delegates to the adapter.

### Phase 3: Error Recovery
- Add explicit error boundaries for FortuneSheet runtime errors.
- Fallback to structured OPPM data view when spreadsheet rendering fails.

## Related Docs

- [`google-sheets-integration.md`](google-sheets-integration.md) — Current Google Sheets integration
- [`spreadsheet-rendering.md`](spreadsheet-rendering.md) — FortuneSheet and template architecture
- [`../../architecture/AI-SYSTEM-CONTEXT.md`](../../architecture/AI-SYSTEM-CONTEXT.md) — Auth flow details

## Update Notes

- This is a **design-first document** — it explains what should be implemented before the implementation phase starts.
- The actual fix has not been implemented yet; this doc serves as the specification.
