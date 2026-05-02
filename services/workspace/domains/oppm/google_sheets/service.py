"""Public async service functions for Google Sheets OPPM integration."""

import asyncio
import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from domains.notification.repository import AuditRepository
from domains.project.repository import ProjectRepository

from .constants import _GOOGLE_SHEET_KEY
from .credentials import (
    _build_sheets_service,
    _resolve_workspace_service_account_info,
    delete_google_sheets_workspace_credentials,
    get_google_sheets_setup_status,
    upsert_google_sheets_workspace_credentials,
)
from .writer import (
    _download_google_sheet_xlsx,
    _extract_link,
    _parse_spreadsheet_id,
    _canonical_spreadsheet_url,
    _push_to_google_sheet,
)

logger = logging.getLogger(__name__)


async def _get_project_or_404(session: AsyncSession, project_id: str, workspace_id: str):
    project_repo = ProjectRepository(session)
    project = await project_repo.find_by_id(project_id)
    if not project or str(project.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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
        xlsx_bytes = await asyncio.to_thread(_download_google_sheet_xlsx, credential_info, spreadsheet_id)
    else:
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


async def execute_sheet_actions(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    actions: list[dict],
) -> dict[str, Any]:
    from domains.oppm.sheet_action_executor import execute_actions

    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=True)
    service = await asyncio.to_thread(_build_sheets_service, credential_info)
    results = await asyncio.to_thread(execute_actions, service, spreadsheet_id, actions)
    return {"results": results}
