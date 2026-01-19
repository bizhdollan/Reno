"""
Image helper functions for loading and converting images.
"""

import base64
from pathlib import Path

import httpx

from src.core.logger import get_logger

logger = get_logger(__name__)


# Configuration
IMAGES_DIR = Path("images")
GENERATED_IMAGES_DIR = IMAGES_DIR / "generated"


async def load_image_as_base64(image_url: str) -> str:
    """
    Load an image and convert to base64 data URL for VLM.

    Args:
        image_url: URL or path to the image (data URL, /api/v1/files/..., or http(s)://)

    Returns:
        Base64-encoded data URL string

    Raises:
        ValueError: If image_url format is unsupported or invalid
        FileNotFoundError: If local file does not exist
        httpx.HTTPError: If remote image cannot be fetched
        IOError: If file cannot be read
    """
    try:
        if not image_url:
            raise ValueError("Image URL cannot be empty")

        # Already a data URL - return as-is
        if image_url.startswith("data:image"):
            logger.debug(f"[load_image_as_base64] Using existing data URL (length: {len(image_url)})")
            return image_url

        # Local file path
        if image_url.startswith("/api/v1/files/"):
            try:
                filename = image_url.replace("/api/v1/files/", "")
                file_path = IMAGES_DIR / filename

                # Security check - prevent path traversal
                if ".." in str(filename) or filename.startswith("/"):
                    raise ValueError(f"Invalid filename: {filename}")

                if not file_path.exists():
                    logger.error(f"[load_image_as_base64] File not found: {file_path}")
                    raise FileNotFoundError(f"Image file not found: {file_path}")

                # Check file is actually an image by extension
                ext = file_path.suffix.lower()
                mime_types = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                }

                if ext not in mime_types:
                    raise ValueError(f"Unsupported file extension: {ext}")

                mime_type = mime_types[ext]

                # Read file with proper error handling
                try:
                    with open(file_path, "rb") as f:
                        content = f.read()

                    if not content:
                        raise IOError(f"File is empty: {file_path}")

                    b64 = base64.b64encode(content).decode("utf-8")
                    logger.debug(f"[load_image_as_base64] Successfully loaded local file: {filename}")
                    return f"data:{mime_type};base64,{b64}"

                except IOError as e:
                    logger.error(f"[load_image_as_base64] Failed to read file {file_path}: {e}")
                    raise IOError(f"Failed to read image file: {e}")

            except (ValueError, FileNotFoundError, IOError):
                raise
            except Exception as e:
                logger.exception(f"[load_image_as_base64] Unexpected error loading local file: {e}")
                raise ValueError(f"Failed to load local image: {e}")

        # Remote URL
        if image_url.startswith("http://") or image_url.startswith("https://"):
            try:
                logger.debug(f"[load_image_as_base64] Fetching remote image: {image_url}")

                async with httpx.AsyncClient(timeout=30.0) as client:
                    try:
                        response = await client.get(image_url)
                        response.raise_for_status()
                    except httpx.TimeoutException:
                        logger.error(f"[load_image_as_base64] Timeout fetching image: {image_url}")
                        raise httpx.HTTPError(f"Timeout fetching image from {image_url}")
                    except httpx.HTTPStatusError as e:
                        logger.error(f"[load_image_as_base64] HTTP {e.response.status_code} fetching image: {image_url}")
                        raise httpx.HTTPError(f"Failed to fetch image (HTTP {e.response.status_code}): {image_url}")
                    except httpx.RequestError as e:
                        logger.error(f"[load_image_as_base64] Network error fetching image: {e}")
                        raise httpx.HTTPError(f"Network error fetching image: {e}")

                    content = response.content

                    if not content:
                        raise ValueError(f"Remote image is empty: {image_url}")

                    # Extract content type
                    content_type = response.headers.get("content-type", "image/jpeg")
                    if ";" in content_type:
                        content_type = content_type.split(";")[0]

                    # Validate it's an image
                    if not content_type.startswith("image/"):
                        raise ValueError(f"URL does not point to an image (content-type: {content_type}): {image_url}")

                    b64 = base64.b64encode(content).decode("utf-8")
                    logger.debug(f"[load_image_as_base64] Successfully loaded remote image (size: {len(content)} bytes)")
                    return f"data:{content_type};base64,{b64}"

            except httpx.HTTPError:
                raise
            except ValueError:
                raise
            except Exception as e:
                logger.exception(f"[load_image_as_base64] Unexpected error fetching remote image: {e}")
                raise httpx.HTTPError(f"Failed to fetch remote image: {e}")

        # Unsupported format
        logger.error(f"[load_image_as_base64] Unsupported URL format: {image_url}")
        raise ValueError(f"Unsupported image URL format: {image_url}")

    except Exception as e:
        # Log and re-raise all exceptions
        logger.error(f"[load_image_as_base64] Error loading image from {image_url}: {e}")
        raise


def get_placeholder_image_url() -> str:
    """
    Get URL for placeholder renovation preview image.

    Returns:
        URL string for placeholder image
    """
    placeholder_url = "/api/v1/files/placeholder-renovation.jpg"
    logger.debug(f"[get_placeholder_image_url] Returning placeholder: {placeholder_url}")
    return placeholder_url
