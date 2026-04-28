"""Google Sheets MVP service for linking a project sheet and pushing AI-filled OPPM data."""

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet, InvalidToken

from config import get_settings
from repositories.notification_repo import AuditRepository
from repositories.project_repo import ProjectRepository
from repositories.workspace_repo import WorkspaceRepository

logger = logging.getLogger(__name__)

_GOOGLE_SHEET_KEY = "google_sheet"
_GOOGLE_CREDENTIALS_KEY = "google_sheets_credentials"
_OPPM_SHEET_TITLE = "OPPM"
_SUMMARY_SHEET_TITLE = "OPPM Summary"
_TASKS_SHEET_TITLE = "OPPM Tasks"
_MEMBERS_SHEET_TITLE = "OPPM Members"
_SPREADSHEET_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_SPREADSHEET_ID_RE = re.compile(r"^[a-zA-Z0-9-_]{20,}$")
_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
_XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_CLASSIC_MAX_TASK_ROWS = 64
_CLASSIC_VISIBLE_TASK_ROWS = 16
_DEFAULT_LAYOUT_SCAN_RANGE = "A1:AZ120"
_CLASSIC_SUB_OBJECTIVE_COLUMNS = 6
_SUMMARY_BLOCK_FIELDS = ("project_objective", "deliverable_output", "start_date", "deadline")
_INLINE_LABEL_FIELDS = {"project_leader", "project_name", "completed_by"}
_VALUE_LABEL_FIELDS = {"project_objective", "deliverable_output", "start_date", "deadline"}
_EXPLICIT_MAPPING_SCALAR_FIELDS = (*sorted(_INLINE_LABEL_FIELDS), *_VALUE_LABEL_FIELDS)
_EXPLICIT_MAPPING_FIELD_IDS = set(_EXPLICIT_MAPPING_SCALAR_FIELDS) | {"task_anchor"}
_SUMMARY_HELPER_LABELS = (
    ("Project Name", "project_name"),
    ("Project Leader", "project_leader"),
    ("Leader Member ID", "project_leader_member_id"),
    ("People Count", "people_count"),
    ("Start Date", "start_date"),
    ("Deadline", "deadline"),
    ("Project Objective", "project_objective"),
    ("Deliverable Output", "deliverable_output"),
    ("Completed By", "completed_by_text"),
)
_SUMMARY_HELPER_REQUIRED_FIELDS = (
    "project_name",
    "project_leader",
    "project_objective",
    "deliverable_output",
    "completed_by_text",
)
_TASKS_TABLE_HEADERS = ["Index", "Title", "Deadline", "Status", "Row Type", "Owners", "Timeline"]
_MEMBERS_TABLE_HEADERS = ["Slot", "Member ID", "Name"]
_TASK_SUB_OBJECTIVE_MARK = "\u2713"
_TIMELINE_SYMBOLS = {
    "planned": "\u25a1",
    "in_progress": "\u25cf",
    "completed": "\u25a0",
    "at_risk": "\u25b2",
    "blocked": "\u2715",
}


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


def _find_first_cell(layout: dict[str, Any], predicate) -> tuple[int, int, str] | None:
    for row, col, text in _iter_layout_cells(layout):
        if predicate(_normalize_cell_text(text)):
            return row, col, text
    return None


def _merge_column_bounds(merges: list[dict[str, int]], row: int, col: int) -> tuple[int, int]:
    row_index = row - 1
    col_index = col - 1
    for merge in merges:
        start_row = merge.get("startRowIndex", 0)
        end_row = merge.get("endRowIndex", 0)
        start_col = merge.get("startColumnIndex", 0)
        end_col = merge.get("endColumnIndex", 0)
        if start_row <= row_index < end_row and start_col <= col_index < end_col:
            # Convert Google zero-based inclusive/exclusive bounds to 1-based inclusive.
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


def _iter_normalized_layout_cells(layout: dict[str, Any]) -> list[tuple[int, int, str, str]]:
    cells: list[tuple[int, int, str, str]] = []
    for row, col, text in _iter_layout_cells(layout):
        cells.append((row, col, text, _normalize_cell_text(text)))
    return cells


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


def _mapping_target_to_dict(target: Any) -> dict[str, Any]:
    if hasattr(target, "model_dump"):
        raw = target.model_dump(exclude_none=True)
    elif isinstance(target, dict):
        raw = dict(target)
    else:
        raw = {
            "row": getattr(target, "row", None),
            "column": getattr(target, "column", None),
            "label": getattr(target, "label", None),
        }
    return {key: value for key, value in raw.items() if value is not None}


def _resolve_scalar_anchor_from_label_cell(layout: dict[str, Any], row: int, col: int) -> tuple[int, int] | None:
    end_col = _merge_end_column(layout.get("merges", []), row, col)
    value_col = end_col + 1
    max_col = int(layout.get("max_col") or 52)
    if value_col > max_col:
        return None
    return row, value_col


def _resolve_task_anchor_from_coordinates(layout: dict[str, Any], row: int, col: int) -> dict[str, Any] | None:
    max_row = int(layout.get("max_row") or 120)
    max_col = int(layout.get("max_col") or 52)
    if row < 1 or col < 1 or row > max_row or col > max_col:
        return None

    max_rows = max(0, min(_CLASSIC_MAX_TASK_ROWS, max_row - row + 1))
    return {
        "column": _column_letter(col),
        "first_row": row,
        "max_rows": max_rows,
    }


def _resolve_task_anchor_from_label_cell(layout: dict[str, Any], row: int, col: int) -> dict[str, Any] | None:
    return _resolve_task_anchor_from_coordinates(layout, row + 1, col)


def _format_mapping_issues(issues: list[dict[str, str]]) -> str:
    ordered: list[str] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        field_id = issue.get("field", "unknown")
        reason = issue.get("reason", "invalid mapping")
        key = (field_id, reason)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(f"{field_id} ({reason})")
    return f"Explicit Google Sheet mapping failed: {', '.join(ordered)}"


