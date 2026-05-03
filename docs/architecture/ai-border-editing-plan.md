# Architecture Plan: AI Border Editing for OPPM FortuneSheet

> **Scope:** Document the component architecture, data pipeline, and FortuneSheet border schema for the `set_sheet_border` AI tool.
> **Status:** Design phase — not yet implemented.

---

## 1. Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + FortuneSheet)                                            │
│  ────────────────────────────────                                             │
│  OPPMView.tsx                                                               │
│    ├── Loads sheet data from /api/v1/workspaces/{ws}/projects/{id}/        │
│    │   oppm/spreadsheet  →  FortuneSheet JSON (celldata + config.borderInfo) │
│    ├── NEW: Loads border overrides from /api/v1/workspaces/{ws}/projects/   │
│    │   {id}/oppm/border-overrides  →  Array<BorderOverride>                │
│    ├── mergeBorderOverrides(sheet, overrides)  →  patched config.borderInfo  │
│    └── Renders <FortuneSheet config={patchedConfig} />                     │
│                                                                              │
│  User clicks border picker toolbar → onOp callback → PATCH border overrides │
│  (optional: teach AI from user manual edits)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKSPACE SERVICE (FastAPI)                                                │
│  ───────────────────────────                                                │
│  routers/v1/oppm.py                                                         │
│    ├── GET /oppm/spreadsheet  →  reads OPPMTemplate.sheet_data (JSONB)     │
│    ├── NEW: GET /oppm/border-overrides  →  reads OPPMBorderOverride rows   │
│    ├── NEW: PUT /oppm/border-overrides  →  upserts OPPMBorderOverride rows │
│    └── (existing) POST /oppm/google-sheet/push  →  writes to Google Sheets │
│                                                                              │
│  repositories/oppm_repository.py                                            │
│    ├── (existing) find_template(), upsert_template()                        │
│    └── NEW: find_border_overrides(), upsert_border_override()              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTELLIGENCE SERVICE (FastAPI)                                             │
│  ──────────────────────────────                                             │
│  skills/oppm_skill.py                                                       │
│    ├── system_prompt now includes border editing instructions              │
│    └── pre_flight loads border overrides into context snapshot              │
│                                                                              │
│  tools/oppm_tools.py                                                        │
│    ├── (existing) create_objective, set_timeline_status, ...               │
│    └── NEW: set_sheet_border  →  writes to OPPMBorderOverride via API      │
│                                                                              │
│  rag/agent_loop.py                                                          │
│    ├── (existing) TAOR loop calls tools from ToolRegistry                    │
│    └── set_sheet_border is now available when OPPM skill is active         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATABASE (PostgreSQL)                                                      │
│  ─────────────────────                                                      │
│  oppm_templates                                                             │
│    ├── id, project_id, workspace_id, sheet_data (JSONB), ...             │
│    └── Stores the full FortuneSheet JSON snapshot                          │
│                                                                              │
│  NEW: oppm_border_overrides                                                 │
│    ├── id (UUID PK)                                                         │
│    ├── project_id (UUID FK → projects)                                      │
│    ├── workspace_id (UUID FK → workspaces)                                  │
│    ├── cell_row (INTEGER)  — 0-indexed row                                  │
│    ├── cell_col (INTEGER)  — 0-indexed column                               │
│    ├── side (VARCHAR(10))  — 'top' | 'bottom' | 'left' | 'right'           │
│    ├── style (VARCHAR(20)) — 'thin' | 'medium' | 'thick' | 'dashed' | ...   │
│    ├── color (VARCHAR(7))  — hex, e.g. '#000000'                          │
│    ├── created_by (UUID FK → users)  — 'ai' or user_id                     │
│    ├── created_at (TIMESTAMPTZ)                                             │
│    └── updated_at (TIMESTAMPTZ)                                             │
│                                                                              │
│  Index: (project_id, cell_row, cell_col, side) UNIQUE                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Pipeline

