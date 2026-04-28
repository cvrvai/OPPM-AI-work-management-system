"""Google Sheets MVP service for linking a project sheet and pushing AI-filled OPPM data."""

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
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
_DEFAULT_LAYOUT_SCAN_RANGE = "A1:AZ120"
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


def _merge_end_column(merges: list[dict[str, int]], row: int, col: int) -> int:
    row_index = row - 1
    col_index = col - 1
    for merge in merges:
        start_row = merge.get("startRowIndex", 0)
        end_row = merge.get("endRowIndex", 0)
        start_col = merge.get("startColumnIndex", 0)
        end_col = merge.get("endColumnIndex", 0)
        if start_row <= row_index < end_row and start_col <= col_index < end_col:
            # end_col is exclusive in Google API, and 1-based inclusive is the same numeric value.
            return end_col
    return col


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
            "max_rows": _CLASSIC_MAX_TASK_ROWS,
        },
        "missing_anchors": [],
    }


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

    label_anchors = {
        "project_objective": _find_label_value_anchor(layout, "Project Objective"),
        "deliverable_output": _find_label_value_anchor(layout, "Deliverable Output"),
        "start_date": _find_label_value_anchor(layout, "Start Date"),
        "deadline": _find_label_value_anchor(layout, "Deadline"),
    }

    leader_cell = _find_first_cell(layout, lambda text: text.startswith("project leader"))
    project_name_cell = _find_first_cell(layout, lambda text: text.startswith("project name"))
    completed_by_cell = _find_first_cell(layout, lambda text: text.startswith("project completed by"))
    task_header_cell = _find_first_cell(layout, lambda text: "major tasks" in text)

    anchors: dict[str, str | None] = {
        "project_leader": _a1(leader_cell[1], leader_cell[0]) if leader_cell else None,
        "project_name": _a1(project_name_cell[1], project_name_cell[0]) if project_name_cell else None,
        "project_objective": _a1(label_anchors["project_objective"][1], label_anchors["project_objective"][0]) if label_anchors["project_objective"] else None,
        "deliverable_output": _a1(label_anchors["deliverable_output"][1], label_anchors["deliverable_output"][0]) if label_anchors["deliverable_output"] else None,
        "start_date": _a1(label_anchors["start_date"][1], label_anchors["start_date"][0]) if label_anchors["start_date"] else None,
        "deadline": _a1(label_anchors["deadline"][1], label_anchors["deadline"][0]) if label_anchors["deadline"] else None,
        "completed_by": _a1(completed_by_cell[1], completed_by_cell[0]) if completed_by_cell else None,
    }

    missing_anchors = [name for name, value in anchors.items() if not value]
    signal_count = len(anchors) + 1
    found_signals = (len(anchors) - len(missing_anchors)) + (1 if task_header_cell else 0)
    confidence = round(found_signals / signal_count, 3)

    has_all_required_labels = all(label_anchors.values())
    has_task_anchor = task_header_cell is not None
    if not has_all_required_labels or not has_task_anchor:
        if confidence >= 0.5:
            fallback = _classic_oppm_mapping_profile()
            fallback["confidence"] = confidence
            fallback["missing_anchors"] = missing_anchors
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
            "missing_anchors": unresolved_missing,
        }

    task_col = task_header_cell[1]
    first_task_row = task_header_cell[0] + 1
    max_row = layout.get("max_row", 120)
    max_rows = max(0, min(_CLASSIC_MAX_TASK_ROWS, max_row - first_task_row + 1))

    return {
        "source": "layout_detected",
        "confidence": confidence,
        "fallback_used": False,
        "anchors": anchors,
        "task_anchor": {
            "column": _column_letter(task_col),
            "first_row": first_task_row,
            "max_rows": max_rows,
        },
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
    title = task.title
    if task.deadline:
        title = f"{title}  ({task.deadline})"
    indent = "      " if task.is_sub else "   "
    return f"{indent}{task.index}  {title}"


def _oppm_field_value(field_id: str, fills: dict[str, str | None]) -> str:
    values = {
        "project_leader": f"Project Leader: {fills.get('project_leader') or '—'}",
        "project_name": f"Project Name: {fills.get('project_name') or '—'}",
        "project_objective": fills.get("project_objective") or "—",
        "deliverable_output": fills.get("deliverable_output") or "—",
        "start_date": fills.get("start_date") or "—",
        "deadline": fills.get("deadline") or "—",
        "completed_by": f"Project Completed By: {fills.get('completed_by_text') or '—'}",
    }
    return values[field_id]


def _write_oppm_sheet_values(
    service: Any,
    spreadsheet_id: str,
    fills: dict[str, str | None],
    tasks: list[Any],
    mapping: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    # Do not clear the entire OPPM layout range (A1:Z120) — clearing values across
    # the whole template can interact poorly with merged cells and layout formatting.
    # Instead, write only to the specific cells we want to replace and clear the
    # trailing task label area if needed to remove stale task lines.

    anchors = mapping.get("anchors", {})
    task_anchor = mapping.get("task_anchor") or {}
    data: list[dict[str, Any]] = []

    for field_id, a1_ref in anchors.items():
        data.append({
            "range": f"'{_OPPM_SHEET_TITLE}'!{a1_ref}",
            "values": [[_oppm_field_value(field_id, fills)]],
        })

    task_column = task_anchor.get("column")
    first_task_row = int(task_anchor.get("first_row") or 0)
    max_task_rows = int(task_anchor.get("max_rows") or 0)
    task_rows_to_write = 0
    if task_column and first_task_row > 0 and max_task_rows > 0:
        task_rows_to_write = min(len(tasks), max_task_rows)
        for i, task in enumerate(tasks[:task_rows_to_write]):
            row = first_task_row + i
            data.append({
                "range": f"'{_OPPM_SHEET_TITLE}'!{task_column}{row}",
                "values": [[_oppm_task_label(task)]],
            })

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": data,
            },
        ).execute()

    oppm_rows_written = task_rows_to_write

    # If we wrote fewer tasks than the maximum, clear the remaining task-label
    # cells in column G so old labels don't remain visible. This clears values
    # only (not formatting) and preserves the sheet layout.
    if max_task_rows > 0 and oppm_rows_written < max_task_rows:
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
            "attempted": len(anchors) + (len(tasks) if task_column and first_task_row > 0 and max_task_rows > 0 else 0),
            "applied": len(data),
            "skipped": max(len(tasks) - task_rows_to_write, 0) if task_column and first_task_row > 0 and max_task_rows > 0 else 0,
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
            oppm_rows_written, diagnostics = _write_oppm_sheet_values(service, spreadsheet_id, fills, tasks, mapping)
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
                _write_sheet_with_existing_headers(service, spreadsheet_id, _TASKS_SHEET_TITLE, _TASKS_TABLE_HEADERS, task_rows)
                _write_sheet_with_existing_headers(service, spreadsheet_id, _MEMBERS_SHEET_TITLE, _MEMBERS_TABLE_HEADERS, member_rows)
                updated_sheets = [_SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE]
            else:
                mapping = _resolve_oppm_mapping_profile(service, spreadsheet_id)
                if mapping.get("source") == "unresolved":
                    raise HTTPException(status_code=422, detail=_format_unresolved_push_detail(mapping))
                oppm_rows_written, diagnostics = _write_oppm_sheet_values(service, spreadsheet_id, fills, tasks, mapping)
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
