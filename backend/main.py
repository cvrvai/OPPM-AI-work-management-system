from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from routers import projects, tasks, git, ai, dashboard

settings = get_settings()

app = FastAPI(
    title="OPPM AI Work Management",
    version="1.0.0",
    description="AI-powered One Page Project Manager backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(git.router, prefix="/api", tags=["git"])
app.include_router(ai.router, prefix="/api", tags=["ai"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "oppm-ai-backend"}
