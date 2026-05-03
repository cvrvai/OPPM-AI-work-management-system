"""Sheet action executor — translates OPPM AI JSON actions to Google Sheets API v4 calls.

Supported actions (matching the OPPM AI system prompt contract):
  insert_rows, delete_rows, copy_format, set_border, set_background,
  clear_background, set_text_wrap, set_value, clear_content,
  fill_timeline, clear_timeline, set_owner,
  set_bold, set_text_color, set_note,
  merge_cells, unmerge_cells,
  set_formula, set_number_format, set_alignment,
  set_font_size, set_font_family,
  set_row_height, set_column_width,
  freeze_rows, freeze_columns,
  set_conditional_formatting, set_data_validation,
  set_hyperlink,
  protect_range, unprotect_range

Border styles supported: NONE, DOTTED, DASHED, SOLID, SOLID_MEDIUM, SOLID_THICK, DOUBLE.
Per-side overrides (top_*, bottom_*, left_*, right_*, inner_horizontal_*, inner_vertical_*)
allow fine-grained border control. style=NONE removes borders entirely.
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

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
    "set_font_size", "set_font_family",
    "set_row_height", "set_column_width",
    "freeze_rows", "freeze_columns",
    "set_conditional_formatting", "set_data_validation",
    "set_hyperlink",
    "protect_range", "unprotect_range",
    "clear_sheet",
})


def execute_actions(
    service: Any,
    spreadsheet_id: str,
    actions: list[dict],
) -> list[dict]:
    """Execute a list of OPPM AI sheet actions synchronously.

    Returns a list of result dicts: {action, success, error}.
    Each action is executed independently; failures do not abort the sequence.
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
            results.append({"action": action_name, "success": True, "error": None})
        except Exception as e:
            logger.warning("execute_actions: action '%s' failed: %s", action_name, e)
            results.append({"action": action_name, "success": False, "error": str(e)})

    return results
