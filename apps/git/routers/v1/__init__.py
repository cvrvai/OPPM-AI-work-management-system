"""v1 API routers — git service."""

from fastapi import APIRouter
from routers.v1 import git

router = APIRouter(prefix="/v1")

router.include_router(git.router, tags=["git"])
