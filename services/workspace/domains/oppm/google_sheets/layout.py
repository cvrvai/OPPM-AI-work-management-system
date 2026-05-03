"""Sheet layout reading and region resolution."""

import logging
from typing import Any

from .cells import (
    _a1,
    _column_letter,
    _find_first_cell,
    _find_matching_label_cells,
    _iter_layout_cells,
    _iter_normalized_layout_cells,
    _merge_column_bounds,
    _merge_end_column,
    _merge_range_bounds,
    _normalize_cell_text,
)
from .constants import (
    _CLASSIC_MAX_TASK_ROWS,
    _CLASSIC_SUB_OBJECTIVE_COLUMNS,
    _CLASSIC_VISIBLE_TASK_ROWS,
    _DEFAULT_LAYOUT_SCAN_RANGE,
    _OPPM_SHEET_TITLE,
    _SUMMARY_BLOCK_FIELDS,
)

logger = logging.getLogger(__name__)


def _read_sheet_layout(service: Any, spreadsheet_id: str, sheet_title: str) -> dict[str, Any]:
    response = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{sheet_title}'!{_DEFAULT_LAYOUT_SCAN_RANGE}"],
        includeGridData=True,
        fields=(
            "sheets.properties.title,"
            "sheets.properties.gridProperties.rowCount,"
            "sheets.properties.gridProperties.columnCount,"
            "sheets.merges,"
            "sheets.data.rowData.values.formattedValue"
        ),
    ).execute()
    sheets = response.get("sheets", [])
    if not sheets:
        return {"row_data": [], "merges": [], "max_row": 120, "max_col": 52}

    sheet = sheets[0]
    properties = sheet.get("properties", {})
    grid = properties.get("gridProperties", {})
    data = sheet.get("data", [])
    first_data = data[0] if data else {}
    return {
        "row_data": first_data.get("rowData", []),
        "merges": sheet.get("merges", []),
        "max_row": int(grid.get("rowCount") or 120),
        "max_col": int(grid.get("columnCount") or 52),
    }


def _find_merged_region(layout: dict[str, Any], predicate) -> dict[str, int] | None:
    cell = _find_first_cell(layout, predicate)
    if not cell:
        return None
    row, col, _ = cell
    start_col, end_col = _merge_column_bounds(layout.get("merges", []), row, col)
    return {
        "row": row,
        "start_col": start_col,
        "end_col": end_col,
    }


def _find_label_value_anchor(
    layout: dict[str, Any],
    label_text: str,
) -> tuple[int, int] | None:
    normalized_label = _normalize_cell_text(label_text)
    label_cell = _find_first_cell(layout, lambda text: text == normalized_label)
    if not label_cell:
        return None
    row, col, _ = label_cell
    end_col = _merge_end_column(layout.get("merges", []), row, col)
    value_col = end_col + 1
    max_col = layout.get("max_col", 52)
    if value_col > max_col:
        return None
    return row, value_col


def _select_preferred_inline_label_cell(
    layout: dict[str, Any],
    label_text: str,
    *,
    task_layout: dict[str, Any] | None = None,
) -> tuple[int, int, str] | None:
    normalized_cells = _iter_normalized_layout_cells(layout)
    matches = _find_matching_label_cells(normalized_cells, label_text, allow_prefix=True)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    preferred_max_row = None
    if task_layout:
        preferred_max_row = int(task_layout.get("task_anchor", {}).get("first_row") or 0) - 1

    def _rank(match: tuple[int, int, str]) -> tuple[int, int, int, int]:
        row, col, _ = match
        start_col, end_col = _merge_column_bounds(layout.get("merges", []), row, col)
        merged_penalty = 0 if end_col > start_col else 1
        if preferred_max_row and preferred_max_row > 0:
            above_penalty = 0 if row <= preferred_max_row else 1
            distance = abs(preferred_max_row - row)
        else:
            above_penalty = 0
            distance = row
        return (above_penalty, distance, merged_penalty, -row)

    return min(matches, key=_rank)


