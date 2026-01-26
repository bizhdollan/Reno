"""
File Upload API for handling image uploads.

Saves files to Google Cloud Storage.
Returns file_id and URL for use in chat messages.
"""

import os
import uuid
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from google.cloud import storage
from google.cloud.exceptions import NotFound

from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["files"])

# Configuration
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
# Size limits
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 25 * 1024 * 1024  # 25MB

# GCS Configuration
# Priority: GCS_BUCKET_NAME > GCS_BUCKET_DEV > GCS_BUCKET_PROD
GCS_BUCKET_NAME = os.getenv(
    "GCS_BUCKET_NAME", 
    os.getenv("GCS_BUCKET_DEV", os.getenv("GCS_BUCKET_PROD", "usebowerbird-images-dev"))
)
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account-key.json")

# Initialize GCS client
def get_gcs_client() -> storage.Client:
    """Get GCS client with service account credentials.
    
    Priority:
    1. GOOGLE_APPLICATION_CREDENTIALS_JSON env var (for Docker/Cloud Run)
    2. Service account key file path (for local dev)
    3. Default credentials (for Cloud Run with attached service account)
    """
    try:
        import json
        from google.oauth2 import service_account
        
        # Option 1: Service account JSON as environment variable (for Docker/Cloud Run)
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            try:
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                logger.info("[get_gcs_client] Using GOOGLE_APPLICATION_CREDENTIALS_JSON from environment")
                return storage.Client(credentials=credentials, project=credentials_info.get('project_id'))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"[get_gcs_client] Failed to parse GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
        
        # Option 2: Service account key file path
        if os.path.isabs(GOOGLE_APPLICATION_CREDENTIALS):
            credentials_path = GOOGLE_APPLICATION_CREDENTIALS
        else:
            # Relative to backend directory
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            credentials_path = os.path.join(backend_dir, GOOGLE_APPLICATION_CREDENTIALS)
        
        if os.path.exists(credentials_path):
            logger.info(f"[get_gcs_client] Using service account key file: {credentials_path}")
            return storage.Client.from_service_account_json(credentials_path)
        
        # Option 3: Default credentials (for Cloud Run with attached service account or local gcloud auth)
        # Cloud Run automatically provides credentials via the attached service account
        logger.info("[get_gcs_client] Using default credentials (Cloud Run service account or local gcloud auth)")
        return storage.Client()
        
    except Exception as e:
        logger.error(f"[get_gcs_client] Failed to initialize GCS client: {e}", exc_info=True)
        raise

def get_bucket() -> storage.Bucket:
    """Get GCS bucket instance."""
    client = get_gcs_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket


class FileUploadResponse(BaseModel):
    """Response for single file upload."""
    file_id: str
    filename: str
    url: str
    size: int
    content_type: str
    file_type: str  # NEW: 'image' or 'video'


class MultiFileUploadResponse(BaseModel):
    """Response for multiple file uploads."""
    files: List[FileUploadResponse]


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return Path(filename).suffix.lower()

def get_file_type(extension: str) -> str:
    """Determine if file is image or video."""
    if extension in IMAGE_EXTENSIONS:
        return "image"
    elif extension in VIDEO_EXTENSIONS:
        return "video"
    return "unknown"

def get_max_size_for_extension(extension: str) -> int:
    """Get max file size based on extension."""
    if extension in IMAGE_EXTENSIONS:
        return MAX_IMAGE_SIZE
    elif extension in VIDEO_EXTENSIONS:
        return MAX_VIDEO_SIZE
    return MAX_IMAGE_SIZE

