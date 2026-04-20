# OPPM Architecture & Rendering

Last updated: 2026-04-20

## Overview
The OPPM (One Page Project Manager) module takes unstructured or structured project data, organizes it via an AI-assisted backend pipeline, and renders it onto a strict visual spreadsheet grid mimicking the industry-standard OPPM template.

## Rendering Library: `@fortune-sheet/react`
The frontend relies on the `FortuneSheet` library. It renders an HTML canvas/DOM hybrid that displays Microsoft Excel (`.xlsx`) files. 

### Core Concepts of FortuneSheet Data Structure
FortuneSheet expects data wrapped in an array of `sheet` objects. A sheet object primarily holds:
- `celldata`: A flat 1D array of cells containing their precise `(row, col)` coordinates and value objects.
- `config`: Handles structural form like row heights (`rowlen`), column widths (`columnlen`), merged ranges (`merge`), and drawn borders (`borderInfo`).

### The Cell Data Schema
A typical text cell in `celldata` looks like this:
```json
{
  "r": 5,      // 0-indexed Row
  "c": 8,      // 0-indexed Column
  "v": {
    "v": "Raw Text Value",
    "m": "Displayed Label",
    "ht": 0,   // Horizontal Alignment (0: Left, 1: Center, 2: Right)
    "vt": 0,   // Vertical Alignment (0: Center, 1: Top, 2: Bottom)
    "fc": "#000000",   // Font Color
    "bg": "#FFFFFF",   // Background color
    "bl": 1            // Bold
  }
}
```

## The AI Fill Algorithm & Layout Mapping

Because user-uploaded OPPM `.xlsx` templates might vary slightly in geometry (additional columns, different row setups), the frontend uses a **positional probing algorithm** rather than hard-coded index maps (e.g. "cell H8").

### 1. Template Probing (Detection)
When "AI Fill" is triggered, the codebase scans the baseline raw `celldata`:

1.  **Task Field**: Scans for the text literal `/^Major Tasks/i` or `/^main task/i`. The row below this establishes `taskStartRow`. The column acts as the root for `taskCol`.
2.  **Date/Timeline Field**: Assumes `col 12` through `col 28` (Excel M–AC). Looks for Excel serial numbers (e.g. `44454`) and formats them cleanly into the user's localized date format based on project start and deadline offsets.
3.  **Owner Columns Field**: Scans the bottom of the right-hand panel for strict matches (`/^Member\s*\d+$/i` or `/^Project\s*Leader$/i`). This defines which columns track which human user identities.
4.  **Bounds Check**: Looks for bottom headers like "Project Completed By" or "People Working" to prevent inserting more tasks than the template physically supports.

### 2. Data Mapping (Injection)
Once landmarks are identified:

- **Tasks**: `OPPMView` maps high-level Objectives (`is_sub=false`) into the `mainTaskCol` and their child sub-tasks into `taskCol`. 
- **Owners**: Uses a fallback array indexing loop. Every backend subtask emits a list of owners (`A`, `B`, `C` priority labels). The UI maps the `owner.member_id` to one of the recorded "Member Column" bounds and writes an `A`, `B` or `C` into that `(task_row, member_col)` cross section.
- **Timeline Limits**: Divides the total date delta (start vs deadline) into 17 even fragments. The week a task is due will place a `■` (Complete) or `●` (In Progress) into the corresponding `colToDate` match.

### 3. Rendering Protections (Idempotency)
Because FortuneSheet draws strictly on rigid boxes, over-long text can crash the layout or bleed into adjacent locked columns.
The `applyFillsToSheet` routine runs character limits (e.g., `estimateCharsForCell()`), which detects the width span of merged boxes, calculates pixel limits, and truncates text (`...`) so it never breaks the structural grid visual format. FortuneSheet's internal `ct` (Rich Text) arrays from Excel schemas are wiped actively during AI Fill to ensure plain text injections apply reliably to the cell surface.

## 4. safe Layout Manipulation (Borders, Columns, & Merges)

To successfully modify the layout programmatically during AI Fill without corrupting the file when re-downloading to `.xlsx`, changes must target the `config` payload predictably.

### Adjusting Columns
- **Widths (`config.columnlen`)**: A dictionary mapping the 0-indexed column string to a pixel width (e.g. `"8": 150`). To widen a column dynamically to fit a task, loop over tasks, determine the max character width, multiply by a font-size constant (~7px per char), and assign the highest value back to `config.columnlen[taskCol]`. Be aware this shifts all right-side structures dynamically.
- **Hiding (`config.colhidden`)**: A dictionary mapping the 0-indexed column string to `0`. (e.g. `"9": 0`). To hide unused member columns without deleting them (which preserves the column indices of elements further to the right), inject them here.

### Managing Merges (`config.merge`)
To merge cells (e.g. stretching a "Sub objective" vertically across grouped tasks):
1. Create a merge dictionary entry: `config.merge["row_col"] = { r: row, c: col, rs: rowSpan, cs: colSpan }`.
2. Add the `mc: { r: row, c: col, rs: rowSpan, cs: colSpan }` attribute onto the root-anchor `v` payload in `celldata`.
3. Add a pointer `mc: { r: root_row, c: root_col }` onto every other `celldata` cell hidden underneath the merged span.

To unmerge, reverse the process: delete the key from `config.merge` and iterate the `celldata` array, removing the `mc` payload from any cell matching the bounding box constraints.

### Managing Borders (`config.borderInfo`)
Excel parses borders as large overlapping ranges. `borderInfo` is an array of objects.
Never attempt to recalculate standard "range" borders (`border-all`) programmatically because crossing spans causes clipping failures visually.
Always use "Cell Level" explicit line drawing overrides, which take precedence over range templates.

```json
{
  "rangeType": "cell",
  "value": {
    "row_index": 5,
    "col_index": 8,
    "l": { "color": "#000000", "style": "1" },   // Left Border
    "r": { "color": "#000000", "style": "1" },   // Right Border
    "t": { "color": "#000000", "style": "1" },   // Top Border
    "b": { "color": "#000000", "style": "1" }    // Bottom Border
  }
}
```

**Border Manipulation Workflow**:
1. Scan `borderInfo` for any previous `"cell"` rules that match your `(r, c)` target and `splice` them completely.
2. Build a new `borderVal` object specifying only the sides that exist (null/omitted values fall back to whatever original range-border is underneath).
3. If drawing an outer border around an entire group (like a Sub-objective block), iterate over the 2D bounding block and apply `t` only on `row = 0`, `b` only on `row = max`, `l` only on `col = 0`, and `r` only on `col = max`.
