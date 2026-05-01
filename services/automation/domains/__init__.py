"""Domain router aggregator — mounts all automation service domains."""

from fastapi import APIRouter

from domains.registry.router import router as registry_router

router = APIRouter(prefix="/v1")

router.include_router(registry_router, tags=["registry"])