### 2.1 Read Path (Frontend → Sheet Render)

```
1. OPPMView mounts
   → GET /api/v1/workspaces/{ws}/projects/{id}/oppm/spreadsheet
   → Returns: { celldata: [...], config: { borderInfo: [...], merge: {...}, ... } }

2. OPPMView also calls
   → GET /api/v1/workspaces/{ws}/projects/{id}/oppm/border-overrides
   → Returns: [ { cell_row, cell_col, side, style, color }, ... ]

3. mergeBorderOverrides(sheet, overrides):
   a. Convert overrides to FortuneSheet borderInfo format
   b. Merge into existing config.borderInfo (overrides win on conflict)
   c. Return patched sheet object

4. <FortuneSheet data={patchedSheet} /> renders with AI/user border edits applied
```

### 2.2 Write Path (AI Agent → Border Override)

```
1. User clicks "Agent Fill" or asks chat assistant to "add a thick border to row 1"

2. Agent loop (TAOR) activates OPPM skill
   → system_prompt includes border editing rules

3. LLM decides to call tool:
   → set_sheet_border({
       cell_range: "A1:AL1",
       borders: { bottom: { style: "thick", color: "#000000" } }
     })

4. Tool handler (_set_sheet_border):
   a. Parse cell_range into (row_start, row_end, col_start, col_end)
   b. For each cell in range, for each specified side:
      - Upsert OPPMBorderOverride row
   c. Return ToolResult with updated_entities=["oppm_border_overrides"]

5. Post-flight (oppm_postflight):
   → Detects "oppm_border_overrides" in updated_entities
   → Frontend invalidates border-overrides query key
   → Sheet re-renders with new borders
```

### 2.3 Write Path (User Manual Edit → Border Override)

```
1. User selects cells in FortuneSheet, clicks border picker toolbar

2. FortuneSheet onOp callback fires with operation details

3. Frontend converts FortuneSheet border change to override format

4. PATCH /api/v1/workspaces/{ws}/projects/{id}/oppm/border-overrides
   → Upserts rows in oppm_border_overrides

5. (Optional future) Feed user manual edits back to AI as training examples
```

---

## 3. FortuneSheet Border Schema (for AI Prompts)

### 3.1 Cell-Level Border Format

FortuneSheet uses **cell-level** `borderInfo` (not range-level) to avoid clipping issues:

```typescript
interface FortuneSheetBorderInfo {
  rangeType: "cell"           // Always "cell" for OPPM
  value: {
    row_index: number          // 0-indexed row
    col_index: number          // 0-indexed column
    l?: BorderSide            // left border
    r?: BorderSide            // right border
    t?: BorderSide            // top border
    b?: BorderSide            // bottom border
  }
}

interface BorderSide {
  style: number               // 1=thin, 2=hair, 3=dotted, 4=dashed,
                              // 5=mediumDashDot, 6=medium, 7=double,
                              // 8=medium (used in OPPM), 9=thick, 10=mediumDashed,
                              // 11=slantDashDot, 13=thick (Excel mapping)
  color: string               // Hex color, e.g. "#000000"
}
```

### 3.2 OPPM Builder Constants

From `frontend/src/lib/oppmSheetBuilder.ts`:

```typescript
const BLK = '#000000'
const THIN = { style: 1, color: BLK }   // thin black
const MED  = { style: 8, color: BLK }   // medium black (OPPM default)
```

### 3.3 Builder Helper Functions

```typescript
// Draw a single cell's borders
function borderCell(r, c, sides: { l?: BS; r?: BS; t?: BS; b?: BS })

// Draw outer frame around rectangle
function drawFrame(borders, r1, c1, r2, c2, style = MED)

// Draw horizontal line (bottom border across columns)
function drawHLine(borders, row, c1, c2, side = 'b', style = THIN)

// Draw vertical line (right border across rows)
function drawVLine(borders, col, r1, r2, side = 'r', style = THIN)

// Draw full grid (all 4 sides on every cell)
function drawGrid(borders, r1, c1, r2, c2, style = THIN)
```

