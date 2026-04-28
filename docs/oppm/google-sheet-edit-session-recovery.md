# Google Sheet Edit Session Recovery Architecture

## Purpose

This document defines the recommended fix architecture for the OPPM linked Google Sheet issue where `Edit in App` can drop visible text, trigger a Fortune Sheet runtime error, and coincide with repeated `401` responses.

This is a design-first document. It explains what should be implemented and why before the implementation phase starts.

Related docs:

- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [AI-SYSTEM-CONTEXT.md](../AI-SYSTEM-CONTEXT.md)
- [frontend/FRONTEND-REFERENCE.md](../frontend/FRONTEND-REFERENCE.md)
- [google-sheets-linked-form.md](google-sheets-linked-form.md)

## Verified Current Behavior

The current implementation has three important characteristics:

1. Frontend requests refresh access tokens independently.
   - `frontend/src/lib/api.ts` retries `401` responses by calling `POST /api/auth/refresh` inside each request helper.
   - `frontend/src/stores/authStore.ts` separately implements refresh behavior during bootstrap and manual session refresh.

2. Backend refresh tokens rotate on every successful refresh.
   - `services/core/services/auth_service.py` revokes the old refresh token and issues a new one on each refresh.

3. The OPPM page mixes auth state, Google Sheet link state, XLSX loading, Fortune conversion, preview fallback, and edit-mode toggling in one route component.
   - `frontend/src/pages/OPPMView.tsx` background-loads linked-sheet XLSX, separately handles `Edit in App`, and also contains an inline blank-sheet generator.
   - A reusable sheet builder already exists in `frontend/src/lib/oppmSheetBuilder.ts`, but the page does not use a single adapter boundary for workbook creation and normalization.

## Root Causes

### 1. Refresh race on concurrent `401` responses

The OPPM route is not the only caller when the page loads. The app shell also starts protected queries such as notifications, and the project route can issue linked-sheet requests at the same time.

Because every request path refreshes independently, an expired session can cause several concurrent `POST /api/auth/refresh` calls.

That is a bad fit with the current backend contract:

- the first refresh succeeds
- the backend rotates the refresh token
- the remaining refresh attempts still use the now-revoked old refresh token
- those later refresh attempts fail with `401`
- the current frontend code clears local tokens immediately on refresh failure

Result: one request can successfully recover while another request clears the session out from under the page.

### 2. OPPM state is not modeled as an explicit state machine

`OPPMView.tsx` currently stores many booleans and imperative transitions:

- linked sheet query state
- background sheet load state
- preview state
- edit mode
- edit loading state
- edit error state
- saved workbook data

This makes it too easy for unrelated failures to bleed into the visible spreadsheet state. An auth failure, an XLSX download failure, and a Fortune conversion failure are all capable of disturbing the same route-local state.

### 3. Workbook input is passed to Fortune Sheet without a dedicated normalization boundary

The runtime error `sheet not found` comes from the Fortune Sheet layer, not from the backend.

The current route directly passes two different workbook sources into the same renderer:

- Fortune data converted from linked-sheet XLSX
- locally generated blank Fortune data

Those sources do not go through one shared validator/normalizer before mounting the `Workbook` component. The effect is that a workbook-shape problem becomes a page-level crash instead of a controlled fallback.

## Recommended Architecture

### A. Frontend session coordinator

Create one shared session coordination module for the whole frontend.

Suggested module: `frontend/src/lib/sessionClient.ts`

Responsibilities:

- own token read/write/clear operations
- expose one in-flight refresh promise at a time
- make refresh single-flight so all pending requests await the same refresh result
- update stored access and refresh tokens exactly once after a successful refresh
- clear tokens only after the shared refresh attempt definitively fails
- provide one typed signal for `session-expired`

This becomes the only place allowed to call `POST /api/auth/refresh`.

### B. Unify `api.ts` and `authStore.ts` around that coordinator

After the session coordinator exists:

- `frontend/src/lib/api.ts` should delegate all refresh behavior to it
- `frontend/src/stores/authStore.ts` should also use the same coordinator for bootstrap and manual refresh
- request helpers (`request`, `requestBlob`, `postFormData`) should share the same retry path instead of re-implementing refresh logic separately

This removes duplicate auth logic and makes refresh-token rotation safe without weakening backend security.

Security [LOW]: Keep refresh-token rotation and revocation on the backend. The fix should serialize client refresh attempts instead of making refresh tokens reusable.

Performance [MED]: Single-flight refresh removes duplicate auth retries during expired-session page loads and prevents redundant follow-up request failures — estimated impact: fewer burst `401`/refresh calls and lower auth traffic during route bootstrap.

