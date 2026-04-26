# Google Sheets Linked Form

This document describes the current Google Sheets integration for the OPPM page as it exists in code today.

Use this document when you need to understand:

- how a project is linked to an existing Google Sheet
- why edits made in Google Sheets can appear inside the app after reload
- when the app uses backend rendering versus browser preview mode
- what the current buttons and UI states mean
- which parts require backend Google credentials and which parts do not

## Purpose

The OPPM page can use an existing Google Sheet as the primary project form display instead of the older in-app scaffold-only sheet flow.

This is intentionally split into two rendering paths:

1. **Backend app render**
   The backend exports the linked Google Sheet as XLSX, the frontend converts it to FortuneSheet data, and the app renders the sheet inside the page.
2. **Browser preview mode**
   If backend rendering is unavailable, the frontend embeds a live Google Sheets browser preview directly in an `iframe`.

Browser preview mode is what makes the following behavior possible:

- edit a value in Google Sheets
- return to the OPPM page
- reload or refresh preview
- see the latest Google Sheet content inside the app

That works because the preview is reading the live Google Sheet from Google, not a stale local copy.

## Files And Ownership

Frontend:

- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/lib/api.ts`

Core backend:

- `services/core/routers/v1/oppm.py`
- `services/core/services/google_sheets_service.py`
- `services/core/schemas/google_sheets.py`

Docker/runtime setup:

- `docker-compose.microservices.yml`
- `services/.env.example`
- `services/secrets/google-service-account.json` on the host machine

## Data Model

The Google Sheet link is stored per project in `projects.metadata` under the `google_sheet` key.

Stored values:

- `spreadsheet_id`
- `spreadsheet_url`

This means the Google Sheet link is project-scoped, not workspace-global.

## User Flow

### 1. Link a Google Sheet

The user opens `/projects/:id/oppm`, pastes either:

- a Google Sheets URL
- or a raw spreadsheet ID

and clicks **Save Link**.

The backend then:

- parses the spreadsheet ID
- stores the canonical Google Sheet URL in the project metadata
- records an audit log entry

### 2. Load the linked sheet in the app

When the OPPM page loads, it requests:

- `GET /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet`

That response tells the frontend:

- whether a sheet is linked
- whether backend Google credentials are configured
- which spreadsheet is linked
- whether there is a non-fatal backend configuration warning

### 3. Choose a render path

The frontend uses one of these paths:

#### Path A: Backend app render

Used when backend Google credentials are available.

Flow:

1. Frontend requests `GET /oppm/google-sheet/xlsx`
2. Core uses Google Drive export to fetch XLSX bytes for the linked sheet
3. Frontend converts the XLSX to FortuneSheet data with `@corbe30/fortune-excel`
4. The page renders the sheet through `@fortune-sheet/react`

This is the preferred in-app render path because it keeps the sheet inside the app’s spreadsheet renderer.

#### Path B: Browser preview mode

Used when backend render is unavailable, including these cases:

- Google service-account file is missing
- Google libraries are missing in the backend container
- backend export fails but the Google Sheet URL/ID is still valid

Flow:

1. Frontend builds `https://docs.google.com/spreadsheets/d/<id>/preview?...`
2. The page embeds that URL in an `iframe`
3. The browser shows the live Google Sheet preview using the user’s own Google session

This is why edits made directly in Google Sheets can appear in the OPPM page after reload.

## Current UI States

### No linked sheet

Shown when the project has no `google_sheet` metadata.

UI behavior:

- input is empty
- Save Link is available
- page shows a no-link placeholder

### Linked sheet with backend app render ready

Shown when:

- a sheet is linked
- backend Google credentials are configured
- XLSX export succeeds

UI behavior:

- page shows linked sheet status
- **Push AI Fill** is enabled
- app attempts FortuneSheet render from backend XLSX

### Linked sheet in browser preview mode

Shown when:

- a sheet is linked
- backend app render is unavailable
- the frontend can still build a Google preview URL

UI behavior:

- the page presents preview mode as an intentional state, not a crash
- preview text explains that changes made in Google Sheets can appear after refresh
- **Refresh Preview** reloads the embedded browser preview
- **Open in Google Sheets** opens the live sheet in a new tab
- **Push AI Fill** remains disabled until backend credentials are configured

This is the current recommended fallback for Docker setups that have not yet mounted a Google service-account key.

### Linked sheet unavailable

Shown only when:

- the linked sheet cannot be rendered by the backend
- and the frontend cannot build a valid browser preview URL

This is the true error state.

## Buttons On The OPPM Page

### Save Link

- validates and saves the Google Sheet URL or spreadsheet ID
- updates project metadata
- refreshes the link-state query

### Push AI Fill

- calls the AI OPPM fill route
- sends the generated fill payload to the core Google Sheets push route
- writes three tabs in the linked spreadsheet:
  - `OPPM Summary`
  - `OPPM Tasks`
  - `OPPM Members`

This requires backend Google credentials and spreadsheet access.

### Open Sheet

- opens the linked Google Sheet in Google Sheets directly

### Unlink

- removes the saved project-level Google Sheet link

### Refresh Preview

- reloads the browser preview mode inside the page
- useful after editing the Google Sheet in another tab

### Retry App Render

- retries the backend XLSX render path
- only useful when backend Google credentials exist and the backend render may now succeed

## Backend Credential Requirements

### Not required for browser preview mode

The browser preview path does **not** require:

- backend Google service-account credentials
- Google Drive export from the backend

It depends on the browser being able to view the linked Google Sheet directly.

### Required for backend app render and Push AI Fill

The backend path requires:

- `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON`
- Google client libraries installed in the backend container
- the linked spreadsheet shared with the service-account email

For Docker in this repository, the expected file path is:

- host: `services/secrets/google-service-account.json`
- container: `/run/secrets/google-service-account.json`

See `docs/docker/README.md` for the Docker wiring details.

## API Surface

### Link-state routes

- `GET /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet`
- `PUT /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet`
- `DELETE /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet`

### Render route

- `GET /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/xlsx`

### Push route

- `POST /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/push`

## Important Current Behavior

- The linked Google Sheet is now the primary display path for linked projects.
- Missing backend Google credentials should block backend render and push, but they should not crash the basic link-state read path.
- Browser preview mode is read-only inside the app.
- The current project/task OPPM data can still exist in the backend even when the page is showing the linked Google Sheet instead of the native OPPM form.
- The native in-app OPPM form endpoints (`header`, `task-items`, `spreadsheet`) are separate from the linked Google Sheet display path.

## Known Limitations

- Browser preview mode depends on the user already being signed in to Google in the browser.
- Browser preview mode is not the same as full FortuneSheet render and may look slightly different.
- In-app editing of Google Sheets is not implemented; edits happen in Google Sheets itself.
- Push AI Fill is one-way from the system to Google Sheets.
- The backend does not currently sync arbitrary Google Sheet edits back into the app database models.

## Practical Outcome

If a project is linked to a Google Sheet and the backend cannot render that sheet, the page should still remain useful:

- the link stays saved
- the project page stays loadable
- the live sheet can still be previewed in the app
- users can continue editing in Google Sheets and refresh the preview in the OPPM page

That preview-mode behavior is intentional and is now part of the expected product experience, not just a temporary error workaround.