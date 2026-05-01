"""Domain router aggregator — mounts all intelligence service domains."""

from fastapi import APIRouter

from domains.chat.router import router as chat_router
from domains.rag.router import router as rag_router
from domains.analysis.router import router as analysis_router
from domains.models.router import router as models_router

router = APIRouter(prefix="/v1")

router.include_router(chat_router, tags=["chat"])
router.include_router(rag_router, tags=["rag"])
router.include_router(analysis_router, tags=["analysis"])
router.include_router(models_router, tags=["models"])
