"""
OCR-fill router — two-stage pipeline:
  Stage 1: gemma4:31b-cloud (Ollama vision) scans the uploaded form image
  Stage 2: existing workspace Ollama model maps OCR output → OPPM schema

POST /workspaces/{workspace_id}/projects/{project_id}/ai/ocr-fill
  Body: multipart/form-data
    file     : image (PNG/JPEG/WEBP), PDF, or XLSX (Google Sheet export) of the OPPM form
    model_id : (optional) workspace AI model UUID to use for Stage 2 fill
"""

import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_workspace_context, WorkspaceContext
from shared.database import get_session
from domains.analysis.schemas import OcrFillResponse
from domains.analysis.ocr_service import extract_text_from_upload, fill_from_ocr
from infrastructure.llm.base import ProviderUnavailableError

logger = logging.getLogger(__name__)
router = APIRouter()

# 20 MB upload limit
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_ALLOWED_MIME_PREFIXES = (
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "application/pdf",
    # Google Sheet downloaded as XLSX
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
)


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/ai/ocr-fill",
    response_model=OcrFillResponse,
    summary="Two-stage OCR → AI OPPM form fill",
    description=(
        "Stage 1: gemma4:31b-cloud reads the form (image, PDF, or XLSX from Google Sheet) "
        "and extracts raw text + field structure. "
        "Stage 2: the workspace's existing Ollama model maps the OCR output "
        "to the standard OPPM fill schema."
    ),
)
async def ocr_fill_route(
    project_id: str,
    file: UploadFile = File(..., description="OPPM form image (PNG/JPEG/WEBP), PDF, or XLSX"),
    model_id: str | None = Form(None, description="Workspace AI model UUID for Stage 2 (optional)"),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
) -> OcrFillResponse:
    # ── Validate upload ───────────────────────────────────────────────────────
    content_type = (file.content_type or "").lower().split(";")[0].strip()

    # Also sniff magic bytes for XLSX (browser may send as octet-stream)
    file_bytes = await file.read()
    is_xlsx_magic = file_bytes[:4] == b"PK\x03\x04"

    if not any(content_type.startswith(p) for p in _ALLOWED_MIME_PREFIXES) and not is_xlsx_magic:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{content_type}'. "
                "Please upload a PNG, JPEG, WEBP image, PDF, or XLSX spreadsheet."
            ),
        )

    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(file_bytes) // 1024} KB). Limit is 20 MB.",
        )

    logger.info(
        "OCR-fill: project=%s workspace=%s file=%s size=%d bytes mime=%s",
        project_id, ws.workspace_id, file.filename, len(file_bytes), content_type,
    )

    # ── Stage 1: OCR with gemma4:31b-cloud ───────────────────────────────────
    try:
        ocr_result = await extract_text_from_upload(
            file_bytes=file_bytes,
            mime_type=content_type,
        )
    except ProviderUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=f"OCR model (gemma4:31b-cloud) is unavailable: {e.reason}",
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # ── Stage 2: Fill with workspace Ollama model ─────────────────────────────
    try:
        result = await fill_from_ocr(
            ocr_result=ocr_result,
            session=session,
            project_id=project_id,
            workspace_id=ws.workspace_id,
            model_id=model_id,
        )
    except ProviderUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Fill model is unavailable: {e.reason}",
        ) from e

    return result
