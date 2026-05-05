"""
BizClone FastAPI Application
Main entry point for the voice-only AI assistant backend.
"""
# CRITICAL: Import pydantic patch FIRST to prevent recursion errors
from app.core import pydantic_patch  # noqa: F401

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.core.logging import get_logger
from app.core.middleware import setup_middleware
from app.api import health, n8n_webhooks, calendar, system
from app.api import admin as admin_ui
from app.api import reports as reports_api
from app.core.business_data_loader import load_business_data
from app.db.session import SessionLocal

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Load business data into database
    try:
        db = SessionLocal()
        summary = load_business_data(db)
        logger.info(
            "business_data_loaded",
            services=summary["services"],
            policies=summary["policies"],
            faqs=summary["faqs"]
        )
        db.close()
    except Exception as e:
        logger.error("business_data_load_failed", error=str(e))

    logger.info("application_started")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    # TODO: Close database connections (Step 3)
    # TODO: Close Redis connections (Step 3)
    
    logger.info("application_shutdown_complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered voice assistant for plumber business automation",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Mount static files
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Include routers
app.include_router(health.router)
app.include_router(n8n_webhooks.router)
app.include_router(calendar.router)
app.include_router(system.router)
app.include_router(admin_ui.router)
app.include_router(reports_api.router)


@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    """Root endpoint."""
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": "/docs" if settings.debug else "disabled",
        }
    )


@app.get("/info", tags=["Info"])
async def info() -> dict:
    """
    Get application information.
    
    Returns:
        dict: Application metadata
    """
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "business_name": settings.business_name,
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "starting_uvicorn_server",
        host=settings.host,
        port=settings.port,
    )
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )

