# Current Phase Tracker

## Task
Google Sheet Status Recovery And OPPM Verification

## Goal
Prevent missing Google service-account files from crashing the OPPM Google Sheet status endpoint, restore the OPPM page to a usable state, and run focused verification of the project/task OPPM surfaces against the live Docker stack.

## Plan

### Phase 1: Failure Analysis
- [x] Capture the failing OPPM Google Sheet route and inspect the controlling backend code path
- [x] Confirm the live Docker `core` container is configured with a missing Google service-account file path

### Phase 2: Backend Recovery
- [x] Make Google Sheets status checks treat missing credentials as "not configured" instead of raising 500
- [x] Expose any non-fatal backend configuration warning in the link-state response

### Phase 3: Frontend Recovery
- [x] Surface the backend configuration warning without breaking the OPPM page

### Phase 4: Validation
- [x] Run focused backend validation
- [x] Rebuild or restart the affected Docker service
- [x] Verify the OPPM page and key project/task endpoints with the live stack

## Status
Complete

## Expected Files
- `services/core/services/google_sheets_service.py`
- `services/core/schemas/google_sheets.py`
- `frontend/src/pages/OPPMView.tsx`
- `docs/PHASE-TRACKER.md`

## Verification
- Confirmed `GET /api/v1/workspaces/.../oppm/google-sheet` calls `_is_backend_configured()` and `_service_account_email()`.
- Confirmed the running `core` container has `GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/google-service-account.json` but that file does not exist inside the container.
- `get_errors` reported no issues in the touched backend and frontend files.
- `python -m py_compile schemas\google_sheets.py services\google_sheets_service.py` in `services/core` passed.
- `npx tsc -p tsconfig.app.json --noEmit` in `frontend` passed.
- Rebuilt the live Docker `core` container with `docker compose -f docker-compose.microservices.yml up -d --build core`.
- Reloaded the live OPPM page and confirmed the Google Sheet link-state route now returns usable data instead of crashing the page.
- Verified the current project OPPM API surface via the authenticated browser session:
	- Combined OPPM route returned `200` with project `3d Enhancement Project`, `6` objectives, `11` tasks, `1` member, and `14` weeks.
	- Objectives route returned `200` with `6` items.
	- Sub-objectives, timeline, deliverables, forecasts, and risks routes returned `200` with empty data for this project.
	- Costs route returned `200` with the expected aggregate shape.
	- Header route returned `200` with `null`.
	- Task-items route returned `200` with an empty array.
	- Spreadsheet route returned `404` with `No spreadsheet template for this project`.
	- Template export returned `200`.
	- OPPM export returned `200`.
	- Google Sheet link-state route returned `200` with `connected=true`, `backend_configured=false`, and `backend_configuration_error="Google service account file does not exist"`.
- Confirmed the page now skips the failing backend XLSX request when backend Google credentials are absent and goes straight to the browser preview fallback.
- Verified the live `Save Link` action succeeds and updates project metadata without backend exceptions even while Google credentials are missing.

## Notes
- The page should still be able to link a Google Sheet and show the browser fallback even when backend Google credentials are absent.
- Missing credentials should block export and push, not the basic link-state read path.
- The native system OPPM form is not currently available for this project through `header`, `task-items`, or `spreadsheet`; the backend data still exists, but the current page is using the linked Google Sheet display path.