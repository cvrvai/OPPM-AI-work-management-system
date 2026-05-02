"""Build, write, push, and download functions for Google Sheets OPPM data."""

import asyncio
import io
import logging
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from .cells import _a1
from .constants import (
    _CLASSIC_MAX_TASK_ROWS,
    _CLASSIC_VISIBLE_TASK_ROWS,
    _MEMBERS_SHEET_TITLE,
    _MEMBERS_TABLE_HEADERS,
    _OPPM_SHEET_TITLE,
    _SPREADSHEET_ID_RE,
    _SPREADSHEET_URL_RE,
    _SUMMARY_BLOCK_FIELDS,
    _SUMMARY_SHEET_TITLE,
    _TASKS_SHEET_TITLE,
    _TASKS_TABLE_HEADERS,
    _TASK_SUB_OBJECTIVE_MARK,
    _TIMELINE_SYMBOLS,
    _XLSX_MIME_TYPE,
)
from .credentials import (
    _build_drive_service,
    _build_sheets_service,
    _service_account_email_from_info,
)
from .layout import (
    _get_sheet_id_by_title,
    _read_sheet_layout,
    _resolve_grouped_task_rows,
    _resolve_table_header_profile,
    _write_table_rows,
)
from .mapping import (
    _classic_oppm_mapping_profile,
    _format_unresolved_push_detail,
    _resolve_explicit_oppm_mapping,
    _resolve_helper_sheet_profile,
    _resolve_oppm_mapping_profile,
)

logger = logging.getLogger(__name__)


def _extract_link(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    link = metadata.get("google_sheet")
    return link if isinstance(link, dict) else None


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

    # Prefer actual task timeline weeks over project start/deadline
    weeks = _collect_timeline_weeks(tasks, limit)
    if weeks:
        return weeks

    start = _parse_iso_date(fills.get("start_date"))
    deadline = _parse_iso_date(fills.get("deadline"))
    if not start and not deadline:
        return _collect_task_due_date_weeks(tasks, limit)

    if not start:
        start = deadline
    if not deadline:
        deadline = start

    if start is None or deadline is None:
        return []

    start_monday = start - timedelta(days=start.weekday())
    deadline_monday = deadline - timedelta(days=deadline.weekday())

    result: list[str] = []
    current = start_monday
    while current <= deadline_monday and len(result) < limit:
        result.append(current.isoformat())
        current += timedelta(weeks=1)

    if not result:
        result.append(start_monday.isoformat())

    return result[:limit]


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
    # If completed_by already looks like a date or date range, just return it
    if completed_by and completed_by != "—":
        return f"Project Completed By: {completed_by}"
    if start_date and deadline:
        return f"Project Completed By: {completed_by} | {start_date} -> {deadline}"
    if start_date:
        return f"Project Completed By: {completed_by} | Start {start_date}"
    if deadline:
        return f"Project Completed By: {completed_by} | Due {deadline}"
    return f"Project Completed By: {completed_by}"


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


def _extend_task_rows_for_overflow(
    task_rows: list[dict[str, int | str]],
    tasks: list[Any],
    task_text_region: dict[str, int] | None,
) -> list[dict[str, int | str]]:
    """Create additional task_rows when tasks exceed the pre-planned layout."""
    if not task_rows or len(tasks) <= len(task_rows):
        return task_rows

    task_start_col = int(task_text_region["start_col"]) if task_text_region else 7
    task_end_col = int(task_text_region["end_col"]) if task_text_region else 20
    index_col = task_start_col - 1

    extended = list(task_rows)
    current_row = max(int(slot["row"]) for slot in task_rows) + 1

    for i in range(len(task_rows), len(tasks)):
        task = tasks[i]
        is_main = not bool(_get_item_value(task, "is_sub", False))
        if is_main:
            extended.append({
                "row": current_row,
                "kind": "main",
                "write_col": index_col,
            })
        else:
            extended.append({
                "row": current_row,
                "kind": "sub",
                "index_col": index_col,
                "title_col": task_start_col,
                "write_col": task_start_col,
            })
        current_row += 1

    return extended


def _build_task_row_merge_requests(
    task_rows: list[dict[str, int | str]],
    tasks: list[Any | None],
    sheet_id: int,
    index_col: int,
    end_col: int,
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for slot, task in zip(task_rows, tasks):
        row = int(slot["row"])
        row_idx = row - 1
        is_main = not bool(_get_item_value(task, "is_sub", False)) if task else False

        if is_main:
            # Merge ALL cells in the row (from index_col to end_col)
            requests.append({
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": index_col - 1,
                        "endColumnIndex": end_col,
                    },
                    "mergeType": "MERGE_ALL",
                }
            })
            # Force left alignment so merged main-task text stays on the left
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": index_col - 1,
                        "endColumnIndex": end_col,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat.horizontalAlignment",
                }
            })
        else:
            # Leave 1 cell for index, merge the rest (from title_col to end_col)
            slot_index_col = int(slot.get("index_col") or slot.get("write_col") or index_col)
            title_col = int(slot.get("title_col") or (slot_index_col + 1))
            requests.append({
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": title_col - 1,
                        "endColumnIndex": end_col,
                    },
                    "mergeType": "MERGE_ALL",
                }
            })

    return requests


