"""
RenovationTech API - Main Application

FastAPI application with:
- Chat endpoint for LangGraph conversation flow
- File upload endpoint for images
- Static file serving for uploaded/generated images
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from src.api.v1.chat import router as chat_router
from src.api.v1.files import router as files_router


app = FastAPI(
    title="RenovationTech API",
    description="AI-Powered Renovation Estimation & Marketplace",
    version="0.1.0",
)

# CORS - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router)
app.include_router(files_router)

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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "renovationtech-backend"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )