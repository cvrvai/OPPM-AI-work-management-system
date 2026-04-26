"""Google Sheets MVP service for linking a project sheet and pushing AI-filled OPPM data."""

import asyncio
import io
import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from repositories.notification_repo import AuditRepository
from repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)

_GOOGLE_SHEET_KEY = "google_sheet"
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


def _load_service_account_info() -> dict[str, Any] | None:
    settings = get_settings()
    if settings.google_service_account_json.strip():
        try:
            return json.loads(settings.google_service_account_json)
        except json.JSONDecodeError as error:
            logger.warning("Invalid GOOGLE_SERVICE_ACCOUNT_JSON: %s", error)
            raise HTTPException(status_code=500, detail="Invalid Google service account JSON configuration")

    if settings.google_service_account_file.strip():
        file_path = Path(settings.google_service_account_file)
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Google service account file does not exist")
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Failed to read Google service account file: %s", error)
            raise HTTPException(status_code=500, detail="Invalid Google service account file configuration")

    return None


def _service_account_email() -> str | None:
    info = _load_service_account_info()
    if not info:
        return None
    return info.get("client_email")


def _is_backend_configured() -> bool:
    return _load_service_account_info() is not None


def _build_google_credentials():
    info = _load_service_account_info()
    if not info:
        raise HTTPException(status_code=503, detail="Google Sheets integration is not configured on the backend")

    try:
        from google.oauth2 import service_account
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    return service_account.Credentials.from_service_account_info(info, scopes=_GOOGLE_SCOPES)


def _build_sheets_service():
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    credentials = _build_google_credentials()
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _build_drive_service():
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Drive dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Drive dependencies are not installed on the backend")

    credentials = _build_google_credentials()
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


def _write_values(service: Any, spreadsheet_id: str, sheet_title: str, rows: list[list[str]]) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()


def _push_to_google_sheet(spreadsheet_id: str, fills: dict[str, str | None], tasks: list[Any], members: list[Any]) -> dict[str, Any]:
    service = _build_sheets_service()
    try:
        _ensure_sheet_tabs(service, spreadsheet_id, [_SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE])
        summary_rows = _summary_rows(fills)
        task_rows = _tasks_rows(tasks, members)
        member_rows = _members_rows(members)
        _write_values(service, spreadsheet_id, _SUMMARY_SHEET_TITLE, summary_rows)
        _write_values(service, spreadsheet_id, _TASKS_SHEET_TITLE, task_rows)
        _write_values(service, spreadsheet_id, _MEMBERS_SHEET_TITLE, member_rows)
        return {
            "updated_sheets": [_SUMMARY_SHEET_TITLE, _TASKS_SHEET_TITLE, _MEMBERS_SHEET_TITLE],
            "rows_written": {
                "summary": max(len(summary_rows) - 1, 0),
                "tasks": max(len(task_rows) - 1, 0),
                "members": max(len(member_rows) - 1, 0),
            },
        }
    except Exception as error:
        status = getattr(getattr(error, "resp", None), "status", None)
        share_email = _service_account_email()
        if status == 403:
            detail = "Google Sheets access denied"
            if share_email:
                detail = f"Google Sheets access denied. Share the spreadsheet with {share_email} and try again"
            raise HTTPException(status_code=403, detail=detail)
        if status == 404:
            raise HTTPException(status_code=404, detail="Google Sheets spreadsheet not found")
        logger.warning("Google Sheets push failed: %s", error)
        raise HTTPException(status_code=502, detail="Failed to push OPPM data to Google Sheets")


def _download_google_sheet_xlsx(spreadsheet_id: str) -> bytes:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as error:
        logger.warning("Google Drive export dependency missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Drive export dependencies are not installed on the backend")

    drive = _build_drive_service()
    request = drive.files().export_media(fileId=spreadsheet_id, mimeType=_XLSX_MIME_TYPE)
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(output, request)

    try:
        done = False
        while not done:
            _, done = downloader.next_chunk()
    except Exception as error:
        status = getattr(getattr(error, "resp", None), "status", None)
        share_email = _service_account_email()
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
    return {
        "connected": bool(link),
        "spreadsheet_id": link.get("spreadsheet_id") if link else None,
        "spreadsheet_url": link.get("spreadsheet_url") if link else None,
        "backend_configured": _is_backend_configured(),
        "service_account_email": _service_account_email(),
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

    return {
        "connected": True,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "backend_configured": _is_backend_configured(),
        "service_account_email": _service_account_email(),
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


async def download_linked_google_sheet_xlsx(session: AsyncSession, project_id: str, workspace_id: str) -> tuple[bytes, str]:
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    xlsx_bytes = await asyncio.to_thread(_download_google_sheet_xlsx, spreadsheet_id)
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
) -> dict[str, Any]:
    audit_repo = AuditRepository(session)
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    result = await asyncio.to_thread(_push_to_google_sheet, spreadsheet_id, fills, tasks, members)
    response = {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": link.get("spreadsheet_url") or _canonical_spreadsheet_url(spreadsheet_id),
        "updated_sheets": result["updated_sheets"],
        "rows_written": result["rows_written"],
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
