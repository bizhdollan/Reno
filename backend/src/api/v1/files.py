"""
File Upload API for handling image uploads.

Saves files locally to /images directory (can be changed to S3 later).
Returns file_id and URL for use in chat messages.
"""

import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


router = APIRouter(prefix="/api/v1", tags=["files"])

# Configuration - can be moved to env/config later
UPLOAD_DIR = Path("images")  # Root level /images folder
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class FileUploadResponse(BaseModel):
    """Response for single file upload."""
    file_id: str
    filename: str
    url: str
    size: int
    content_type: str


class MultiFileUploadResponse(BaseModel):
    """Response for multiple file uploads."""
    files: List[FileUploadResponse]


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return Path(filename).suffix.lower()


def generate_file_id() -> str:
    """Generate unique file ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{timestamp}_{unique_id}"


def get_file_path(file_id: str, extension: str) -> Path:
    """Get full file path for a file ID."""
    return UPLOAD_DIR / f"{file_id}{extension}"


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)) -> FileUploadResponse:
    """
    Upload a single image file.
    
    Returns file_id and URL that can be used in chat messages.
    """
    # Validate extension
    extension = get_file_extension(file.filename or "")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Generate file ID and save
    file_id = generate_file_id()
    file_path = get_file_path(file_id, extension)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename or f"{file_id}{extension}",
        url=f"/api/v1/files/{file_id}{extension}",
        size=len(content),
        content_type=file.content_type or "image/jpeg"
    )


@router.post("/upload/multiple", response_model=MultiFileUploadResponse)
async def upload_multiple_files(
    files: List[UploadFile] = File(...)
) -> MultiFileUploadResponse:
    """
    Upload multiple image files at once.
    
    Returns list of file_ids and URLs.
    """
    results = []
    
    for file in files:
        # Validate extension
        extension = get_file_extension(file.filename or "")
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Read and validate size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Generate ID and save
        file_id = generate_file_id()
        file_path = get_file_path(file_id, extension)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        results.append(FileUploadResponse(
            file_id=file_id,
            filename=file.filename or f"{file_id}{extension}",
            url=f"/api/v1/files/{file_id}{extension}",
            size=len(content),
            content_type=file.content_type or "image/jpeg"
        ))
    
    return MultiFileUploadResponse(files=results)


@router.get("/files/{filename}")
async def get_file(filename: str) -> FileResponse:
    """
    Serve uploaded files.
    
    This endpoint serves files from the /images directory.
    """
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Security: ensure path doesn't escape upload directory
    if not file_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Determine media type
    extension = get_file_extension(filename)
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(extension, "application/octet-stream")
    
    return FileResponse(file_path, media_type=media_type)


@router.delete("/files/{file_id}")
async def delete_file(file_id: str) -> dict:
    """
    Delete an uploaded file.
    """
    # Find file with any extension
    for ext in ALLOWED_EXTENSIONS:
        file_path = get_file_path(file_id, ext)
        if file_path.exists():
            file_path.unlink()
            return {"deleted": True, "file_id": file_id}
    
    raise HTTPException(status_code=404, detail="File not found")


# === Generated Images ===

GENERATED_DIR = UPLOAD_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


class GeneratedImageResponse(BaseModel):
    """Response for generated/placeholder image."""
    file_id: str
    url: str


def get_placeholder_image_path() -> Path:
    """Get path to default placeholder image."""
    return UPLOAD_DIR / "placeholder-renovation.jpg"


@router.get("/generated/placeholder", response_model=GeneratedImageResponse)
async def get_placeholder_image() -> GeneratedImageResponse:
    """
    Get the placeholder renovation preview image.
    
    Used when actual image generation is disabled.
    """
    placeholder_path = get_placeholder_image_path()
    
    if not placeholder_path.exists():
        raise HTTPException(
            status_code=404, 
            detail="Placeholder image not found. Please add 'placeholder-renovation.jpg' to /images folder."
        )
    
    return GeneratedImageResponse(
        file_id="placeholder",
        url="/api/v1/files/placeholder-renovation.jpg"
    )


@router.post("/generated/save", response_model=GeneratedImageResponse)
async def save_generated_image(file: UploadFile = File(...)) -> GeneratedImageResponse:
    """
    Save an AI-generated image.
    
    This endpoint is for saving images generated by AI models.
    Can be used when actual image generation is implemented.
    """
    extension = get_file_extension(file.filename or ".jpg")
    if extension not in ALLOWED_EXTENSIONS:
        extension = ".jpg"
    
    content = await file.read()
    
    file_id = f"gen_{generate_file_id()}"
    file_path = GENERATED_DIR / f"{file_id}{extension}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return GeneratedImageResponse(
        file_id=file_id,
        url=f"/api/v1/files/generated/{file_id}{extension}"
    )


@router.get("/files/generated/{filename}")
async def get_generated_file(filename: str) -> FileResponse:
    """
    Serve generated images.
    """
    file_path = GENERATED_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Generated file not found")
    
    extension = get_file_extension(filename)
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    media_type = media_types.get(extension, "image/jpeg")
    
    return FileResponse(file_path, media_type=media_type)