def _resolve_explicit_oppm_mapping(
    service: Any,
    spreadsheet_id: str,
    explicit_mapping: dict[str, Any],
) -> dict[str, Any]:
    if not explicit_mapping:
        raise HTTPException(status_code=400, detail="Explicit Google Sheet mapping must include at least one field")

    layout = _read_sheet_layout(service, spreadsheet_id, _OPPM_SHEET_TITLE)
    normalized_cells = _iter_normalized_layout_cells(layout)
    max_row = int(layout.get("max_row") or 120)
    max_col = int(layout.get("max_col") or 52)

    resolved_anchors: dict[str, str] = {}
    resolved_fields: dict[str, Any] = {}
    task_anchor: dict[str, Any] | None = None
    destination_usage: dict[str, list[str]] = {}
    issues: list[dict[str, str]] = []

    for field_id, target in explicit_mapping.items():
        if field_id not in _EXPLICIT_MAPPING_FIELD_IDS:
            issues.append({"field": field_id, "reason": "unsupported field id"})
            continue

        mapping_target = _mapping_target_to_dict(target)
        label = mapping_target.get("label")
        locator_source = "label" if label else "coordinates"

        if label:
            matches = _find_matching_label_cells(
                normalized_cells,
                str(label),
                allow_prefix=field_id in _INLINE_LABEL_FIELDS,
            )
            if not matches:
                issues.append({"field": field_id, "reason": f'label "{label}" was not found'})
                continue
            if len(matches) > 1:
                issues.append({"field": field_id, "reason": f'label "{label}" matched {len(matches)} cells'})
                continue

            match_row, match_col, _ = matches[0]
            if field_id in _INLINE_LABEL_FIELDS:
                target_row = match_row
                target_col = match_col
            elif field_id in _VALUE_LABEL_FIELDS:
                scalar_anchor = _resolve_scalar_anchor_from_label_cell(layout, match_row, match_col)
                if not scalar_anchor:
                    issues.append({"field": field_id, "reason": f'label "{label}" did not resolve to a writable value cell'})
                    continue
                target_row, target_col = scalar_anchor
            else:
                resolved_task_anchor = _resolve_task_anchor_from_label_cell(layout, match_row, match_col)
                if not resolved_task_anchor or int(resolved_task_anchor.get("max_rows") or 0) <= 0:
                    issues.append({"field": field_id, "reason": f'label "{label}" did not resolve to writable task rows'})
                    continue
                task_anchor = resolved_task_anchor
                destination_key = f"{task_anchor['column']}{task_anchor['first_row']}"
                destination_usage.setdefault(destination_key, []).append(field_id)
                resolved_fields[field_id] = {
                    "source": locator_source,
                    "target": destination_key,
                    "task_anchor": task_anchor,
                }
                continue
        else:
            target_row = int(mapping_target.get("row") or 0)
            target_col = int(mapping_target.get("column") or 0)
            if target_row < 1 or target_col < 1 or target_row > max_row or target_col > max_col:
                issues.append({
                    "field": field_id,
                    "reason": f"row {target_row}, column {target_col} is outside the OPPM sheet bounds ({max_row}x{max_col})",
                })
                continue
            if field_id == "task_anchor":
                resolved_task_anchor = _resolve_task_anchor_from_coordinates(layout, target_row, target_col)
                if not resolved_task_anchor or int(resolved_task_anchor.get("max_rows") or 0) <= 0:
                    issues.append({"field": field_id, "reason": "task_anchor does not resolve to writable task rows"})
                    continue
                task_anchor = resolved_task_anchor
                destination_key = f"{task_anchor['column']}{task_anchor['first_row']}"
                destination_usage.setdefault(destination_key, []).append(field_id)
                resolved_fields[field_id] = {
                    "source": locator_source,
                    "target": destination_key,
                    "task_anchor": task_anchor,
                }
                continue

        destination_a1 = _a1(target_col, target_row)
        destination_usage.setdefault(destination_a1, []).append(field_id)
        resolved_anchors[field_id] = destination_a1
        resolved_fields[field_id] = {
            "source": locator_source,
            "target": destination_a1,
        }

    for destination, field_ids in destination_usage.items():
        if len(field_ids) <= 1:
            continue
        for field_id in field_ids:
            issues.append({"field": field_id, "reason": f"duplicate destination {destination}"})

    if issues:
        raise HTTPException(status_code=400, detail=_format_mapping_issues(issues))

    return {
        "source": "explicit_mapping",
        "anchors": resolved_anchors,
        "task_anchor": task_anchor,
        "resolved_fields": resolved_fields,
    }


