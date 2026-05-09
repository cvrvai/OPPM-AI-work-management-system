from typing import Any
import logging
from .utils import (
    _col_index_to_letters, _col_letters_to_index, _range_to_grid_range,
    _hex_to_rgb, _border_style, _parse_range, _parse_cell,
    _date_to_timeline_col, _read_timeline_header_dates, _find_sheet_id,
)
from .assets import _upload_local_asset_to_drive
from .data_builders import _exec_clear_sheet
logger = logging.getLogger(__name__)
# ── scaffold_oppm_form: deterministic full-form expansion ──
#
# A single high-level action that emits the complete authentic OPPM layout in
# one call: 5-row header, N task rows numbered 1..N, bottom matrix with month
# labels + cost area + legend, full border hierarchy (header black grid, task
# area gray grid, timeline cleared, thick section dividers, thick outer frame),
# standard fonts/alignment/widths/heights, and frozen header.
#
# This exists because the LLM was inconsistent at producing all ~80 atomic
# actions that recreate a Clark Campbell OPPM form. With this action, the AI
# emits ONE call and the executor produces a faithful form every time.

_SCAFFOLD_HEADER_BLACK = "#000000"
_SCAFFOLD_TASK_GRAY = "#CCCCCC"
_SCAFFOLD_HEADER_BG = "#E8E8E8"
_SCAFFOLD_DEFAULT_TASK_COUNT = 24
_SCAFFOLD_TASK_ROW_HEIGHT = 21
_SCAFFOLD_MATRIX_DATE_ROW_HEIGHT = 100  # top matrix row holds rotated date headers — needs vertical room
_SCAFFOLD_MATRIX_BODY_ROW_HEIGHT = 50   # body matrix rows (X-pattern / image area) — taller so the legend fills space like the reference OPPM
_SCAFFOLD_MATRIX_HEIGHT_ROWS = 13      # header(1) + body(12); the identity strip lives immediately above the matrix.
_SCAFFOLD_WEEK_DATE_COLS = 17           # M..AC (17 weekly date columns)
_SCAFFOLD_OWNER_COLS = 6                # AE..AJ (6 owner columns)
_SCAFFOLD_LAST_COL = "AJ"               # rightmost column of the form


