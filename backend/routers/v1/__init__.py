"""v1 API routers — workspace-scoped, authenticated endpoints."""

from fastapi import APIRouter
from routers.v1 import (
    auth,
    workspaces,
    projects,
    tasks,
    oppm,
    git,
    ai,
    notifications,
    dashboard,
)

router = APIRouter(prefix="/v1")

router.include_router(auth.router, tags=["auth"])
router.include_router(workspaces.router, tags=["workspaces"])
router.include_router(projects.router, tags=["projects"])
router.include_router(tasks.router, tags=["tasks"])
router.include_router(oppm.router, tags=["oppm"])
router.include_router(git.router, tags=["git"])
router.include_router(ai.router, tags=["ai"])
router.include_router(notifications.router, tags=["notifications"])
router.include_router(dashboard.router, tags=["dashboard"])
