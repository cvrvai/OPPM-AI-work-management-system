# Current Phase Tracker

## Task

Fix OPPM sheet builder column layout to match the reference XLSX template exactly — correct column counts, widths, and proportions section by section.

## Goal

- Match the reference OPPM column structure: 6 narrow sub-obj cols, **5** task cols, N date cols, up to 6 member cols, 4 legend cols.
- Match the header split point: "Project Leader:" = B–L, "Project Name:" = M onwards.
- Info block: 2 merged rows with multiline text (Objective: Text, Deliverable: Text, Start, Deadline).
- Correct column widths for 5-column task area.

## Column-by-Column Analysis

### Reference OPPM Layout (deep OCR from reference image)

| # | Section | Col Range (0-idx) | Count | Width | Purpose |
|---|---------|-------------------|-------|-------|---------|
| 0 | Spacer | 0 | 1 | 30px | Left margin row-number area |
| 1 | Sub-objectives | 1–6 | 6 | 25px each | Narrow checkmark grid |
| 2 | Task text | 7–11 | 5 | Col 7: 80px; cols 8–11: 55px each | Merged per row for task name + deadline |
| 3 | Date/Timeline | 12–23 | 0–24 (default 12) | 38px each | Status symbols per week |
| 4 | Owner/Member | 24–28 | 1–6 (default 5) | 60px each | Priority letters (A/B/C) |
| 5 | Legend | 29–32 | 4 (fixed) | 1st: 40px; rest: 60px | Priority + Identity Symbol panels |

**Header split proof:** "Project Leader:" at cols 1–11 (B–L), "Project Name:" at cols 12+ (M–end).
Total columns: 1 + 6 + 5 + 12 + 5 + 4 = **33** (A through AG), fits within visible AI range.
| 1 | Sub-objectives | 1–6 | 6 | 25px each | Narrow checkmark grid linking tasks to sub-objectives |
| 2 | Task text | 7–11 | **5** | Col 7: 80px; cols 8–11: 55px | Merged per row for task name |
| 3 | Date/Timeline | 12–23 | 0–24 (default 12) | 38px each | Week status symbols |
| 4 | Owner/Member | 24–28 | 1–6 (default 5) | 60px each | Priority letters |
| 5 | Legend | 29–32 | 4 (fixed) | 1st: 40px; rest: 60px | Priority + Identity panels |

### Deep OCR Findings (v3 correction)

1. **TASK_COLS was set to 14** — but reference image shows only ~5 columns for tasks (H–L). Header split at col L confirmed this.
2. **Info block text** — reference shows "Project Objective: Text" and "Deliverable Output : Text" (with placeholder "Text").
3. **Column widths** — task cols needed to be wider (80px + 55px each) since there are fewer of them.
4. **Total column count** — 33 columns (A–AG) fits within the visible range in the reference.

### Row Structure (Reference)

| Row (0-idx) | Content |
|-------------|---------|
| 0 | Empty spacer |
| 1 | Header: "Project Leader:" / "Project Name:" (1 row, gray bg) |
| 2–3 | Info block: 2 rows merged, multiline (Objective: Text, Deliverable: Text, Start, Deadline) |
| 4 | Column headers: Sub objective / Major Tasks (Deadline) / Completed By / Owner-Priority |
| 5–20 | Task grid (default 16 rows): sub-obj checks, task text, date dots, member letters |
| 21 | Separator bar (gray) |
| 22–25 | Gap rows (Identity Symbol panel in legend cols) |
| 26 | "# People working on the project:" bar |
| 27 | Bottom label row (sub-obj numbers 1–6) |
| 28–33 | Bottom section: rotated sub-obj labels, "Major Tasks", "Target Dates", member names |

## Plan

1. ~~Change TASK_COLS from 6 to 14~~ → Changed to 5 based on deep OCR.
2. ~~Fix column widths~~ → Updated for 5-col layout.
3. ~~Update info block text~~ → Added "Text" placeholders.
4. Verify TypeScript diagnostics.

## Status

- `Completed` — TASK_COLS corrected: 6 → 14 → **5** (matched to reference image header split).
- `Completed` — column widths: task first 80px, rest 55px; members 60px; legend 40+60.
- `Completed` — info text: "Project Objective: Text", "Deliverable Output : Text".
- `Completed` — version bumped to `scalable-v3`.
- `Completed` — TypeScript diagnostics: 0 errors.

## Files Expected

- `frontend/src/lib/oppmSheetBuilder.ts` (edited) ✓
- `docs/PHASE-TRACKER.md` (this file) ✓

## Verification

- TypeScript diagnostics: 0 errors in oppmSheetBuilder.ts and OPPMView.tsx.

## Notes

- Previous tracker archived as `docs/phase-history/2026-04-08-170000-scalable-oppm-grid-sections.md`.
- Reference sources: `services/core/exports/oppm_exporter.py` (layout constants), user screenshots (visual target).
