"""Domain router aggregator — mounts all workspace service domains."""

from fastapi import APIRouter

from domains.auth.router import router as auth_router
from domains.workspace.router import router as workspaces_router
from domains.project.router import router as projects_router
from domains.task.router import router as tasks_router
from domains.oppm.router import router as oppm_router
from domains.agile.router import router as agile_router
from domains.waterfall.router import router as waterfall_router
from domains.notification.router import router as notifications_router
from domains.dashboard.router import router as dashboard_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router, tags=["auth"])
router.include_router(workspaces_router, tags=["workspaces"])
router.include_router(projects_router, tags=["projects"])
router.include_router(tasks_router, tags=["tasks"])
router.include_router(oppm_router, tags=["oppm"])
router.include_router(agile_router, tags=["agile"])
router.include_router(waterfall_router, tags=["waterfall"])
router.include_router(notifications_router, tags=["notifications"])
router.include_router(dashboard_router, tags=["dashboard"])
