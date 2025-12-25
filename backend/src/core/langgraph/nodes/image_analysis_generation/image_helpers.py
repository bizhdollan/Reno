"""
Image helper functions for loading and converting images.
"""

import base64
from pathlib import Path

import httpx


# Configuration
IMAGES_DIR = Path("images")
GENERATED_IMAGES_DIR = IMAGES_DIR / "generated"


async def load_image_as_base64(image_url: str) -> str:
    """Load an image and convert to base64 data URL for VLM."""
    if image_url.startswith("data:image"):
        return image_url

    if image_url.startswith("/api/v1/files/"):
        filename = image_url.replace("/api/v1/files/", "")
        file_path = IMAGES_DIR / filename

        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()

            ext = file_path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            mime_type = mime_types.get(ext, "image/jpeg")

            b64 = base64.b64encode(content).decode("utf-8")
            return f"data:{mime_type};base64,{b64}"
        else:
            raise FileNotFoundError(f"Image file not found: {file_path}")

    if image_url.startswith("http"):
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "image/jpeg")
            if ";" in content_type:
                content_type = content_type.split(";")[0]
            b64 = base64.b64encode(content).decode("utf-8")
            return f"data:{content_type};base64,{b64}"

    raise ValueError(f"Unsupported image URL format: {image_url}")


def get_placeholder_image_url() -> str:
    """Get URL for placeholder renovation preview image."""
    return "/api/v1/files/placeholder-renovation.jpg"
