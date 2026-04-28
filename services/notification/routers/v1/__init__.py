"""v1 router aggregator — notification service."""

from fastapi import APIRouter
from routers.v1 import notifications

router = APIRouter(prefix="/v1")
router.include_router(notifications.router, tags=["notifications"])
