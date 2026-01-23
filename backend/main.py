"""
RenovationTech API - Main Application

FastAPI application with:
- Chat endpoint for LangGraph conversation flow
- File upload endpoint for images
- Static file serving for uploaded/generated images
- PostgreSQL database integration
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn
from sqlalchemy import text

# Initialize logging FIRST before other imports
from src.core.logger import setup_logging, get_logger
setup_logging()

logger = get_logger(__name__)

from src.api.v1.chat import router as chat_router
from src.api.v1.files import router as files_router
from src.api.v1.projects import router as projects_router
from src.api.v1.marketplace import router as marketplace_router
from src.api.v1.unlock import router as unlock_router
from src.api.v1.stream import router as stream_router
from src.db.database import engine, SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown"""
    # Startup
    logger.info("Application startup initiated")
    try:
        # Test database connection
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        logger.warning("Make sure PostgreSQL is running: docker-compose up -d")

    yield

    # Shutdown (cleanup if needed)
    logger.info("Application shutting down")


app = FastAPI(
    title="RenovationTech API",
    description="AI-Powered Renovation Estimation & Marketplace",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cisted-repletely-isabela.ngrok-free.dev","*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(projects_router)
app.include_router(marketplace_router)
app.include_router(unlock_router)
app.include_router(stream_router)

# Ensure images directory exists
IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
(IMAGES_DIR / "generated").mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to RenovationTech API",
        "status": "running",
        "version": "0.1.0",
        "endpoints": {
            "chat": "/api/v1/chat",
            "upload": "/api/v1/upload",
            "upload_multiple": "/api/v1/upload/multiple",
            "files": "/api/v1/files/{filename}",
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint with database connectivity"""
    db_status = "unknown"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
        logger.debug("Health check: Database connected")
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.warning(f"Health check: Database error - {e}")

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "renovationtech-backend",
        "database": db_status
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )