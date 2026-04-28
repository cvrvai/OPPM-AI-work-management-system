# Current Phase Tracker

## Task
Database-Backed Google Sheets Credentials Setup

## Goal
Allow workspace admins to configure Google Sheets write credentials in the app and store them in the database (encrypted), so Push AI Fill can work without mounting credential files on the server.

## Plan

### Phase 1: Backend Credential Storage
- [ ] Add workspace-scoped setup endpoints for Google Sheets credentials
- [ ] Encrypt/decrypt service-account JSON before storing in workspace settings JSONB
- [ ] Keep environment/file credentials as fallback for backward compatibility

### Phase 2: Status and Validation
- [ ] Update setup-status response to reflect database credential source
- [ ] Expose service-account email from decrypted DB credential when available
- [ ] Keep configuration errors explicit and safe for UI display

### Phase 3: Frontend Setup UX
- [ ] Extend Google Sheets Setup tab with credential paste/save/clear actions
- [ ] Use workspace-scoped setup API routes
- [ ] Refresh status after save/clear and show success/error notices

### Phase 4: OPPM Integration
- [ ] Keep Push AI Fill enablement tied to backend-configured status
- [ ] Ensure existing OPPM setup shortcut continues to work

### Phase 5: Validation
- [ ] Run frontend type validation
- [ ] Run backend syntax validation
- [ ] Rebuild core service and verify setup status shows DB source

## Status
In Progress

## Expected Files
- `services/core/schemas/google_sheets.py`
- `services/core/services/google_sheets_service.py`
- `services/core/routers/v1/oppm.py`
- `frontend/src/pages/Settings.tsx`
- `docs/PHASE-TRACKER.md`

## Verification
- Pending

## Notes
- Security-sensitive data must never be returned in API responses.
- Database credentials should be workspace-scoped and only writable by workspace admins/owners.
