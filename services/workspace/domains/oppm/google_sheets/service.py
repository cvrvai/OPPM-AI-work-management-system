"""Public async service functions for Google Sheets OPPM integration."""

import asyncio
import logging
from typing import Any

from fastapi import HTTPException
from googleapiclient.errors import HttpError
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

    oppm_sheet_gid: int | None = None
    spreadsheet_id = link.get("spreadsheet_id") if link else None
    if spreadsheet_id and setup_status["backend_configured"]:
        try:
            credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
            if credential_info:
                service = await asyncio.to_thread(_build_sheets_service, credential_info)
                resp = await asyncio.to_thread(
                    service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id,
                        fields="sheets.properties.sheetId,sheets.properties.title",
                    ).execute
                )
                for sheet in resp.get("sheets", []):
                    props = sheet.get("properties", {})
                    if props.get("title") == "OPPM":
                        oppm_sheet_gid = int(props["sheetId"])
                        break
        except Exception as e:
            logger.warning("get_google_sheet_link: could not look up OPPM gid: %s", e)

    return {
        "connected": bool(link),
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": link.get("spreadsheet_url") if link else None,
        "oppm_sheet_gid": oppm_sheet_gid,
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
    from domains.oppm.sheet_executor import execute_sheet_actions

    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=True)
    service = await asyncio.to_thread(_build_sheets_service, credential_info)
    # Pass credential_info through so executor actions that need Drive (e.g.
    # upload_asset_to_drive, scaffold_oppm_form's matrix_image_asset path) can
    # build a Drive client lazily without re-resolving credentials.
    results = await asyncio.to_thread(execute_sheet_actions, service, spreadsheet_id, actions, sa_info=credential_info)
    success_count = sum(1 for r in results if r.get("success"))
    error_count = len(results) - success_count
    return {"results": results, "success_count": success_count, "error_count": error_count}


