"""Internal API routes — called by other services, not exposed publicly.

Protected by X-Internal-API-Key header validation.
"""

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shared.auth import verify_internal_key
from services.ai_analyzer import analyze_commits

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal")


class AnalyzeCommitsRequest(BaseModel):
    commits: list[dict]
    project_id: str


@router.post("/analyze-commits", dependencies=[Depends(verify_internal_key)])
async def analyze_commits_route(data: AnalyzeCommitsRequest):
    """Trigger commit analysis — called by the git service after webhook processing."""
    logger.info(
        "Internal analyze-commits: project=%s count=%d",
        data.project_id, len(data.commits),
    )
    result = await analyze_commits(
        commit_events=data.commits,
        project_id=data.project_id,
    )
    return {"status": "ok", "result": result}
