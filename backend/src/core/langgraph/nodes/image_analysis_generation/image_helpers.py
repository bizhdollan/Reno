"""
Image helper functions for loading and converting images.
"""

import base64
import os
from pathlib import Path

import httpx

from src.core.logger import get_logger

logger = get_logger(__name__)


# Configuration
IMAGES_DIR = Path("images")
GENERATED_IMAGES_DIR = IMAGES_DIR / "generated"
# Base URL for API requests (for fetching from /api/v1/files/... endpoints)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


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

        # API endpoint path (e.g., /api/v1/files/{filename})
        # This fetches from GCS via our endpoint, which generates fresh signed URLs
        if image_url.startswith("/api/v1/files/"):
            try:
                # Construct full URL to our own API endpoint
                # The endpoint will redirect to a fresh signed URL from GCS
                full_url = f"{API_BASE_URL}{image_url}"
                logger.debug(f"[load_image_as_base64] Fetching from API endpoint: {full_url}")

                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    try:
                        response = await client.get(full_url)
                        response.raise_for_status()
                    except httpx.TimeoutException:
                        logger.error(f"[load_image_as_base64] Timeout fetching from API: {full_url}")
                        raise httpx.HTTPError(f"Timeout fetching image from API endpoint: {image_url}")
                    except httpx.HTTPStatusError as e:
                        logger.error(f"[load_image_as_base64] HTTP {e.response.status_code} fetching from API: {full_url}")
                        raise httpx.HTTPError(f"Failed to fetch image from API (HTTP {e.response.status_code}): {image_url}")
                    except httpx.RequestError as e:
                        logger.error(f"[load_image_as_base64] Network error fetching from API: {e}")
                        raise httpx.HTTPError(f"Network error fetching image from API: {e}")

                    content = response.content

                    if not content:
                        raise ValueError(f"Image from API endpoint is empty: {image_url}")

                    # Extract content type
                    content_type = response.headers.get("content-type", "image/jpeg")
                    if ";" in content_type:
                        content_type = content_type.split(";")[0]

                    # Validate it's an image
                    if not content_type.startswith("image/"):
                        raise ValueError(f"API endpoint does not return an image (content-type: {content_type}): {image_url}")

                    b64 = base64.b64encode(content).decode("utf-8")
                    logger.debug(f"[load_image_as_base64] Successfully loaded image from API endpoint (size: {len(content)} bytes)")
                    return f"data:{content_type};base64,{b64}"

            except httpx.HTTPError:
                raise
            except ValueError:
                raise
            except Exception as e:
                logger.exception(f"[load_image_as_base64] Unexpected error fetching from API endpoint: {e}")
                raise httpx.HTTPError(f"Failed to fetch image from API endpoint: {e}")

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