def _classic_oppm_mapping_profile() -> dict[str, Any]:
    return {
        "source": "classic_fallback",
        "confidence": 1.0,
        "fallback_used": True,
        "anchors": {
            "project_leader": "A1",
            "project_name": "U1",
            "project_objective": "G3",
            "deliverable_output": "G4",
            "start_date": "G5",
            "deadline": "G6",
            "completed_by": "U7",
        },
        "task_anchor": {
            "column": "G",
            "first_row": 8,
            "max_rows": _CLASSIC_VISIBLE_TASK_ROWS,
        },
        "regions": {
            "sub_objectives": {
                "start_col": 1,
                "end_col": 6,
                "first_row": 8,
                "max_rows": _CLASSIC_VISIBLE_TASK_ROWS,
            },
            "task_text": {
                "start_col": 7,
                "end_col": 20,
                "first_row": 8,
                "max_rows": _CLASSIC_VISIBLE_TASK_ROWS,
            },
        },
        "clear_anchors": [],
        "missing_anchors": [],
    }


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
        # Use the row immediately after the people-count cell as the date header row
        # because the row above first_task_row is typically a merged cell (e.g. "Project
        # Completed By: X weeks") that cannot hold individual per-column date values.
        timeline_date_header_row = (
            people_count_cell[0] + 1
            if people_count_cell and people_count_cell[0] > first_task_row
            else first_task_row - 1
        )
        regions["timeline"] = {
            "start_col": int(timeline_region["start_col"]),
            "end_col": int(timeline_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
            "date_header_row": timeline_date_header_row,
        }
    if owner_region:
        regions["owners"] = {
            "start_col": int(owner_region["start_col"]),
            "end_col": int(owner_region["end_col"]),
            "first_row": first_task_row,
            "max_rows": max_rows,
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


def _resolve_oppm_mapping_profile(service: Any, spreadsheet_id: str) -> dict[str, Any]:
    layout = _read_sheet_layout(service, spreadsheet_id, _OPPM_SHEET_TITLE)
    task_layout = _resolve_task_layout_regions(layout)

    label_anchors = {
        "project_objective": _find_label_value_anchor(layout, "Project Objective"),
        "deliverable_output": _find_label_value_anchor(layout, "Deliverable Output"),
        "start_date": _find_label_value_anchor(layout, "Start Date"),
        "deadline": _find_label_value_anchor(layout, "Deadline"),
    }
    summary_block_cell = None
    if any(anchor is None for anchor in label_anchors.values()):
        summary_block_cell = _find_summary_block_cell(layout, task_layout=task_layout)
    summary_block_anchor = _a1(summary_block_cell[1], summary_block_cell[0]) if summary_block_cell else None
    summary_block_range = None
    if summary_block_cell:
        start_row, end_row, start_col, end_col = _merge_range_bounds(layout.get("merges", []), summary_block_cell[0], summary_block_cell[1])
        summary_block_range = _a1(start_col, start_row)
        if (start_row, end_row, start_col, end_col) != (summary_block_cell[0], summary_block_cell[0], summary_block_cell[1], summary_block_cell[1]):
            summary_block_range = f"{summary_block_range}:{_a1(end_col, end_row)}"
    covered_value_fields = set(_SUMMARY_BLOCK_FIELDS) if summary_block_anchor else set()

    leader_cell = _select_preferred_inline_label_cell(layout, "Project Leader", task_layout=task_layout)
    project_name_cell = _select_preferred_inline_label_cell(layout, "Project Name", task_layout=task_layout)
    completed_by_cell = _select_preferred_inline_label_cell(layout, "Project Completed By", task_layout=task_layout)

    summary_anchors: dict[str, str | None] = {
        "project_leader": _a1(leader_cell[1], leader_cell[0]) if leader_cell else None,
        "project_name": _a1(project_name_cell[1], project_name_cell[0]) if project_name_cell else None,
        "project_objective": _a1(label_anchors["project_objective"][1], label_anchors["project_objective"][0]) if label_anchors["project_objective"] else None,
        "deliverable_output": _a1(label_anchors["deliverable_output"][1], label_anchors["deliverable_output"][0]) if label_anchors["deliverable_output"] else None,
        "start_date": _a1(label_anchors["start_date"][1], label_anchors["start_date"][0]) if label_anchors["start_date"] else None,
        "deadline": _a1(label_anchors["deadline"][1], label_anchors["deadline"][0]) if label_anchors["deadline"] else None,
        "completed_by": _a1(completed_by_cell[1], completed_by_cell[0]) if completed_by_cell else None,
    }
    anchors = {field_id: value for field_id, value in summary_anchors.items() if value}
    if task_layout and task_layout.get("people_count_anchor"):
        anchors["people_count"] = task_layout["people_count_anchor"]

    missing_anchors = [
        name
        for name, value in summary_anchors.items()
        if not value and name not in covered_value_fields
    ]
    signal_count = len(summary_anchors) + 1
    resolved_summary_fields = sum(
        1
        for field_id, value in summary_anchors.items()
        if value or field_id in covered_value_fields
    )
    found_signals = resolved_summary_fields + (1 if task_layout else 0)
    confidence = round(found_signals / signal_count, 3)

    has_all_required_labels = all(label_anchors[field_id] or field_id in covered_value_fields for field_id in _VALUE_LABEL_FIELDS)
    has_task_anchor = task_layout is not None

    classic_anchors = dict(_classic_oppm_mapping_profile()["anchors"])

    def _clear_anchors_for_mapping(resolved_anchors: dict[str, str | None]) -> list[str]:
        stale: list[str] = []
        for field_id, a1_ref in classic_anchors.items():
            anchor = resolved_anchors.get(field_id)
            if anchor and anchor != a1_ref:
                stale.append(a1_ref)
                continue
            if field_id in covered_value_fields:
                stale.append(a1_ref)
        return list(dict.fromkeys(stale))

    if not has_all_required_labels or not has_task_anchor:
        if confidence >= 0.5:
            fallback = _classic_oppm_mapping_profile()
            fallback["confidence"] = confidence
            fallback["missing_anchors"] = missing_anchors
            fallback["anchors"].update({
                field_id: value
                for field_id, value in anchors.items()
                if value
            })
            for field_id, value in summary_anchors.items():
                if value is None:
                    fallback["anchors"].pop(field_id, None)
            fallback["summary_block_anchor"] = summary_block_anchor
            fallback["summary_block_range"] = summary_block_range
            if task_layout:
                fallback["task_anchor"] = task_layout["task_anchor"]
                fallback["regions"] = task_layout["regions"]
                fallback["task_rows"] = task_layout.get("task_rows", [])
                if task_layout.get("people_count_anchor"):
                    fallback["anchors"]["people_count"] = task_layout["people_count_anchor"]
                else:
                    fallback["anchors"].pop("people_count", None)
            fallback["clear_anchors"] = _clear_anchors_for_mapping(fallback["anchors"])
            return fallback

        unresolved_missing = list(missing_anchors)
        if not has_task_anchor:
            unresolved_missing.append("task_header")
        return {
            "source": "unresolved",
            "confidence": confidence,
            "fallback_used": False,
            "anchors": anchors,
            "task_anchor": {
                "column": None,
                "first_row": 0,
                "max_rows": 0,
            },
            "regions": {},
            "task_rows": [],
            "summary_block_anchor": summary_block_anchor,
            "summary_block_range": summary_block_range,
            "clear_anchors": [],
            "missing_anchors": unresolved_missing,
        }

    return {
        "source": "layout_detected",
        "confidence": confidence,
        "fallback_used": False,
        "anchors": anchors,
        "task_anchor": task_layout["task_anchor"],
        "regions": task_layout["regions"],
        "task_rows": task_layout.get("task_rows", []),
        "summary_block_anchor": summary_block_anchor,
        "summary_block_range": summary_block_range,
        "clear_anchors": _clear_anchors_for_mapping(anchors),
        "missing_anchors": missing_anchors,
    }


def _format_unresolved_push_detail(mapping: dict[str, Any]) -> str:
    missing = mapping.get("missing_anchors") or []
    detail = (
        "Linked workbook layout was not recognized for Push AI Fill. "
        "No OPPM cells were updated. Add the expected helper-sheet labels on the OPPM Summary tab "
        "or use a supported OPPM template."
    )
    if missing:
        detail = f"{detail} Missing anchors: {', '.join(missing)}."
    return detail


def _parse_spreadsheet_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Spreadsheet URL or ID is required")

    url_match = _SPREADSHEET_URL_RE.search(raw)
    if url_match:
        return url_match.group(1)

    if _SPREADSHEET_ID_RE.match(raw):
        return raw

    raise HTTPException(status_code=400, detail="Invalid Google Sheets URL or spreadsheet ID")


def _canonical_spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def _build_workspace_cipher() -> Fernet:
    settings = get_settings()
    key_bytes = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def _encrypt_workspace_credential(plain_text: str) -> str:
    return _build_workspace_cipher().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def _decrypt_workspace_credential(cipher_text: str) -> str:
    try:
        decrypted = _build_workspace_cipher().decrypt(cipher_text.encode("utf-8"))
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Invalid encrypted Google service account credential")
    return decrypted.decode("utf-8")


async def _resolve_workspace_service_account_info(
    session: AsyncSession,
    workspace_id: str,
    strict: bool = True,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    workspace_repo = WorkspaceRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if workspace:
        settings_blob = dict(workspace.settings or {})
        credentials = settings_blob.get(_GOOGLE_CREDENTIALS_KEY)
        if isinstance(credentials, dict):
            encrypted_json = credentials.get("encrypted_json")
            if isinstance(encrypted_json, str) and encrypted_json.strip():
                try:
                    decrypted_json = _decrypt_workspace_credential(encrypted_json)
                    return json.loads(decrypted_json), None, "database"
                except HTTPException as error:
                    if strict:
                        raise error
                    return None, error.detail, "database"
                except json.JSONDecodeError:
                    detail = "Invalid Google service account data stored for workspace"
                    if strict:
                        raise HTTPException(status_code=500, detail=detail)
                    return None, detail, "database"

    env_info, env_error = _resolve_service_account_info(strict=strict)
    return env_info, env_error, _credential_source()


def _resolve_service_account_info(strict: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    settings = get_settings()
    if settings.google_service_account_json.strip():
        try:
            return json.loads(settings.google_service_account_json), None
        except json.JSONDecodeError as error:
            logger.warning("Invalid GOOGLE_SERVICE_ACCOUNT_JSON: %s", error)
            detail = "Invalid Google service account JSON configuration"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail

    if settings.google_service_account_file.strip():
        file_path = Path(settings.google_service_account_file)
        if not file_path.exists():
            detail = "Google service account file does not exist"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail
        try:
            return json.loads(file_path.read_text(encoding="utf-8")), None
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Failed to read Google service account file: %s", error)
            detail = "Invalid Google service account file configuration"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail

    return None, None


def _load_service_account_info(strict: bool = True) -> dict[str, Any] | None:
    info, _ = _resolve_service_account_info(strict=strict)
    return info


def _service_account_email_from_info(info: dict[str, Any] | None) -> str | None:
    if not info:
        return None
    return info.get("client_email")


async def _service_account_email(session: AsyncSession, workspace_id: str) -> str | None:
    info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return _service_account_email_from_info(info)


async def _backend_configuration_error(session: AsyncSession, workspace_id: str) -> str | None:
    _, error, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return error


async def _is_backend_configured(session: AsyncSession, workspace_id: str) -> bool:
    info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return info is not None


def _credential_source() -> str | None:
    settings = get_settings()
    if settings.google_service_account_json.strip():
        return "env_json"
    if settings.google_service_account_file.strip():
        return "file"
    return None


def _build_google_credentials(info: dict[str, Any] | None):
    if not info:
        raise HTTPException(status_code=503, detail="Google Sheets integration is not configured on the backend")

    try:
        from google.oauth2 import service_account
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    return service_account.Credentials.from_service_account_info(info, scopes=_GOOGLE_SCOPES)


def _build_authorized_http(credentials):
    """Return an AuthorizedHttp transport with SSL verification disabled.

    Inside Docker containers the system CA bundle is often incomplete,
    causing [SSL: CERTIFICATE_VERIFY_FAILED] errors against Google APIs.
    Disabling certificate validation at the transport level is the
    standard workaround for containerised service-account workloads that
    communicate exclusively with Google's own endpoints.
    """
    try:
        import httplib2
        import google_auth_httplib2
        http = httplib2.Http(disable_ssl_certificate_validation=True)
        return google_auth_httplib2.AuthorizedHttp(credentials, http=http)
    except ImportError:
        return None  # fall back to default transport


def _build_sheets_service(info: dict[str, Any] | None):
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    credentials = _build_google_credentials(info)
    authorized_http = _build_authorized_http(credentials)
    if authorized_http is not None:
        return build("sheets", "v4", http=authorized_http, cache_discovery=False)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _build_drive_service(info: dict[str, Any] | None):
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Drive dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Drive dependencies are not installed on the backend")

    credentials = _build_google_credentials(info)
    authorized_http = _build_authorized_http(credentials)
    if authorized_http is not None:
        return build("drive", "v3", http=authorized_http, cache_discovery=False)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _extract_link(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    link = metadata.get(_GOOGLE_SHEET_KEY)
    return link if isinstance(link, dict) else None


async def _get_project_or_404(session: AsyncSession, project_id: str, workspace_id: str):
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def upsert_google_sheets_workspace_credentials(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    service_account_json: str,
) -> dict[str, Any]:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        info = json.loads(service_account_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid service account JSON")

    client_email = info.get("client_email")
    private_key = info.get("private_key")
    if not client_email or not private_key:
        raise HTTPException(status_code=400, detail="Service account JSON must include client_email and private_key")

    encrypted_json = _encrypt_workspace_credential(service_account_json)
    settings_blob = dict(workspace.settings or {})
    settings_blob[_GOOGLE_CREDENTIALS_KEY] = {
        "encrypted_json": encrypted_json,
        "client_email": client_email,
    }

    await workspace_repo.update(workspace_id, {"settings": settings_blob})
    await audit_repo.log(
        workspace_id,
        user_id,
        "update",
        "workspace_google_sheets_credentials",
        workspace_id,
        new_data={"client_email": client_email, "credential_source": "database"},
    )

    return await get_google_sheets_setup_status(session, workspace_id)


async def delete_google_sheets_workspace_credentials(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
) -> dict[str, Any]:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    settings_blob = dict(workspace.settings or {})
    previous = settings_blob.pop(_GOOGLE_CREDENTIALS_KEY, None)
    await workspace_repo.update(workspace_id, {"settings": settings_blob})
    await audit_repo.log(
        workspace_id,
        user_id,
        "delete",
        "workspace_google_sheets_credentials",
        workspace_id,
        old_data={"had_credentials": bool(previous)},
        new_data={"had_credentials": False},
    )

    return await get_google_sheets_setup_status(session, workspace_id)


async def get_google_sheets_setup_status(session: AsyncSession, workspace_id: str) -> dict[str, Any]:
    """Return backend Google Sheets configuration status for setup UX."""
    info, error, source = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return {
        "backend_configured": info is not None,
        "service_account_email": _service_account_email_from_info(info),
        "backend_configuration_error": error,
        "credential_source": source,
    }


def _summary_rows(fills: dict[str, str | None]) -> list[list[str]]:
    ordered = [
        ("Project Name", fills.get("project_name")),
        ("Project Leader", fills.get("project_leader")),
        ("Leader Member ID", fills.get("project_leader_member_id")),
        ("Start Date", fills.get("start_date")),
        ("Deadline", fills.get("deadline")),
        ("Project Objective", fills.get("project_objective")),
        ("Deliverable Output", fills.get("deliverable_output")),
        ("Completed By", fills.get("completed_by_text")),
        ("People Count", fills.get("people_count")),
    ]
    rows = [["Field", "Value"]]
    rows.extend([[label, value or ""] for label, value in ordered])
    return rows


def _resolve_helper_sheet_profile(service: Any, spreadsheet_id: str) -> dict[str, Any] | None:
    layout = _read_sheet_layout(service, spreadsheet_id, _SUMMARY_SHEET_TITLE)
    anchors: dict[str, str] = {}

    for label, field_key in _SUMMARY_HELPER_LABELS:
        anchor = _find_label_value_anchor(layout, label)
        if not anchor:
            continue
        anchors[field_key] = _a1(anchor[1], anchor[0])

    if not all(field_key in anchors for field_key in _SUMMARY_HELPER_REQUIRED_FIELDS):
        return None

    resolved_fields = {
        field_key: {
            "source": "helper_sheet",
            "target": f"{_SUMMARY_SHEET_TITLE}!{a1_ref}",
        }
        for field_key, a1_ref in anchors.items()
    }
    resolved_fields["task_anchor"] = {
        "source": "helper_sheet",
        "target": f"{_TASKS_SHEET_TITLE}!A2",
    }

    return {
        "source": "helper_sheet_profile",
        "summary_anchors": anchors,
        "resolved_fields": resolved_fields,
    }


def _summary_helper_value(field_key: str, fills: dict[str, str | None]) -> str:
    value = fills.get(field_key)
    return value or ""


def _write_summary_helper_sheet_values(
    service: Any,
    spreadsheet_id: str,
    fills: dict[str, str | None],
    profile: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    anchors = profile.get("summary_anchors", {})
    data = [
        {
            "range": f"'{_SUMMARY_SHEET_TITLE}'!{a1_ref}",
            "values": [[_summary_helper_value(field_key, fills)]],
        }
        for field_key, a1_ref in anchors.items()
    ]

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": data,
            },
        ).execute()

    diagnostics = {
        "mapping": {
            "source": profile.get("source"),
            "resolved_fields": profile.get("resolved_fields", {}),
        },
        "writes": {
            "attempted": len(data),
            "applied": len(data),
            "skipped": 0,
        },
    }

    logger.info(
        "Google Sheets helper profile resolved: fields=%s",
        sorted(anchors),
    )

    return len(data), diagnostics


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


def _write_sheet_with_existing_headers(
    service: Any,
    spreadsheet_id: str,
    sheet_title: str,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    layout = _read_sheet_layout(service, spreadsheet_id, sheet_title)
    header_profile = _resolve_table_header_profile(layout, headers)
    if header_profile:
        _write_table_rows(service, spreadsheet_id, sheet_title, header_profile, headers, rows)
        return
    _write_values(service, spreadsheet_id, sheet_title, rows)


def _members_rows(members: list[Any]) -> list[list[str]]:
    rows = [["Slot", "Member ID", "Name"]]
    for member in sorted(members, key=lambda item: item.slot):
        rows.append([str(member.slot), member.id, member.name])
    return rows


def _tasks_rows(tasks: list[Any], members: list[Any]) -> list[list[str]]:
    member_names = {member.id: member.name for member in members}
    rows = [["Index", "Title", "Deadline", "Status", "Row Type", "Owners", "Timeline"]]
    for task in tasks:
        owners = ", ".join(
            f"{owner.priority}:{member_names.get(owner.member_id, owner.member_id)}"
            for owner in task.owners
        )
        timeline = "; ".join(
            ", ".join(filter(None, [item.week_start, item.status, item.quality]))
            for item in task.timeline
        )
        rows.append([
            task.index,
            task.title,
            task.deadline or "",
            task.status or "",
            "Sub Task" if task.is_sub else "Main Task",
            owners,
            timeline,
        ])
    return rows


def _ensure_sheet_tabs(service: Any, spreadsheet_id: str, titles: list[str]) -> None:
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties.title",
    ).execute()
    existing = {
        sheet.get("properties", {}).get("title")
        for sheet in spreadsheet.get("sheets", [])
    }
    missing = [title for title in titles if title not in existing]
    if not missing:
        return

    requests = [
        {"addSheet": {"properties": {"title": title}}}
        for title in missing
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def _write_values(service: Any, spreadsheet_id: str, sheet_title: str, rows: list[list[str]]) -> None:
    # Update the sheet values starting at A1 without clearing the whole sheet
    # to preserve formatting, merges and layout created in the template.
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Clear any stale rows below the written range to avoid leftover data.
    # Clearing values (not formatting) in a modest trailing range keeps the sheet tidy
    # while avoiding a full-sheet clear that can disrupt complex templates.
    if rows:
        last_row = len(rows)
        # clear rows below the last written row up to a reasonable limit
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!A{last_row + 1}:Z1000",
                body={},
            ).execute()
        except Exception:
            # Non-fatal: if clear fails for some reason, leave the written values intact.
            logger.debug("Trailing clear failed for %s", sheet_title)


def _oppm_task_label(task: Any) -> str:
    title = str(_get_item_value(task, "title", "") or "")
    deadline = _get_item_value(task, "deadline")
    if deadline:
        title = f"{title}  ({deadline})"
    indent = "      " if bool(_get_item_value(task, "is_sub", False)) else "   "
    return f"{indent}{_get_item_value(task, 'index', '')}  {title}"


def _oppm_field_value(field_id: str, fills: dict[str, str | None]) -> str:
    values = {
        "project_leader": f"Project Leader: {fills.get('project_leader') or '—'}",
        "project_name": f"Project Name: {fills.get('project_name') or '—'}",
        "project_objective": fills.get("project_objective") or "—",
        "deliverable_output": fills.get("deliverable_output") or "—",
        "start_date": fills.get("start_date") or "—",
        "deadline": fills.get("deadline") or "—",
        "completed_by": f"Project Completed By: {fills.get('completed_by_text') or '—'}",
        "people_count": (
            f"# People working on the project: {fills.get('people_count')}"
            if fills.get("people_count")
            else "# People working on the project"
        ),
    }
    return values[field_id]


def _oppm_summary_block_value(fills: dict[str, str | None]) -> str:
    return "\n".join([
        f"Project Objective: {fills.get('project_objective') or '—'}",
        f"Deliverable Output: {fills.get('deliverable_output') or '—'}",
        f"Start Date: {fills.get('start_date') or '—'}",
        f"Deadline: {fills.get('deadline') or '—'}",
    ])


def _oppm_timeline_header_value(fills: dict[str, str | None]) -> str:
    completed_by = fills.get("completed_by_text") or "—"
    start_date = fills.get("start_date") or ""
    deadline = fills.get("deadline") or ""
    if start_date and deadline:
        return f"Project Completed By: {completed_by} | {start_date} -> {deadline}"
    if start_date:
        return f"Project Completed By: {completed_by} | Start {start_date}"
    if deadline:
        return f"Project Completed By: {completed_by} | Due {deadline}"
    return f"Project Completed By: {completed_by}"


def _get_item_value(item: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(field_name, default)
    return getattr(item, field_name, default)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _collect_timeline_weeks(tasks: list[Any], limit: int) -> list[str]:
    if limit <= 0:
        return []
    weeks = {
        str(_get_item_value(entry, "week_start"))
        for task in tasks
        for entry in (_get_item_value(task, "timeline", []) or [])
        if _get_item_value(entry, "week_start")
    }
    return sorted(weeks)[:limit]


def _collect_task_due_date_weeks(tasks: list[Any], limit: int) -> list[str]:
    """Derive weekly column dates from task due_date / start_date when no explicit
    timeline entries and no project start/deadline are available."""
    if limit <= 0:
        return []
    all_dates: set[date] = set()
    for task in tasks:
        for field in ("deadline", "start_date", "due_date"):
            d = _parse_iso_date(_get_item_value(task, field))
            if d:
                all_dates.add(d)
    if not all_dates:
        return []
    min_date = min(all_dates)
    max_date = max(all_dates)
    start_monday = min_date - timedelta(days=min_date.weekday())
    end_monday = max_date - timedelta(days=max_date.weekday())
    weeks: list[str] = []
    current = start_monday
    while current <= end_monday and len(weeks) < limit:
        weeks.append(current.isoformat())
        current += timedelta(weeks=1)
    if not weeks:
        weeks.append(start_monday.isoformat())
    return weeks[:limit]


def _resolve_timeline_weeks(
    fills: dict[str, str | None],
    tasks: list[Any],
    limit: int,
) -> list[str]:
    if limit <= 0:
        return []

    start = _parse_iso_date(fills.get("start_date"))
    deadline = _parse_iso_date(fills.get("deadline"))
    if not start and not deadline:
        weeks = _collect_timeline_weeks(tasks, limit)
        if weeks:
            return weeks
        return _collect_task_due_date_weeks(tasks, limit)

    if not start:
        start = deadline
    if not deadline:
        deadline = start

    if start is None or deadline is None:
        return _collect_timeline_weeks(tasks, limit)

    start_monday = start - timedelta(days=start.weekday())
    deadline_monday = deadline - timedelta(days=deadline.weekday())

    weeks: list[str] = []
    current = start_monday
    while current <= deadline_monday and len(weeks) < limit:
        weeks.append(current.isoformat())
        current += timedelta(weeks=1)

    if not weeks:
        weeks.append(start_monday.isoformat())

    return weeks[:limit]


def _timeline_symbol(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    if normalized == "todo":
        normalized = "planned"
    return _TIMELINE_SYMBOLS.get(normalized, "")


def _closest_week_index(weeks: list[str], deadline: str | None) -> int | None:
    due_date = _parse_iso_date(deadline)
    if due_date is None or not weeks:
        return None

    best_index: int | None = None
    best_diff: int | None = None
    for index, week_start in enumerate(weeks):
        week_date = _parse_iso_date(week_start)
        if week_date is None:
            continue
        diff = abs((week_date - due_date).days)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = index
    return best_index


def _build_sub_objective_rows(tasks: list[Any], width: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for task in tasks:
        selected = {
            int(position)
            for position in (_get_item_value(task, "sub_objective_positions", []) or [])
            if 1 <= int(position) <= width
        }
        rows.append([
            _TASK_SUB_OBJECTIVE_MARK if index + 1 in selected else ""
            for index in range(width)
        ])
    return rows


def _build_task_text_rows(tasks: list[Any]) -> list[list[str]]:
    return [[_oppm_task_label(task)] for task in tasks]


def _oppm_task_title(task: Any) -> str:
    title = str(_get_item_value(task, "title", "") or "")
    deadline = _get_item_value(task, "deadline")
    if deadline:
        title = f"{title}  ({deadline})"
    return title


def _oppm_grouped_task_title(task: Any) -> str:
    return str(_get_item_value(task, "title", "") or "")


def _oppm_grouped_task_label(task: Any) -> str:
    return f"{_get_item_value(task, 'index', '')}  {_oppm_grouped_task_title(task)}".strip()


def _align_tasks_to_grouped_rows(tasks: list[Any], task_rows: list[dict[str, int | str]]) -> list[Any | None]:
    if not task_rows:
        return tasks

    aligned: list[Any | None] = [None] * len(task_rows)
    for slot_index, task in enumerate(tasks[:len(task_rows)]):
        aligned[slot_index] = task
    return aligned


def _grouped_task_text_updates(task_rows: list[dict[str, int | str]], tasks: list[Any | None]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for slot, task in zip(task_rows, tasks):
        row = int(slot["row"])
        kind = str(slot.get("kind"))
        if kind == "main":
            value = _oppm_grouped_task_label(task) if task else ""
            data.append({
                "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(int(slot['write_col']), row)}",
                "values": [[value]],
            })
            continue

        index_value = str(_get_item_value(task, "index", "") or "") if task else ""
        title_value = _oppm_grouped_task_title(task) if task else ""
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(int(slot['index_col']), row)}",
            "values": [[index_value]],
        })
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(int(slot['title_col']), row)}",
            "values": [[title_value]],
        })

    return data


def _build_timeline_rows(
    fills: dict[str, str | None],
    tasks: list[Any],
    width: int,
) -> list[list[str]]:
    weeks = _resolve_timeline_weeks(fills, tasks, width)
    rows: list[list[str]] = []
    for task in tasks:
        row = [""] * width
        for entry in (_get_item_value(task, "timeline", []) or []):
            week_start = str(_get_item_value(entry, "week_start") or "")
            if not week_start:
                continue
            try:
                index = weeks.index(week_start)
            except ValueError:
                continue
            symbol = _timeline_symbol(_get_item_value(entry, "status"))
            if symbol:
                row[index] = symbol

        if not any(row):
            fallback_index = _closest_week_index(weeks, _get_item_value(task, "deadline"))
            if fallback_index is not None:
                row[fallback_index] = _timeline_symbol(_get_item_value(task, "status"))

        rows.append(row)
    return rows


def _build_owner_rows(tasks: list[Any], members: list[Any], width: int) -> list[list[str]]:
    ordered_members = sorted(members, key=lambda item: int(_get_item_value(item, "slot", 0)))[:width]
    rows: list[list[str]] = []
    for task in tasks:
        owners_by_member = {
            str(_get_item_value(owner, "member_id")): str(_get_item_value(owner, "priority") or "")
            for owner in (_get_item_value(task, "owners", []) or [])
            if _get_item_value(owner, "member_id")
        }
        values = [
            owners_by_member.get(str(_get_item_value(member, "id", "")), "")
            for member in ordered_members
        ]
        if len(values) < width:
            values.extend([""] * (width - len(values)))
        rows.append(values[:width])
    return rows


def _write_sheet_region_values(
    service: Any,
    spreadsheet_id: str,
    sheet_title: str,
    region: dict[str, int] | None,
    rows: list[list[str]],
) -> int:
    if not region:
        return 0

    start_col = int(region.get("start_col") or 0)
    end_col = int(region.get("end_col") or 0)
    first_row = int(region.get("first_row") or 0)
    max_rows = int(region.get("max_rows") or 0)
    if start_col <= 0 or end_col < start_col or first_row <= 0 or max_rows <= 0:
        return 0

    width = end_col - start_col + 1
    rendered_rows = [
        (list(row[:width]) + [""] * width)[:width]
        for row in rows[:max_rows]
    ]

    if rendered_rows:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=(
                f"'{sheet_title}'!{_a1(start_col, first_row)}:"
                f"{_a1(end_col, first_row + len(rendered_rows) - 1)}"
            ),
            valueInputOption="RAW",
            body={"values": rendered_rows},
        ).execute()

    clear_start_row = first_row + len(rendered_rows)
    clear_end_row = first_row + max_rows - 1
    if clear_start_row <= clear_end_row:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=(
                f"'{sheet_title}'!{_a1(start_col, clear_start_row)}:"
                f"{_a1(end_col, clear_end_row)}"
            ),
            body={},
        ).execute()

    return len(rendered_rows)


def _write_oppm_sheet_values(
    service: Any,
    spreadsheet_id: str,
    fills: dict[str, str | None],
    tasks: list[Any],
    members: list[Any],
    mapping: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    # Do not clear the entire OPPM layout range (A1:Z120) — clearing values across
    # the whole template can interact poorly with merged cells and layout formatting.
    # Instead, write only to the specific cells we want to replace and clear the
    # trailing task label area if needed to remove stale task lines.

    anchors = mapping.get("anchors", {})
    task_anchor = mapping.get("task_anchor") or {}
    regions = mapping.get("regions") or {}
    task_rows = mapping.get("task_rows") or []
    summary_block_anchor = mapping.get("summary_block_anchor")
    summary_block_range = mapping.get("summary_block_range") or summary_block_anchor
    clear_anchors = mapping.get("clear_anchors") or []
    data: list[dict[str, Any]] = []

    for field_id, a1_ref in anchors.items():
        value = _oppm_field_value(field_id, fills)
        if field_id == "completed_by" and summary_block_anchor and regions.get("timeline"):
            value = _oppm_timeline_header_value(fills)
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{a1_ref}",
            "values": [[value]],
        })

    if summary_block_range:
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{summary_block_range}",
            "values": [[_oppm_summary_block_value(fills)]],
        })

    task_column = task_anchor.get("column")
    first_task_row = int(task_anchor.get("first_row") or 0)
    max_task_rows = int(task_anchor.get("max_rows") or 0)
    task_rows_to_write = min(len(tasks), max_task_rows) if task_column and first_task_row > 0 and max_task_rows > 0 else 0

    if task_rows:
        rendered_tasks = _align_tasks_to_grouped_rows(tasks, task_rows)
        oppm_rows_written = sum(1 for task in rendered_tasks if task)
    else:
        oppm_rows_written = task_rows_to_write
        rendered_tasks = tasks[:task_rows_to_write]
    region_writes = 0

    task_text_region = regions.get("task_text")
    if task_rows:
        data.extend(_grouped_task_text_updates(task_rows, rendered_tasks))
    elif task_text_region:
        region_writes += _write_sheet_region_values(
            service,
            spreadsheet_id,
            _OPPM_SHEET_TITLE,
            {
                **task_text_region,
                "end_col": int(task_text_region["start_col"]),
            },
            _build_task_text_rows(rendered_tasks),
        )
    elif task_rows_to_write:
        for i, task in enumerate(rendered_tasks):
            row = first_task_row + i
            data.append({
                "range": f"'{_OPPM_SHEET_TITLE}'!{task_column}{row}",
                "values": [[_oppm_task_label(task)]],
            })

    sub_objective_region = regions.get("sub_objectives")
    if sub_objective_region:
        region_writes += _write_sheet_region_values(
            service,
            spreadsheet_id,
            _OPPM_SHEET_TITLE,
            sub_objective_region,
            _build_sub_objective_rows(
                rendered_tasks,
                int(sub_objective_region["end_col"]) - int(sub_objective_region["start_col"]) + 1,
            ),
        )

    timeline_region = regions.get("timeline")
    if timeline_region:
        tl_width = int(timeline_region["end_col"]) - int(timeline_region["start_col"]) + 1
        region_writes += _write_sheet_region_values(
            service,
            spreadsheet_id,
            _OPPM_SHEET_TITLE,
            timeline_region,
            _build_timeline_rows(
                fills,
                rendered_tasks,
                tl_width,
            ),
        )
        # Write the date column headers in the designated date-header row.
        # For templates where the row above the first task row is a merged cell
        # (e.g. "Project Completed By: X weeks"), the date_header_row points to
        # a different row (typically right after the people-count label) that has
        # individual per-column cells that can each hold a date value.
        tl_first_row = int(timeline_region["first_row"])
        tl_header_row = int(timeline_region.get("date_header_row") or tl_first_row - 1)
        if tl_header_row >= 1:
            weeks = _resolve_timeline_weeks(fills, rendered_tasks, tl_width)
            if weeks:
                formatted_dates = []
                for week_str in weeks:
                    week_date = _parse_iso_date(week_str)
                    formatted_dates.append(
                        week_date.strftime("%d-%b-%Y") if week_date else week_str
                    )
                # Pad with empty strings if fewer weeks than columns
                row_values = (formatted_dates + [""] * tl_width)[:tl_width]
                tl_start_col = int(timeline_region["start_col"])
                tl_end_col = int(timeline_region["end_col"])
                try:
                    service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=(
                            f"'{_OPPM_SHEET_TITLE}'!{_a1(tl_start_col, tl_header_row)}:"
                            f"{_a1(tl_end_col, tl_header_row)}"
                        ),
                        valueInputOption="RAW",
                        body={"values": [row_values]},
                    ).execute()
                    region_writes += 1
                except Exception:
                    logger.debug("Failed to write timeline date headers at row %s", tl_header_row)

    owner_region = regions.get("owners")
    if owner_region:
        region_writes += _write_sheet_region_values(
            service,
            spreadsheet_id,
            _OPPM_SHEET_TITLE,
            owner_region,
            _build_owner_rows(
                rendered_tasks,
                members,
                int(owner_region["end_col"]) - int(owner_region["start_col"]) + 1,
            ),
        )

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": data,
            },
        ).execute()

    for a1_ref in clear_anchors:
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{_OPPM_SHEET_TITLE}'!{a1_ref}",
                body={},
            ).execute()
        except Exception:
            logger.debug("Failed to clear stale OPPM anchor %s", a1_ref)

    # If we wrote fewer tasks than the maximum, clear the remaining task-label
    # cells in column G so old labels don't remain visible. This clears values
    # only (not formatting) and preserves the sheet layout.
    if not task_rows and not task_text_region and max_task_rows > 0 and oppm_rows_written < max_task_rows:
        start_row = first_task_row + oppm_rows_written
        end_row = first_task_row + max_task_rows - 1
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{_OPPM_SHEET_TITLE}'!{task_column}{start_row}:{task_column}{end_row}",
                body={},
            ).execute()
        except Exception:
            logger.debug("Failed to clear trailing OPPM task rows %s%s:%s%s", task_column, start_row, task_column, end_row)

    diagnostics = {
        "mapping": mapping,
        "writes": {
            "attempted": len(anchors) + len(tasks) + (1 if summary_block_range else 0),
            "applied": len(data) + region_writes,
            "skipped": max(len(tasks) - task_rows_to_write, 0),
        },
    }
    logger.info(
        "OPPM mapping resolved: source=%s fields=%s task_anchor=%s%s max_rows=%s",
        mapping.get("source"),
        sorted(anchors),
        task_column or "?",
        first_task_row or "?",
        max_task_rows,
    )

    return oppm_rows_written, diagnostics


