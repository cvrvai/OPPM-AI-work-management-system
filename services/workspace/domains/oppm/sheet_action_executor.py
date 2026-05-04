"""Sheet action executor — translates OPPM AI JSON actions to Google Sheets API v4 calls.

Supported actions (matching the OPPM AI system prompt contract):
  insert_rows, delete_rows, copy_format, set_border, set_background,
  clear_background, set_text_wrap, set_value, clear_content,
  fill_timeline, clear_timeline, set_owner,
  set_bold, set_text_color, set_note,
  merge_cells, unmerge_cells,
  set_formula, set_number_format, set_alignment,
  set_font_size, set_font_family, set_text_rotation,
  set_row_height, set_column_width,
  freeze_rows, freeze_columns,
  set_conditional_formatting, set_data_validation,
  set_hyperlink,
  protect_range, unprotect_range,
  insert_image, upload_asset_to_drive,
  scaffold_oppm_form

Border styles supported: NONE, DOTTED, DASHED, SOLID, SOLID_MEDIUM, SOLID_THICK, DOUBLE.
Per-side overrides (top_*, bottom_*, left_*, right_*, inner_horizontal_*, inner_vertical_*)
allow fine-grained border control. style=NONE removes borders entirely.
"""

import logging
import mimetypes
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Local asset → Drive upload (Option A image embedding) ──────────────────
#
# Resolves the project's `assets/` folder so the AI can reference local files
# (e.g. "OPPM NHRS.png") and the backend uploads them to the service account's
# Drive on demand, then embeds via =IMAGE(). Override with OPPM_ASSETS_DIR env
# var if the layout ever changes.

_DEFAULT_ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"
_ASSETS_DIR = Path(os.environ.get("OPPM_ASSETS_DIR") or _DEFAULT_ASSETS_DIR).resolve()

# Cache of (asset_filename, mtime_ns) -> {"file_id": ..., "url": ...}.
# Avoids re-uploading the same file every scaffold call. mtime invalidates the
# cache automatically when the user edits the asset.
_ASSET_DRIVE_CACHE: dict[tuple[str, int], dict[str, str]] = {}

_ALLOWED_IMAGE_MIME_PREFIX = "image/"


def _resolve_safe_asset_path(asset_filename: str) -> Path:
    """Resolve `asset_filename` inside the assets/ dir, rejecting path traversal."""
    if not asset_filename or not isinstance(asset_filename, str):
        raise ValueError("asset_filename is required")
    # Strip surrounding whitespace / quotes (defensive — AI sometimes wraps args)
    name = asset_filename.strip().strip('"').strip("'")
    if not name:
        raise ValueError("asset_filename is empty")
    # Reject anything that smells like a traversal or absolute path
    if name.startswith(("/", "\\")) or ":" in name or ".." in name.replace("\\", "/").split("/"):
        raise ValueError(f"asset_filename must be a plain filename (no path traversal): {asset_filename!r}")
    candidate = (_ASSETS_DIR / name).resolve()
    # Final containment check: candidate must live inside the assets dir
    try:
        candidate.relative_to(_ASSETS_DIR)
    except ValueError:
        raise ValueError(f"asset_filename resolves outside assets dir: {asset_filename!r}")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"Asset not found: {name} (looked in {_ASSETS_DIR})")
    return candidate


def _upload_local_asset_to_drive(sa_info: dict[str, Any] | None, asset_filename: str) -> dict[str, str]:
    """Upload a local asset to the service account's Drive, share it publicly,
    and return {file_id, url}. Caches by (filename, mtime) to avoid re-uploads.

    Raises ValueError on bad asset name, FileNotFoundError on missing file,
    RuntimeError on Drive errors (caller logs and degrades gracefully).
    """
    if sa_info is None:
        raise RuntimeError("Service account credentials unavailable — cannot upload to Drive")

    path = _resolve_safe_asset_path(asset_filename)
    mtime_ns = path.stat().st_mtime_ns
    cache_key = (path.name, mtime_ns)
    cached = _ASSET_DRIVE_CACHE.get(cache_key)
    if cached:
        logger.debug("upload_asset: cache hit for %s", path.name)
        return cached

    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith(_ALLOWED_IMAGE_MIME_PREFIX):
        raise ValueError(f"Asset is not a recognised image (mime={mime_type!r}): {path.name}")

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("googleapiclient.http is required for Drive uploads") from exc

    # Lazy import keeps this module's top-level imports lean.
    from domains.oppm.google_sheets.credentials import _build_drive_service

    drive = _build_drive_service(sa_info)
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
    created = drive.files().create(
        body={"name": path.name},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    file_id = created["id"]

    # Make publicly readable so =IMAGE() can fetch it from Google's servers
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
        supportsAllDrives=True,
    ).execute()

    public_url = f"https://drive.google.com/uc?export=view&id={file_id}"
    result = {"file_id": file_id, "url": public_url, "asset_filename": path.name, "mime_type": mime_type}
    _ASSET_DRIVE_CACHE[cache_key] = result
    logger.info("upload_asset: %s → %s", path.name, file_id)
    return result

# ── A1 notation helpers ──

_COL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _col_letters_to_index(letters: str) -> int:
    """Convert column letters to 1-based index. A→1, Z→26, AA→27."""
    index = 0
    for char in letters.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index


def _col_index_to_letters(index: int) -> str:
    """Convert 1-based column index to letters. 1→A, 26→Z, 27→AA."""
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _parse_cell(cell: str) -> tuple[int, int]:
    """Parse A1 cell reference to (row, col) both 1-based. Returns (0,0) on failure."""
    m = _COL_RE.match(cell.strip().upper())
    if not m:
        return 0, 0
    return int(m.group(2)), _col_letters_to_index(m.group(1))


