"""AI OPPM Fill router — generates suggested cell values for the OPPM spreadsheet header."""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_workspace_context, WorkspaceContext
from shared.database import get_session
from schemas.oppm_fill import OPPMFillRequest, OPPMFillResponse
from services.oppm_fill_service import fill_oppm

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/projects/{project_id}/ai/oppm-fill",
    response_model=OPPMFillResponse,
)
async def oppm_fill_route(
    project_id: str,
    data: OPPMFillRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Use project data + LLM to suggest OPPM spreadsheet header cell values."""
    result = await fill_oppm(
        session=session,
        project_id=project_id,
        workspace_id=ws.workspace_id,
        model_id=data.model_id,
    )
    return OPPMFillResponse(
        fills=result["fills"],
        tasks=result["tasks"],
        members=result["members"],
    )
