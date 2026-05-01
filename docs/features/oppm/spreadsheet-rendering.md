# Feature: OPPM Spreadsheet Template, Header, Task Items, Import, Export, And AI Fill

Last updated: 2026-05-01

## What It Does

- Spreadsheet-style OPPM editing in the UI
- Saved FortuneSheet JSON per project
- XLSX template import/export
- Per-project OPPM header fields
- OPPM task-numbering rows separate from general tasks
- AI-assisted spreadsheet fill
- OCR-style image extraction to OPPM JSON

## How It Works

1. `frontend/src/pages/OPPMView.tsx` loads `/oppm/spreadsheet` for the current project.
2. If no saved spreadsheet exists, the frontend loads the bundled default XLSX template, converts it to FortuneSheet JSON, and saves it back to the backend.
3. Spreadsheet persistence is handled by `oppm_templates` through `PUT /oppm/spreadsheet`.
4. Additional free-text form data lives in `oppm_header`.
5. Numbered OPPM task rows live in `oppm_task_items`, which are distinct from the general `tasks` table.
6. `GET /oppm/export` renders a current XLSX export from structured data.
7. `POST /oppm/import`, `POST /oppm/preview-xlsx`, and `POST /oppm/import-json` handle spreadsheet and OCR import paths.
8. `POST /projects/{project_id}/ai/oppm-fill` returns suggested cell values derived from project data plus AI.
9. `POST /ai/oppm-extract` uses a vision model to produce structured JSON without saving it directly.

## Frontend Files

- `frontend/src/pages/OPPMView.tsx`

## Backend Files

- `services/workspace/domains/oppm/router.py`
- `services/workspace/domains/workspace/export_service.py`
- `services/intelligence/domains/analysis/oppm_fill_router.py`
- `services/intelligence/domains/models/router.py`
- `services/intelligence/domains/analysis/oppm_fill_service.py`
- `shared/models/oppm.py`

## Primary Tables

- `oppm_templates`
- `oppm_header`
- `oppm_task_items`
- plus the structured OPPM tables

## Update Notes

- This is the highest-coupling area in the system.
- When changing OPPM behavior, check both the structured OPPM API and the spreadsheet/template path.