### 3.4 AI Prompt — Border Editing Rules

```
## Border Editing Rules

When the user asks to modify cell borders, call `set_sheet_border`.

### Parameters
- cell_range: A1 notation range, e.g. "A1:AL1" or "H6:H10"
- borders: Object specifying which sides to modify:
  { top?: { style, color }, bottom?: { style, color },
    left?: { style, color }, right?: { style, color } }

### Style values
- "thin"  → style: 1  (default for internal grid lines)
- "medium"→ style: 8  (default for section dividers in OPPM)
- "thick" → style: 9  (use for emphasis, outer frames)
- "dashed"→ style: 4  (use for temporary / draft areas)

### Color values
- "#000000" → black (default)
- "#CCCCCC" → light gray (subtle dividers)
- "#FF0000" → red (highlighting issues)

### Important notes
- Row and column indexes in cell_range are 1-based (A1 = row 0, col 0 internally)
- The tool converts A1 notation to 0-indexed internally
- Only specify the sides you want to CHANGE — unspecified sides are left untouched
- To REMOVE a border side, set style to "none"
- After inserting new rows, ALWAYS re-apply borders to maintain visual consistency
```

---

## 4. API Surface

### 4.1 New Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/workspaces/{ws}/projects/{id}/oppm/border-overrides` | Member | Returns all border overrides for the project |
| `PUT` | `/api/v1/workspaces/{ws}/projects/{id}/oppm/border-overrides` | Write | Upserts border overrides (batch) |
| `DELETE` | `/api/v1/workspaces/{ws}/projects/{id}/oppm/border-overrides` | Write | Clears all border overrides |

### 4.2 Request/Response Schemas

**PUT /border-overrides (batch upsert)**
```json
{
  "overrides": [
    {
      "cell_row": 0,
      "cell_col": 0,
      "side": "bottom",
      "style": "thick",
      "color": "#000000"
    }
  ]
}
```

**GET /border-overrides (response)**
```json
{
  "items": [
    {
      "id": "uuid",
      "cell_row": 0,
      "cell_col": 0,
      "side": "bottom",
      "style": "thick",
      "color": "#000000",
      "created_by": "uuid",
      "created_at": "2026-05-02T10:00:00Z"
    }
  ]
}
```

---

## 5. Cross-Cutting Concerns

### 5.1 Conflict Resolution

When AI overrides and manual user edits overlap on the same (row, col, side):
- **Last-write-wins** based on `updated_at`
- Frontend merge: overrides are applied ON TOP of generated scaffold
- If user manually edits a cell that has an AI override, the user edit wins (upsert with user_id)

### 5.2 Performance

- Border overrides are small (typically < 200 rows per project)
- Fetch alongside sheet data or via separate lightweight endpoint
- Frontend caches overrides in React Query with 5-min staleTime

### 5.3 Security

- All endpoints workspace-scoped via `require_write`
- `created_by` field tracks whether AI or user made the change
- Never expose internal sheet coordinates to unauthorized users

---

## 6. Migration Plan

```sql
-- 005-oppm-border-overrides.sql
CREATE TABLE IF NOT EXISTS oppm_border_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    cell_row INTEGER NOT NULL,
    cell_col INTEGER NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('top', 'bottom', 'left', 'right')),
    style VARCHAR(20) NOT NULL CHECK (style IN ('thin', 'medium', 'thick', 'dashed', 'dotted', 'none')),
    color VARCHAR(7) NOT NULL DEFAULT '#000000',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, cell_row, cell_col, side)
);

CREATE INDEX idx_oppm_border_overrides_project ON oppm_border_overrides(project_id);
```

---

*Document created: 2026-05-02*
*Next step: Implement DB model + migration, then tool handler, then API, then frontend merge*