def generate_file_id() -> str:
    """Generate unique file ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{timestamp}_{unique_id}"


def get_media_type(extension: str) -> str:
    """Get proper MIME type for file extension."""
    media_types = {
        # Images
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        # Videos
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    return media_types.get(extension, "application/octet-stream")

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)) -> FileUploadResponse:
    """
    Upload a single image or video file to Google Cloud Storage.
    
    Images: Max 10MB
    Videos: Max 25MB
    
    Returns file_id and URL that can be used in chat messages.
    """
    try:
        # Validate extension
        extension = get_file_extension(file.filename or "")
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        
        # Get file type and size limit
        file_type = get_file_type(extension)
        max_size = get_max_size_for_extension(extension)
        
        # Read file content
        content = await file.read()
        
        # Validate size
        if len(content) > max_size:
            max_size_mb = max_size // (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"{file_type.capitalize()} file too large. Maximum size: {max_size_mb}MB"
            )
        
        # Generate file ID and GCS path
        file_id = generate_file_id()
        gcs_path = f"images/{file_id}{extension}"
        
        # Determine content type
        content_type = file.content_type or get_media_type(extension)
        
        # Upload to GCS
        bucket = get_bucket()
        blob = bucket.blob(gcs_path)
        blob.content_type = content_type
        blob.upload_from_string(content, content_type=content_type)
        
        # Return relative URL instead of signed URL
        # This ensures images always work - the /files/{filename} endpoint generates fresh signed URLs on-demand
        # No expiration issues, and images remain accessible indefinitely
        relative_url = f"/api/v1/files/{file_id}{extension}"
        
        logger.info(f"[upload_file] Successfully uploaded {file.filename} to GCS: {gcs_path}")
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename or f"{file_id}{extension}",
            url=relative_url,
            size=len(content),
            content_type=content_type,
            file_type=file_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[upload_file] Error uploading file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )

@router.post("/upload/multiple", response_model=MultiFileUploadResponse)
async def upload_multiple_files(
    files: List[UploadFile] = File(...)
) -> MultiFileUploadResponse:
    """
    Upload multiple image/video files at once to Google Cloud Storage.
    
    Images: Max 10MB each
    Videos: Max 25MB each
    
    Returns list of file_ids and URLs.
    """
    results = []
    bucket = get_bucket()
    
    try:
        for file in files:
            # Validate extension
            extension = get_file_extension(file.filename or "")
            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                )
            
            # Get file type and size limit
            file_type = get_file_type(extension)
            max_size = get_max_size_for_extension(extension)
            
            # Read and validate size
            content = await file.read()
            if len(content) > max_size:
                max_size_mb = max_size // (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=f"{file_type.capitalize()} '{file.filename}' too large. Maximum: {max_size_mb}MB"
                )
            
            # Generate ID and GCS path
            file_id = generate_file_id()
            gcs_path = f"images/{file_id}{extension}"
            
            # Determine content type
            content_type = file.content_type or get_media_type(extension)
            
            # Upload to GCS
            blob = bucket.blob(gcs_path)
            blob.content_type = content_type
            blob.upload_from_string(content, content_type=content_type)
            
            # Return relative URL instead of signed URL
            # This ensures images always work - the /files/{filename} endpoint generates fresh signed URLs on-demand
            relative_url = f"/api/v1/files/{file_id}{extension}"
            
            results.append(FileUploadResponse(
                file_id=file_id,
                filename=file.filename or f"{file_id}{extension}",
                url=relative_url,
                size=len(content),
                content_type=content_type,
                file_type=file_type
            ))
        
        logger.info(f"[upload_multiple_files] Successfully uploaded {len(results)} files to GCS")
        return MultiFileUploadResponse(files=results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[upload_multiple_files] Error uploading files: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload files: {str(e)}"
        )

@router.get("/files/{filename}")
async def get_file(filename: str):
    """
    Redirect to GCS signed URL for uploaded files.
    
    This endpoint generates a signed URL and redirects to it.
    Signed URLs are time-limited and more secure than public URLs.
    """
    try:
        # Try to find the file in GCS
        bucket = get_bucket()
        
        # Try images/ prefix first
        gcs_path = f"images/{filename}"
        blob = bucket.blob(gcs_path)
        
        if not blob.exists():
            # Try generated/ prefix
            gcs_path = f"images/generated/{filename}"
            blob = bucket.blob(gcs_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Generate signed URL (valid for 24 hours)
        # This endpoint is the primary way to access images, so longer expiration is fine
        # Fresh URLs are generated on each request, so images always work
        expiration = datetime.utcnow() + timedelta(hours=24)  # 24 hours from now
        signed_url = blob.generate_signed_url(
            expiration=expiration,
            method='GET'
        )
        
        return RedirectResponse(url=signed_url, status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_file] Error retrieving file {filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve file: {str(e)}"
        )


@router.delete("/files/{file_id}")
async def delete_file(file_id: str) -> dict:
    """
    Delete an uploaded file from Google Cloud Storage.
    
    Searches for the file with any allowed extension and deletes it.
    """
    try:
        bucket = get_bucket()
        deleted = False
        
        for ext in ALLOWED_EXTENSIONS:
            gcs_path = f"images/{file_id}{ext}"
            blob = bucket.blob(gcs_path)
            
            if blob.exists():
                blob.delete()
                deleted = True
                logger.info(f"[delete_file] Deleted file from GCS: {gcs_path}")
                break
        
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {"message": "File deleted successfully", "file_id": file_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[delete_file] Error deleting file {file_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )



# === Generated Images ===

class GeneratedImageResponse(BaseModel):
    """Response for generated/placeholder image."""
    file_id: str
    url: str


@router.get("/generated/placeholder", response_model=GeneratedImageResponse)
async def get_placeholder_image() -> GeneratedImageResponse:
    """
    Get the placeholder renovation preview image.
    
    Used when actual image generation is disabled.
    """
    try:
        bucket = get_bucket()
        gcs_path = "images/placeholder-renovation.jpg"
        blob = bucket.blob(gcs_path)
        
        if not blob.exists():
            raise HTTPException(
                status_code=404, 
                detail="Placeholder image not found. Please upload 'placeholder-renovation.jpg' to GCS bucket."
            )
        
        # Return relative URL - the endpoint generates fresh signed URLs on-demand
        relative_url = "/api/v1/files/placeholder-renovation.jpg"
        
        return GeneratedImageResponse(
            file_id="placeholder",
            url=relative_url
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_placeholder_image] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve placeholder image: {str(e)}"
        )


@router.post("/generated/save", response_model=GeneratedImageResponse)
async def save_generated_image(file: UploadFile = File(...)) -> GeneratedImageResponse:
    """
    Save an AI-generated image to Google Cloud Storage.
    
    This endpoint is for saving images generated by AI models.
    """
    try:
        extension = get_file_extension(file.filename or ".jpg")
        if extension not in ALLOWED_EXTENSIONS:
            extension = ".jpg"
        
        content = await file.read()
        
        file_id = f"gen_{generate_file_id()}"
        gcs_path = f"images/generated/{file_id}{extension}"
        
        # Upload to GCS
        bucket = get_bucket()
        blob = bucket.blob(gcs_path)
        content_type = file.content_type or get_media_type(extension)
        blob.content_type = content_type
        blob.upload_from_string(content, content_type=content_type)
        
        # Return relative URL instead of signed URL
        # This ensures images always work - the /files/generated/{filename} endpoint generates fresh signed URLs on-demand
        relative_url = f"/api/v1/files/generated/{file_id}{extension}"
        
        logger.info(f"[save_generated_image] Saved generated image to GCS: {gcs_path}")
        
        return GeneratedImageResponse(
            file_id=file_id,
            url=relative_url
        )
    except Exception as e:
        logger.error(f"[save_generated_image] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save generated image: {str(e)}"
        )


@router.get("/files/generated/{filename}")
async def get_generated_file(filename: str):
    """
    Redirect to GCS signed URL for generated images.
    
    Signed URLs are time-limited and more secure than public URLs.
    """
    try:
        bucket = get_bucket()
        gcs_path = f"images/generated/{filename}"
        blob = bucket.blob(gcs_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Generated file not found")
        
        # Generate signed URL (valid for 1 hour for temporary access)
        expiration = datetime.utcnow() + timedelta(hours=1)  # 1 hour from now
        signed_url = blob.generate_signed_url(
            expiration=expiration,
            method='GET'
        )
        
        return RedirectResponse(url=signed_url, status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_generated_file] Error retrieving {filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generated file: {str(e)}"
        )