def _find_summary_block_cell(
    layout: dict[str, Any],
    *,
    task_layout: dict[str, Any] | None = None,
) -> tuple[int, int, str] | None:
    required_labels = tuple(_normalize_cell_text(label.replace("_", " ")) for label in _SUMMARY_BLOCK_FIELDS)
    matches: list[tuple[int, int, str]] = []
    for row, col, text, normalized_text in _iter_normalized_layout_cells(layout):
        if all(label in normalized_text for label in required_labels):
            matches.append((row, col, text))

    if not matches:
        return None

    preferred_max_row = None
    if task_layout:
        preferred_max_row = int(task_layout.get("task_anchor", {}).get("first_row") or 0) - 1

    def _rank(match: tuple[int, int, str]) -> tuple[int, int, int, int]:
        row, col, _ = match
        start_col, end_col = _merge_column_bounds(layout.get("merges", []), row, col)
        merged_penalty = 0 if end_col > start_col else 1
        if preferred_max_row and preferred_max_row > 0:
            above_penalty = 0 if row <= preferred_max_row else 1
            distance = abs(preferred_max_row - row)
        else:
            above_penalty = 0
            distance = row
        return (above_penalty, distance, merged_penalty, -row)

    return min(matches, key=_rank)


def _resolve_task_layout_regions(layout: dict[str, Any]) -> dict[str, Any] | None:
    task_region = _find_merged_region(layout, lambda text: "major tasks" in text)
    if not task_region:
        return None

    header_row = int(task_region["row"])
    first_task_row = header_row + 1
    people_count_cell = _find_first_cell(layout, lambda text: text.startswith("# people working on the project"))
    max_rows = _CLASSIC_VISIBLE_TASK_ROWS
    if people_count_cell and people_count_cell[0] > first_task_row:
        max_rows = people_count_cell[0] - first_task_row
    if max_rows <= 0:
        max_rows = _CLASSIC_VISIBLE_TASK_ROWS

    sub_objective_region = _find_merged_region(layout, lambda text: text == "sub objective")
    if sub_objective_region and int(sub_objective_region["row"]) != header_row:
        sub_objective_region = None
    if not sub_objective_region:
        inferred_end = int(task_region["start_col"]) - 1
        if inferred_end >= 1:
            inferred_start = max(1, inferred_end - (_CLASSIC_SUB_OBJECTIVE_COLUMNS - 1))
            sub_objective_region = {
                "row": header_row,
                "start_col": inferred_start,
                "end_col": inferred_end,
            }

    timeline_region = _find_merged_region(layout, lambda text: text.startswith("project completed by"))
    if timeline_region and int(timeline_region["row"]) != header_row:
        timeline_region = None

    owner_region = _find_merged_region(layout, lambda text: text == "owner / priority")
    if owner_region and int(owner_region["row"]) != header_row:
        owner_region = None

    regions: dict[str, dict[str, int]] = {
        "task_text": {
            "start_col": int(task_region["start_col"]),
            "end_col": int(task_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
        }
    }
    if sub_objective_region:
        regions["sub_objectives"] = {
            "start_col": int(sub_objective_region["start_col"]),
            "end_col": int(sub_objective_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
        }
    if timeline_region:
        # Only set a dedicated date header row when the #people cell gives us a
        # clear gap below the task block.  Otherwise leave it unset so the writer
        # does not overwrite the "Project Completed By" header row.
        if people_count_cell and people_count_cell[0] > first_task_row:
            timeline_date_header_row = people_count_cell[0] + 1
        else:
            timeline_date_header_row = 0
        regions["timeline"] = {
            "start_col": int(timeline_region["start_col"]),
            "end_col": int(timeline_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
            "date_header_row": timeline_date_header_row,
        }
    if owner_region:
        # Same logic as timeline: only set a dedicated member header row when
        # there is a clear gap below the task block.
        if people_count_cell and people_count_cell[0] > first_task_row:
            owner_member_header_row = people_count_cell[0] + 1
        else:
            owner_member_header_row = 0
        regions["owners"] = {
            "start_col": int(owner_region["start_col"]),
            "end_col": int(owner_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
            "member_header_row": owner_member_header_row,
        }

    task_rows = _resolve_grouped_task_rows(layout, task_region, first_task_row, max_rows)

    return {
        "task_anchor": {
            "column": _column_letter(int(task_rows[0]["write_col"]) if task_rows else int(task_region["start_col"])),
            "first_row": first_task_row,
            "max_rows": max_rows,
        },
        "regions": regions,
        "task_rows": task_rows,
        "people_count_anchor": _a1(people_count_cell[1], people_count_cell[0]) if people_count_cell else None,
    }


def _resolve_grouped_task_rows(
    layout: dict[str, Any],
    task_region: dict[str, int],
    first_task_row: int,
    max_rows: int,
) -> list[dict[str, int | str]]:
    if max_rows <= 0:
        return []

    start_col = int(task_region["start_col"])
    end_col = int(task_region["end_col"])
    index_col = start_col - 1
    if index_col <= 0:
        return []

    merge_by_row: dict[int, tuple[int, int]] = {}
    for merge in layout.get("merges", []):
        start_row = int(merge.get("startRowIndex", 0)) + 1
        end_row = int(merge.get("endRowIndex", 0))
        merge_start_col = int(merge.get("startColumnIndex", 0)) + 1
        merge_end_col = int(merge.get("endColumnIndex", 0))
        if end_row != start_row:
            continue
        merge_by_row[start_row] = (merge_start_col, merge_end_col)

    task_rows: list[dict[str, int | str]] = []
    for row in range(first_task_row, first_task_row + max_rows):
        merge = merge_by_row.get(row)
        if not merge:
            continue

        merge_start_col, merge_end_col = merge
        if merge_end_col != end_col:
            continue
        if merge_start_col == index_col:
            task_rows.append({"row": row, "kind": "main", "write_col": index_col})
        elif merge_start_col == start_col:
            task_rows.append({
                "row": row,
                "kind": "sub",
                "index_col": index_col,
                "title_col": start_col,
                "write_col": start_col,
            })

    has_main = any(str(slot.get("kind")) == "main" for slot in task_rows)
    has_sub = any(str(slot.get("kind")) == "sub" for slot in task_rows)
    return task_rows if has_main and has_sub else []


def _get_sheet_id_by_title(service: Any, spreadsheet_id: str, sheet_title: str) -> int | None:
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties",
    ).execute()
    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_title:
            return props.get("sheetId")
    return None


def _resolve_table_header_profile(layout: dict[str, Any], headers: list[str]) -> dict[str, Any] | None:
    normalized_headers = {_normalize_cell_text(header): header for header in headers}
    rows: dict[int, dict[str, int]] = {}

    for row, col, text, normalized_text in _iter_normalized_layout_cells(layout):
        if normalized_text not in normalized_headers:
            continue
        rows.setdefault(row, {})[normalized_text] = col

    for row, columns in sorted(rows.items()):
        if not all(header in columns for header in normalized_headers):
            continue
        start_col = min(columns.values())
        end_col = max(columns.values())
        return {
            "header_row": row,
            "start_col": start_col,
            "end_col": end_col,
            "columns": columns,
        }

    return None


def _write_table_rows(
    service: Any,
    spreadsheet_id: str,
    sheet_title: str,
    header_profile: dict[str, Any],
    headers: list[str],
    rows: list[list[str]],
) -> None:
    start_row = int(header_profile["header_row"]) + 1
    start_col = int(header_profile["start_col"])
    end_col = int(header_profile["end_col"])
    width = end_col - start_col + 1
    normalized_headers = [_normalize_cell_text(header) for header in headers]

    rendered_rows: list[list[str]] = []
    for row_values in rows[1:]:
        rendered = [""] * width
        for header_key, value in zip(normalized_headers, row_values):
            column = header_profile["columns"].get(header_key)
            if column is None:
                continue
            rendered[column - start_col] = value
        rendered_rows.append(rendered)

    if rendered_rows:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=(
                f"'{sheet_title}'!{_a1(start_col, start_row)}:"
                f"{_a1(end_col, start_row + len(rendered_rows) - 1)}"
            ),
            valueInputOption="RAW",
            body={"values": rendered_rows},
        ).execute()

    try:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_title}'!{_a1(start_col, start_row + len(rendered_rows))}:{_a1(end_col, 1000)}",
            body={},
        ).execute()
    except Exception:
        logger.debug("Trailing clear failed for %s helper rows", sheet_title)
