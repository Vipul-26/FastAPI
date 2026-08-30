"""FastAPI application entrypoint.

Uvicorn loads this module as: uvicorn app.main:app
"""

from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers

# Create the FastAPI app (title and debug come from .env via Settings)
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

register_exception_handlers(app)

# Mount versioned API routers under /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Simple root endpoint — returns the app name."""
    return {
        "message": settings.app_name
    }


@app.get("/health")
async def health():
    """Health check — useful for Docker/Kubernetes probes."""
    return {
        "status": "ok",
        "environment": settings.app_env,
    }