def _push_to_google_sheet(
    credential_info: dict[str, Any] | None,
    spreadsheet_id: str,
    fills: dict[str, str | None],
    tasks: list[Any],
    members: list[Any],
    explicit_mapping: dict[str, Any] | None,
) -> dict[str, Any]:
    service = _build_sheets_service(credential_info)
    share_email = _service_account_email_from_info(credential_info)
    try:
        _ensure_sheet_tabs(service, spreadsheet_id, [_OPPM_SHEET_TITLE, _SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE])
        summary_rows = _summary_rows(fills)
        task_rows = _tasks_rows(tasks, members)
        member_rows = _members_rows(members)
        if explicit_mapping:
            mapping = _resolve_explicit_oppm_mapping(service, spreadsheet_id, explicit_mapping)
            oppm_rows_written, diagnostics = _write_oppm_sheet_values(service, spreadsheet_id, fills, tasks, members, mapping)
            _write_values(service, spreadsheet_id, _SUMMARY_SHEET_TITLE, summary_rows)
            _write_values(service, spreadsheet_id, _TASKS_SHEET_TITLE, task_rows)
            _write_values(service, spreadsheet_id, _MEMBERS_SHEET_TITLE, member_rows)
            updated_sheets = [_OPPM_SHEET_TITLE, _SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE]
            summary_rows_written = max(len(summary_rows) - 1, 0)
        else:
            helper_profile = _resolve_helper_sheet_profile(service, spreadsheet_id)
            if helper_profile:
                summary_rows_written, diagnostics = _write_summary_helper_sheet_values(
                    service,
                    spreadsheet_id,
                    fills,
                    helper_profile,
                )
                oppm_rows_written = 0
                mapping = _resolve_oppm_mapping_profile(service, spreadsheet_id)
                if mapping.get("source") != "unresolved":
                    oppm_rows_written, diagnostics = _write_oppm_sheet_values(service, spreadsheet_id, fills, tasks, members, mapping)
                _write_sheet_with_existing_headers(service, spreadsheet_id, _TASKS_SHEET_TITLE, _TASKS_TABLE_HEADERS, task_rows)
                _write_sheet_with_existing_headers(service, spreadsheet_id, _MEMBERS_SHEET_TITLE, _MEMBERS_TABLE_HEADERS, member_rows)
                updated_sheets = [_SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE]
                if oppm_rows_written > 0:
                    updated_sheets.insert(0, _OPPM_SHEET_TITLE)
            else:
                mapping = _resolve_oppm_mapping_profile(service, spreadsheet_id)
                if mapping.get("source") == "unresolved":
                    raise HTTPException(status_code=422, detail=_format_unresolved_push_detail(mapping))
                oppm_rows_written, diagnostics = _write_oppm_sheet_values(service, spreadsheet_id, fills, tasks, members, mapping)
                _write_values(service, spreadsheet_id, _SUMMARY_SHEET_TITLE, summary_rows)
                _write_values(service, spreadsheet_id, _TASKS_SHEET_TITLE, task_rows)
                _write_values(service, spreadsheet_id, _MEMBERS_SHEET_TITLE, member_rows)
                updated_sheets = [_OPPM_SHEET_TITLE, _SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE]
                summary_rows_written = max(len(summary_rows) - 1, 0)

        return {
            "updated_sheets": updated_sheets,
            "rows_written": {
                "oppm": oppm_rows_written,
                "summary": summary_rows_written,
                "tasks": max(len(task_rows) - 1, 0),
                "members": max(len(member_rows) - 1, 0),
            },
            "diagnostics": diagnostics,
        }
    except HTTPException:
        raise
    except Exception as error:
        status = getattr(getattr(error, "resp", None), "status", None)
        if status == 403:
            detail = "Google Sheets access denied"
            if share_email:
                detail = f"Google Sheets access denied. Share the spreadsheet with {share_email} and try again"
            raise HTTPException(status_code=403, detail=detail)
        if status == 404:
            raise HTTPException(status_code=404, detail="Google Sheets spreadsheet not found")
        logger.warning("Google Sheets push failed: %s", error)
        raise HTTPException(status_code=502, detail="Failed to push OPPM data to Google Sheets")


