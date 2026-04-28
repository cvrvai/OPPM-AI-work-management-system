"""v1 router aggregator — project service."""

from fastapi import APIRouter
from routers.v1 import projects, tasks

router = APIRouter(prefix="/v1")
router.include_router(projects.router, tags=["projects"])
router.include_router(tasks.router, tags=["tasks"])