def _build_scaffold_actions(params: dict) -> list[dict]:
    """Build the deterministic action list for a full OPPM form scaffold.

    Layout follows the authentic OPPM PDF reference (Clark Campbell),
    with 1 empty row at top and 1 empty column on left for spacing:
      Row 1            empty (spacer)
      Rows 2-3         merged: Logo (B:G) | "Project Leader: ..." (H:K) | "Project Name: ..." (L:AJ)
      Rows 4-5         MERGED H4:AJ5 — multi-line block: Objective + Deliverable + Start + Deadline
      Row 6            sub-headers: "Sub objective" (B:G) | "Major Tasks (Deadline)" (H:M)
                       | "Project Completed By: ..." (N:AD) | "Owner / Priority" (AE:AJ)
    Rows 7 .. 6+N    task rows, numbered 1..N in column I (default N=24)
    Identity strip (A..F) starts immediately after the last task row in column H
    R_MATRIX         13-row bottom matrix immediately below the identity strip:
                         B:G  rotated labels merged in body
                         I:M  blank image area for OPPM legend image
                         N:AD rotated week-date headers (17 cols, header row only)
                         AE:AJ rotated owner-name labels (Project Leader, Member 1..5, header row)
      R_SUMMARY        Summary / Forecast / Risk section (4 rows each):
                         H:I column rotated section labels
                         J:AJ placeholder text rows

    All cells are atomically valid — caller can fill any of them later.
    """
    from datetime import date as _d, timedelta as _td

    title = str(params.get("title") or "[Project Name]")
    leader = str(params.get("leader") or "[Leader Name]")
    objective = str(params.get("objective") or "[Project Objective]")
    deliverable = str(params.get("deliverable") or "[Deliverable Output]")
    start_date = str(params.get("start_date") or "[Start Date]")
    deadline = str(params.get("deadline") or "[Deadline]")
    weeks = params.get("completed_by_weeks")
    weeks_label = f"{int(weeks)} weeks" if weeks else "N weeks"
    task_count = max(1, int(params.get("task_count") or _SCAFFOLD_DEFAULT_TASK_COUNT))
    tasks = params.get("tasks") or []
    weeks_data = params.get("weeks") or []
    members = params.get("members") or []
    # Optional public image URL for the X-pattern matrix center (replaces the
    # five text labels Major Tasks / Target Dates / Sub Objectives / Costs /
    # Summary & Forecast with an embedded image). Must be publicly fetchable
    # by Google Sheets — typically a Google Drive shared URL of the form
    # https://drive.google.com/uc?export=view&id=FILE_ID.
    matrix_image_url = params.get("matrix_image_url")
    matrix_image_url = str(matrix_image_url).strip() if matrix_image_url else None

    # Row positions
    ROW_OFFSET = 1                              # leave 1 empty row at top
    GAP_ROWS = 0                                # no spacer gap — identity strip starts right after last task
    LAST_TASK = 5 + task_count + ROW_OFFSET
    R_GAP_START = LAST_TASK + 1                 # (unused when GAP_ROWS == 0)
    R_GAP_END = R_GAP_START + GAP_ROWS - 1      # (unused when GAP_ROWS == 0)
    R_IDENTITY_START = LAST_TASK + 1            # first identity row (letter A), immediately after tasks, immediately after tasks
    R_IDENTITY_END = R_IDENTITY_START + 5       # last identity row (letter F)
    R_MATRIX_TOP = R_IDENTITY_END + 1           # matrix header row
    R_MATRIX_HEADER = R_MATRIX_TOP
    R_MATRIX_BOTTOM = R_MATRIX_TOP + _SCAFFOLD_MATRIX_HEIGHT_ROWS - 1
    R_SUMMARY_START = R_MATRIX_BOTTOM + 1
    R_SUMMARY_DELIV_END = R_SUMMARY_START + 3   # 4 deliverable rows
    R_FORECAST_START = R_SUMMARY_DELIV_END + 1
    R_FORECAST_END = R_FORECAST_START + 3       # 4 forecast rows
    R_RISK_START = R_FORECAST_END + 1
    R_RISK_END = R_RISK_START + 3               # 4 risk rows
    R_FORM_BOTTOM = R_RISK_END                   # last form row

    # ── Dynamic column counts ──
    # Scale up/down based on actual data; minimum 4 columns as fallback
    week_col_count = max(4, len(weeks_data)) if weeks_data and isinstance(weeks_data, list) else 4
    owner_col_count = max(4, len(members)) if members and isinstance(members, list) else 4

    # Column indices (0-based) for dynamic ranges
    COL_OFFSET = 1                              # leave 1 empty column on left
    C_WEEK_START = 13 + COL_OFFSET              # N = column 14 (0-based)
    C_WEEK_END = C_WEEK_START + week_col_count - 1
    C_OWNER_START = C_WEEK_END + 1
    C_OWNER_END = C_OWNER_START + owner_col_count - 1
    LAST_COL_LETTER = _col_index_to_letters(C_OWNER_END + 1)

    # Pre-computed column letters for cleaner range strings
    L_WEEK_START = _col_index_to_letters(C_WEEK_START)     # 14 → N
    L_WEEK_END   = _col_index_to_letters(C_WEEK_END)
    L_OWNER_START = _col_index_to_letters(C_OWNER_START)
    L_OWNER_END  = _col_index_to_letters(C_OWNER_END)
    L_OWNER_2ND  = _col_index_to_letters(C_OWNER_START + 1)  # second owner column
    L_TASK_END   = "M"  # task title area ends at M (fixed)

    # Try to compute real week-date labels if start_date is parseable
    start_dt: _d | None = None
    if start_date and start_date != "[Start Date]":
        try:
            start_dt = _d.fromisoformat(start_date)
        except ValueError:
            start_dt = None

    a: list[dict] = []

    # ── 1. Clear everything (also resets row heights + standard col widths) ──
    a.append({"action": "clear_sheet", "params": {}})

    # ── 2. Header content ──
    # Row 2: Logo placeholder (B:G) | Project Leader (H:K) | Project Name (L:AJ)
    a.append({"action": "set_value", "params": {"range": "B2", "value": ""}})
    a.append({"action": "set_value", "params": {"range": "H2", "value": f"Project Leader: {leader}"}})
    a.append({"action": "set_value", "params": {"range": "M2", "value": f"Project Name: {title}"}})
    # Rows 3-5: metadata block (one line per row)
    a.append({"action": "set_value", "params": {"range": "H3", "value": f"Project Objective: {objective}"}})
    a.append({"action": "set_value", "params": {"range": "H4", "value": f"Deliverable Output: {deliverable}"}})
    a.append({"action": "set_value", "params": {"range": "H5", "value": f"Start Date: {start_date}    Deadline: {deadline}"}})
    # Row 6: 4 sub-headers
    a.append({"action": "set_value", "params": {"range": "B6", "value": "Sub objective"}})
    a.append({"action": "set_value", "params": {"range": "H6", "value": "Major Tasks (Deadline)"}})
    a.append({"action": "set_value", "params": {"range": f"{L_WEEK_START}6", "value": f"Project Completed By: {weeks_label}"}})
    a.append({"action": "set_value", "params": {"range": f"{L_OWNER_START}6", "value": "Owner / Priority"}})

    # ── 3. Task numbers 1..N in column G (G:H merged per row) + task names in I:M ──
    for i in range(1, task_count + 1):
        a.append({"action": "set_value", "params": {"range": f"H{6 + i}", "value": str(i)}})
        task_name = ""
        if i <= len(tasks):
            t = tasks[i - 1]
            task_name = str(t.get("name") or t.get("title") or "")
        a.append({"action": "set_value", "params": {"range": f"I{6 + i}", "value": task_name}})

    # ── 4. Bottom matrix content ──
    # 4a. Sub-objective numbers 1..6 in the matrix header row A:F (row 42)
    for col_idx in range(2, 8):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_HEADER}", "value": str(col_idx)}})
    # 4a-ii. Sub-objective labels in the matrix body — each column A-F is merged vertically
    sub_obj_labels = ["Sub Obj 1", "Sub Obj 2", "Sub Obj 3", "Sub Obj 4", "Sub Obj 5", "Sub Obj 6"]
    for col_idx, label in enumerate(sub_obj_labels, start=2):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_HEADER + 1}", "value": label}})

    # 4b. X-pattern center area — one large blank rectangle (H:L) for image insertion
    # Blank white area spans the full 13-row matrix block within the body
    X_TOP = R_MATRIX_HEADER + 1                 # = 43
    X_BOTTOM = R_MATRIX_BOTTOM                  # = 54
    # Leave the area blank (no text values) — user will insert an image later
    a.append({"action": "set_value", "params": {"range": f"I{X_TOP}", "value": ""}})

    # 4c. Identity Symbol section — A-F vertical, one letter per row, column H
    identity_letters = ["A", "B", "C", "D", "E", "F"]
    for idx, letter in enumerate(identity_letters):
        row = R_IDENTITY_START + idx
        a.append({"action": "set_value", "params": {"range": f"H{row}", "value": letter}})

    # ── 5. Gap rows (R_GAP_START .. R_GAP_END) — no content, no borders ──
    for r in range(R_GAP_START, R_GAP_END + 1):
        a.append({"action": "set_value", "params": {"range": f"B{r}", "value": ""}})

    # 5c. Week-date rotated headers — on matrix header row
    # Use real week dates if available, otherwise fall back to "Week N"
    week_labels = []
    if weeks_data and isinstance(weeks_data, list):
        for w in weeks_data[:week_col_count]:
            if isinstance(w, dict):
                label = w.get("label") or w.get("date") or ""
            else:
                label = str(w)
            week_labels.append(label)
    # Pad with placeholders if fewer than week_col_count weeks
    while len(week_labels) < week_col_count:
        week_labels.append(f"Week {len(week_labels) + 1}")
    for w in range(week_col_count):
        col_letter = _col_index_to_letters(C_WEEK_START + w)  # 1-based
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_HEADER}", "value": week_labels[w]}})

    # 5d. Owner-name rotated headers in AD:AI (6 owner columns) — on matrix header row
    # Use real member names if available
    owner_labels = ["Project Leader"]
    for i in range(owner_col_count - 1):
        if i < len(members):
            owner_labels.append(members[i])
        else:
            owner_labels.append(f"Member {i + 1}")
    for col_idx, label in enumerate(owner_labels):
        col_letter = _col_index_to_letters(C_OWNER_START + col_idx)
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_HEADER}", "value": label}})

    # ── 6. Summary / Forecast / Risk section ──
    # Rotated section labels in column G (merged vertically per 4-row section)
    a.append({"action": "set_value", "params": {"range": f"H{R_SUMMARY_START}", "value": "Summary Deliverable"}})
    a.append({"action": "set_value", "params": {"range": f"H{R_FORECAST_START}", "value": "Forecast"}})
    a.append({"action": "set_value", "params": {"range": f"H{R_RISK_START}", "value": "Risk"}})
    # Placeholder text — one line per row in H:AI (single cell per row, not merged vertically)
    for i in range(4):
        a.append({"action": "set_value", "params": {"range": f"I{R_SUMMARY_START + i}", "value": f"Deliverable item {i + 1}: ..."}})
    for i in range(4):
        a.append({"action": "set_value", "params": {"range": f"I{R_FORECAST_START + i}", "value": f"Forecast: ..."}})
    for i in range(4):
        a.append({"action": "set_value", "params": {"range": f"I{R_RISK_START + i}", "value": f"Risk: ..."}})

    # ── 7. Merges ──
    # Row 2: logo | project leader | project name (each standalone row)
    a.append({"action": "merge_cells", "params": {"range": "B2:G2"}})
    a.append({"action": "merge_cells", "params": {"range": "H2:K2"}})
    a.append({"action": "merge_cells", "params": {"range": f"M2:{L_OWNER_END}2"}})
    # Rows 3-5: each row merged separately
    a.append({"action": "merge_cells", "params": {"range": f"H3:{L_OWNER_END}3"}})
    a.append({"action": "merge_cells", "params": {"range": f"H4:{L_OWNER_END}4"}})
    a.append({"action": "merge_cells", "params": {"range": f"H5:{L_OWNER_END}5"}})
    # Row 6 sub-headers
    a.append({"action": "merge_cells", "params": {"range": "B6:G6"}})
    a.append({"action": "merge_cells", "params": {"range": "H6:M6"}})
    a.append({"action": "merge_cells", "params": {"range": f"{L_WEEK_START}6:{L_WEEK_END}6"}})
    a.append({"action": "merge_cells", "params": {"range": f"{L_OWNER_START}6:{L_OWNER_END}6"}})
    # Task rows: G holds the task number (same width as identity letter column)
    # H:L merged per row as the task title/description area
    for i in range(1, task_count + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{6 + i}:M{6 + i}"}})
    # Identity rows: merge I:M on each row to give a description/label area
    for r in range(R_IDENTITY_START, R_IDENTITY_END + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{r}:M{r}"}})
    # Big white image area: one rectangle spanning G42:L54 (combines header row G:L + body G column + X-pattern)
    a.append({"action": "merge_cells", "params": {"range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}"}})
    # Sub-objective body merges: each column A-F merged vertically from row 43 to row 66 (bottom of risk section)
    for col_idx in range(2, 8):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "merge_cells", "params": {"range": f"{col_letter}{R_MATRIX_HEADER + 1}:{col_letter}{R_FORM_BOTTOM}"}})
    # Timeline date header columns and owner columns: each column merged vertically rows 42-48
    # so the rotated labels occupy a taller area; grid cells start at row 49
    R_DATE_HEADER_END = R_MATRIX_HEADER + 6  # = 48
    for col_idx in range(C_WEEK_START, C_OWNER_END + 1):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "merge_cells", "params": {"range": f"{col_letter}{R_MATRIX_HEADER}:{col_letter}{R_DATE_HEADER_END}"}})
    # Summary/Forecast/Risk: G column labels merged vertically per section
    # H:AI text rows merged per row (each row spans full width)
    a.append({"action": "merge_cells", "params": {"range": f"H{R_SUMMARY_START}:H{R_SUMMARY_DELIV_END}"}})
    a.append({"action": "merge_cells", "params": {"range": f"H{R_FORECAST_START}:H{R_FORECAST_END}"}})
    a.append({"action": "merge_cells", "params": {"range": f"H{R_RISK_START}:H{R_RISK_END}"}})
    for r in range(R_SUMMARY_START, R_RISK_END + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{r}:{L_OWNER_END}{r}"}})

    # ── 8. Row heights ──
    # Rows 1-2 header: compact
    a.append({"action": "set_row_height", "params": {"start_index": 2, "end_index": 3, "height": _SCAFFOLD_TASK_ROW_HEIGHT}})
    # Rows 3-5 metadata: compact height for each row
    a.append({"action": "set_row_height", "params": {"start_index": 4, "end_index": 6, "height": _SCAFFOLD_TASK_ROW_HEIGHT}})
    a.append({"action": "set_row_height", "params": {"start_index": 7, "end_index": LAST_TASK, "height": _SCAFFOLD_TASK_ROW_HEIGHT}})
    # All matrix rows at body height first
    a.append({"action": "set_row_height", "params": {"start_index": R_MATRIX_TOP, "end_index": R_MATRIX_BOTTOM, "height": _SCAFFOLD_MATRIX_BODY_ROW_HEIGHT}})
    # Row 42 (matrix header): compact — date/member labels span rows 42-46 via column merges
    a.append({"action": "set_row_height", "params": {"start_index": R_MATRIX_HEADER, "end_index": R_MATRIX_HEADER, "height": 21}})
    # Rows 43-54 (matrix body A:L): compact height
    a.append({"action": "set_row_height", "params": {"start_index": X_TOP, "end_index": R_MATRIX_BOTTOM, "height": 21}})
    # Identity rows (A-F, one per row) — same height as task rows
    a.append({"action": "set_row_height", "params": {"start_index": R_IDENTITY_START, "end_index": R_IDENTITY_END, "height": _SCAFFOLD_TASK_ROW_HEIGHT}})
    # Summary/Forecast/Risk rows: taller so text fills the merged area
    a.append({"action": "set_row_height", "params": {"start_index": R_SUMMARY_START, "end_index": R_RISK_END, "height": 40}})
    # Column H wider so identity letters and task numbers are clearly visible
    a.append({"action": "set_column_width", "params": {"start_index": 7, "end_index": 7, "width": 50}})
    # Columns B-G compact width (30px) for sub-objective check columns
    a.append({"action": "set_column_width", "params": {"start_index": 1, "end_index": 6, "width": 30}})
    # Column I (task title): wide for long task descriptions
    a.append({"action": "set_column_width", "params": {"start_index": 8, "end_index": 8, "width": 280}})
    # Timeline grid columns: week_col_count columns at 25px each
    a.append({"action": "set_column_width", "params": {"start_index": 9, "end_index": C_WEEK_END + 1, "width": 25}})
    # Owner columns: owner_col_count columns at 25px
    a.append({"action": "set_column_width", "params": {"start_index": C_OWNER_START + 1, "end_index": C_OWNER_END + 1, "width": 25}})

    # ── 9. Backgrounds ──
    # Big white image area (G42:L54) — white blank background for image insertion
    a.append({"action": "set_background", "params": {"range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}", "color": "#FFFFFF"}})

    # ── 10. Borders — frame-only for merged areas, grid for non-merged areas ──
    # 10a. Header rows 2-6 → outer frame only (avoid borders inside merged cells)
    a.append({"action": "set_border", "params": {
        "range": f"B2:{L_OWNER_END}6",
        "style": "NONE",
        "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # 10a-i. Inner vertical dividers in header: between logo/leader, leader/title
    a.append({"action": "set_border", "params": {
        "range": "B2:G2",
        "style": "NONE",
        "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # 10a-ii. Thick right border between Project Leader (H:K) and Project Name (M:AJ) (row 2)
    a.append({"action": "set_border", "params": {
        "range": "K2",
        "style": "NONE",
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # 10a-iii. Inner horizontal divider between rows 2 and 3 (below leader/title, above metadata)
    a.append({"action": "set_border", "params": {"range": f"B2:{L_OWNER_END}2", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # 10a-iv. Inner horizontal divider between rows 5 and 6 (below metadata, above sub-headers)
    a.append({"action": "set_border", "params": {"range": f"H5:{L_OWNER_END}5", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Top border on Sub objective cell (B6:G6)
    a.append({"action": "set_border", "params": {"range": "B6:G6", "style": "NONE",
                                                  "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1}})
    # 10b. Task area sub-objectives (B:F) → gray grid.
    # Row 7 omits its top border so row 6's black divider remains visible.
    a.append({"action": "set_border", "params": {
        "range": "B7:F7",
        "style": "NONE",
        "left_style": "SOLID", "left_color": _SCAFFOLD_TASK_GRAY, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_TASK_GRAY, "right_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_TASK_GRAY, "bottom_width": 1,
    }})
    if LAST_TASK >= 8:
        a.append({"action": "set_border", "params": {"range": f"B8:F{LAST_TASK}", "style": "SOLID", "color": _SCAFFOLD_TASK_GRAY, "width": 1}})
    # 10b-i. Task-number column H keeps horizontal row lines and its right grid line,
    # but no left border so the G separator stays right-border-only.
    for row in range(7, LAST_TASK + 1):
        a.append({"action": "set_border", "params": {
            "range": f"H{row}:H{row}",
            "style": "NONE",
            "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_TASK_GRAY, "bottom_width": 1,
            "right_style": "SOLID", "right_color": _SCAFFOLD_TASK_GRAY, "right_width": 1,
            **({"top_style": "SOLID", "top_color": _SCAFFOLD_TASK_GRAY, "top_width": 1} if row > 7 else {}),
        }})
    # 10b-ii. Task title area (I:M) → gray grid.
    # Row 7 omits its top border so row 6's black divider remains visible.
    a.append({"action": "set_border", "params": {
        "range": "I7:M7",
        "style": "NONE",
        "left_style": "SOLID", "left_color": _SCAFFOLD_TASK_GRAY, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_TASK_GRAY, "right_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_TASK_GRAY, "bottom_width": 1,
    }})
    if LAST_TASK >= 8:
        a.append({"action": "set_border", "params": {"range": f"I8:M{LAST_TASK}", "style": "SOLID", "color": _SCAFFOLD_TASK_GRAY, "width": 1}})
    # 10b-iii. Remove borders from timeline area (N:AD) in task rows
    a.append({"action": "set_border", "params": {"range": f"{L_WEEK_START}7:{L_WEEK_END}{LAST_TASK}", "style": "NONE"}})
    # Restore the right divider at the edge of the Project Completed By area.
    a.append({"action": "set_border", "params": {
        "range": f"{L_WEEK_END}7:{L_WEEK_END}{LAST_TASK}",
        "style": "NONE",
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # 10c. Task area owners (AE:AJ) → gray grid.
    # The first owner column AE omits its left border so the black divider on AD remains visible.
    for row in range(7, LAST_TASK + 1):
        a.append({"action": "set_border", "params": {
            "range": f"{L_OWNER_START}{row}:{L_OWNER_START}{row}",
            "style": "NONE",
            "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_TASK_GRAY, "bottom_width": 1,
            "right_style": "SOLID", "right_color": _SCAFFOLD_TASK_GRAY, "right_width": 1,
            **({"top_style": "SOLID", "top_color": _SCAFFOLD_TASK_GRAY, "top_width": 1} if row > 7 else {}),
        }})
    a.append({"action": "set_border", "params": {
        "range": f"{L_OWNER_2ND}7:{L_OWNER_END}7",
        "style": "NONE",
        "left_style": "SOLID", "left_color": _SCAFFOLD_TASK_GRAY, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_TASK_GRAY, "right_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_TASK_GRAY, "bottom_width": 1,
    }})
    if LAST_TASK >= 8:
        a.append({"action": "set_border", "params": {"range": f"{L_OWNER_2ND}8:{L_OWNER_END}{LAST_TASK}", "style": "SOLID", "color": _SCAFFOLD_TASK_GRAY, "width": 1}})
    # 10e. Bottom matrix → outer border only on B:G (sub-obj check columns + identity column)
    # (inner vertical borders removed so columns C-F don't show lines)
    a.append({"action": "set_border", "params": {
        "range": f"B{R_MATRIX_TOP}:G{R_MATRIX_BOTTOM}",
        "style": "NONE",
        "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # Border around the full G42:L54 merged area (outer edges only)
    a.append({"action": "set_border", "params": {
        "range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}",
        "style": "NONE",
        "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # Timeline grid header row (H:AI row 42) — outer border only, no inner grid
    # (week/member columns are merged vertically; inner borders would show at row 43)
    a.append({"action": "set_border", "params": {
        "range": f"I{R_MATRIX_TOP}:{L_OWNER_END}{R_MATRIX_TOP}",
        "style": "NONE",
        "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # Timeline grid body (H:AI rows 43-54) — outer border only, no inner grid
    a.append({"action": "set_border", "params": {
        "range": f"I{X_TOP}:{L_OWNER_END}{X_BOTTOM}",
        "style": "NONE",
        "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # 10f. Summary/Forecast/Risk section → outer borders only (avoid conflicts with merged H:AI)
    for (s, e) in ((R_SUMMARY_START, R_SUMMARY_DELIV_END), (R_FORECAST_START, R_FORECAST_END), (R_RISK_START, R_RISK_END)):
        a.append({"action": "set_border", "params": {
            "range": f"H{s}:{L_OWNER_END}{e}",
            "style": "NONE",
            "top_style": "SOLID", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 1,
            "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1,
            "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
            "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
        }})
    # 10g. Vertical thick dividers (G, M on the right) — applied through task area only
    for col in ("G", "M"):
        a.append({
            "action": "set_border",
            "params": {
                "range": f"{col}1:{col}{LAST_TASK}",
                "style": "NONE",
                "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
            },
        })
    # Left border on column L + right border on column M for task rows
    # (separates H:L merged title area from timeline area)
    a.append({
        "action": "set_border",
        "params": {
            "range": f"M7:M{LAST_TASK}",
            "style": "NONE",
            "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        },
    })
    a.append({
        "action": "set_border",
        "params": {
            "range": f"{L_WEEK_START}7:{L_WEEK_START}{LAST_TASK}",
            "style": "NONE",
            "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
        },
    })
    # 10g-i. Thick right border on column F in the matrix area (Identity Symbol separator)
    a.append({
        "action": "set_border",
        "params": {
            "range": f"G{R_MATRIX_TOP}:G{R_MATRIX_BOTTOM}",
            "style": "NONE",
            "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
        },
    })
    # 10h. Horizontal thick dividers
    a.append({"action": "set_border", "params": {"range": f"B6:{L_OWNER_END}6", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    a.append({"action": "set_border", "params": {"range": f"B{LAST_TASK}:{L_OWNER_END}{LAST_TASK}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Thick divider below matrix header row
    a.append({"action": "set_border", "params": {"range": f"B{R_MATRIX_HEADER}:{L_OWNER_END}{R_MATRIX_HEADER}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Thick divider above identity strip (separates the task block from the identity rows)
    a.append({"action": "set_border", "params": {"range": f"B{R_IDENTITY_START - 1}:{L_OWNER_END}{R_IDENTITY_START - 1}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Thick divider below identity strip (separates identity rows from the matrix below)
    a.append({"action": "set_border", "params": {"range": f"B{R_IDENTITY_END}:{L_OWNER_END}{R_IDENTITY_END}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Left border on column G (identity letters) and right border on the merged H:L label area
    a.append({"action": "set_border", "params": {
        "range": f"H{R_IDENTITY_START}:H{R_IDENTITY_END}",
        "style": "NONE",
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
    }})
    # Apply the right border on the full merged range H:L so it targets the right
    # edge of each merged cell correctly (column-only targeting is unreliable on merges)
    a.append({"action": "set_border", "params": {
        "range": f"I{R_IDENTITY_START}:M{R_IDENTITY_END}",
        "style": "NONE",
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
        "inner_vertical_style": "NONE",
    }})
    # Thick divider below matrix (separates timeline body from Summary section)
    a.append({"action": "set_border", "params": {"range": f"B{R_MATRIX_BOTTOM}:{L_OWNER_END}{R_MATRIX_BOTTOM}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # ── Matrix header area bottom borders ──
    # Week section: bottom border at end of merged header area
    a.append({"action": "set_border", "params": {"range": f"{L_WEEK_START}{R_DATE_HEADER_END}:{L_WEEK_END}{R_DATE_HEADER_END}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Week section right border at column AD (vertical divider between week and member)
    a.append({"action": "set_border", "params": {"range": f"{L_WEEK_END}{R_MATRIX_HEADER}:{L_WEEK_END}{R_DATE_HEADER_END}", "style": "NONE",
                                                  "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1}})
    # Member section (AD:AJ): bottom border at end of merged header area
    a.append({"action": "set_border", "params": {"range": f"{L_WEEK_END}{R_DATE_HEADER_END}:{L_OWNER_END}{R_DATE_HEADER_END}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})
    # Restore the outer left/right edges after interior grids so task-row gray borders
    # do not override the full-form frame.
    a.append({"action": "set_border", "params": {
        "range": f"B1:B{R_FORM_BOTTOM}",
        "style": "NONE",
        "left_style": "SOLID", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 1,
    }})
    a.append({"action": "set_border", "params": {
        "range": f"{L_OWNER_END}1:{L_OWNER_END}{R_FORM_BOTTOM}",
        "style": "NONE",
        "right_style": "SOLID", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 1,
    }})
    # Bottom border at the end of the form (row 67 for 10 tasks)
    a.append({"action": "set_border", "params": {"range": f"B{R_FORM_BOTTOM}:G{R_FORM_BOTTOM}", "style": "NONE",
                                                  "bottom_style": "SOLID", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 1}})

    # ── 11. Fonts, alignment, rotation ──
    # Rows 1-2 leader/name
    a.append({"action": "set_font_size", "params": {"range": f"B2:{L_OWNER_END}2", "size": 11}})
    a.append({"action": "set_bold", "params": {"range": f"B2:{L_OWNER_END}2", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"B2:{L_OWNER_END}2", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Rows 3-5 metadata (left aligned, NOT bold — matches example)
    a.append({"action": "set_font_size", "params": {"range": f"H3:{L_OWNER_END}5", "size": 10}})
    a.append({"action": "set_alignment", "params": {"range": f"H3:{L_OWNER_END}5", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    # Row 5 sub-headers
    a.append({"action": "set_font_size", "params": {"range": f"B6:{L_OWNER_END}6", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": f"B6:{L_OWNER_END}6", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"B6:{L_OWNER_END}6", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Task numbers (column G only — same width as identity letter column)
    a.append({"action": "set_font_size", "params": {"range": f"H7:H{LAST_TASK}", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": f"H7:H{LAST_TASK}", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"H7:H{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Task titles (H:L merged per row) — left aligned, CLIP to preserve row height
    a.append({"action": "set_font_size", "params": {"range": f"I7:M{LAST_TASK}", "size": 10}})
    a.append({"action": "set_alignment", "params": {"range": f"I7:M{LAST_TASK}", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    a.append({"action": "set_text_wrap", "params": {"range": f"I7:M{LAST_TASK}", "mode": "CLIP"}})
    # Sub-objective check columns (A-F) and owner columns (AD-AI)
    a.append({"action": "set_alignment", "params": {"range": f"B7:G{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_alignment", "params": {"range": f"{L_OWNER_START}7:{L_OWNER_END}{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Bottom matrix sub-objective header row numbers (A:F, row 42): horizontal, centered, small, bold
    a.append({"action": "set_alignment", "params": {"range": f"B{R_MATRIX_HEADER}:G{R_MATRIX_HEADER}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"B{R_MATRIX_HEADER}:G{R_MATRIX_HEADER}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"B{R_MATRIX_HEADER}:G{R_MATRIX_HEADER}", "bold": True}})
    # Bottom matrix sub-objective body merged cells: rotated 90° + center + small font + bold
    a.append({"action": "set_text_rotation", "params": {"range": f"B{R_MATRIX_HEADER + 1}:G{R_MATRIX_BOTTOM}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"B{R_MATRIX_HEADER + 1}:G{R_MATRIX_BOTTOM}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"B{R_MATRIX_HEADER + 1}:G{R_MATRIX_BOTTOM}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"B{R_MATRIX_HEADER + 1}:G{R_MATRIX_BOTTOM}", "bold": True}})
    # Identity letters (A-F, one per row, rows 36-41, column G): bold + center
    a.append({"action": "set_alignment", "params": {"range": f"H{R_IDENTITY_START}:H{R_IDENTITY_END}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"H{R_IDENTITY_START}:H{R_IDENTITY_END}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"H{R_IDENTITY_START}:H{R_IDENTITY_END}", "bold": True}})
    # Bottom matrix date/timeline columns (M-AC): rotated 90° + center + small font
    a.append({"action": "set_text_rotation", "params": {"range": f"{L_WEEK_START}{R_MATRIX_HEADER}:{L_WEEK_END}{R_MATRIX_HEADER}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"{L_WEEK_START}{R_MATRIX_HEADER}:{L_WEEK_END}{R_MATRIX_HEADER}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"{L_WEEK_START}{R_MATRIX_HEADER}:{L_WEEK_END}{R_MATRIX_HEADER}", "size": 9}})
    # Bottom matrix owner columns (AD-AI): header row rotated 90° + center
    a.append({"action": "set_text_rotation", "params": {"range": f"{L_OWNER_START}{R_MATRIX_HEADER}:{L_OWNER_END}{R_MATRIX_HEADER}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"{L_OWNER_START}{R_MATRIX_HEADER}:{L_OWNER_END}{R_MATRIX_HEADER}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"{L_OWNER_START}{R_MATRIX_HEADER}:{L_OWNER_END}{R_MATRIX_HEADER}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"{L_OWNER_START}{R_MATRIX_HEADER}:{L_OWNER_END}{R_MATRIX_HEADER}", "bold": True}})
    # Big white image area (G42:L54): centered
    a.append({"action": "set_alignment", "params": {"range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": f"H{R_MATRIX_HEADER}:M{R_MATRIX_BOTTOM}", "bold": True}})
    # Summary section labels: rotated in column G only (single cell per row)
    a.append({"action": "set_text_rotation", "params": {"range": f"H{R_SUMMARY_START}:H{R_RISK_END}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"H{R_SUMMARY_START}:H{R_RISK_END}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_bold", "params": {"range": f"H{R_SUMMARY_START}:H{R_RISK_END}", "bold": True}})
    a.append({"action": "set_font_size", "params": {"range": f"H{R_SUMMARY_START}:H{R_RISK_END}", "size": 9}})
    # Summary text rows: smaller font, left-align, wrap
    a.append({"action": "set_font_size", "params": {"range": f"I{R_SUMMARY_START}:{L_OWNER_END}{R_RISK_END}", "size": 9}})
    a.append({"action": "set_alignment", "params": {"range": f"I{R_SUMMARY_START}:{L_OWNER_END}{R_RISK_END}", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    a.append({"action": "set_text_wrap", "params": {"range": f"I{R_SUMMARY_START}:{L_OWNER_END}{R_RISK_END}", "mode": "WRAP"}})

    # ── 12. Freeze header rows ──
    a.append({"action": "freeze_rows", "params": {"row_count": 6}})

    return a


def _scaffold_action_to_request(action: str, params: dict, sheet_id: int) -> dict | None:
    """Build a single Google Sheets `batchUpdate` request from a scaffold sub-action.

    Returns None if the action is not a formatting/structural one (e.g. set_value
    is handled separately via values.batchUpdate, clear_sheet is run before this).
    Mirrors the request shapes built by the per-action _exec_* helpers — kept
    inline so the scaffold can batch ~100 requests into a single API call.
    """
    if action == "merge_cells":
        return {"mergeCells": {"range": _range_to_grid_range(str(params["range"]), sheet_id), "mergeType": "MERGE_ALL"}}

    if action == "set_border":
        range_str = str(params["range"])
        style = str(params.get("style", "SOLID"))
        color = str(params.get("color", "#CCCCCC"))
        width = int(params.get("width", 1))
        top = _border_style(str(params.get("top_style", style)), str(params.get("top_color", color)), int(params.get("top_width", width)))
        bottom = _border_style(str(params.get("bottom_style", style)), str(params.get("bottom_color", color)), int(params.get("bottom_width", width)))
        left = _border_style(str(params.get("left_style", style)), str(params.get("left_color", color)), int(params.get("left_width", width)))
        right = _border_style(str(params.get("right_style", style)), str(params.get("right_color", color)), int(params.get("right_width", width)))
        inner_h = _border_style(str(params.get("inner_horizontal_style", style)), str(params.get("inner_horizontal_color", color)), int(params.get("inner_horizontal_width", width)))
        inner_v = _border_style(str(params.get("inner_vertical_style", style)), str(params.get("inner_vertical_color", color)), int(params.get("inner_vertical_width", width)))
        ub: dict = {"range": _range_to_grid_range(range_str, sheet_id)}
        if top is not None: ub["top"] = top
        if bottom is not None: ub["bottom"] = bottom
        if left is not None: ub["left"] = left
        if right is not None: ub["right"] = right
        if inner_h is not None: ub["innerHorizontal"] = inner_h
        if inner_v is not None: ub["innerVertical"] = inner_v
        # If every side ended up None, the API call would be a no-op — skip it.
        if len(ub) == 1:
            return None
        return {"updateBorders": ub}

    if action == "set_background":
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {"backgroundColor": _hex_to_rgb(str(params.get("color", "#FFFFFF")))}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }

    if action == "set_alignment":
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {
                    "horizontalAlignment": str(params.get("horizontal", "LEFT")).upper(),
                    "verticalAlignment": str(params.get("vertical", "BOTTOM")).upper(),
                }},
                "fields": "userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment",
            }
        }

    if action == "set_font_size":
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {"textFormat": {"fontSize": int(params.get("size", 10))}}},
                "fields": "userEnteredFormat.textFormat.fontSize",
            }
        }

    if action == "set_bold":
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {"textFormat": {"bold": bool(params.get("bold", True))}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        }

    if action == "set_text_wrap":
        mode = str(params.get("mode", "CLIP")).upper()
        if mode not in ("CLIP", "WRAP", "OVERFLOW_CELL"):
            mode = "CLIP"
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {"wrapStrategy": mode}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        }

    if action == "set_row_height":
        start = int(params["start_index"]) - 1
        end = int(params.get("end_index", params["start_index"]))
        return {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": start, "endIndex": end},
                "properties": {"pixelSize": int(params.get("height", 21))},
                "fields": "pixelSize",
            }
        }

    if action == "set_column_width":
        start = int(params["start_index"]) - 1
        end = int(params.get("end_index", params["start_index"]))
        return {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": start, "endIndex": end},
                "properties": {"pixelSize": int(params.get("width", 100))},
                "fields": "pixelSize",
            }
        }

    if action == "freeze_rows":
        return {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": int(params.get("row_count", 1))}},
                "fields": "gridProperties.frozenRowCount",
            }
        }

    if action == "set_text_rotation":
        if params.get("vertical"):
            rotation = {"vertical": True}
            fields = "userEnteredFormat.textRotation.vertical"
        else:
            angle = max(-90, min(90, int(params.get("angle", 90))))
            rotation = {"angle": angle}
            fields = "userEnteredFormat.textRotation.angle"
        return {
            "repeatCell": {
                "range": _range_to_grid_range(str(params["range"]), sheet_id),
                "cell": {"userEnteredFormat": {"textRotation": rotation}},
                "fields": fields,
            }
        }

    return None


def _exec_scaffold_oppm_form(
    service: Any,
    spreadsheet_id: str,
    params: dict,
    sheet_id: int,
    sheet_title: str,
    *,
    sa_info: dict[str, Any] | None = None,
) -> dict:
    """Write the full OPPM form layout directly to the sheet via batched API calls.

    Layout (Clark Campbell OPPM):
      Rows 1-2    : Logo (A:F) | Project Leader (G:J) | Project Name (K:AI)
      Rows 3-4    : Metadata block G:AI (Objective, Deliverable, Start, Deadline)
      Row 5       : Sub-headers  A:F | G:L | M:AC | AD:AI
      Rows 6-35   : Task rows — task# in G, title in H:L, timeline in M:AC, owner in AD:AI
      Rows 36-41  : Identity rows — letter A-F in G, description in H:L
      Row 42      : Matrix header — sub-obj# in A:F, image area G:L, date headers M:AC, owner headers AD:AI
      Rows 43-54  : Matrix body — sub-obj cols A:F merged, image area, timeline/owner dots
      Rows 55-66  : Summary / Forecast / Risk — G label (rotated), H:AI text
    """
    title = str(params.get("title") or "[Project Name]")
    leader = str(params.get("leader") or "[Leader Name]")
    objective = str(params.get("objective") or "[Project Objective]")
    deliverable = str(params.get("deliverable") or "[Deliverable Output]")
    start_date = str(params.get("start_date") or "[Start Date]")
    deadline = str(params.get("deadline") or "[Deadline]")
    task_count = max(1, int(params.get("task_count") or 24))

    sq = sheet_title.replace("'", "''")  # escape single quotes for A1 range notation
    LAST_TASK = 5 + task_count           # last row of task area
    R_IDENTITY_START = LAST_TASK + 1
    R_IDENTITY_END = R_IDENTITY_START + 5
    R_MATRIX_TOP = R_IDENTITY_END + 1
    R_MATRIX_BOTTOM = R_MATRIX_TOP + 12
    R_SUMMARY_START = R_MATRIX_BOTTOM + 1
    R_SUMMARY_END = R_SUMMARY_START + 11

    # ── Dynamic column computation (mirrors _build_scaffold_actions) ──
    weeks_data = params.get("weeks") or []
    members = params.get("members") or []
    week_col_count = max(4, len(weeks_data)) if weeks_data and isinstance(weeks_data, list) else 4
    owner_col_count = max(4, len(members)) if members and isinstance(members, list) else 4
    C_WEEK_START = 14          # N = 14 (0-based)
    C_WEEK_END = C_WEEK_START + week_col_count - 1
    C_OWNER_START = C_WEEK_END + 1
    C_OWNER_END = C_OWNER_START + owner_col_count - 1
    LAST_COL_LETTER = _col_index_to_letters(C_OWNER_END + 1)
    L_WEEK_START = _col_index_to_letters(C_WEEK_START)
    L_WEEK_END = _col_index_to_letters(C_WEEK_END)
    L_OWNER_START = _col_index_to_letters(C_OWNER_START)
    L_OWNER_END = _col_index_to_letters(C_OWNER_END)
    L_OWNER_2ND = _col_index_to_letters(C_OWNER_START + 1)

    # ── Step 0: Expand grid (default sheet has 26 cols; expand to fit dynamic columns) ─
    total_cols = C_OWNER_END + 2  # 0-based end + 1 for 1-based count
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"rowCount": 100, "columnCount": total_cols},
                },
                "fields": "gridProperties.rowCount,gridProperties.columnCount",
            }}]},
        ).execute()
    except Exception as e:
        raise RuntimeError(f"scaffold: grid expand failed — cannot proceed: {e}") from e

    # ── Step 1: Clear ────────────────────────────────────────────────────────
    try:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{sq}'!A1:{LAST_COL_LETTER}100",
            body={},
        ).execute()
    except Exception as e:
        logger.warning("scaffold clear failed (non-fatal): %s", e)

    # ── Step 2: Write all cell values in one batchUpdate ────────────────────
    metadata_block = (
        f"Project Objective: {objective}\n"
        f"Deliverable Output: {deliverable}\n"
        f"Start Date: {start_date}\n"
        f"Deadline: {deadline}"
    )

    # _col_index_to_letters is 1-based: 1=A, 13=M, 29=AC, 30=AD, 35=AI
    week_headers  = [f"W{i}" for i in range(1, week_col_count + 1)]
    owner_headers = ["Project Leader"] + [f"Owner {i}" for i in range(1, owner_col_count)]
    sub_obj_labels = ["Sub Obj 1", "Sub Obj 2", "Sub Obj 3",
                      "Sub Obj 4", "Sub Obj 5", "Sub Obj 6"]
    sub_obj_labels = ["Sub Obj 1", "Sub Obj 2", "Sub Obj 3",  # body A43:F43
                      "Sub Obj 4", "Sub Obj 5", "Sub Obj 6"]

    value_data: list[dict] = [
        # ── Header rows 1-2 ──────────────────────────────────────────────────
        {"range": f"'{sq}'!G1",  "values": [[f"Project Leader: {leader}"]]},
        # K1 is the top-left of the K1:AI2 merged range — value MUST go here
        {"range": f"'{sq}'!K1",  "values": [[f"Project Name: {title}"]]},
        # ── Metadata rows 3-4 ────────────────────────────────────────────────
        {"range": f"'{sq}'!G3",  "values": [[metadata_block]]},
        # ── Sub-header row 5 ─────────────────────────────────────────────────
        {"range": f"'{sq}'!A5",  "values": [["Sub objective"]]},
        {"range": f"'{sq}'!G5",  "values": [["Major Tasks (Deadline)"]]},
        {"range": f"'{sq}'!{L_WEEK_START}5",  "values": [["Project Completed By:"]]},
        {"range": f"'{sq}'!{L_OWNER_START}5", "values": [["Owner / Priority"]]},
    ]

    # Task numbers 1..N in column G (rows 6..LAST_TASK)
    for i in range(1, task_count + 1):
        value_data.append({"range": f"'{sq}'!G{5 + i}", "values": [[str(i)]]})

    # Identity letters A-F in column G — NOT column A
    for idx, letter in enumerate(["A", "B", "C", "D", "E", "F"]):
        value_data.append({"range": f"'{sq}'!G{R_IDENTITY_START + idx}", "values": [[letter]]})

    # Matrix header row: sub-obj numbers in A:F
    for col_i in range(6):
        col = chr(ord("A") + col_i)
        value_data.append({"range": f"'{sq}'!{col}{R_MATRIX_TOP}", "values": [[str(col_i + 1)]]})

    # Sub-obj labels at top of each merged body column
    for col_i, label in enumerate(sub_obj_labels):
        col = chr(ord("A") + col_i)
        value_data.append({"range": f"'{sq}'!{col}{R_MATRIX_TOP + 1}", "values": [[label]]})

    # Week headers in matrix header row (cols 13..C_WEEK_END, 1-based)
    for w_i, label in enumerate(week_headers):
        col = _col_index_to_letters(13 + w_i)   # M=13, N=14, ...
        value_data.append({"range": f"'{sq}'!{col}{R_MATRIX_TOP}", "values": [[label]]})

    # Owner headers in matrix header row (cols C_OWNER_START..C_OWNER_END, 1-based)
    for o_i, label in enumerate(owner_headers):
        col = _col_index_to_letters(C_OWNER_START + 1 + o_i)
        value_data.append({"range": f"'{sq}'!{col}{R_MATRIX_TOP}", "values": [[label]]})

    # Summary section labels (top of each merged G column)
    value_data += [
        {"range": f"'{sq}'!G{R_SUMMARY_START}",     "values": [["Summary Deliverable"]]},
        {"range": f"'{sq}'!G{R_SUMMARY_START + 4}", "values": [["Forecast"]]},
        {"range": f"'{sq}'!G{R_SUMMARY_START + 8}", "values": [["Risk"]]},
    ]

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": value_data},
    ).execute()

    # ── Step 3: Build all format/structure requests ──────────────────────────
    def rng(r: str) -> dict:
        return _range_to_grid_range(r, sheet_id)

    def sb(color: str = "#000000") -> dict:
        """Solid border dict."""
        return {"style": "SOLID", "width": 1, "colorStyle": {"rgbColor": _hex_to_rgb(color)}}

    def rc(range_str: str, fmt: dict, fields: str) -> dict:
        """repeatCell request."""
        return {"repeatCell": {"range": rng(range_str), "cell": {"userEnteredFormat": fmt}, "fields": fields}}

    def full_grid(range_str: str, color: str = "#000000") -> dict:
        """Full grid border on all inner + outer edges."""
        return {"updateBorders": {
            "range": rng(range_str),
            "top": sb(color), "bottom": sb(color), "left": sb(color), "right": sb(color),
            "innerHorizontal": sb(color), "innerVertical": sb(color),
        }}

    def outer_border(range_str: str, color: str = "#000000") -> dict:
        """Outer border only (no inner grid)."""
        return {"updateBorders": {
            "range": rng(range_str),
            "top": sb(color), "bottom": sb(color), "left": sb(color), "right": sb(color),
        }}

    def row_height(start: int, end: int, px: int) -> dict:
        return {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": start - 1, "endIndex": end},
            "properties": {"pixelSize": px}, "fields": "pixelSize",
        }}

    def col_width(start: int, end: int, px: int) -> dict:
        return {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": start - 1, "endIndex": end},
            "properties": {"pixelSize": px}, "fields": "pixelSize",
        }}

    requests: list[dict] = []

    # ── Merges ───────────────────────────────────────────────────────────────
    merge_list: list[str] = [
        # Header rows 1-4
        "B2:G5",      # Logo area
        "H2:K3",      # Project Leader  (value at G1)
        f"L2:{LAST_COL_LETTER}3",     # Project Name    (value at K1 ← must be top-left)
        f"H4:{LAST_COL_LETTER}5",     # Metadata block  (value at G3)
        # Sub-header row 5
        "B6:G6", "H6:M6", f"{L_WEEK_START}6:{L_WEEK_END}6", f"{L_OWNER_START}6:{L_OWNER_END}6",
        # Matrix image area (G:L)
        f"G{R_MATRIX_TOP}:L{R_MATRIX_BOTTOM}",
        # Summary G-column labels
        f"G{R_SUMMARY_START}:G{R_SUMMARY_START + 3}",
        f"G{R_SUMMARY_START + 4}:G{R_SUMMARY_START + 7}",
        f"G{R_SUMMARY_START + 8}:G{R_SUMMARY_START + 11}",
    ]
    # Task title cells H:L per task row
    for i in range(1, task_count + 1):
        merge_list.append(f"I{6 + i}:M{6 + i}")
    # Identity rows H:L per row
    for r in range(R_IDENTITY_START, R_IDENTITY_END + 1):
        merge_list.append(f"I{r}:M{r}")
    # Sub-obj columns A-F merged vertically through matrix + summary
    for col_i in range(6):
        col = chr(ord("A") + col_i)
        merge_list.append(f"{col}{R_MATRIX_TOP + 1}:{col}{R_SUMMARY_END}")
    # Timeline/owner header columns merged vertically (rotated labels)
    for col_1based in range(C_WEEK_START + 1, C_OWNER_END + 2):
        col = _col_index_to_letters(col_1based)
        merge_list.append(f"{col}{R_MATRIX_TOP}:{col}{R_MATRIX_TOP + 6}")
    # Summary text rows H:AI merged per row
    for r in range(R_SUMMARY_START, R_SUMMARY_END + 1):
        merge_list.append(f"I{r}:{L_OWNER_END}{r}")

    for mr in merge_list:
        try:
            requests.append({"mergeCells": {"range": rng(mr), "mergeType": "MERGE_ALL"}})
        except Exception as e:
            logger.warning("scaffold: bad merge %s: %s", mr, e)

    # ── Dimension properties ──────────────────────────────────────────────────
    requests += [
        row_height(1, 2, 21),               # header rows compact
        row_height(3, 3, 80),               # metadata row taller
        row_height(4, 4, 21),
        row_height(5, 5, 25),               # sub-header row slightly taller
        row_height(6, LAST_TASK, 21),       # task rows
        row_height(R_IDENTITY_START, R_IDENTITY_END, 21),   # identity rows
        row_height(R_MATRIX_TOP, R_MATRIX_TOP, 21),           # matrix header row
        row_height(R_MATRIX_TOP + 1, R_MATRIX_BOTTOM, 21),    # matrix body rows
        row_height(R_SUMMARY_START, R_SUMMARY_END, 40),       # summary rows (taller for text)
        col_width(1, 6, 22),               # A-F: narrow sub-obj check columns
        col_width(7, 7, 30),               # G:  identity/task-number column
        col_width(8, 12, 90),              # H-L: task title area
        col_width(13, C_WEEK_END + 1, 25),             # M..L_WEEK_END: weekly timeline columns
        col_width(C_OWNER_START + 1, C_OWNER_END + 1, 35),  # owner columns
    ]

    # ── Freeze rows 1-5 ──────────────────────────────────────────────────────
    requests.append({"updateSheetProperties": {
        "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 5}},
        "fields": "gridProperties.frozenRowCount",
    }})

    # ── Backgrounds ──────────────────────────────────────────────────────────
    BG_HEADER = _hex_to_rgb("#E8E8E8")
    BG_WHITE  = _hex_to_rgb("#FFFFFF")
    requests += [
        # Rows 1-4 white (clean header — no fill)
        rc(f"A1:{LAST_COL_LETTER}4",   {"backgroundColor": BG_WHITE},  "userEnteredFormat.backgroundColor"),
        # Row 5 sub-header row gets light gray so it reads as a column header
        rc(f"B6:{LAST_COL_LETTER}6",   {"backgroundColor": BG_HEADER}, "userEnteredFormat.backgroundColor"),
        # Matrix header row
        rc(f"A{R_MATRIX_TOP}:F{R_MATRIX_TOP}",  {"backgroundColor": BG_HEADER}, "userEnteredFormat.backgroundColor"),
        rc(f"M{R_MATRIX_TOP}:{LAST_COL_LETTER}{R_MATRIX_TOP}", {"backgroundColor": BG_HEADER}, "userEnteredFormat.backgroundColor"),
        # Image area in matrix stays white
        rc(f"G{R_MATRIX_TOP}:L{R_MATRIX_BOTTOM}",  {"backgroundColor": BG_WHITE},  "userEnteredFormat.backgroundColor"),
    ]

    # ── Borders ───────────────────────────────────────────────────────────────
    # Header rows 1-5: full black grid
    requests.append(full_grid(f"B2:{LAST_COL_LETTER}6"))
    # Task area: gray grid for A:L and owner columns
    requests.append(full_grid(f"B7:M{LAST_TASK}",  "#CCCCCC"))
    requests.append(full_grid(f"{L_OWNER_START}7:{L_OWNER_END}{LAST_TASK}", "#CCCCCC"))
    # Identity rows A:L: black grid
    requests.append(full_grid(f"A{R_IDENTITY_START}:L{R_IDENTITY_END}"))
    # Matrix header row: black grid
    requests.append(full_grid(f"A{R_MATRIX_TOP}:{LAST_COL_LETTER}{R_MATRIX_TOP}"))
    # Matrix body A:F (sub-obj area): black grid
    requests.append(full_grid(f"A{R_MATRIX_TOP + 1}:F{R_MATRIX_BOTTOM}"))
    # Matrix body H..LAST_COL: black grid  (G:L is the image area — outer border only)
    requests.append(full_grid(f"M{R_MATRIX_TOP + 1}:{LAST_COL_LETTER}{R_MATRIX_BOTTOM}"))
    requests.append(outer_border(f"G{R_MATRIX_TOP}:L{R_MATRIX_BOTTOM}"))
    # Summary section: black grid
    requests.append(full_grid(f"A{R_SUMMARY_START}:{LAST_COL_LETTER}{R_SUMMARY_END}"))
    # Outer frame for the entire form
    requests.append(outer_border(f"A1:{LAST_COL_LETTER}{R_SUMMARY_END}"))

    # ── Text alignment + formatting ───────────────────────────────────────────
    CENTER_MIDDLE = {
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    }
    LEFT_MIDDLE = {
        "horizontalAlignment": "LEFT",
        "verticalAlignment": "MIDDLE",
    }
    BOLD = {"textFormat": {"bold": True}}
    CENTER_FIELDS = ("userEnteredFormat.horizontalAlignment,"
                     "userEnteredFormat.verticalAlignment")
    BOLD_FIELDS   = "userEnteredFormat.textFormat.bold"
    CM_BOLD_FIELDS = CENTER_FIELDS + ",userEnteredFormat.textFormat.bold"

    # Rows 1-2: center + bold
    requests.append(rc(f"B2:{LAST_COL_LETTER}3", {**CENTER_MIDDLE, **BOLD}, CM_BOLD_FIELDS))
    # Row 5: center + bold
    requests.append(rc(f"B6:{LAST_COL_LETTER}6", {**CENTER_MIDDLE, **BOLD}, CM_BOLD_FIELDS))
    # Metadata block rows 3-4: left-align + wrap
    requests.append(rc(f"H4:{LAST_COL_LETTER}5", {
        **LEFT_MIDDLE,
        "wrapStrategy": "WRAP",
    }, CENTER_FIELDS + ",userEnteredFormat.wrapStrategy"))
    # Task numbers column G: center + bold
    requests.append(rc(f"H7:H{LAST_TASK}", {**CENTER_MIDDLE, **BOLD}, CM_BOLD_FIELDS))
    # Identity letters column G: center + bold
    requests.append(rc(f"G{R_IDENTITY_START}:G{R_IDENTITY_END}", {**CENTER_MIDDLE, **BOLD}, CM_BOLD_FIELDS))
    # Matrix header row: center + bold
    requests.append(rc(f"A{R_MATRIX_TOP}:AI{R_MATRIX_TOP}", {**CENTER_MIDDLE, **BOLD}, CM_BOLD_FIELDS))
    # Sub-obj matrix body A:F — rotated 90° + center + bold + small font
    requests.append(rc(f"A{R_MATRIX_TOP + 1}:F{R_MATRIX_BOTTOM}", {
        "textRotation": {"angle": 90},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {"bold": True, "fontSize": 9},
    }, "userEnteredFormat.textRotation,userEnteredFormat.horizontalAlignment,"
       "userEnteredFormat.verticalAlignment,userEnteredFormat.textFormat"))
    # Summary G labels — rotated 90° + center + bold
    requests.append(rc(f"G{R_SUMMARY_START}:G{R_SUMMARY_END}", {
        "textRotation": {"angle": 90},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "textFormat": {"bold": True},
    }, "userEnteredFormat.textRotation,userEnteredFormat.horizontalAlignment,"
       "userEnteredFormat.verticalAlignment,userEnteredFormat.textFormat.bold"))
    # Timeline/owner header labels M:AI matrix header area (merged per column, rotated text)
    requests.append(rc(f"M{R_MATRIX_TOP}:AI{R_MATRIX_TOP + 6}", {
        "textRotation": {"angle": 90},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "BOTTOM",
        "textFormat": {"bold": True, "fontSize": 8},
    }, "userEnteredFormat.textRotation,userEnteredFormat.horizontalAlignment,"
       "userEnteredFormat.verticalAlignment,userEnteredFormat.textFormat"))

    # ── Fire in 200-request chunks ────────────────────────────────────────────
    CHUNK = 200
    errors: list[str] = []
    for i in range(0, len(requests), CHUNK):
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests[i:i + CHUNK]},
            ).execute()
        except Exception as e:
            logger.warning("scaffold batchUpdate [%d:%d] failed: %s", i, i + CHUNK, e)
            errors.append(str(e))

    if errors:
        raise RuntimeError(f"scaffold_oppm_form had {len(errors)} error(s): {errors[0]}")

    logger.info(
        "scaffold_oppm_form done — %d values, %d format requests, sheet=%s",
        len(value_data), len(requests), sheet_title,
    )
    return {
        "value_writes": len(value_data),
        "format_requests": len(requests),
        "sheet_title": sheet_title,
        "errors": [],
    }


def _exec_fill_timeline(
    service: Any,
    spreadsheet_id: str,
    params: dict,
    sheet_id: int,
    sheet_title: str,
) -> None:
    task_row = int(params["task_row"])
    start_date_str = str(params["start_date"])
    end_date_str = str(params["end_date"])
    color_hex = str(params.get("color", "#1D9E75"))

    # Parse dates
    start_dt = date.fromisoformat(start_date_str)
    end_dt = date.fromisoformat(end_date_str)

    # Read timeline header row to find date columns
    header_dates = _read_timeline_header_dates(service, spreadsheet_id, sheet_title)

    if not header_dates or all(d is None for d in header_dates):
        # Fallback: use formula from system prompt — col J + floor((date - first_date)/7)
        # We can't calculate without knowing timeline start, so skip gracefully
        logger.warning("fill_timeline: no header dates found, skipping action")
        return

    # Find first and last column that fall within start_date..end_date
    start_col: int | None = None
    end_col: int | None = None
    for idx, hd in enumerate(header_dates):
        if hd is None:
            continue
        col = idx + _TIMELINE_START_COL_INDEX  # 1-based
        if hd >= start_dt and hd <= end_dt:
            if start_col is None or col < start_col:
                start_col = col
            if end_col is None or col > end_col:
                end_col = col

    if start_col is None or end_col is None:
        logger.warning("fill_timeline: no columns found in date range %s–%s", start_date_str, end_date_str)
        return

    start_col_letter = _col_index_to_letters(start_col)
    end_col_letter = _col_index_to_letters(end_col)
    range_str = f"{start_col_letter}{task_row}:{end_col_letter}{task_row}"
    _exec_set_background(service, spreadsheet_id, {"range": range_str, "color": color_hex}, sheet_id)


def _exec_clear_timeline(
    service: Any,
    spreadsheet_id: str,
    params: dict,
    sheet_id: int,
) -> None:
    task_row = int(params["task_row"])
    # Clear the entire timeline region for this row: columns J..AI (10..35)
    start_col = _col_index_to_letters(_TIMELINE_START_COL_INDEX)
    end_col = _col_index_to_letters(35)  # AI column
    range_str = f"{start_col}{task_row}:{end_col}{task_row}"
    _exec_clear_background(service, spreadsheet_id, {"range": range_str}, sheet_id)


def _exec_set_owner(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    task_row = int(params["task_row"])
    owner = str(params.get("owner", ""))
    priority = str(params.get("priority", "A")).upper()

    # AJ=col 36 (A-priority), AK=col 37 (B-helper), AL=col 38 (C-secondary)
    priority_col_map = {"A": "AJ", "B": "AK", "C": "AL"}
    col = priority_col_map.get(priority, "AJ")
    _exec_set_value(service, spreadsheet_id, {"range": f"{col}{task_row}", "value": owner}, sheet_title)


def _exec_set_bold(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    bold = bool(params.get("bold", True))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": bold}
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_text_color(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    color = params.get("color", {"red": 0.0, "green": 0.0, "blue": 0.0})
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "foregroundColor": {
                                        "red": float(color.get("red", 0.0)),
                                        "green": float(color.get("green", 0.0)),
                                        "blue": float(color.get("blue", 0.0)),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.foregroundColor",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_note(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    note = str(params.get("note", ""))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "rows": [
                            {
                                "values": [
                                    {
                                        "note": note,
                                    }
                                ]
                            }
                        ],
                        "fields": "note",
                    }
                }
            ]
        },
    ).execute()


def _exec_merge_cells(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "mergeCells": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "mergeType": "MERGE_ALL",
                    }
                }
            ]
        },
    ).execute()


def _exec_unmerge_cells(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "unmergeCells": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                    }
                }
            ]
        },
    ).execute()


def _exec_set_formula(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    formula = str(params.get("formula", ""))
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        valueInputOption="USER_ENTERED",
        body={"values": [[formula]]},
    ).execute()


def _exec_set_number_format(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    pattern = str(params.get("pattern", "General"))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": pattern,
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_alignment(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    horizontal = str(params.get("horizontal", "LEFT")).upper()
    vertical = str(params.get("vertical", "BOTTOM")).upper()
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": horizontal,
                                "verticalAlignment": vertical,
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_font_size(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    size = int(params.get("size", 10))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"fontSize": size}
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.fontSize",
                    }
                }
            ]
        },
    ).execute()


def _exec_insert_image(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    """Insert an image into a cell via Google Sheets' =IMAGE() formula.

    The URL MUST be publicly fetchable from Google's servers — localhost and
    auth-protected URLs will not work. For private images, upload to Google
    Drive and share publicly, then use the URL form:
      https://drive.google.com/uc?export=view&id=FILE_ID

    params:
      range: A1 cell reference (or merged range top-left)
      url:   public HTTPS URL of the image
      mode:  1 (default — fit, keep aspect)
             2 (stretch to fill cell — distorts)
             3 (original size — may overflow)
    """
    range_str = str(params["range"])
    url = str(params["url"])
    mode = int(params.get("mode", 1))
    # Strip a single pair of double-quotes from URL (defensive — AI sometimes wraps it)
    url = url.strip().strip('"').strip("'")
    # Escape any embedded double quotes for the formula
    safe_url = url.replace('"', '""')
    formula = f'=IMAGE("{safe_url}",{mode})'
    # Use USER_ENTERED so the formula evaluates instead of being stored literally
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        valueInputOption="USER_ENTERED",
        body={"values": [[formula]]},
    ).execute()


def _exec_upload_asset_to_drive(
    service: Any,
    spreadsheet_id: str,
    params: dict,
    sheet_title: str,
    *,
    sa_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upload a local image asset to the SA's Drive (publicly viewable) and
    optionally embed it at a target range via =IMAGE().

    params:
      asset_filename: filename inside the project's assets/ folder (e.g. "OPPM NHRS.png")
      range:          optional A1 cell to write =IMAGE(url) into after upload
      mode:           optional IMAGE() display mode (1=fit, 2=stretch, 3=original) — default 1
    """
    asset_filename = str(params.get("asset_filename", "")).strip()
    if not asset_filename:
        raise ValueError("upload_asset_to_drive: asset_filename is required")

    upload = _upload_local_asset_to_drive(sa_info, asset_filename)
    target_range = params.get("range")
    if target_range:
        mode = int(params.get("mode", 1))
        _exec_insert_image(
            service,
            spreadsheet_id,
            {"range": str(target_range), "url": upload["url"], "mode": mode},
            sheet_title,
        )
        upload["embedded_at"] = str(target_range)
    return upload


def _exec_set_text_rotation(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    """Rotate text in a range. Pass `angle` (degrees, -90..90) OR `vertical: true`
    for stacked text. Used heavily by the OPPM bottom matrix headers.
    """
    range_str = str(params["range"])
    if params.get("vertical"):
        rotation = {"vertical": True}
        fields = "userEnteredFormat.textRotation.vertical"
    else:
        angle = int(params.get("angle", 90))
        # Sheets API accepts -90..90
        angle = max(-90, min(90, angle))
        rotation = {"angle": angle}
        fields = "userEnteredFormat.textRotation.angle"
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {"userEnteredFormat": {"textRotation": rotation}},
                        "fields": fields,
                    }
                }
            ]
        },
    ).execute()


def _exec_set_font_family(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    family = str(params.get("family", "Arial"))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"fontFamily": family}
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.fontFamily",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_row_height(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1
    end = int(params.get("end_index", params["start_index"]))
    height = int(params.get("height", 21))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": end,
                        },
                        "properties": {"pixelSize": height},
                        "fields": "pixelSize",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_column_width(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1
    end = int(params.get("end_index", params["start_index"]))
    width = int(params.get("width", 100))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": start,
                            "endIndex": end,
                        },
                        "properties": {"pixelSize": width},
                        "fields": "pixelSize",
                    }
                }
            ]
        },
    ).execute()


def _exec_freeze_rows(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    count = int(params.get("row_count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": count},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                }
            ]
        },
    ).execute()


def _exec_freeze_columns(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    count = int(params.get("column_count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenColumnCount": count},
                        },
                        "fields": "gridProperties.frozenColumnCount",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_conditional_formatting(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    rule_type = str(params.get("rule_type", "NUMBER_GREATER")).upper()
    value = params.get("value", 0)
    color_hex = str(params.get("color", "#1D9E75"))

    rgb = _hex_to_rgb(color_hex)
    condition: dict = {"type": rule_type}
    if rule_type in ("NUMBER_GREATER", "NUMBER_GREATER_THAN_EQ", "NUMBER_LESS", "NUMBER_LESS_THAN_EQ", "NUMBER_EQ"):
        condition["values"] = [{"userEnteredValue": str(value)}]
    elif rule_type in ("TEXT_CONTAINS", "TEXT_NOT_CONTAINS", "TEXT_STARTS_WITH", "TEXT_ENDS_WITH"):
        condition["values"] = [{"userEnteredValue": str(value)}]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [_range_to_grid_range(range_str, sheet_id)],
                            "booleanRule": {
                                "condition": condition,
                                "format": {
                                    "backgroundColor": rgb,
                                },
                            },
                        },
                        "index": 0,
                    }
                }
            ]
        },
    ).execute()


def _exec_set_data_validation(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    criteria = str(params.get("criteria", "ONE_OF_LIST")).upper()
    values = params.get("values", [])
    allow_empty = bool(params.get("allow_empty", True))

    condition: dict = {"type": criteria}
    if criteria == "ONE_OF_LIST":
        condition["values"] = [{"userEnteredValue": str(v)} for v in values]
    elif criteria in ("NUMBER_GREATER", "NUMBER_LESS", "NUMBER_EQ"):
        condition["values"] = [{"userEnteredValue": str(values[0])}] if values else []
    elif criteria == "NUMBER_BETWEEN":
        condition["values"] = [
            {"userEnteredValue": str(values[0])},
            {"userEnteredValue": str(values[1])},
        ] if len(values) >= 2 else []
    elif criteria == "TEXT_CONTAINS":
        condition["values"] = [{"userEnteredValue": str(values[0])}] if values else []

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "setDataValidation": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "rule": {
                            "condition": condition,
                            "showCustomUi": True,
                            "strict": not allow_empty,
                        },
                    }
                }
            ]
        },
    ).execute()


def _exec_set_hyperlink(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    url = str(params.get("url", ""))
    text = str(params.get("text", url))
    formula = f'=HYPERLINK("{url}","{text}")'
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        valueInputOption="USER_ENTERED",
        body={"values": [[formula]]},
    ).execute()


def _exec_protect_range(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    description = str(params.get("description", "Protected range"))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addProtectedRange": {
                        "protectedRange": {
                            "range": _range_to_grid_range(range_str, sheet_id),
                            "description": description,
                            "warningOnly": False,
                        }
                    }
                }
            ]
        },
    ).execute()


def _exec_unprotect_range(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    # Find existing protected range ID for this range, then delete it
    resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.protectedRanges.protectedRangeId,sheets.protectedRanges.range",
    ).execute()
    target_id = None
    for sheet in resp.get("sheets", []):
        for pr in sheet.get("protectedRanges", []):
            pr_range = pr.get("range", {})
            if (
                pr_range.get("sheetId") == sheet_id
                and pr_range.get("startRowIndex") == _parse_range(range_str)[0] - 1
                and pr_range.get("startColumnIndex") == _parse_range(range_str)[1] - 1
            ):
                target_id = pr["protectedRangeId"]
                break
        if target_id:
            break

    if target_id is None:
        raise ValueError(f"No protected range found for {range_str}")

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "deleteProtectedRange": {
                        "protectedRangeId": target_id,
                    }
                }
            ]
        },
    ).execute()


