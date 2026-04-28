"""V1 router aggregator for AI service — registers AI-specific sub-routers only."""

from fastapi import APIRouter
from routers.v1.ai import router as ai_router
from routers.v1.ai_chat import router as ai_chat_router
from routers.v1.rag import router as rag_router
from routers.v1.oppm_fill import router as oppm_fill_router
from routers.v1.ocr_fill import router as ocr_fill_router
from routers.v1.graphql import router as graphql_router

router = APIRouter(prefix="/v1")
router.include_router(ai_router, tags=["ai-models"])
router.include_router(ai_chat_router, tags=["ai-chat"])
router.include_router(rag_router, tags=["rag"])
router.include_router(oppm_fill_router, tags=["oppm-fill"])
router.include_router(ocr_fill_router, tags=["ocr-fill"])
router.include_router(graphql_router, tags=["graphql"])