def _download_google_sheet_xlsx(credential_info: dict[str, Any] | None, spreadsheet_id: str) -> bytes:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as error:
        logger.warning("Google Drive export dependency missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Drive export dependencies are not installed on the backend")

    drive = _build_drive_service(credential_info)
    share_email = _service_account_email_from_info(credential_info)
    request = drive.files().export_media(fileId=spreadsheet_id, mimeType=_XLSX_MIME_TYPE)
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(output, request)

    try:
        done = False
        while not done:
            _, done = downloader.next_chunk()
    except Exception as error:
        status = getattr(getattr(error, "resp", None), "status", None)
        if status == 403:
            detail = "Google Sheets access denied"
            if share_email:
                detail = f"Google Sheets access denied. Share the spreadsheet with {share_email} and try again"
            raise HTTPException(status_code=403, detail=detail)
        if status == 404:
            raise HTTPException(status_code=404, detail="Google Sheets spreadsheet not found")
        logger.warning("Google Sheets export failed: %s", error)
        raise HTTPException(status_code=502, detail="Failed to fetch linked Google Sheet")

    return output.getvalue()


async def get_google_sheet_link(session: AsyncSession, project_id: str, workspace_id: str) -> dict[str, Any]:
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    setup_status = await get_google_sheets_setup_status(session, workspace_id)
    return {
        "connected": bool(link),
        "spreadsheet_id": link.get("spreadsheet_id") if link else None,
        "spreadsheet_url": link.get("spreadsheet_url") if link else None,
        "backend_configured": setup_status["backend_configured"],
        "service_account_email": setup_status["service_account_email"],
        "backend_configuration_error": setup_status["backend_configuration_error"],
    }


