# OPPM Features

Last updated: 2026-05-01

The OPPM (One Page Project Manager) domain is the most complex feature area in the system. It has two parallel data layers:

1. **Structured OPPM Planning** — API-driven data model with objectives, sub-objectives, timeline, costs, deliverables, forecasts, risks, and task links.
2. **Spreadsheet OPPM** — Visual spreadsheet rendering using `@fortune-sheet/react`, with XLSX import/export, template storage, and AI-assisted fill.

## Sub-Features

| Feature | File | Description |
|---------|------|-------------|
| Structured OPPM Planning | [`structured-planning.md`](structured-planning.md) | Objectives, timeline, costs, risks, task links |
| Spreadsheet Rendering & Templates | [`spreadsheet-rendering.md`](spreadsheet-rendering.md) | FortuneSheet, XLSX import/export, templates |
| Google Sheets Integration | [`google-sheets-integration.md`](google-sheets-integration.md) | Linked Google Sheets, embedded editor |
| AI Fill & OCR Extraction | [`ai-fill-and-extract.md`](ai-fill-and-extract.md) | AI-assisted cell fill, image-to-OPPM extraction |
| Session Recovery | [`session-recovery.md`](session-recovery.md) | Auth and edit session recovery design |

## Key Caveats

- This is the **highest-coupling area** in the system.
- When changing OPPM behavior, check **both** the structured OPPM API and the spreadsheet/template path.
- The frontend uses a **positional probing algorithm** for template detection rather than hard-coded cell coordinates.
- `oppm_task_items` are distinct from the general `tasks` table.

## Related Docs

- [`../../architecture/ai-system-context.md`](../../architecture/ai-system-context.md) — Feature sections 6 and 7
- [`../../database/schema.md`](../../database/schema.md) — OPPM table definitions
- [`../../ai/AI-PIPELINE-REFERENCE.md`](../../ai/AI-PIPELINE-REFERENCE.md) — AI pipeline for OPPM fill
- [`../../frontend/FRONTEND-REFERENCE.md`](../../frontend/FRONTEND-REFERENCE.md) — Frontend OPPM patterns
