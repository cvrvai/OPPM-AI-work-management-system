"""Project file routes — upload, download, list, delete project files (workspace-scoped)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from shared.schemas.common import SuccessResponse
from domains.project_files.service import (
    list_project_files,
    upload_project_file,
    get_project_file,
    delete_project_file,
)

router = APIRouter()


@router.get("/workspaces/{workspace_id}/projects/{project_id}/files")
async def list_project_files_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_project_files(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/files", status_code=201)
async def upload_project_file_route(
    project_id: str,
    file: UploadFile = File(...),
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await upload_project_file(
        session, ws.workspace_id, project_id, ws.member_id, ws.user.id, file
    )


@router.get("/workspaces/{workspace_id}/projects/{project_id}/files/{file_id}")
async def download_project_file_route(
    project_id: str,
    file_id: str,
    download: bool = False,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    record = await get_project_file(session, file_id, ws.workspace_id)
    return FileResponse(
        path=record.storage_path,
        filename=record.original_name,
        media_type=record.content_type,
        content_disposition_type="attachment" if download else "inline",
    )


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/files/{file_id}")
async def delete_project_file_route(
    project_id: str,
    file_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_project_file(session, file_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()
