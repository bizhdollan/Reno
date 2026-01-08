"""
SSE (Server-Sent Events) endpoint for real-time context gathering progress.

Streams events during:
- Image analysis (extracting materials, colors, etc.)
- Tavily search (queries executed, sources found)
- Context ready notification

Frontend connects to this endpoint after image upload to show
Claude Code-style streaming progress.
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

from src.core.services.event_broadcaster import subscribe, has_subscribers

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])


async def event_generator(project_id: str) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a project.

    Yields events in SSE format:
        event: event_type
        data: json_payload

    """
    try:
        async for event in subscribe(project_id, timeout=120.0):
            event_type = event.get("type", "message")
            event_data = json.dumps(event.get("data", {}))

            # SSE format: event type line, data line, empty line
            yield f"event: {event_type}\ndata: {event_data}\n\n"

    except Exception as e:
        # Send error event before closing
        error_data = json.dumps({"error": str(e)})
        yield f"event: error\ndata: {error_data}\n\n"


@router.get("/{project_id}")
async def stream_context_progress(project_id: str):
    """
    Stream context gathering progress events for a project.

    This endpoint uses Server-Sent Events (SSE) to stream real-time
    progress updates during image analysis and Tavily search.

    Event types:
    - analysis_start: Image analysis begins
    - analysis_progress: Analysis step completed
    - analysis_complete: All images analyzed
    - search_start: Tavily search begins
    - search_query: Search query executed
    - search_result: Search result found
    - search_complete: Search finished
    - context_ready: All context gathering complete
    - heartbeat: Keep-alive ping
    - error: Error occurred
    - timeout: Stream timeout

    Args:
        project_id: Project ID (PRJ-XXXXX format)

    Returns:
        StreamingResponse with SSE content type
    """
    if not project_id:
        raise HTTPException(status_code=400, detail="Project ID required")

    return StreamingResponse(
        event_generator(project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/{project_id}/status")
async def check_stream_status(project_id: str):
    """
    Check if a project has active stream subscribers.

    Useful for debugging and checking connection status.
    """
    has_subs = await has_subscribers(project_id)
    return {
        "project_id": project_id,
        "has_subscribers": has_subs
    }
