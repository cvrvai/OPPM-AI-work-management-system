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
    "deliverable": "One-sentence deliverable output",
    "start_date": "YYYY-MM-DD",
    "deadline": "YYYY-MM-DD",
    "completed_by_weeks": 31,
    "task_count": 30
}}
```

## Phase 1.8: Batched API calls + authentic Clark Campbell PDF layout (DONE)

Two follow-up upgrades after the user reported a Gateway Timeout and asked for
the scaffold to match the official OPPM PDF reference.

### 1.8a — Gateway Timeout fix
The original scaffold dispatched its 107 sub-actions one-by-one through the
existing `_exec_*` helpers, requiring 107 sequential Google Sheets API calls
(~30s wall-clock). With the gateway proxy timeout at ~60s and Sheets API
rate-limit pauses, the request often timed out before the full form rendered.

- [x] Added `_scaffold_action_to_request(action, params, sheet_id)` that
  builds a single Google Sheets API request dict from a scaffold sub-action,
  mirroring the request shapes used by every per-action helper.
- [x] Refactored `_exec_scaffold_oppm_form` to collect all sub-actions then
  dispatch via just **3 batched calls**:
  1. `clear_sheet` (its own multi-call routine — runs first)
  2. ONE `spreadsheets.values.batchUpdate` carrying every set_value
  3. ONE `spreadsheets.batchUpdate` (chunked at 200 requests) carrying every
     formatting / structural request
- [x] Verified by simulation: 154 sub-actions → 64 value writes + 89 format
  requests → 3 API calls, completes in ~2-3s.

### 1.8b — Authentic PDF layout
Rewrote `_build_scaffold_actions` to match the user-supplied OPPM.pdf
reference (Clark Campbell's official template). New structure:

| Row band | Content |
|---|---|
| Row 1 | Blank spacer |
| Row 2 | Split — `Project Leader: ...` (A:N merged) \| `Project Name: ...` (O:AL merged) |
| Rows 3-4 | MERGED A3:AL4 — multi-line block: Objective + Deliverable + Start + Deadline (wrapped, top-aligned) |
| Row 5 | 4 sub-headers: `Sub objective` (A:F) \| `Major Tasks (Deadline)` (H:I) \| `Project Completed By: N weeks` (J:AI) \| `Owner / Priority` (AJ:AL) |
| Rows 6 .. 5+N | Task rows numbered 1..N in column H (default N=30, can pass 19 for tighter PDF-matching layout) |
| R_PEOPLE | `# People working on the project:` full-width row, gray bg, thick black bottom border |
| R_MATRIX (9 rows) | Bottom cross-reference matrix: rotated A-F sub-objective headers, rotated J-AI week-date headers (computed from start_date if available, else "Week 1"…"Week 12"), rotated AJ-AL owner headers, X-pattern center labels (`Major Tasks` / `Target Dates` / `Sub Objectives` / `Costs` / `Summary & Forecast`) |
| R_SUMMARY (8 rows) | Summary / Forecast / Risk section: rotated G-column section labels (`Summary Deliverable` 4 rows, `Forecast` 2 rows, `Risk` 2 rows) with placeholder text rows merged across I:AL, all wrapped |

Border hierarchy preserved: black header grid, gray task grid (with no
borders inside the timeline area), thick vertical dividers at F/I/AI rights,
thick horizontal dividers at row 5 / last task row / # People / matrix bottom,
thick black outer frame around the whole form.