### C. Introduce an OPPM sheet adapter boundary

Create a route-independent adapter for linked-sheet loading and blank-sheet creation.

Suggested module: `frontend/src/lib/oppmGoogleSheetAdapter.ts`

Responsibilities:

- download linked-sheet XLSX when appropriate
- convert XLSX into Fortune data
- normalize workbook shape before render
- validate the minimum workbook contract before mounting Fortune Sheet
- return a discriminated result instead of mutating route-local state directly
- generate blank OPPM workbooks through the reusable builder in `frontend/src/lib/oppmSheetBuilder.ts`

Recommended result shape:

```ts
type OppmSheetLoadResult =
  | { kind: 'session-expired' }
  | { kind: 'no-link' }
  | { kind: 'preview'; previewUrl: string; message?: string }
  | { kind: 'workbook-ready'; workbook: FortuneSheetData[]; source: 'linked-sheet' | 'blank-template' }
  | { kind: 'render-error'; message: string; fallbackPreviewUrl?: string }
```

This keeps sheet preparation and validation out of the route component.

### D. Refactor `OPPMView` to an explicit view-state model

The route should become a consumer of prepared states instead of hand-managing every transition.

Recommended top-level view states:

- `bootstrapping-session`
- `session-expired`
- `no-linked-sheet`
- `linked-preview`
- `linked-editor-ready`
- `linked-editor-open`
- `linked-render-error`

Rules:

- never replace a linked workbook with a blank workbook automatically
- preserve the last successful preview or workbook while retrying
- if linked-sheet edit preparation fails, stay on preview and show a retry banner
- if the session is expired, show a re-authentication or retry state instead of collapsing into `no-link`
- keep edit mode transitions separate from load-state transitions

### E. Add an error boundary around Fortune Sheet

The `Workbook` mount should be wrapped in a route-local error boundary so renderer failures do not wipe the page.

If Fortune throws:

- capture the error
- keep the last good sheet or preview state available
- show a recoverable message
- allow retry after re-normalizing workbook data

This prevents a Fortune runtime exception from turning into a destructive user experience.

## Recommended Non-Goals For Phase 1

These are not the first changes to make:

- do not relax backend refresh-token rotation
- do not redesign the backend auth contract first
- do not patch the OPPM route with more booleans and guards before introducing the session coordinator
- do not keep two blank-sheet builders alive after the adapter is introduced

## Proposed Implementation Order

### Phase 1: Session stability

- add the shared session coordinator
- move all refresh behavior in `api.ts` and `authStore.ts` onto that path
- ensure concurrent requests wait for the same refresh result

### Phase 2: Sheet adapter and route boundaries

- create the OPPM sheet adapter
- move linked-sheet preparation and blank-template creation into it
- switch blank template generation to the reusable builder

### Phase 3: OPPM route state machine

- refactor `OPPMView.tsx` to explicit view states
- preserve last known-good sheet state on failure
- differentiate `session-expired`, `preview`, and `render-error`

### Phase 4: Recovery hardening

- wrap Fortune Sheet in an error boundary
- add focused tests for refresh races and editor recovery

## Why This Is The Best Fix

This approach fixes the root cause at the correct boundaries:

- auth/session recovery is fixed once for the whole app instead of per page
- OPPM sheet handling becomes deterministic instead of route-local and ad hoc
- linked Google Sheet preview remains usable even when edit-mode preparation fails
- backend token rotation stays secure
- the spreadsheet renderer stops being the first place that validates workbook shape

In short: the right fix is not to special-case one button. It is to separate session coordination, sheet preparation, and route rendering into three explicit layers.

## Suggested Test Cases

Test: Concurrent refresh is single-flight
Input: Open the OPPM page with an expired access token, a valid refresh token, and multiple protected queries starting at once.
Expected: Exactly one refresh flow runs, pending requests retry successfully, and the user remains authenticated.
Priority: high

Test: Session expiry does not wipe linked-sheet state
Input: Open a linked Google Sheet OPPM page with an expired access token and an invalid refresh token.
Expected: The page enters a `session-expired` state with a recovery prompt; it does not silently show `no linked sheet` or replace linked content with a blank workbook.
Priority: high

Test: Linked-sheet edit failure falls back safely
Input: Click `Edit in App` for a linked sheet whose XLSX converts into an invalid Fortune workbook.
Expected: The route shows a controlled render error with retry options and preserves preview access; the app does not crash with `sheet not found`.
Priority: high

Test: Blank editor uses one canonical builder
Input: Open the OPPM page with no linked sheet and click `Edit in App`.
Expected: The editor loads from the shared OPPM sheet builder path and no route-local blank template generator remains.
Priority: medium