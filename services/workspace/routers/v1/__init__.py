"""v1 router aggregator — workspace service."""

from fastapi import APIRouter
from routers.v1 import workspaces

router = APIRouter(prefix="/v1")
router.include_router(workspaces.router, tags=["workspaces"])
