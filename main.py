"""
Main FastAPI application for PyAirtable Automation Services.
Consolidates file processing and workflow engine functionality.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from config import settings
from database import init_db, get_db
from routes.files import router as files_router
from routes.workflows import router as workflows_router
from services.scheduler import WorkflowScheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global scheduler
    
    # Startup
    logger.info("Starting PyAirtable Automation Services...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start scheduler
    scheduler = WorkflowScheduler()
    await scheduler.start()
    logger.info("Workflow scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")
    if scheduler:
        await scheduler.stop()
    logger.info("Services stopped")


# Create FastAPI application
app = FastAPI(
    title="PyAirtable Automation Services",
    description="Consolidated file processing and workflow automation service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for both services."""
    try:
        # Check database connection
        db = next(get_db())
        await db.execute("SELECT 1")
        
        # Check scheduler status
        scheduler_status = scheduler.is_running() if scheduler else False
        
        return {
            "status": "healthy",
            "service": "pyairtable-automation-services",
            "components": {
                "database": "healthy",
                "scheduler": "healthy" if scheduler_status else "unhealthy",
                "file_processor": "healthy",
                "workflow_engine": "healthy",
            },
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "PyAirtable Automation Services",
        "version": "1.0.0",
        "description": "Consolidated file processing and workflow automation service",
        "endpoints": {
            "files": "/files",
            "workflows": "/workflows",
            "health": "/health",
            "docs": "/docs",
        },
    }


# Include routers
app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(workflows_router, prefix="/workflows", tags=["workflows"])

# Legacy endpoints for backward compatibility
app.include_router(files_router, prefix="", tags=["files-legacy"])
app.include_router(workflows_router, prefix="", tags=["workflows-legacy"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )