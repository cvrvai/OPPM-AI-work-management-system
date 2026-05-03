# Phase Tracker — AI Agent Architecture Phase 1: TemplateReference

## Task
Build `TemplateReference` class to give the AI a structured, programmatic understanding of the OPPM template so it never guesses row numbers, column widths, or border colors.

## Goal
- Replace text-only prompts with structured YAML template rules
- AI queries template programmatically for exact values (ranges, colors, sizes)
- Validate AI-generated actions against template before execution
- Foundation for Phase 2 (Planning), Phase 3 (Verification), Phase 4 (Learning)

## Plan

### Phase 1.1: Create `TemplateReference` class
- [x] Create `services/intelligence/infrastructure/perception/` directory
- [x] Create `template_reference.py` with `TemplateReference` class
- [x] Methods: `get_border_rule()`, `get_font_rule()`, `get_column_width()`, `get_row_height()`, `get_content_template()`, `validate_action()`
- [x] Load from `services/intelligence/skills/oppm-traditional/template.yaml`

### Phase 1.2: Update OPPM Skill Pre-flight
- [x] Modify `oppm_preflight()` in `oppm_skill.py` to load template reference
- [x] Build `template_summary` string for LLM context
- [x] Inject template summary into preflight_data

### Phase 1.3: Update System Prompt
- [x] Replace text-only OPPM rules in `_OPPM_SYSTEM_PROMPT` with template reference
- [x] Add "TEMPLATE REFERENCE" section that references structured rules
- [x] Remove hardcoded border/font/size rules from prompt (move to YAML)

### Phase 1.4: Add Template Validation
- [x] Add `validate_action()` calls before executing sheet actions
- [x] Warn if AI tries to set border on timeline area (J-AI)
- [x] Warn if AI uses wrong column widths or row heights

### Phase 1.5: Update Frontend (if needed)
- [x] Ensure `oppm-traditional/template.yaml` is accessible
- [x] No frontend changes required for Phase 1

## Status
Completed — Phase 1.1-1.5 implemented. ✅ Tested end-to-end: AI generates 30 actions, all succeed.

## Phase 1.6: Real OPPM Border Structure (IN PROGRESS)
User feedback: current form looks good but borders don't match the real OPPM form (see reference image).

### Goal
Make the sheet look like the authentic Clark Campbell OPPM form with proper visual hierarchy:
- Thick outer frame around entire sheet
- Thick section dividers (sub-objectives → tasks → timeline → owners)
- Clean timeline area with NO borders (for dot markers)
- Professional grid structure

### Changes Made
- [x] Updated `_OPPM_SYSTEM_PROMPT` in `oppm_skill.py` with detailed border editing rules
- [x] Added complete border structure documentation (7 sections: outer frame, header, task area, timeline, dividers, bottom matrix, legend)
- [x] Updated all YAML examples in `template.yaml` to use proper border structure:
  - "Complete fill for empty sheet" example now includes full border setup
  - "Add borders to task rows" example includes thick dividers
  - "Make it standard" example includes complete border hierarchy
  - "Recreate form from scratch" example includes full border structure
- [x] Fixed tool name reference: `set_sheet_border` → `set_border` (correct tool name)
- [x] Added per-side border override examples (top_style, bottom_style, etc.)

### Verification Notes
- [x] AI outputs correct column widths (40, 10, 50, 280, 25, 80) without being told in prompt
- [x] AI knows timeline area (J-AI) should have NO borders
- [x] AI knows header rows (1-5) should have black borders
- [x] AI can answer "What should the border on row 5 be?" by querying template
- [x] Template validation catches incorrect actions before execution
- [x] AI generates thick vertical dividers between sections (F, I, AI) — via scaffold_oppm_form
- [x] AI generates thick bottom border on last task row — via scaffold_oppm_form
- [x] AI generates bottom matrix section with proper borders — via scaffold_oppm_form
- [x] Final sheet visually matches real OPPM form reference image — via scaffold_oppm_form

## Phase 1.7: scaffold_oppm_form server-side macro (DONE)

The LLM was inconsistent at producing all ~80 atomic actions for a full form
(per the user's screenshot: AI emitted 29 actions and stopped at headers,
leaving rows 6-35 + bottom matrix empty). Added a single deterministic
high-level action so the AI emits ONE call and the backend produces a full
authentic OPPM every time.

### Implementation
- [x] `_build_scaffold_actions(params)` and `_exec_scaffold_oppm_form(...)` in
  `services/workspace/domains/oppm/sheet_action_executor.py` — expands to 107
  sub-actions: clear_sheet, header content, 30 task numbers in column H,
  bottom matrix (Month 01-12, Owner labels, Major Tasks/Objectives/Costs/
  Summary & Forecast cross-reference, Capital/Expenses/Other cost area,
  Expended/Budgeted legend), full border hierarchy (header black grid, task
  area gray grid, timeline cleared, F/I/AI thick vertical dividers, row 5 +
  last-task-row thick horizontal dividers, outer thick black frame), fonts,
  alignment, text wrap CLIP, freeze 5 rows.
- [x] Registered in `SUPPORTED_ACTIONS` and dispatcher; result includes
  `summary` with executed/failed/sample_errors counts.
- [x] System prompt updated in `services/intelligence/domains/chat/service.py`:
  added "PRIORITY 1 — Full-form scaffold shortcut" section, replaced verbose
  Example 6 (manual recreate) with single scaffold call, updated clear_sheet
  description and the "Delete the form and recreate" decision rule to redirect
  to scaffold_oppm_form.

### Action params (all optional)
```json
{ "action": "scaffold_oppm_form", "params": {
    "title": "Project name",
    "leader": "Project leader name",
    "objective": "One-sentence objective",
    "start_date": "YYYY-MM-DD",
    "deadline": "YYYY-MM-DD",
    "completed_by_weeks": 31,
    "task_count": 30
}}
```

## Related Documents
- `docs/AI-AGENT-ARCHITECTURE-RESEARCH.md` — Full research + gap analysis
- `docs/AI-AGENT-IMPLEMENTATION-PLAN.md` — 8-week roadmap
- `services/intelligence/skills/oppm-traditional/template.yaml` — Template definition