def _build_task_row_border_requests(
    task_rows: list[dict[str, int | str]],
    tasks: list[Any | None],
    sheet_id: int,
    index_col: int,
    end_col: int,
    original_max_rows: int,
) -> list[dict[str, Any]]:
    """Move the thick bottom border from the original last task row to the new last task row."""
    requests: list[dict[str, Any]] = []
    if len(task_rows) <= original_max_rows:
        return requests

    # Original last task row (0-based)
    original_last = task_rows[original_max_rows - 1]
    original_row_idx = int(original_last["row"]) - 1

    # New actual last task row (0-based)
    new_last = task_rows[-1]
    new_row_idx = int(new_last["row"]) - 1

    # Remove thick bottom border from original last row
    requests.append({
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": original_row_idx,
                "endRowIndex": original_row_idx + 1,
                "startColumnIndex": index_col - 1,
                "endColumnIndex": end_col,
            },
            "bottom": {
                "style": "SOLID",
                "width": 1,
                "color": {"red": 0.0, "green": 0.0, "blue": 0.0},
            },
        }
    })

    # Add thick bottom border to new last row
    requests.append({
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": new_row_idx,
                "endRowIndex": new_row_idx + 1,
                "startColumnIndex": index_col - 1,
                "endColumnIndex": end_col,
            },
            "bottom": {
                "style": "SOLID_MEDIUM",
                "width": 2,
                "color": {"red": 0.0, "green": 0.0, "blue": 0.0},
            },
        }
    })

    return requests


def _grouped_task_text_updates(task_rows: list[dict[str, int | str]], tasks: list[Any | None]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for slot, task in zip(task_rows, tasks):
        row = int(slot["row"])
        is_main = not bool(_get_item_value(task, "is_sub", False)) if task else False
        if is_main:
            # After mergeCells runs, write_col IS the single merged cell — just write once
            value = _oppm_grouped_task_label(task) if task else ""
            data.append({
                "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(int(slot['write_col']), row)}",
                "values": [[value]],
            })
            continue

        # Sub-task: split into two columns — index in first, title in second
        # Derive columns from slot; if slot is a main-task slot, compute defaults
        slot_index_col = int(slot.get("index_col") or slot.get("write_col") or 0)
        slot_title_col = int(slot.get("title_col") or (slot_index_col + 1) or 0)
        index_value = str(_get_item_value(task, "index", "") or "") if task else ""
        title_value = _oppm_grouped_task_title(task) if task else ""
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(slot_index_col, row)}",
            "values": [[index_value]],
        })
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{_a1(slot_title_col, row)}",
            "values": [[title_value]],
        })

    return data


def _build_task_text_rows(tasks: list[Any]) -> list[list[str]]:
    return [[_oppm_task_label(task)] for task in tasks]


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


def _write_values(service: Any, spreadsheet_id: str, sheet_title: str, rows: list[list[str]]) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    if rows:
        last_row = len(rows)
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!A{last_row + 1}:Z1000",
                body={},
            ).execute()
        except Exception:
            logger.debug("Trailing clear failed for %s", sheet_title)


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
            valueInputOption="USER_ENTERED",
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
            "values": [[fills.get(field_key) or ""]],
        }
        for field_key, a1_ref in anchors.items()
    ]

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "USER_ENTERED",
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


