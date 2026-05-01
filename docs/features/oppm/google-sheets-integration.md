# Feature: Google Sheets Integration

Last updated: 2026-05-01

## What It Does

- Links an existing Google Sheet to a project as the primary OPPM display
- Embeds the real Google Sheets editor in an iframe so users edit the live sheet inside the app
- Syncs changes between Google Sheets and the OPPM page on reload

## How It Works

1. A project can be linked to an existing Google Sheet via the OPPM page.
2. The frontend embeds the Google Sheets edit URL directly in an `iframe` on the OPPM page.
3. Users edit the linked spreadsheet inside the app while Google Sheets remains the source of truth.
4. On reload or refresh preview, the app fetches the latest Google Sheet content.

This design means:
- Edit a value in Google Sheets → return to OPPM page → reload → see latest content
- The embedded editor is the **live Google Sheet**, not a stale local copy

## Frontend Files

- `frontend/src/pages/OPPMView.tsx`

## Backend Files

- `services/workspace/domains/oppm/router.py`
- `services/workspace/domains/oppm/service.py`

## Primary Tables

- `oppm_templates`
- `projects` (for `google_sheet_url` or similar link field)

## Update Notes

- This requires backend Google OAuth credentials.
- The iframe approach avoids sync conflicts by using Google Sheets as the single source of truth.
- See [`session-recovery.md`](session-recovery.md) for known issues with auth state during editing.
