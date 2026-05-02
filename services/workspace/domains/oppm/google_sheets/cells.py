"""Cell notation helpers and layout cell iterators."""

import re
from typing import Any


def _column_letter(column_number: int) -> str:
    if column_number <= 0:
        raise ValueError("Column number must be >= 1")
    letters = ""
    number = column_number
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _a1(column_number: int, row_number: int) -> str:
    return f"{_column_letter(column_number)}{row_number}"


def _normalize_cell_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = normalized.replace(":", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _find_first_cell(layout: dict[str, Any], predicate) -> tuple[int, int, str] | None:
    for row, col, text in _iter_layout_cells(layout):
        if predicate(_normalize_cell_text(text)):
            return row, col, text
    return None


def _iter_layout_cells(layout: dict[str, Any]) -> list[tuple[int, int, str]]:
    row_data = layout.get("row_data", [])
    cells: list[tuple[int, int, str]] = []
    for row_index, row in enumerate(row_data, start=1):
        values = row.get("values", [])
        for column_index, value in enumerate(values, start=1):
            text = value.get("formattedValue")
            if isinstance(text, str) and text.strip():
                cells.append((row_index, column_index, text.strip()))
    return cells


def _iter_normalized_layout_cells(layout: dict[str, Any]) -> list[tuple[int, int, str, str]]:
    cells: list[tuple[int, int, str, str]] = []
    for row, col, text in _iter_layout_cells(layout):
        cells.append((row, col, text, _normalize_cell_text(text)))
    return cells


def _merge_column_bounds(merges: list[dict[str, int]], row: int, col: int) -> tuple[int, int]:
    row_index = row - 1
    col_index = col - 1
    for merge in merges:
        start_row = merge.get("startRowIndex", 0)
        end_row = merge.get("endRowIndex", 0)
        start_col = merge.get("startColumnIndex", 0)
        end_col = merge.get("endColumnIndex", 0)
        if start_row <= row_index < end_row and start_col <= col_index < end_col:
            return start_col + 1, end_col
    return col, col


def _merge_range_bounds(merges: list[dict[str, int]], row: int, col: int) -> tuple[int, int, int, int]:
    row_index = row - 1
    col_index = col - 1
    for merge in merges:
        start_row = merge.get("startRowIndex", 0)
        end_row = merge.get("endRowIndex", 0)
        start_col = merge.get("startColumnIndex", 0)
        end_col = merge.get("endColumnIndex", 0)
        if start_row <= row_index < end_row and start_col <= col_index < end_col:
            return start_row + 1, end_row, start_col + 1, end_col
    return row, row, col, col


def _merge_end_column(merges: list[dict[str, int]], row: int, col: int) -> int:
    return _merge_column_bounds(merges, row, col)[1]


def _find_matching_label_cells(
    normalized_cells: list[tuple[int, int, str, str]],
    label_text: str,
    *,
    allow_prefix: bool = False,
) -> list[tuple[int, int, str]]:
    normalized_label = _normalize_cell_text(label_text)
    if not normalized_label:
        return []

    matches: list[tuple[int, int, str]] = []
    for row, col, text, normalized_text in normalized_cells:
        if normalized_text == normalized_label:
            matches.append((row, col, text))
            continue
        if allow_prefix and normalized_text.startswith(f"{normalized_label} "):
            matches.append((row, col, text))
    return matches


def _resolve_scalar_anchor_from_label_cell(layout: dict[str, Any], row: int, col: int) -> tuple[int, int] | None:
    end_col = _merge_end_column(layout.get("merges", []), row, col)
    value_col = end_col + 1
    max_col = int(layout.get("max_col") or 52)
    if value_col > max_col:
        return None
    return row, value_col