def _write_oppm_sheet_values(
    service: Any,
    spreadsheet_id: str,
    fills: dict[str, str | None],
    tasks: list[Any],
    members: list[Any],
    mapping: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
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
    task_text_region = regions.get("task_text")

    sheet_id = _get_sheet_id_by_title(service, spreadsheet_id, _OPPM_SHEET_TITLE)

    overflow = len(tasks) - max_task_rows if task_rows and max_task_rows > 0 else 0
    if overflow > 0 and first_task_row > 0 and max_task_rows > 0 and sheet_id is not None:
        insert_at = first_task_row + max_task_rows - 1
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "insertDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": insert_at,
                                    "endIndex": insert_at + overflow,
                                },
                                "inheritFromBefore": True,
                            }
                        }
                    ]
                },
            ).execute()
            max_task_rows += overflow
            task_anchor = {**task_anchor, "max_rows": max_task_rows}
            regions = {
                k: ({**v, **{
                    f: int(v[f]) + overflow
                    for f in ("max_rows", "date_header_row", "member_header_row")
                    if f in v
                }} if isinstance(v, dict) else v)
                for k, v in regions.items()
            }
            task_rows_to_write = min(len(tasks), max_task_rows)
        except Exception:
            logger.debug("Failed to insert overflow rows into OPPM sheet")

    if task_rows:
        task_rows = _extend_task_rows_for_overflow(task_rows, tasks, task_text_region)
        rendered_tasks = _align_tasks_to_grouped_rows(tasks, task_rows)
        oppm_rows_written = sum(1 for task in rendered_tasks if task)
    else:
        oppm_rows_written = task_rows_to_write
        rendered_tasks = tasks[:task_rows_to_write]
    region_writes = 0

    if task_rows:
        task_text_region_safe = task_text_region or {}
        task_end_col = int(task_text_region_safe.get("end_col") or 0)
        task_start_col = int(task_text_region_safe.get("start_col") or 0)
        index_col = task_start_col - 1
        if index_col >= 1 and task_end_col >= task_start_col and sheet_id is not None:
            merge_requests = _build_task_row_merge_requests(
                task_rows, rendered_tasks, sheet_id, index_col, task_end_col
            )
            original_max_rows = int(mapping.get("task_anchor", {}).get("max_rows", 0))
            if original_max_rows > 0:
                border_requests = _build_task_row_border_requests(
                    task_rows, rendered_tasks, sheet_id, index_col, task_end_col, original_max_rows
                )
                merge_requests.extend(border_requests)
            if merge_requests:
                try:
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body={"requests": merge_requests},
                    ).execute()
                except Exception:
                    logger.debug("Failed to apply task row merge/unmerge requests")

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
                        valueInputOption="USER_ENTERED",
                        body={"values": [row_values]},
                    ).execute()
                    region_writes += 1
                except Exception:
                    logger.debug("Failed to write timeline date headers at row %s", tl_header_row)

    owner_region = regions.get("owners")
    if owner_region:
        owner_width = int(owner_region["end_col"]) - int(owner_region["start_col"]) + 1
        region_writes += _write_sheet_region_values(
            service,
            spreadsheet_id,
            _OPPM_SHEET_TITLE,
            owner_region,
            _build_owner_rows(
                rendered_tasks,
                members,
                owner_width,
            ),
        )
        member_header_row = int(owner_region.get("member_header_row") or 0)
        if member_header_row >= 1 and members:
            ordered = sorted(members, key=lambda m: int(_get_item_value(m, "slot", 0)))
            name_values = (
                [str(_get_item_value(m, "name") or "") for m in ordered] + [""] * owner_width
            )[:owner_width]
            ow_start_col = int(owner_region["start_col"])
            ow_end_col = int(owner_region["end_col"])
            try:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=(
                        f"'{_OPPM_SHEET_TITLE}'!{_a1(ow_start_col, member_header_row)}:"
                        f"{_a1(ow_end_col, member_header_row)}"
                    ),
                    valueInputOption="USER_ENTERED",
                    body={"values": [name_values]},
                ).execute()
                region_writes += 1
            except Exception:
                logger.debug("Failed to write member name headers at row %s", member_header_row)

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "USER_ENTERED",
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
        logger.exception("Google Sheets push failed: %s", error)
        raise HTTPException(status_code=502, detail=f"Failed to push OPPM data to Google Sheets: {error}")


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
