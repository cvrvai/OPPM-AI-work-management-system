# Current Phase Tracker

## Task
Switch AI fallback and selectable default model to `gemma4:31b-cloud`

## Goal
Make chat and OPPM AI flows use `gemma4:31b-cloud` instead of the old `kimi-k2.5:cloud` fallback, prefer Gemma when multiple active Ollama models exist, and ensure the frontend can add/select the Gemma cloud model consistently.

## Plan

### Phase 1: Confirm the routing gap
- [x] Verify project chat requests do not currently send `model_id`
- [x] Verify backend AI fallback still defaults to `kimi-k2.5:cloud`
- [x] Verify frontend settings presets do not currently include `gemma4:31b-cloud` in Ollama Cloud

### Phase 2: Patch model selection
- [x] Update backend default fallback model to `gemma4:31b-cloud` and prefer Gemma among active Ollama models
- [x] Add `gemma4:31b-cloud` to the frontend Ollama Cloud presets
- [x] Confirm project chat still uses backend-driven fallback because there is no separate chat model selector in the current UI

### Phase 3: Validate
- [x] Run focused backend/frontend checks for the new fallback and request payload
- [x] Re-check touched files for errors

## Status
Completed and validated.

## Expected Files
- services/ai/services/ai_chat_service.py
- services/ai/services/oppm_fill_service.py
- services/ai/services/ocr_fill_service.py
- frontend/src/pages/Settings.tsx
- docs/PHASE-TRACKER.md

## Verification
- `Set-Location "c:\Users\cheon\work project\internal\OPPM-AI-work-management-system" ; $repoRoot = (Get-Location).Path ; $aiRoot = Join-Path $repoRoot 'services/ai' ; $env:PYTHONPATH = "$repoRoot;$aiRoot" ; @'...smoke check...'@ | python -`
- `frontend build validation in frontend`
- VS Code error check on touched AI service and frontend settings files

## Notes
- The 502 is thrown by the AI service when all candidate models fail with `ProviderUnavailableError`.
- The chat UI currently sends only `messages`, so backend fallback is still controlling model selection in that path.
- The runtime fallback now matches the OCR pipeline's existing `gemma4:31b-cloud` model choice.
- Active-model ordering is now deterministic for Gemma in the shared chat/fill model resolver.
