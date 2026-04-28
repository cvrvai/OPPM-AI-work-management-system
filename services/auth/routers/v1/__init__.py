"""v1 router aggregator — auth service."""

from fastapi import APIRouter
from routers.v1 import auth

router = APIRouter(prefix="/v1")
router.include_router(auth.router, tags=["auth"])
