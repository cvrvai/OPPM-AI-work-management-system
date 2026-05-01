# Feature: AI Fill And OCR Extraction

Last updated: 2026-05-01

## What It Does

- AI-assisted spreadsheet cell fill based on project data
- OCR-style image extraction to produce structured OPPM JSON
- Template probing algorithm for variable-layout XLSX files

## How It Works

### AI Fill

1. User triggers "AI Fill" in `frontend/src/pages/OPPMView.tsx`.
2. The frontend scans the baseline raw `celldata` using a **positional probing algorithm**:
   - **Task Field**: Scans for `/^Major Tasks/i` or `/^main task/i`. The row below establishes `taskStartRow`.
   - **Date/Timeline Field**: Assumes `col 12` through `col 28` (Excel M–AC). Looks for Excel serial numbers and formats them.
   - **Owner Columns**: Scans the bottom right for `/^Member\s*\d+$/i` or `/^Project\s*Leader$/i`.
   - **Bounds Check**: Looks for "Project Completed By" or "People Working" to prevent overflow.
3. Once landmarks are identified:
   - Objectives (`is_sub=false`) map to `mainTaskCol`
   - Sub-tasks map to `taskCol`
   - Owners map to member columns with `A`, `B`, `C` priority labels
4. `POST /projects/{project_id}/ai/oppm-fill` returns suggested cell values.
5. The frontend injects values into the FortuneSheet data structure.

### OCR Extraction

1. User uploads an image of an OPPM sheet.
2. `POST /ai/oppm-extract` sends the image to a vision model.
3. The model returns structured JSON without saving it directly.
4. The frontend can then import the JSON into the spreadsheet.

## Frontend Files

- `frontend/src/pages/OPPMView.tsx`
- `frontend/src/lib/oppmSheetBuilder.ts`

## Backend Files

- `services/intelligence/domains/analysis/oppm_fill_router.py`
- `services/intelligence/domains/analysis/oppm_fill_service.py`
- `services/intelligence/domains/models/router.py`

## Primary Tables

- `oppm_templates`
- `oppm_header`
- `oppm_task_items`
- `tasks`
- `oppm_objectives`

## Update Notes

- The probing algorithm is designed to handle templates with slight geometry variations.
- When changing the template format, verify the probing regexes still match.
- This is the highest-coupling area in the system — changes here affect both structured data and spreadsheet rendering.
