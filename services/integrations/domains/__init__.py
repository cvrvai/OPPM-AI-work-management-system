"""Domain router aggregator — mounts all integrations service domains."""

from fastapi import APIRouter

from domains.github.router import router as github_router

router = APIRouter(prefix="/v1")

router.include_router(github_router, tags=["github"])