### 1.8c — set_text_rotation action
Added `set_text_rotation` as a public sheet action so the AI can rotate
arbitrary cells outside the scaffold (e.g. "rotate the column headers
vertically", "make the Summary label sideways"). Registered in
`SUPPORTED_ACTIONS`, dispatcher, scaffold request mapper, and documented in
the OPPM sheet system prompt with two examples.

### Verified
- [x] Compile-clean (`python -m py_compile` on both edited files)
- [x] Smoke test: 154 sub-actions, batches into 3 API calls, zero unhandled
- [x] `set_text_rotation` callable as a top-level AI action

## Phase 1.9: Date-row sizing + image embedding for matrix center (DONE)

User feedback after 1.8b: dates in the matrix top row rendered as just "026"
because the row was too short for the rotated full date string ("16-Feb-2026"),
and the X-pattern text labels (Major Tasks / Target Dates / Sub Objectives /
Costs / Summary & Forecast) were not visually conveying the diamond
diagram from the official OPPM PDF.

### 1.9a — Matrix date-row clipping fix
- [x] Split the single `set_row_height` for the matrix into two:
  - `R_MATRIX_TOP` row → 100px (`_SCAFFOLD_MATRIX_DATE_ROW_HEIGHT`) so rotated week-date labels fit fully
  - `R_MATRIX_TOP+1 .. R_MATRIX_BOTTOM` → 30px (`_SCAFFOLD_MATRIX_BODY_ROW_HEIGHT`) for the X-pattern / image area below

### 1.9b — `insert_image` action (standalone)
- [x] Added `_exec_insert_image` in `sheet_action_executor.py` — wraps a public
  URL in `=IMAGE(url, mode)` and writes via `values.update` with
  `valueInputOption=USER_ENTERED` so Sheets evaluates the formula.
- [x] Defensive URL hygiene: strips surrounding quotes, escapes embedded
  double-quotes for the formula.
- [x] Registered in `SUPPORTED_ACTIONS` and the dispatcher.
- [x] Documented in the OPPM sheet system prompt with two examples and a
  prominent note that the URL must be publicly fetchable from Google's
  servers (localhost / file:// / auth-protected URLs do NOT work; for
  private images, upload to Google Drive and use
  `https://drive.google.com/uc?export=view&id=FILE_ID`).

### 1.9c — `matrix_image_url` param on `scaffold_oppm_form`
- [x] New optional param. When provided, the scaffold:
  - Merges `H{matrix_top+1}:AI{matrix_bottom}` into one large rectangle
  - Writes `=IMAGE(url, 1)` into the top-left of that merge (mode 1 = fit, preserve aspect)
  - Skips the five X-pattern text labels (Major Tasks / Target Dates / Sub Objectives / Costs / Summary & Forecast)
- [x] Backwards compatible: when omitted, falls back to the original five text labels.
- [x] Documented in the PRIORITY 1 section of the prompt with explicit
  guidance that the AI should ASK the user for a public URL rather than
  invent one.

### Verified
- [x] Compile-clean
- [x] Simulation, no image: 155 sub-actions → 64 values + 90 format requests → 3 API calls
- [x] Simulation, with image: 152 sub-actions → 60 values (1 IMAGE formula) + 91 format requests (extra merge) → 3 API calls
- [x] `insert_image` callable as a top-level AI action

## Phase 1.10: Direct image upload from local assets/ (DONE — Option A)

User asked to skip the manual Drive upload step entirely. Now the AI can
just reference an image filename in the project's `assets/` folder and the
backend handles upload + public-share + embed in one shot.

### Scope upgrade
- [x] Added `https://www.googleapis.com/auth/drive.file` to `_GOOGLE_SCOPES`
  in `services/workspace/domains/oppm/google_sheets/constants.py`. This is
  the narrowest scope that lets the service account create files in its own
  Drive and manage permissions on them — does not grant access to the user's
  other Drive content. The existing `drive.readonly` scope is preserved
  (still needed by `writer.py:1265` for sheet exports).

### Upload helper
- [x] `_upload_local_asset_to_drive(sa_info, asset_filename) → {file_id, url}`
  in `sheet_action_executor.py`. Reads from `OPPM_ASSETS_DIR` env var (defaults
  to `<repo-root>/assets/`), uploads via `googleapiclient.http.MediaFileUpload`,
  sets `{type: "anyone", role: "reader"}` permission, returns
  `https://drive.google.com/uc?export=view&id=FILE_ID`.
- [x] Security: `_resolve_safe_asset_path` rejects path traversal (`../`),
  absolute paths, mixed-separator traversal, and empty filenames.
  Verified by 4 negative tests.
- [x] MIME guard: rejects non-image files (auto-detects from extension).
- [x] In-memory cache keyed on `(filename, mtime_ns)` so re-running the
  scaffold with the same asset doesn't re-upload; auto-invalidates when the
  user edits the file on disk.

### `sa_info` plumbing
- [x] `execute_actions` now accepts `*, sa_info=None` and passes it through
  to handlers that need a Drive client.
- [x] `execute_sheet_actions` (in `google_sheets/service.py`) builds the
  credential dict once and passes it as `sa_info` so neither the executor
  nor the handlers need to re-resolve credentials.

### New `upload_asset_to_drive` action
- [x] Standalone sheet action — uploads an asset and OPTIONALLY embeds it
  at a target range via `=IMAGE()` if `range` is given.
- [x] Returns `{file_id, url, asset_filename, mime_type, embedded_at}` so the
  caller / chat UI can show what happened.
- [x] Registered in `SUPPORTED_ACTIONS` and dispatcher.
- [x] Documented in the OPPM sheet system prompt with two natural-language
  examples and a strong note about path-traversal rejection.

### `matrix_image_asset` scaffold param
- [x] New optional param on `scaffold_oppm_form`. When provided,
  `_exec_scaffold_oppm_form` uploads the asset BEFORE building the action
  list and translates it into `matrix_image_url` for `_build_scaffold_actions`.
- [x] Graceful degradation: if upload fails (asset missing, Drive error),
  logs a warning, surfaces the error in the result `summary.matrix_image_upload`,
  and falls back to the five text labels.
- [x] Precedence: explicit `matrix_image_url` wins over `matrix_image_asset`
  (lets the user override the auto-upload if they have a preferred URL).

### Verified
- [x] Compile-clean across all 4 modified files
- [x] Path-traversal: 4 attack variants rejected, legit asset resolves
- [x] Scaffold w/ `matrix_image_url`: 143 sub-actions, 1 IMAGE formula
- [x] Scaffold w/o image: 146 sub-actions, all 5 X-pattern text labels present
- [x] Both new actions registered in `SUPPORTED_ACTIONS`

### Caveats
- The Drive scope change requires a workspace-service restart so the SA
  credential builder picks up the new scope on next request.
- Files uploaded by the SA live in *its* Drive, not the user's Drive. The
  user can still view them via the public link and they're embedded in the
  sheet via `=IMAGE()`, but they won't appear in the user's "My Drive."
- `googleapiclient.http.MediaFileUpload` must be installed (it ships with
  `google-api-python-client` which the project already uses).

## Related Documents
- `docs/AI-AGENT-ARCHITECTURE-RESEARCH.md` — Full research + gap analysis
- `docs/AI-AGENT-IMPLEMENTATION-PLAN.md` — 8-week roadmap
- `services/intelligence/skills/oppm-traditional/template.yaml` — Template definition
