# Phase Tracker — AI Border Editing Tool for OPPM

## Task
Implement `set_sheet_border` tool and teach the OPPM skill agent to edit FortuneSheet cell borders.

## Goal
- Add a new AI-callable tool `set_sheet_border` to the ToolRegistry
- Store border overrides in the database (project-scoped)
- Teach the OPPM skill system prompt about border editing
- Update the frontend to merge AI border overrides into the FortuneSheet `config.borderInfo`
- Document the FortuneSheet border schema for AI consumption

## Plan

### Phase 1: Architecture & Schema Documentation
- [x] Document FortuneSheet `borderInfo` cell-level schema for AI prompts
- [x] Document component architecture and data pipeline
- [x] Design DB storage for border overrides (`oppm_sheet_overrides` or extend `oppm_templates`)

### Phase 2: Backend — Tool Implementation
- [x] Add `set_sheet_border` handler in `services/intelligence/infrastructure/tools/oppm_tools.py`
- [x] Register tool in ToolRegistry with proper schema
- [x] Add DB model / migration for storing border overrides
- [x] Add repository method to upsert border overrides
- [x] Wire tool into OPPM skill system prompt

### Phase 3: Backend — API & Retrieval
- [x] Add GET endpoint to retrieve border overrides for a project
- [x] Add PUT endpoint to batch upsert border overrides
- [x] Add DELETE endpoint to clear border overrides
- [x] Ensure overrides are returned in the spreadsheet snapshot

### Phase 4: Frontend — Integration
- [x] Fetch border overrides alongside sheet data
- [x] Merge overrides into `config.borderInfo` before rendering FortuneSheet
- [ ] Handle override conflicts (AI vs user manual edits) — deferred to future iteration

### Phase 5: Testing
- [ ] Test tool execution via agent loop
- [ ] Test border override persistence
- [ ] Test frontend merge logic
- [ ] Test edge cases (out-of-range cells, invalid styles)

## Status
Completed — Phases 1-4 implemented. Phase 5 (testing) pending manual verification.

## Expected Files
- `services/intelligence/infrastructure/tools/oppm_tools.py` (add `set_sheet_border`)
- `services/intelligence/infrastructure/skills/oppm_skill.py` (update system prompt)
- `shared/models/oppm.py` (add border override model)
- `services/workspace/domains/oppm/...` (repository + API)
- `frontend/src/lib/oppmSheetBuilder.ts` or `OPPMView.tsx` (merge overrides)
- `docs/...` (border schema documentation)

## Verification Notes
- Agent Fill should be able to say "add a thick bottom border to the header row"
- Border overrides must survive page reload
- Manual user edits via FortuneSheet toolbar should coexist with AI overrides
