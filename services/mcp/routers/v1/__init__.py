"""V1 router aggregator for MCP service — registers MCP sub-routers only."""

from fastapi import APIRouter
from routers.v1.mcp import router as mcp_router

router = APIRouter(prefix="/v1")
router.include_router(mcp_router, tags=["mcp"])