async def upsert_google_sheet_link(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    spreadsheet_input: str,
) -> dict[str, Any]:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    project = await _get_project_or_404(session, project_id, workspace_id)

    spreadsheet_id = _parse_spreadsheet_id(spreadsheet_input)
    spreadsheet_url = _canonical_spreadsheet_url(spreadsheet_id)
    previous_link = _extract_link(project.metadata_)
    metadata = dict(project.metadata_ or {})
    metadata[_GOOGLE_SHEET_KEY] = {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
    }
    await project_repo.update(project_id, {"metadata_": metadata})
    await audit_repo.log(
        workspace_id,
        user_id,
        "update",
        "project_google_sheet",
        project_id,
        old_data=previous_link,
        new_data=metadata[_GOOGLE_SHEET_KEY],
    )

    setup_status = await get_google_sheets_setup_status(session, workspace_id)

    return {
        "connected": True,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "backend_configured": setup_status["backend_configured"],
        "service_account_email": setup_status["service_account_email"],
        "backend_configuration_error": setup_status["backend_configuration_error"],
    }


async def delete_google_sheet_link(session: AsyncSession, project_id: str, workspace_id: str, user_id: str) -> None:
    project_repo = ProjectRepository(session)
    audit_repo = AuditRepository(session)
    project = await _get_project_or_404(session, project_id, workspace_id)
    previous_link = _extract_link(project.metadata_)
    metadata = dict(project.metadata_ or {})
    metadata.pop(_GOOGLE_SHEET_KEY, None)
    await project_repo.update(project_id, {"metadata_": metadata})
    await audit_repo.log(
        workspace_id,
        user_id,
        "delete",
        "project_google_sheet",
        project_id,
        old_data=previous_link,
        new_data=None,
    )


