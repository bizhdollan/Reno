"""
Event Broadcaster for Server-Sent Events (SSE)

Provides a simple pub/sub mechanism for broadcasting real-time progress events
during context gathering (image analysis, Tavily search, etc.).

Usage:
    # Publishing events
    await broadcast(project_id, "analysis_progress", {"step": "extracting_materials"})

    # Subscribing (in SSE endpoint)
    async for event in subscribe(project_id):
        yield {"event": event["type"], "data": json.dumps(event["data"])}
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID


@dataclass
class ContextEvent:
    """Represents a context gathering progress event."""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


# In-memory event queues by project ID
_event_queues: Dict[str, asyncio.Queue] = {}
_event_queue_lock = asyncio.Lock()


async def broadcast(
    project_id: str | UUID,
    event_type: str,
    data: Dict[str, Any]
) -> None:
    """
    Broadcast an event to all subscribers for a project.

    Args:
        project_id: Project ID (string or UUID)
        event_type: Type of event (e.g., "analysis_progress", "search_query")
        data: Event payload data
    """
    key = str(project_id)

    async with _event_queue_lock:
        if key in _event_queues:
            event = ContextEvent(event_type=event_type, data=data)
            await _event_queues[key].put(event.to_dict())
            print(f"[event_broadcaster] Broadcast {event_type} to {key}")


async def subscribe(
    project_id: str | UUID,
    timeout: float = 60.0
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Subscribe to events for a project.

    Yields events until "context_ready" is received or timeout.

    Args:
        project_id: Project ID to subscribe to
        timeout: Maximum time to wait for events (seconds)

    Yields:
        Event dictionaries with type and data
    """
    key = str(project_id)

    # Create queue for this subscription
    async with _event_queue_lock:
        if key not in _event_queues:
            _event_queues[key] = asyncio.Queue()

    queue = _event_queues[key]
    start_time = asyncio.get_event_loop().time()

    try:
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                # Timeout - yield final event
                yield {"type": "timeout", "data": {"elapsed": elapsed}}
                break

            try:
                # Wait for event with remaining timeout
                remaining = timeout - elapsed
                event = await asyncio.wait_for(queue.get(), timeout=min(remaining, 5.0))
                yield event

                # Check for terminal events
                if event.get("type") in ["context_ready", "error", "cancelled"]:
                    break

            except asyncio.TimeoutError:
                # No event received, send heartbeat
                yield {"type": "heartbeat", "data": {"elapsed": elapsed}}

    finally:
        # Cleanup queue when done
        async with _event_queue_lock:
            if key in _event_queues:
                del _event_queues[key]
                print(f"[event_broadcaster] Cleaned up queue for {key}")


async def has_subscribers(project_id: str | UUID) -> bool:
    """Check if a project has active subscribers."""
    key = str(project_id)
    async with _event_queue_lock:
        return key in _event_queues


# =============================================================================
# Convenience functions for common event types
# =============================================================================

async def emit_analysis_start(project_id: str | UUID, num_images: int) -> None:
    """Emit event when image analysis starts."""
    await broadcast(project_id, "analysis_start", {
        "total_images": num_images,
        "status": "started"
    })


async def emit_analysis_progress(
    project_id: str | UUID,
    image_index: int,
    total_images: int,
    step: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """Emit event for analysis progress."""
    await broadcast(project_id, "analysis_progress", {
        "image": image_index + 1,
        "total": total_images,
        "step": step,
        "details": details or {}
    })


async def emit_analysis_complete(
    project_id: str | UUID,
    categories_found: list[str],
    search_insights: Optional[Dict[str, Any]] = None
) -> None:
    """Emit event when analysis completes."""
    await broadcast(project_id, "analysis_complete", {
        "categories": categories_found,
        "search_insights": search_insights
    })


async def emit_search_start(project_id: str | UUID, queries: list[str]) -> None:
    """Emit event when Tavily search starts."""
    await broadcast(project_id, "search_start", {
        "total_queries": len(queries),
        "queries": queries
    })


async def emit_search_query(
    project_id: str | UUID,
    query: str,
    index: int,
    total: int
) -> None:
    """Emit event for each search query."""
    await broadcast(project_id, "search_query", {
        "query": query,
        "index": index + 1,
        "total": total
    })


async def emit_search_result(
    project_id: str | UUID,
    title: str,
    url: str,
    snippet: Optional[str] = None
) -> None:
    """Emit event for each search result found."""
    await broadcast(project_id, "search_result", {
        "title": title,
        "url": url,
        "snippet": snippet[:150] if snippet else None
    })


async def emit_search_complete(
    project_id: str | UUID,
    total_sources: int,
    styles_found: int,
    materials_found: int
) -> None:
    """Emit event when search completes."""
    await broadcast(project_id, "search_complete", {
        "total_sources": total_sources,
        "styles_found": styles_found,
        "materials_found": materials_found
    })


async def emit_context_ready(project_id: str | UUID) -> None:
    """Emit final event when all context gathering is complete."""
    await broadcast(project_id, "context_ready", {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat()
    })


async def emit_error(project_id: str | UUID, error: str) -> None:
    """Emit error event."""
    await broadcast(project_id, "error", {
        "message": error,
        "timestamp": datetime.utcnow().isoformat()
    })