async def get_google_sheet_snapshot(
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """Read the current state of the linked OPPM Google Sheet for AI context.

    Returns a compact snapshot with:
    - cell values (formattedValue) for key regions
    - row heights, column widths
    - merged cell ranges
    - border styles per cell (simplified)
    """
    project = await _get_project_or_404(session, project_id, workspace_id)
    link = _extract_link(project.metadata_)
    if not link:
        raise HTTPException(status_code=404, detail="No Google Sheet linked for this project")

    spreadsheet_id = link.get("spreadsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Linked Google Sheet is missing its spreadsheet ID")

    credential_info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    if not credential_info:
        raise HTTPException(status_code=503, detail="Google Sheets service account not configured")

    service = await asyncio.to_thread(_build_sheets_service, credential_info)

    # Read the full OPPM sheet with grid data (values + formatting)
    try:
        response = await asyncio.to_thread(
            service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=["'OPPM'!A1:AL120"],
                includeGridData=True,
                fields=(
                    "sheets.properties.sheetId,"
                    "sheets.properties.title,"
                    "sheets.properties.gridProperties.rowCount,"
                    "sheets.properties.gridProperties.columnCount,"
                    "sheets.merges,"
                    "sheets.data.rowData.values.formattedValue,"
                    "sheets.data.rowData.values.effectiveFormat.backgroundColor,"
                    "sheets.data.rowData.values.effectiveFormat.borders,"
                    "sheets.data.rowData.values.effectiveFormat.textFormat.bold,"
                    "sheets.data.rowData.values.effectiveFormat.textFormat.fontSize,"
                    "sheets.data.rowData.values.effectiveFormat.textFormat.foregroundColor,"
                    "sheets.data.rowData.values.note"
                ),
            ).execute
        )
    except HttpError as e:
        if e.resp.status == 400:
            # Sheet tab 'OPPM' does not exist yet — return empty snapshot instead of 500
            logger.warning("get_google_sheet_snapshot: OPPM tab not found in %s: %s", spreadsheet_id, e)
            return {"cells": [], "merges": [], "row_count": 0, "col_count": 0, "sheet_exists": False}
        raise

    sheets = response.get("sheets", [])
    if not sheets:
        return {"cells": [], "merges": [], "row_count": 0, "col_count": 0, "sheet_exists": False}

    sheet = sheets[0]
    properties = sheet.get("properties", {})
    grid = properties.get("gridProperties", {})
    data = sheet.get("data", [])
    first_data = data[0] if data else {}
    row_data = first_data.get("rowData", [])
    merges = sheet.get("merges", [])

    # Build compact cell map: only non-empty / formatted cells
    cells: list[dict] = []
    for row_idx, row in enumerate(row_data):
        values = row.get("values", [])
        for col_idx, cell in enumerate(values):
            formatted = cell.get("formattedValue", "")
            note = cell.get("note", "")
            ef = cell.get("effectiveFormat", {})
            bg = ef.get("backgroundColor", {})
            borders = ef.get("borders", {})
            tf = ef.get("textFormat", {})

            # Skip truly empty cells with no formatting
            is_empty = not formatted and not note
            has_bg = any(v for v in bg.values() if v)
            has_border = any(borders.get(side, {}).get("style") for side in ("top", "bottom", "left", "right"))
            is_bold = tf.get("bold", False)
            font_size = tf.get("fontSize")
            fg = tf.get("foregroundColor", {})
            has_fg = any(v for v in fg.values() if v)

            if is_empty and not has_bg and not has_border and not is_bold and not font_size and not has_fg:
                continue

            cell_entry: dict[str, Any] = {"r": row_idx + 1, "c": col_idx + 1}
            if formatted:
                cell_entry["v"] = formatted[:200]  # truncate long values
            if note:
                cell_entry["n"] = note[:100]
            if has_bg:
                cell_entry["bg"] = _rgb_to_hex(bg)
            if has_border:
                cell_entry["b"] = _summarize_borders(borders)
            if is_bold:
                cell_entry["bold"] = True
            if font_size:
                cell_entry["fs"] = font_size
            if has_fg:
                cell_entry["fg"] = _rgb_to_hex(fg)
            cells.append(cell_entry)

    # Summarize merges
    merge_ranges: list[str] = []
    for m in merges:
        r = m.get("range", {})
        srow = r.get("startRowIndex", 0) + 1
        erow = r.get("endRowIndex", 0)
        scol = r.get("startColumnIndex", 0) + 1
        ecol = r.get("endColumnIndex", 0)
        merge_ranges.append(f"{_col_letter(scol)}{srow}:{_col_letter(ecol)}{erow}")

    return {
        "spreadsheet_id": spreadsheet_id,
        "sheet_title": properties.get("title", "OPPM"),
        "max_row": int(grid.get("rowCount") or 120),
        "max_col": int(grid.get("columnCount") or 52),
        "merge_ranges": merge_ranges,
        "cells": cells,
        "cell_count": len(cells),
    }


def _rgb_to_hex(color: dict[str, float]) -> str:
    """Convert {red, green, blue} 0-1 floats to #RRGGBB."""
    r = int(round(color.get("red", 0) * 255))
    g = int(round(color.get("green", 0) * 255))
    b = int(round(color.get("blue", 0) * 255))
    return f"#{r:02X}{g:02X}{b:02X}"


def _summarize_borders(borders: dict[str, Any]) -> str:
    """Summarize border state as a compact string, e.g. 'T:S1#CCC|B:S1#CCC'."""
    parts: list[str] = []
    side_map = {"top": "T", "bottom": "B", "left": "L", "right": "R"}
    for side, abbrev in side_map.items():
        b = borders.get(side, {})
        style = b.get("style", "")
        if style:
            color = b.get("color", {})
            hex_color = _rgb_to_hex(color) if color else "#000000"
            width = b.get("width", 1)
            parts.append(f"{abbrev}:{style[0]}{width}{hex_color}")
    return "|".join(parts) if parts else ""


def _col_letter(col_index: int) -> str:
    """Convert 1-based column index to letters (1→A, 27→AA)."""
    letters = ""
    while col_index > 0:
        col_index, rem = divmod(col_index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
