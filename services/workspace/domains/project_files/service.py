"""Project file service — business logic for file upload, download, list, delete."""

import logging
import os
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from domains.project.service import get_project
from domains.project_files.repository import ProjectFileRepository
from domains.notification.repository import AuditRepository
from shared.models.project_file import ProjectFile

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


def _get_storage_dir() -> Path:
    """Return the uploads storage directory, creating it if needed."""
    base = Path(os.environ.get("UPLOADS_DIR", "./uploads"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_filename(name: str) -> str:
    """Sanitize original filename for safe storage."""
    import re
    base = os.path.basename(name)
    safe = re.sub(r"[^\w\-.]", "_", base)
    return safe[:200] or "file"


async def list_project_files(session: AsyncSession, project_id: str, workspace_id: str) -> dict:
    """List all files for a project."""
    await get_project(session, project_id, workspace_id)
    repo = ProjectFileRepository(session)
    items = await repo.find_by_project(project_id)
    return {"items": items, "total": len(items)}


async def upload_project_file(
    session: AsyncSession,
    workspace_id: str,
    project_id: str,
    member_id: str,
    user_id: str,
    file: UploadFile,
) -> dict:
    """Save uploaded file to disk and record metadata in DB."""
    await get_project(session, project_id, workspace_id)

    content = await file.read()
    size = len(content)
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)} MB limit")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '{content_type}' not allowed")

    storage_dir = _get_storage_dir()
    safe_name = _sanitize_filename(file.filename or "upload")
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = storage_dir / unique_name

    try:
        file_path.write_bytes(content)
    except OSError as exc:
        logger.error("Failed to write file %s: %s", file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to save file") from exc

    repo = ProjectFileRepository(session)
    audit = AuditRepository(session)
    record = await repo.create({
        "workspace_id": workspace_id,
        "project_id": project_id,
        "file_name": unique_name,
        "original_name": safe_name,
        "file_size": size,
        "content_type": content_type,
        "storage_path": str(file_path),
        "uploaded_by": member_id,
    })
    await audit.log(workspace_id, user_id, "create", "project_file", str(record.id))
    return record


async def get_project_file(session: AsyncSession, file_id: str, workspace_id: str) -> ProjectFile:
    """Get a single file record by ID, verifying workspace scope."""
    repo = ProjectFileRepository(session)
    record = await repo.find_by_id(file_id)
    if not record or str(record.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="File not found")
    return record


async def delete_project_file(session: AsyncSession, file_id: str, workspace_id: str, user_id: str) -> bool:
    """Delete a file from disk and DB."""
    repo = ProjectFileRepository(session)
    audit = AuditRepository(session)
    record = await repo.find_by_id(file_id)
    if not record or str(record.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove from disk
    try:
        Path(record.storage_path).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to delete file %s: %s", record.storage_path, exc)

    await repo.delete_by_id(file_id)
    await audit.log(workspace_id, user_id, "delete", "project_file", file_id)
    return True