async def _download_google_sheet_xlsx_public(spreadsheet_id: str) -> bytes:
    """Download a Google Sheet as XLSX using the public export URL (no credentials).

    Works for sheets shared as 'Anyone with the link can view'.
    Raises HTTP 403 if the sheet is private (Google redirects to login page).
    """
    import httpx

    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(export_url)
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="Google Sheet export request timed out") from error
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail=f"Failed to reach Google Sheets: {error}") from error

    content_type = response.headers.get("content-type", "")
    is_spreadsheet = any(s in content_type for s in ("spreadsheet", "excel", "octet-stream", "zip"))
    if response.status_code == 200 and is_spreadsheet:
        return response.content

    # Google returned HTML — sheet is not publicly accessible.
    raise HTTPException(
        status_code=403,
        detail=(
            "Google Sheet is not publicly accessible. "
            "Either make the sheet viewable by anyone with the link, "
            "or configure a Google service account under Settings → Google Sheets."
        ),
    )


async def download_linked_google_sheet_xlsx(session: AsyncSession, project_id: str, workspace_id: str) -> tuple[bytes, str]:
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    if credential_info:
        # Preferred: authenticated download via service account (works for private sheets).
        xlsx_bytes = await asyncio.to_thread(_download_google_sheet_xlsx, credential_info, spreadsheet_id)
    else:
        # Fallback: unauthenticated public export URL (works when the sheet is publicly shared).
        xlsx_bytes = await _download_google_sheet_xlsx_public(spreadsheet_id)

    file_name = f"linked-google-sheet-{project_id[:8]}.xlsx"
    return xlsx_bytes, file_name


async def push_google_sheet_fill(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    fills: dict[str, str | None],
    tasks: list[Any],
    members: list[Any],
    explicit_mapping: dict[str, Any] | None,
) -> dict[str, Any]:
    audit_repo = AuditRepository(session)
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=True)
    result = await asyncio.to_thread(
        _push_to_google_sheet,
        credential_info,
        spreadsheet_id,
        fills,
        tasks,
        members,
        explicit_mapping,
    )
    response = {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": link.get("spreadsheet_url") or _canonical_spreadsheet_url(spreadsheet_id),
        "updated_sheets": result["updated_sheets"],
        "rows_written": result["rows_written"],
        "diagnostics": result.get("diagnostics", {}),
    }
    await audit_repo.log(
        workspace_id,
        user_id,
        "update",
        "project_google_sheet_push",
        project_id,
        new_data=response,
    )
    return response
