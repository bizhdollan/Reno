from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.api.v1.chat import router as chat_router


app = FastAPI(
    title="RenovationTech API",
    description="AI-Powered Renovation Estimation & Marketplace",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to RenovationTech API",
        "status": "running",
        "version": "0.1.0"
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
