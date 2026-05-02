"""Mapping profile resolution: classic fallback, explicit mapping, helper sheet."""

import logging
from typing import Any

from fastapi import HTTPException

from .cells import (
    _a1,
    _find_first_cell,
    _find_matching_label_cells,
    _iter_normalized_layout_cells,
    _merge_column_bounds,
    _merge_end_column,
    _merge_range_bounds,
    _normalize_cell_text,
    _resolve_scalar_anchor_from_label_cell,
)
from .constants import (
    _CLASSIC_MAX_TASK_ROWS,
    _CLASSIC_VISIBLE_TASK_ROWS,
    _EXPLICIT_MAPPING_FIELD_IDS,
    _INLINE_LABEL_FIELDS,
    _OPPM_SHEET_TITLE,
    _SPREADSHEET_ID_RE,
    _SPREADSHEET_URL_RE,
    _SUMMARY_BLOCK_FIELDS,
    _SUMMARY_HELPER_LABELS,
    _SUMMARY_HELPER_REQUIRED_FIELDS,
    _SUMMARY_SHEET_TITLE,
    _TASKS_SHEET_TITLE,
    _VALUE_LABEL_FIELDS,
)
from .layout import (
    _find_label_value_anchor,
    _find_summary_block_cell,
    _read_sheet_layout,
    _resolve_grouped_task_rows,
    _resolve_task_layout_regions,
    _select_preferred_inline_label_cell,
)

logger = logging.getLogger(__name__)


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
        "column": _a1(col, row)[0],
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