def _parse_range(range_str: str) -> tuple[int, int, int, int]:
    """Parse 'A1:B3' to (start_row, start_col, end_row, end_col), all 1-based."""
    parts = range_str.strip().upper().split(":")
    if len(parts) == 1:
        r, c = _parse_cell(parts[0])
        return r, c, r, c
    r1, c1 = _parse_cell(parts[0])
    r2, c2 = _parse_cell(parts[1])
    return r1, c1, r2, c2


def _range_to_grid_range(range_str: str, sheet_id: int) -> dict:
    """Convert A1 range to Sheets API GridRange (0-based exclusive)."""
    r1, c1, r2, c2 = _parse_range(range_str)
    return {
        "sheetId": sheet_id,
        "startRowIndex": r1 - 1,
        "endRowIndex": r2,
        "startColumnIndex": c1 - 1,
        "endColumnIndex": c2,
    }


def _hex_to_rgb(hex_color: str) -> dict:
    """Convert '#RRGGBB' to {red, green, blue} with 0-1 floats."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return {"red": r / 255.0, "green": g / 255.0, "blue": b / 255.0}


def _border_style(style: str, color: str = "#CCCCCC", width: int = 1) -> dict | None:
    """Return a border dict for Sheets API updateBorders.

    Returns None when style is NONE so the caller can omit the side key
    entirely (which removes the border for that side).
    """
    style_upper = style.upper() if style else "SOLID"
    if style_upper == "NONE":
        return None
    # Google Sheets API border styles: NONE, DOTTED, DASHED, SOLID, SOLID_MEDIUM, SOLID_THICK, DOUBLE
    valid_styles = {"NONE", "DOTTED", "DASHED", "SOLID", "SOLID_MEDIUM", "SOLID_THICK", "DOUBLE"}
    api_style = style_upper if style_upper in valid_styles else "SOLID"
    return {
        "style": api_style,
        "width": width,
        "color": _hex_to_rgb(color),
    }


# ── Timeline helpers ──

_TIMELINE_START_COL_INDEX = 10  # Column J is index 10 (1-based)
_TIMELINE_HEADER_ROW = 5


def _date_to_timeline_col(target: date, header_dates: list[date | None]) -> int | None:
    """Return 1-based column index for a given date from timeline header dates list."""
    for idx, header_date in enumerate(header_dates):
        if header_date is None:
            continue
        if header_date <= target:
            # Find the last column whose date is <= target
            pass
    # Find the rightmost column whose date <= target
    best_col = None
    for idx, header_date in enumerate(header_dates):
        if header_date is None:
            continue
        if header_date <= target:
            best_col = idx + _TIMELINE_START_COL_INDEX  # 1-based col
    return best_col


def _parse_header_dates(header_row_values: list[str | None]) -> list[date | None]:
    """Parse date strings from the timeline header row into date objects."""
    result: list[date | None] = []
    for val in header_row_values:
        if not val:
            result.append(None)
            continue
        parsed = None
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y", "%m/%d/%Y", "%d %B %Y", "%b %d, %Y"):
            try:
                parsed = datetime.strptime(val.strip(), fmt).date()
                break
            except ValueError:
                continue
        result.append(parsed)
    return result


def _read_timeline_header_dates(service: Any, spreadsheet_id: str, sheet_title: str) -> list[date | None]:
    """Read the timeline header row and return parsed dates starting from column J."""
    # Read row 5 from column J onward (columns 10..52)
    range_ref = f"'{sheet_title}'!J{_TIMELINE_HEADER_ROW}:AI{_TIMELINE_HEADER_ROW}"
    try:
        resp = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_ref,
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        values = resp.get("values", [[]])[0] if resp.get("values") else []
        return _parse_header_dates(values)
    except Exception as e:
        logger.warning("Failed to read timeline header dates: %s", e)
        return []


def _find_sheet_id(service: Any, spreadsheet_id: str, sheet_title: str) -> int:
    """Return the sheetId integer for a named sheet tab."""
    resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties.sheetId,sheets.properties.title",
    ).execute()
    for sheet in resp.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_title:
            return int(props["sheetId"])
    raise ValueError(f"Sheet '{sheet_title}' not found in spreadsheet")


# ── Action dispatchers ──

def _exec_insert_rows(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1  # convert to 0-based
    count = int(params.get("count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": start + count,
                        },
                        "inheritFromBefore": True,
                    }
                }
            ]
        },
    ).execute()


def _exec_delete_rows(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1  # 0-based
    count = int(params.get("count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": start + count,
                        }
                    }
                }
            ]
        },
    ).execute()


def _exec_copy_format(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    from_range = str(params["from_range"])
    to_range = str(params["to_range"])
    fr1, fc1, fr2, fc2 = _parse_range(from_range)
    tr1, tc1, tr2, tc2 = _parse_range(to_range)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "copyPaste": {
                        "source": {
                            "sheetId": sheet_id,
                            "startRowIndex": fr1 - 1,
                            "endRowIndex": fr2,
                            "startColumnIndex": fc1 - 1,
                            "endColumnIndex": fc2,
                        },
                        "destination": {
                            "sheetId": sheet_id,
                            "startRowIndex": tr1 - 1,
                            "endRowIndex": tr2,
                            "startColumnIndex": tc1 - 1,
                            "endColumnIndex": tc2,
                        },
                        "pasteType": "PASTE_FORMAT",
                        "pasteOrientation": "NORMAL",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_border(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    style = str(params.get("style", "SOLID"))
    color = str(params.get("color", "#CCCCCC"))
    width = int(params.get("width", 1))

    # Build per-side border objects; None means remove that side
    top = _border_style(str(params.get("top_style", style)), str(params.get("top_color", color)), int(params.get("top_width", width)))
    bottom = _border_style(str(params.get("bottom_style", style)), str(params.get("bottom_color", color)), int(params.get("bottom_width", width)))
    left = _border_style(str(params.get("left_style", style)), str(params.get("left_color", color)), int(params.get("left_width", width)))
    right = _border_style(str(params.get("right_style", style)), str(params.get("right_color", color)), int(params.get("right_width", width)))
    inner_h = _border_style(str(params.get("inner_horizontal_style", style)), str(params.get("inner_horizontal_color", color)), int(params.get("inner_horizontal_width", width)))
    inner_v = _border_style(str(params.get("inner_vertical_style", style)), str(params.get("inner_vertical_color", color)), int(params.get("inner_vertical_width", width)))

    request: dict = {
        "updateBorders": {
            "range": _range_to_grid_range(range_str, sheet_id),
        }
    }
    if top is not None:
        request["updateBorders"]["top"] = top
    if bottom is not None:
        request["updateBorders"]["bottom"] = bottom
    if left is not None:
        request["updateBorders"]["left"] = left
    if right is not None:
        request["updateBorders"]["right"] = right
    if inner_h is not None:
        request["updateBorders"]["innerHorizontal"] = inner_h
    if inner_v is not None:
        request["updateBorders"]["innerVertical"] = inner_v

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [request]},
    ).execute()


def _exec_set_background(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    color_hex = str(params.get("color", "#FFFFFF"))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _hex_to_rgb(color_hex)
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]
        },
    ).execute()


def _exec_clear_background(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_text_wrap(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    mode = str(params.get("mode", "CLIP")).upper()
    if mode not in ("CLIP", "WRAP", "OVERFLOW_CELL"):
        mode = "CLIP"
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {"wrapStrategy": mode}
                        },
                        "fields": "userEnteredFormat.wrapStrategy",
                    }
                }
            ]
        },
    ).execute()


def _exec_set_value(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    value = params.get("value", "")
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        valueInputOption="USER_ENTERED",
        body={"values": [[value]]},
    ).execute()


def _exec_clear_content(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        body={},
    ).execute()


def _exec_clear_sheet(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    """Clear the entire OPPM sheet: values, formatting, merges, then reset dimensions."""
    # 1. Clear all values
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'OPPM'!A1:AL1000",
        body={},
    ).execute()

    # 2. Unmerge all cells
    merges = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=["'OPPM'"],
        fields="sheets.merges",
    ).execute()
    merge_requests = []
    for sheet in merges.get("sheets", []):
        for merge in sheet.get("merges", []):
            merge_requests.append({"unmergeCells": {"range": merge}})
    if merge_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": merge_requests},
        ).execute()

    # 3. Clear all formatting (borders, backgrounds, fonts, alignment, number format, etc.)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1000,
                            "startColumnIndex": 0,
                            "endColumnIndex": 40,
                        },
                        "fields": "userEnteredFormat",
                    }
                }
            ]
        },
    ).execute()

    # 4. Reset row heights to default (21px for all rows)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 0,
                            "endIndex": 1000,
                        },
                        "properties": {"pixelSize": 21},
                        "fields": "pixelSize",
                    }
                }
            ]
        },
    ).execute()

    # 5. Reset column widths to standard OPPM values
    col_widths = [
        (0, 6, 40),    # A-F: 40px
        (6, 7, 10),    # G: 10px
        (7, 8, 50),    # H: 50px
        (8, 9, 280),   # I: 280px
        (9, 35, 25),   # J-AI: 25px
        (35, 38, 80),  # AJ-AL: 80px
    ]
    requests = []
    for start, end, width in col_widths:
        requests.append({
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
        })
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


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
_SCAFFOLD_DEFAULT_TASK_COUNT = 30
_SCAFFOLD_TASK_ROW_HEIGHT = 21
_SCAFFOLD_MATRIX_DATE_ROW_HEIGHT = 100  # top matrix row holds rotated date headers — needs vertical room
_SCAFFOLD_MATRIX_BODY_ROW_HEIGHT = 30   # body matrix rows (X-pattern / image area)
_SCAFFOLD_MATRIX_HEIGHT_ROWS = 9        # rows in the bottom cross-reference matrix


def _build_scaffold_actions(params: dict) -> list[dict]:
    """Build the deterministic action list for a full OPPM form scaffold.

    Layout follows the authentic OPPM PDF reference (Clark Campbell):
      Row 1            blank spacer
      Row 2            split: "Project Leader: ..." (A:N) | "Project Name: ..." (O:AL)
      Rows 3-4         MERGED A3:AL4 — multi-line block: Objective + Deliverable + Start + Deadline
      Row 5            sub-headers: "Sub objective" (A:F) | "Major Tasks (Deadline)" (H:I)
                       | "Project Completed By: ..." (J:AI) | "Owner / Priority" (AJ:AL)
      Rows 6 .. 5+N    task rows, numbered 1..N in column H (default N=30)
      R_PEOPLE         "# People working on the project:" full-width row
      R_MATRIX         9-row bottom matrix:
                         A:F  rotated sub-objective headers (1..6 with placeholder labels)
                         I:AI X-pattern labels (Major Tasks / Target Dates / Sub Objectives /
                              Costs / Summary & Forecast) + rotated week-date headers in J:U
                         AJ:AL rotated owner-name placeholders
      R_SUMMARY        Summary / Forecast / Risk section:
                         G column rotated section labels (Summary Deliverable, Forecast, Risk)
                         I:AL placeholder text rows for each section item

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
    task_count = max(1, min(30, int(params.get("task_count") or _SCAFFOLD_DEFAULT_TASK_COUNT)))
    # Optional public image URL for the X-pattern matrix center (replaces the
    # five text labels Major Tasks / Target Dates / Sub Objectives / Costs /
    # Summary & Forecast with an embedded image). Must be publicly fetchable
    # by Google Sheets — typically a Google Drive shared URL of the form
    # https://drive.google.com/uc?export=view&id=FILE_ID.
    matrix_image_url = params.get("matrix_image_url")
    matrix_image_url = str(matrix_image_url).strip() if matrix_image_url else None

    # Row positions
    LAST_TASK = 5 + task_count
    R_PEOPLE = LAST_TASK + 1
    R_MATRIX_TOP = R_PEOPLE + 1
    R_MATRIX_BOTTOM = R_MATRIX_TOP + _SCAFFOLD_MATRIX_HEIGHT_ROWS - 1
    R_SUMMARY_START = R_MATRIX_BOTTOM + 1
    R_SUMMARY_DELIV_END = R_SUMMARY_START + 3   # 4 deliverable rows
    R_FORECAST_START = R_SUMMARY_DELIV_END + 1
    R_FORECAST_END = R_FORECAST_START + 1       # 2 forecast rows
    R_RISK_START = R_FORECAST_END + 1
    R_RISK_END = R_RISK_START + 1               # 2 risk rows
    R_FORM_BOTTOM = R_RISK_END                   # last form row

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
    # Row 2: Project Leader (left) | Project Name (right)
    a.append({"action": "set_value", "params": {"range": "A2", "value": f"Project Leader: {leader}"}})
    a.append({"action": "set_value", "params": {"range": "O2", "value": f"Project Name: {title}"}})
    # Rows 3-4 (merged): multi-line metadata block
    metadata_block = (
        f"Project Objective: {objective}\n"
        f"Deliverable Output: {deliverable}\n"
        f"Start Date: {start_date}\n"
        f"Deadline: {deadline}"
    )
    a.append({"action": "set_value", "params": {"range": "A3", "value": metadata_block}})
    # Row 5: 4 sub-headers
    a.append({"action": "set_value", "params": {"range": "A5", "value": "Sub objective"}})
    a.append({"action": "set_value", "params": {"range": "H5", "value": "Major Tasks (Deadline)"}})
    a.append({"action": "set_value", "params": {"range": "J5", "value": f"Project Completed By: {weeks_label}"}})
    a.append({"action": "set_value", "params": {"range": "AJ5", "value": "Owner / Priority"}})

    # ── 3. Task numbers 1..N in column H ──
    for i in range(1, task_count + 1):
        a.append({"action": "set_value", "params": {"range": f"H{5 + i}", "value": str(i)}})

    # ── 4. # People working row ──
    a.append({"action": "set_value", "params": {"range": f"A{R_PEOPLE}", "value": "# People working on the project:"}})

    # ── 5. Bottom matrix content ──
    # 5a. Sub-objective rotated headers in A:F
    sub_obj_placeholders = [
        "1 Sub-Objective 1", "2 Sub-Objective 2", "3 Sub-Objective 3",
        "4 Sub-Objective 4", "5 Sub-Objective 5", "6 Sub-Objective 6",
    ]
    for col_idx, label in enumerate(sub_obj_placeholders, start=1):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_TOP}", "value": label}})

    # 5b. X-pattern center area — ALWAYS leave it as one big merged empty cell
    #     ready for image insertion. If an explicit matrix_image_url was given,
    #     drop the =IMAGE() formula in. Otherwise the cell stays blank — the
    #     user can manually insert their X-pattern diagram via Google Sheets'
    #     "Insert → Image → Image in cell" UI. We deliberately do NOT write
    #     "Major Tasks / Target Dates / Sub Objectives / Costs / Summary &
    #     Forecast" text labels because they look messy and clutter the area
    #     where the user wants their actual diagram.
    if matrix_image_url:
        safe_url = matrix_image_url.replace('"', '""')
        a.append({"action": "set_value", "params": {
            "range": f"H{R_MATRIX_TOP + 1}",
            "value": f'=IMAGE("{safe_url}",1)',
        }})

    # 5c. Week-date rotated headers in J:U (12 weekly placeholders)
    for w in range(12):
        col_letter = _col_index_to_letters(10 + w)  # J=10..U=21
        if start_dt:
            label = (start_dt + _td(weeks=w)).strftime("%d-%b-%Y")
        else:
            label = f"Week {w + 1}"
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_TOP}", "value": label}})

    # 5d. Owner-name rotated placeholders in AJ/AK/AL
    for idx, col_letter in enumerate(("AJ", "AK", "AL"), start=1):
        a.append({"action": "set_value", "params": {"range": f"{col_letter}{R_MATRIX_TOP}", "value": f"Team Member {idx}"}})

    # ── 6. Summary / Forecast / Risk section ──
    # Rotated section labels in column G
    a.append({"action": "set_value", "params": {"range": f"G{R_SUMMARY_START}", "value": "Summary Deliverable"}})
    a.append({"action": "set_value", "params": {"range": f"G{R_FORECAST_START}", "value": "Forecast"}})
    a.append({"action": "set_value", "params": {"range": f"G{R_RISK_START}", "value": "Risk"}})
    # Placeholder text rows
    for i in range(4):
        a.append({"action": "set_value", "params": {"range": f"I{R_SUMMARY_START + i}", "value": f"Deliverable item {i + 1}: ..."}})
    for i in range(2):
        a.append({"action": "set_value", "params": {"range": f"I{R_FORECAST_START + i}", "value": f"Forecast: ..."}})
    for i in range(2):
        a.append({"action": "set_value", "params": {"range": f"I{R_RISK_START + i}", "value": f"Risk: ..."}})

    # ── 7. Merges ──
    # Row 2 split
    a.append({"action": "merge_cells", "params": {"range": "A2:N2"}})
    a.append({"action": "merge_cells", "params": {"range": "O2:AL2"}})
    # Rows 3-4 metadata block
    a.append({"action": "merge_cells", "params": {"range": "A3:AL4"}})
    # Row 5 sub-headers
    a.append({"action": "merge_cells", "params": {"range": "A5:F5"}})
    a.append({"action": "merge_cells", "params": {"range": "H5:I5"}})
    a.append({"action": "merge_cells", "params": {"range": "J5:AI5"}})
    a.append({"action": "merge_cells", "params": {"range": "AJ5:AL5"}})
    # # People row (full width)
    a.append({"action": "merge_cells", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}"}})
    # Bottom matrix sub-objective columns: each column merged across full matrix height for rotated text
    for col_idx in range(1, 7):
        col_letter = _col_index_to_letters(col_idx)
        a.append({"action": "merge_cells", "params": {"range": f"{col_letter}{R_MATRIX_TOP}:{col_letter}{R_MATRIX_BOTTOM}"}})
    # Bottom matrix owner columns: each merged across full matrix height
    for col_letter in ("AJ", "AK", "AL"):
        a.append({"action": "merge_cells", "params": {"range": f"{col_letter}{R_MATRIX_TOP}:{col_letter}{R_MATRIX_BOTTOM}"}})
    # Bottom matrix center area — ALWAYS merge H..AI from row matrix_top+1
    # down into one big rectangle. Either =IMAGE() fills it, or the user
    # drops their X-pattern diagram in via "Insert → Image → Image in cell".
    a.append({"action": "merge_cells", "params": {"range": f"H{R_MATRIX_TOP + 1}:AI{R_MATRIX_BOTTOM}"}})
    # Summary/Forecast/Risk: rotated G-column labels span their section rows
    a.append({"action": "merge_cells", "params": {"range": f"G{R_SUMMARY_START}:G{R_SUMMARY_DELIV_END}"}})
    a.append({"action": "merge_cells", "params": {"range": f"G{R_FORECAST_START}:G{R_FORECAST_END}"}})
    a.append({"action": "merge_cells", "params": {"range": f"G{R_RISK_START}:G{R_RISK_END}"}})
    # Each summary/forecast/risk text row spans I:AL
    for r in range(R_SUMMARY_START, R_SUMMARY_DELIV_END + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{r}:AL{r}"}})
    for r in range(R_FORECAST_START, R_FORECAST_END + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{r}:AL{r}"}})
    for r in range(R_RISK_START, R_RISK_END + 1):
        a.append({"action": "merge_cells", "params": {"range": f"I{r}:AL{r}"}})

    # ── 8. Row heights ──
    a.append({"action": "set_row_height", "params": {"start_index": 3, "end_index": 4, "height": 28}})
    a.append({"action": "set_row_height", "params": {"start_index": 6, "end_index": LAST_TASK, "height": _SCAFFOLD_TASK_ROW_HEIGHT}})
    # Top matrix row carries rotated week-date labels — needs lots of vertical
    # room or "16-Feb-2026" gets clipped to just "026" at the cell edge.
    a.append({"action": "set_row_height", "params": {"start_index": R_MATRIX_TOP, "end_index": R_MATRIX_TOP, "height": _SCAFFOLD_MATRIX_DATE_ROW_HEIGHT}})
    # Remaining matrix rows (the X-pattern / image area)
    a.append({"action": "set_row_height", "params": {"start_index": R_MATRIX_TOP + 1, "end_index": R_MATRIX_BOTTOM, "height": _SCAFFOLD_MATRIX_BODY_ROW_HEIGHT}})

    # ── 9. Backgrounds ──
    a.append({"action": "set_background", "params": {"range": "A5:AL5", "color": _SCAFFOLD_HEADER_BG}})
    a.append({"action": "set_background", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "color": _SCAFFOLD_HEADER_BG}})

    # ── 10. Borders — large fills first, then specific overrides on top ──
    # 10a. Header rows 1-5 → black grid
    a.append({"action": "set_border", "params": {"range": "A1:AL5", "style": "SOLID", "color": _SCAFFOLD_HEADER_BLACK, "width": 1}})
    # 10b. Task area sub-objectives + numbers/titles (A:I) → gray grid
    a.append({"action": "set_border", "params": {"range": f"A6:I{LAST_TASK}", "style": "SOLID", "color": _SCAFFOLD_TASK_GRAY, "width": 1}})
    # 10c. Task area owners (AJ:AL) → gray grid
    a.append({"action": "set_border", "params": {"range": f"AJ6:AL{LAST_TASK}", "style": "SOLID", "color": _SCAFFOLD_TASK_GRAY, "width": 1}})
    # 10d. # People row → black border
    a.append({"action": "set_border", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "style": "SOLID", "color": _SCAFFOLD_HEADER_BLACK, "width": 1}})
    # 10e. Bottom matrix → black grid
    a.append({"action": "set_border", "params": {"range": f"A{R_MATRIX_TOP}:AL{R_MATRIX_BOTTOM}", "style": "SOLID", "color": _SCAFFOLD_HEADER_BLACK, "width": 1}})
    # 10f. Summary/Forecast/Risk section → black grid
    a.append({"action": "set_border", "params": {"range": f"G{R_SUMMARY_START}:AL{R_RISK_END}", "style": "SOLID", "color": _SCAFFOLD_HEADER_BLACK, "width": 1}})
    # 10g. Vertical thick dividers (F, I, AI on the right) — applied through task area only
    for col in ("F", "I", "AI"):
        a.append({
            "action": "set_border",
            "params": {
                "range": f"{col}1:{col}{LAST_TASK}",
                "style": "NONE",
                "right_style": "SOLID_THICK", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 3,
            },
        })
    # 10h. Horizontal thick dividers
    a.append({"action": "set_border", "params": {"range": "A5:AL5", "style": "NONE",
                                                  "bottom_style": "SOLID_THICK", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 3}})
    a.append({"action": "set_border", "params": {"range": f"A{LAST_TASK}:AL{LAST_TASK}", "style": "NONE",
                                                  "bottom_style": "SOLID_THICK", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 3}})
    a.append({"action": "set_border", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "style": "NONE",
                                                  "bottom_style": "SOLID_THICK", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 3}})
    a.append({"action": "set_border", "params": {"range": f"A{R_MATRIX_BOTTOM}:AL{R_MATRIX_BOTTOM}", "style": "NONE",
                                                  "bottom_style": "SOLID_THICK", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 3}})
    # 10i. Outer thick frame around the whole form (rows 1..R_FORM_BOTTOM)
    a.append({
        "action": "set_border",
        "params": {
            "range": f"A1:AL{R_FORM_BOTTOM}",
            "style": "NONE",
            "top_style": "SOLID_THICK", "top_color": _SCAFFOLD_HEADER_BLACK, "top_width": 3,
            "bottom_style": "SOLID_THICK", "bottom_color": _SCAFFOLD_HEADER_BLACK, "bottom_width": 3,
            "left_style": "SOLID_THICK", "left_color": _SCAFFOLD_HEADER_BLACK, "left_width": 3,
            "right_style": "SOLID_THICK", "right_color": _SCAFFOLD_HEADER_BLACK, "right_width": 3,
        },
    })

    # ── 11. Fonts, alignment, rotation ──
    # Row 2 leader/name
    a.append({"action": "set_font_size", "params": {"range": "A2:AL2", "size": 11}})
    a.append({"action": "set_bold", "params": {"range": "A2:AL2", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": "A2:AL2", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Rows 3-4 metadata (multi-line, top-left, wrap)
    a.append({"action": "set_font_size", "params": {"range": "A3:AL4", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": "A3:AL4", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": "A3:AL4", "horizontal": "LEFT", "vertical": "TOP"}})
    a.append({"action": "set_text_wrap", "params": {"range": "A3:AL4", "mode": "WRAP"}})
    # Row 5 sub-headers
    a.append({"action": "set_font_size", "params": {"range": "A5:AL5", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": "A5:AL5", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": "A5:AL5", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Task numbers (column H)
    a.append({"action": "set_font_size", "params": {"range": f"H6:H{LAST_TASK}", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": f"H6:H{LAST_TASK}", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"H6:H{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Task titles (column I) — left aligned, CLIP to preserve row height
    a.append({"action": "set_font_size", "params": {"range": f"I6:I{LAST_TASK}", "size": 10}})
    a.append({"action": "set_alignment", "params": {"range": f"I6:I{LAST_TASK}", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    a.append({"action": "set_text_wrap", "params": {"range": f"I6:I{LAST_TASK}", "mode": "CLIP"}})
    # Sub-objective check columns (A-F) and owner columns (AJ-AL)
    a.append({"action": "set_alignment", "params": {"range": f"A6:F{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_alignment", "params": {"range": f"AJ6:AL{LAST_TASK}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # # People row
    a.append({"action": "set_font_size", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "size": 10}})
    a.append({"action": "set_bold", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"A{R_PEOPLE}:AL{R_PEOPLE}", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    # Bottom matrix sub-objective columns (A-F): rotated 90° + center + small font
    a.append({"action": "set_text_rotation", "params": {"range": f"A{R_MATRIX_TOP}:F{R_MATRIX_BOTTOM}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"A{R_MATRIX_TOP}:F{R_MATRIX_BOTTOM}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"A{R_MATRIX_TOP}:F{R_MATRIX_BOTTOM}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"A{R_MATRIX_TOP}:F{R_MATRIX_BOTTOM}", "bold": True}})
    # Bottom matrix date/timeline columns (J-AI): rotated 90° + center + small font
    a.append({"action": "set_text_rotation", "params": {"range": f"J{R_MATRIX_TOP}:AI{R_MATRIX_TOP}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"J{R_MATRIX_TOP}:AI{R_MATRIX_TOP}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"J{R_MATRIX_TOP}:AI{R_MATRIX_TOP}", "size": 9}})
    # Bottom matrix owner columns (AJ-AL): rotated 90° + center
    a.append({"action": "set_text_rotation", "params": {"range": f"AJ{R_MATRIX_TOP}:AL{R_MATRIX_BOTTOM}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"AJ{R_MATRIX_TOP}:AL{R_MATRIX_BOTTOM}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_font_size", "params": {"range": f"AJ{R_MATRIX_TOP}:AL{R_MATRIX_BOTTOM}", "size": 9}})
    a.append({"action": "set_bold", "params": {"range": f"AJ{R_MATRIX_TOP}:AL{R_MATRIX_BOTTOM}", "bold": True}})
    # Bottom matrix center area (X-pattern labels): bold + center
    a.append({"action": "set_bold", "params": {"range": f"H{R_MATRIX_TOP}:AI{R_MATRIX_BOTTOM}", "bold": True}})
    a.append({"action": "set_alignment", "params": {"range": f"H{R_MATRIX_TOP + 1}:AI{R_MATRIX_BOTTOM}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    # Summary section: rotated G-column labels
    a.append({"action": "set_text_rotation", "params": {"range": f"G{R_SUMMARY_START}:G{R_RISK_END}", "angle": 90}})
    a.append({"action": "set_alignment", "params": {"range": f"G{R_SUMMARY_START}:G{R_RISK_END}", "horizontal": "CENTER", "vertical": "MIDDLE"}})
    a.append({"action": "set_bold", "params": {"range": f"G{R_SUMMARY_START}:G{R_RISK_END}", "bold": True}})
    a.append({"action": "set_font_size", "params": {"range": f"G{R_SUMMARY_START}:G{R_RISK_END}", "size": 9}})
    # Summary text rows: smaller font, left-align, wrap
    a.append({"action": "set_font_size", "params": {"range": f"I{R_SUMMARY_START}:AL{R_RISK_END}", "size": 9}})
    a.append({"action": "set_alignment", "params": {"range": f"I{R_SUMMARY_START}:AL{R_RISK_END}", "horizontal": "LEFT", "vertical": "MIDDLE"}})
    a.append({"action": "set_text_wrap", "params": {"range": f"I{R_SUMMARY_START}:AL{R_RISK_END}", "mode": "WRAP"}})

    # ── 12. Freeze header rows ──
    a.append({"action": "freeze_rows", "params": {"row_count": 5}})

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
    """Execute the full OPPM form scaffold using batched API calls.

    Sequence:
      1. (optional) Resolve matrix_image_asset → upload to Drive → use as matrix_image_url
      2. clear_sheet (already a multi-call routine — runs first so the values
         and formatting batches operate on a clean slate)
      3. ONE values.batchUpdate carrying every set_value sub-action
      4. ONE spreadsheets.batchUpdate carrying every formatting/structural request
         (chunked at 200 requests per call to stay under API limits)

    This collapses ~150 sequential round-trips down to ~3 round-trips so the
    full scaffold completes well within typical gateway timeouts (~60s).
    """
    # Pre-step — if the caller supplied a local asset filename for the matrix
    # center, upload it to the SA's Drive now and translate to a public URL so
    # _build_scaffold_actions sees it as `matrix_image_url`.
    matrix_image_asset = params.get("matrix_image_asset")
    upload_summary: dict[str, Any] | None = None
    effective_params = dict(params)
    if matrix_image_asset and not effective_params.get("matrix_image_url"):
        try:
            upload_summary = _upload_local_asset_to_drive(sa_info, str(matrix_image_asset))
            effective_params["matrix_image_url"] = upload_summary["url"]
            logger.info(
                "scaffold_oppm_form: embedded matrix_image_asset=%s as %s",
                matrix_image_asset, upload_summary["url"],
            )
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            # Non-fatal — fall back to text labels and surface the error to caller
            logger.warning("scaffold_oppm_form: matrix_image_asset upload failed: %s", e)
            upload_summary = {"error": str(e), "asset_filename": str(matrix_image_asset)}

    sub_actions = _build_scaffold_actions(effective_params)

    value_data: list[dict] = []
    format_requests: list[dict] = []
    has_clear = False

    for sub in sub_actions:
        sub_name = sub.get("action", "")
        sub_params = sub.get("params", {}) or {}
        if sub_name == "clear_sheet":
            has_clear = True
            continue
        if sub_name == "set_value":
            value_data.append({
                "range": f"'{sheet_title}'!{sub_params['range']}",
                "values": [[sub_params.get("value", "")]],
            })
            continue
        try:
            req = _scaffold_action_to_request(sub_name, sub_params, sheet_id)
        except Exception as e:
            logger.warning("scaffold: failed to build request for '%s': %s", sub_name, e)
            continue
        if req is not None:
            format_requests.append(req)

    errors: list[str] = []
    executed_groups = 0

    # Step 1 — clear_sheet (its own multi-call routine; safe to fail silently
    # since an existing-form scaffold will overwrite anything left behind).
    if has_clear:
        try:
            _exec_clear_sheet(service, spreadsheet_id, {}, sheet_id)
            executed_groups += 1
        except Exception as e:
            logger.warning("scaffold: clear_sheet failed: %s", e)
            errors.append(f"clear_sheet: {e}")

    # Step 2 — all values in one call
    if value_data:
        try:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": value_data},
            ).execute()
            executed_groups += 1
        except Exception as e:
            logger.warning("scaffold: values.batchUpdate failed: %s", e)
            errors.append(f"values_batch: {e}")

    # Step 3 — all formatting requests, chunked to stay under per-call limits
    chunk_size = 200
    for i in range(0, len(format_requests), chunk_size):
        chunk = format_requests[i:i + chunk_size]
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": chunk},
            ).execute()
            executed_groups += 1
        except Exception as e:
            logger.warning("scaffold: format batch [%d:%d] failed: %s", i, i + len(chunk), e)
            errors.append(f"format_batch[{i}:{i + len(chunk)}]: {e}")

    summary = {
        "sub_actions_total": len(sub_actions),
        "value_writes": len(value_data),
        "format_requests": len(format_requests),
        "api_calls": executed_groups,
        "errors": errors[:5],
    }
    if upload_summary is not None:
        summary["matrix_image_upload"] = upload_summary
    logger.info("scaffold_oppm_form: %s", summary)
    return summary


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


# ── Public dispatcher ──

_SHEET_NAME_FROM_PARAMS = "OPPM"

SUPPORTED_ACTIONS = frozenset({
    "insert_rows", "delete_rows", "copy_format", "set_border",
    "set_background", "clear_background", "set_text_wrap",
    "set_value", "clear_content", "fill_timeline", "clear_timeline", "set_owner",
    "set_bold", "set_text_color", "set_note",
    "merge_cells", "unmerge_cells",
    "set_formula", "set_number_format", "set_alignment",
    "set_font_size", "set_font_family", "set_text_rotation", "insert_image", "upload_asset_to_drive",
    "set_row_height", "set_column_width",
    "freeze_rows", "freeze_columns",
    "set_conditional_formatting", "set_data_validation",
    "set_hyperlink",
    "protect_range", "unprotect_range",
    "clear_sheet",
    "scaffold_oppm_form",
})


def execute_actions(
    service: Any,
    spreadsheet_id: str,
    actions: list[dict],
    *,
    sa_info: dict[str, Any] | None = None,
) -> list[dict]:
    """Execute a list of OPPM AI sheet actions synchronously.

    Returns a list of result dicts: {action, success, error}.
    Each action is executed independently; failures do not abort the sequence.

    sa_info is the service account credential dict — passed through to actions
    that need to build a Drive client on demand (e.g. upload_asset_to_drive,
    scaffold_oppm_form when matrix_image_asset is supplied).
    """
    sheet_title = _SHEET_NAME_FROM_PARAMS
    try:
        sheet_id = _find_sheet_id(service, spreadsheet_id, sheet_title)
    except Exception as e:
        logger.warning("execute_actions: cannot find sheet '%s': %s", sheet_title, e)
        return [
            {"action": a.get("action", "unknown"), "success": False, "error": str(e)}
            for a in actions
        ]

    results: list[dict] = []
    for action_obj in actions:
        action_name = str(action_obj.get("action", ""))
        # Support both nested params {action, params: {...}} and flat {action, range, value}
        if "params" in action_obj:
            params = dict(action_obj.get("params", {}))
        else:
            params = {k: v for k, v in action_obj.items() if k != "action"}

        if action_name not in SUPPORTED_ACTIONS:
            results.append({"action": action_name, "success": False, "error": f"Unsupported action: {action_name}"})
            continue

        # Inject sheet name from params if provided (AI may pass "sheet": "OPPM")
        if "sheet" in params:
            sheet_title = str(params.pop("sheet", sheet_title)) or sheet_title

        try:
            if action_name == "insert_rows":
                _exec_insert_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "delete_rows":
                _exec_delete_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "copy_format":
                _exec_copy_format(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_border":
                _exec_set_border(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_background":
                _exec_set_background(service, spreadsheet_id, params, sheet_id)
            elif action_name == "clear_background":
                _exec_clear_background(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_wrap":
                _exec_set_text_wrap(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_value":
                _exec_set_value(service, spreadsheet_id, params, sheet_title)
            elif action_name == "clear_content":
                _exec_clear_content(service, spreadsheet_id, params, sheet_title)
            elif action_name == "fill_timeline":
                _exec_fill_timeline(service, spreadsheet_id, params, sheet_id, sheet_title)
            elif action_name == "clear_timeline":
                _exec_clear_timeline(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_owner":
                _exec_set_owner(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_bold":
                _exec_set_bold(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_color":
                _exec_set_text_color(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_note":
                _exec_set_note(service, spreadsheet_id, params, sheet_id)
            elif action_name == "merge_cells":
                _exec_merge_cells(service, spreadsheet_id, params, sheet_id)
            elif action_name == "unmerge_cells":
                _exec_unmerge_cells(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_formula":
                _exec_set_formula(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_number_format":
                _exec_set_number_format(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_alignment":
                _exec_set_alignment(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_font_size":
                _exec_set_font_size(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_font_family":
                _exec_set_font_family(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_rotation":
                _exec_set_text_rotation(service, spreadsheet_id, params, sheet_id)
            elif action_name == "insert_image":
                _exec_insert_image(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_row_height":
                _exec_set_row_height(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_column_width":
                _exec_set_column_width(service, spreadsheet_id, params, sheet_id)
            elif action_name == "freeze_rows":
                _exec_freeze_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "freeze_columns":
                _exec_freeze_columns(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_conditional_formatting":
                _exec_set_conditional_formatting(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_data_validation":
                _exec_set_data_validation(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_hyperlink":
                _exec_set_hyperlink(service, spreadsheet_id, params, sheet_title)
            elif action_name == "protect_range":
                _exec_protect_range(service, spreadsheet_id, params, sheet_id)
            elif action_name == "unprotect_range":
                _exec_unprotect_range(service, spreadsheet_id, params, sheet_id)
            elif action_name == "clear_sheet":
                _exec_clear_sheet(service, spreadsheet_id, params, sheet_id)
            elif action_name == "scaffold_oppm_form":
                summary = _exec_scaffold_oppm_form(service, spreadsheet_id, params, sheet_id, sheet_title, sa_info=sa_info)
                results.append({"action": action_name, "success": True, "error": None, "summary": summary})
                continue
            elif action_name == "upload_asset_to_drive":
                upload = _exec_upload_asset_to_drive(service, spreadsheet_id, params, sheet_title, sa_info=sa_info)
                results.append({"action": action_name, "success": True, "error": None, "summary": upload})
                continue
            results.append({"action": action_name, "success": True, "error": None})
        except Exception as e:
            logger.warning("execute_actions: action '%s' failed: %s", action_name, e)
            results.append({"action": action_name, "success": False, "error": str(e)})

    return results
