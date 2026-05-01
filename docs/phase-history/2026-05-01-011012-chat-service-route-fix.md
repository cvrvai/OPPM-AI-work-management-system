# Current Phase Tracker

## Task
Fix chat-service route ownership and prompt stability across the frontend shell and AI service.

## Goal
Remove frontend calls to unsupported AI model routes, ensure project-scoped pages bind the chat panel to the correct project route, and add the missing project-chat history guardrail so long conversations do not overflow the AI prompt.

## Plan

### Phase 1: Tracker handoff
- [x] Archive the previous task tracker into `docs/phase-history/`
- [x] Create a new tracker for the chat-service fix

### Phase 2: Frontend route ownership cleanup
- [ ] Remove unsupported `/ai/models` fallbacks from Settings
- [ ] Remove unsupported non-workspace project detail fallbacks

### Phase 3: Mixed-service page chat context
- [ ] Bind OPPMView chat to the current project context

### Phase 4: AI prompt stability
- [ ] Add project-chat history truncation similar to workspace chat
- [ ] Reuse the same history budget helper for workspace chat

### Phase 5: Validation
- [ ] Build the frontend after route/context fixes
- [ ] Run a focused Python compile check on the AI chat service

## Status
In progress - Phase 2 frontend cleanup

## Expected Files
- `frontend/src/pages/Settings.tsx`
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/OPPMView.tsx`
- `services/ai/services/ai_chat_service.py`
- `docs/PHASE-TRACKER.md`

## Verification
- [ ] `cd frontend && npm run build`
- [ ] `python -m py_compile services/ai/services/ai_chat_service.py`
- [ ] Manual spot-check: Settings AI models waits for workspace selection and does not call `/ai/models`
- [ ] Manual spot-check: OPPMView chat opens in project context and project chat survives longer histories

## Notes
- Verified route ownership: AI model CRUD is only mounted under `/api/v1/workspaces/{workspace_id}/ai/models*`; no backend service owns `/api/ai/models*`.
- Verified chat ownership: project and workspace chat both route to `services/ai/routers/v1/ai_chat.py`, while OPPM and Google Sheet flows remain owned by `services/core/routers/v1/oppm.py`.
