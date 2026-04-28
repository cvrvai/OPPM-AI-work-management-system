# Google Sheets Linked Form

This document describes the current Google Sheets integration for the OPPM page as it exists in code today.

Use this document when you need to understand:

- how a project is linked to an existing Google Sheet
- why edits made in Google Sheets can appear inside the app after reload
- how linked sheets are now edited directly inside the website
- what the current buttons and UI states mean
- which parts require backend Google credentials and which parts do not

## Purpose

The OPPM page can use an existing Google Sheet as the primary project form display instead of the older in-app scaffold-only sheet flow.

Linked sheets now use one safe path inside the app:

1. **Embedded Google Sheets editor**
  The frontend embeds the real Google Sheets edit URL directly in an `iframe`, so users edit the linked spreadsheet inside the OPPM page while Google Sheets remains the source of truth.

This is what makes the following behavior possible:

- edit a value in Google Sheets
- return to the OPPM page
- reload or refresh preview
- see the latest Google Sheet content inside the app

That works because the embedded editor is the live Google Sheet itself, not a stale local copy or an in-app workbook export.

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

### 3. Render and edit the linked sheet

For linked sheets, the frontend now follows this flow:

1. Frontend builds `https://docs.google.com/spreadsheets/d/<id>/edit?...`
2. The page embeds that URL in an `iframe`
3. Users edit the live spreadsheet directly inside the website

This keeps editing inside the website while all changes still happen on the original Google Sheet.

## Current UI States

### No linked sheet

Shown when the project has no `google_sheet` metadata.

UI behavior:

- input is empty
- Save Link is available
- page shows a no-link placeholder

### Linked sheet in embedded editor mode

Shown when:

- a sheet is linked
- the frontend can build a Google preview URL

UI behavior:

- the page presents the embedded editor as the primary linked-sheet experience
- users edit the live Google Sheet directly inside the page iframe
- **Open in New Tab** opens the same live sheet in a separate browser tab when needed
- **Push AI Fill** remains controlled by backend credential availability

This is now the recommended and safest linked-sheet workflow.

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

### Open in New Tab

- opens the linked Google Sheet in Google Sheets directly
- useful when the user wants the full standalone Google Sheets window

### Edit in App

- only available when there is no linked Google Sheet yet
- opens a blank local OPPM template for rough drafting inside the app
- it is not used to write back into linked Google Sheets

### Unlink

- removes the saved project-level Google Sheet link

### Refresh Preview

- reloads the browser preview mode inside the page
- useful after editing the Google Sheet in another tab

### Retry App Render

- retries the backend XLSX render path
- only useful when backend Google credentials exist and the backend render may now succeed

## Backend Credential Requirements

### Not required for embedded editor mode

The embedded editor path does **not** require:

- backend Google service-account credentials
- Google Drive export from the backend

It depends on the browser being able to open the linked Google Sheet directly in the user session.

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

### Push route

- `POST /api/v1/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/push`

## Important Current Behavior

- The linked Google Sheet is now the primary display path for linked projects.
- Linked-sheet editing happens in Google Sheets itself, not through an in-app save-back feature.
- The old in-app linked-sheet save path was disabled because rebuilding the sheet from Fortune cell data could destroy the original form structure.
- Missing backend Google credentials should block backend render and push, but they should not crash the basic link-state read path.
- The embedded editor keeps live Google Sheets behavior inside the app.
- The current project/task OPPM data can still exist in the backend even when the page is showing the linked Google Sheet instead of the native OPPM form.
- The native in-app OPPM form endpoints (`header`, `task-items`, `spreadsheet`) are separate from the linked Google Sheet display path.

## Known Limitations

- Embedded editing depends on the user already being signed in to Google in the browser.
- The embedded editor is Google Sheets itself, so behavior and persistence follow Google Sheets.
- Push AI Fill is one-way from the system to Google Sheets.
- The backend does not currently sync arbitrary Google Sheet edits back into the app database models.

## Practical Outcome

If a project is linked to a Google Sheet and the backend cannot render that sheet, the page should still remain useful:

- the link stays saved
- the project page stays loadable
- the live sheet can still be previewed in the app
- users can continue editing in Google Sheets and refresh the preview in the OPPM page

That preview-mode behavior is intentional and is now part of the expected product experience, not just a temporary error workaround.