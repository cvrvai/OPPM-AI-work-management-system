"""v1 API routers — core service (workspace, project, task, oppm, agile, waterfall, notification, dashboard, auth)."""

from fastapi import APIRouter
from routers.v1 import (
    auth,
    workspaces,
    projects,
    tasks,
    oppm,
    agile,
    waterfall,
    notifications,
    dashboard,
)

router = APIRouter(prefix="/v1")

router.include_router(auth.router, tags=["auth"])
router.include_router(workspaces.router, tags=["workspaces"])
router.include_router(projects.router, tags=["projects"])
router.include_router(tasks.router, tags=["tasks"])
router.include_router(oppm.router, tags=["oppm"])
router.include_router(agile.router, tags=["agile"])
router.include_router(waterfall.router, tags=["waterfall"])
router.include_router(notifications.router, tags=["notifications"])
router.include_router(dashboard.router, tags=["dashboard"])
