"""
Renovation Inspiration Service.

Retrieves location-based renovation ideas and inspirations using:
1. Evidence-based data (Census, NWS, Tavily web search) when available
2. LLM synthesis for formatting and filling gaps
3. Falls back to LLM-only approach if data sources unavailable

Runs in background and stores results in the database for later use.
"""

import asyncio
import os
import time
import threading
from typing import Optional, Dict, Any
from uuid import UUID

from src.core.llm.provider import LLMProvider
from src.core.services.location_service import extract_location_from_zip, validate_us_zip_code
from src.db.database import SessionLocal
from src.db.models import Project

# Simple in-memory cache for inspiration data by zip code
# This avoids re-fetching for the same location
_inspiration_cache: Dict[str, Dict[str, Any]] = {}
_inspiration_cache_lock = threading.Lock()

# Import the new structured data service
try:
    from src.core.services.zip_structured_data_service import get_zip_structured_data
    HAS_STRUCTURED_DATA_SERVICE = True
except ImportError:
    HAS_STRUCTURED_DATA_SERVICE = False


RENOVATION_INSPIRATION_PROMPT = """You are a renovation design expert. Based on the location and project type, provide comprehensive renovation ideas and inspirations that contractors in this area commonly reference.

Location: {location_display}
City: {city}
State: {state}
Project Type: {project_type}

Provide detailed renovation ideas covering:
1. **Popular Design Styles** - What design styles are trending in {city}, {state} for {project_type} renovations?
2. **Local Materials & Finishes** - What materials and finishes are commonly used by contractors in {state}?
3. **Climate Considerations** - What design considerations should be made for {state}'s climate?
4. **Color Palettes** - What color schemes are popular in {city} for {project_type}s?
5. **Layout Trends** - Common layout patterns for {project_type}s in this region?
6. **Fixtures & Features** - Popular fixtures, appliances, or features for {project_type}s?
7. **Budget-Friendly Options** - Cost-effective materials/designs popular in this area?
8. **Luxury Options** - High-end materials/designs for premium renovations?

Return a comprehensive JSON response with this structure:
{{
    "location": {{
        "city": "{city}",
        "state": "{state}",
        "state_code": "{state_code}"
    }},
    "project_type": "{project_type}",
    "design_styles": [
        {{
            "name": "Style Name",
            "description": "Brief description",
            "popularity": "high/medium/low"
        }}
    ],
    "materials": [
        {{
            "category": "flooring/walls/countertops/etc",
            "options": [
                {{
                    "name": "Material Name",
                    "description": "Brief description",
                    "tier": "budget/mid/luxury"
                }}
            ]
        }}
    ],
    "climate_considerations": [
        "Consideration 1",
        "Consideration 2"
    ],
    "color_palettes": [
        {{
            "name": "Palette Name",
            "colors": ["color1", "color2", "color3"],
            "description": "When to use this palette"
        }}
    ],
    "layout_trends": [
        {{
            "name": "Layout Name",
            "description": "Description of layout",
            "best_for": "space size or preference"
        }}
    ],
    "fixtures_features": [
        {{
            "name": "Feature Name",
            "description": "Brief description",
            "tier": "budget/mid/luxury"
        }}
    ],
    "regional_notes": "Any other important regional considerations for {city}, {state}"
}}

Be specific to {city}, {state} and {project_type}. Provide practical, actionable inspiration that contractors would actually use.
"""


def format_structured_data_as_inspirations(
    structured_data: Dict[str, Any],
    project_type: str
) -> Dict[str, Any]:
    """
    Format structured data from zip_structured_data_service as inspirations.
    The contractor_knowledge IS the inspiration - no LLM transformation needed.

    Args:
        structured_data: Output from get_zip_structured_data() with contractor_knowledge
        project_type: Type of renovation

    Returns:
        Inspirations in a format ready for use in suggestions, image generation, cost estimation
    """
    location = structured_data.get("location", {})
    contractor_knowledge = structured_data.get("contractor_knowledge", {})
    budget_indicators = structured_data.get("budget_indicators", {})
    climate = structured_data.get("climate", {})
    renovation_context = structured_data.get("renovation_context", {})

    print(f"[renovation_inspiration] Formatting structured data for {project_type} in {location.get('city')}, {location.get('state_abbr')}")

    # Return the contractor knowledge directly - it's already in perfect format
    inspirations = {
        "location": location,
        "project_type": project_type,
        "budget_indicators": budget_indicators,
        "climate": climate,
        "renovation_context": renovation_context,
        "contractor_knowledge": contractor_knowledge,  # This is the gold - all the extracted knowledge
    }

    print(f"[renovation_inspiration] Formatted inspirations with {len(contractor_knowledge.get('popular_styles', []))} styles, {len(contractor_knowledge.get('popular_materials', []))} materials")
    return inspirations


async def retrieve_renovation_inspirations(
    project_type: str,
    zip_code: str,
    location_data: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieve renovation ideas and inspirations based on location and project type.

    Uses a hybrid approach:
    1. Try to get evidence-based data (Census, NWS, Tavily) if available
    2. Transform structured data using LLM for comprehensive inspirations
    3. Fall back to LLM-only approach if structured data unavailable

    Args:
        project_type: Type of renovation (kitchen, bathroom, etc.)
        zip_code: US zip code
        location_data: Optional pre-extracted location data. If not provided, will extract.

    Returns:
        Dictionary containing renovation inspirations or None if failed
    """
    # Validate zip code
    if not validate_us_zip_code(zip_code):
        print(f"[renovation_inspiration] Invalid zip code: {zip_code}")
        return None

    # Extract location if not provided
    if not location_data:
        location_data = await extract_location_from_zip(zip_code)

    if not location_data or not location_data.get('city'):
        print(f"[renovation_inspiration] Could not extract location for zip: {zip_code}")
        return None

    city = location_data.get('city', 'Unknown')
    state = location_data.get('state', 'Unknown')
    state_code = location_data.get('state_code', 'XX')
    location_display = f"{city}, {state_code}"

    print(f"[renovation_inspiration] Retrieving inspirations for {project_type} in {location_display}")

    # Try evidence-based approach first (if service available and Tavily API key present)
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if HAS_STRUCTURED_DATA_SERVICE and tavily_api_key:
        print(f"[renovation_inspiration] Using evidence-based approach (Census + NWS + Tavily)")
        try:
            # Get structured data
            structured_data = await get_zip_structured_data(
                zip_code=zip_code,
                tavily_api_key=tavily_api_key
            )

            if structured_data:
                # Format to inspiration format (no transformation needed)
                inspirations = format_structured_data_as_inspirations(
                    structured_data=structured_data,
                    project_type=project_type
                )

                print(f"[renovation_inspiration] Successfully retrieved evidence-based inspirations")
                return inspirations

        except Exception as e:
            print(f"[renovation_inspiration] Evidence-based approach failed: {e}, falling back to LLM-only")

    # Fall back to LLM-only approach
    print(f"[renovation_inspiration] Using LLM-only approach")

    # Use LLM to generate renovation inspirations
    provider = LLMProvider.for_llm()

    prompt = RENOVATION_INSPIRATION_PROMPT.format(
        location_display=location_display,
        city=city,
        state=state,
        state_code=state_code,
        project_type=project_type
    )

    try:
        response = await provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a renovation design expert with deep knowledge of regional design trends and contractor practices. Return only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,  # Some creativity for variety
            max_tokens=2000,  # Comprehensive response
            operation_type="renovation_inspiration"
        )

        # Parse JSON response
        import json

        # Clean up response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(line for line in lines if not line.startswith('```'))

        inspirations = json.loads(response.strip())

        print(f"[renovation_inspiration] Successfully retrieved LLM-only inspirations for {project_type} in {location_display}")
        return inspirations

    except Exception as e:
        print(f"[renovation_inspiration] Failed to retrieve inspirations: {e}")
        return None


async def store_renovation_inspirations(
    project_id: UUID,
    inspirations: Dict[str, Any]
) -> bool:
    """
    Store renovation inspirations in the database.

    Args:
        project_id: UUID of the project
        inspirations: Dictionary of renovation inspirations

    Returns:
        True if successful, False otherwise
    """
    try:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                print(f"[renovation_inspiration] Project not found: {project_id}")
                return False

            # Store inspirations
            project.renovation_inspirations = inspirations
            db.commit()

            print(f"[renovation_inspiration] Stored inspirations for project {project_id}")
            
            return True

        finally:
            db.close()

    except Exception as e:
        print(f"[renovation_inspiration] Failed to store inspirations: {e}")
        return False


async def retrieve_and_store_inspirations_background(
    project_id: UUID,
    project_type: str,
    zip_code: str
) -> None:
    """
    Background task to retrieve and store renovation inspirations.

    This runs asynchronously without blocking the main workflow.

    Args:
        project_id: UUID of the project
        project_type: Type of renovation
        zip_code: US zip code
    """
    start_time = time.time()
    try:
        print(f"[renovation_inspiration] 🚀 Background task started for project {project_id} | zip={zip_code}")

        # Check cache first
        with _inspiration_cache_lock:
            if zip_code in _inspiration_cache:
                cached_inspirations = _inspiration_cache[zip_code].copy()
                cached_inspirations['project_type'] = project_type
                success = await store_renovation_inspirations(project_id, cached_inspirations)
                elapsed = time.time() - start_time
                print(f"[renovation_inspiration] ✅ Used cached data for zip {zip_code} | took {elapsed:.2f}s")
                return

        # Extract location
        location_start = time.time()
        location_data = await extract_location_from_zip(zip_code)
        location_time = time.time() - location_start
        print(f"[renovation_inspiration] ⏱️  Location extraction: {location_time:.2f}s")

        if not location_data:
            print(f"[renovation_inspiration] ❌ Failed to extract location for zip {zip_code}")
            return

        # Retrieve inspirations
        inspire_start = time.time()
        inspirations = await retrieve_renovation_inspirations(
            project_type=project_type,
            zip_code=zip_code,
            location_data=location_data
        )
        inspire_time = time.time() - inspire_start
        print(f"[renovation_inspiration] ⏱️  Data retrieval: {inspire_time:.2f}s")

        if not inspirations:
            print(f"[renovation_inspiration] ❌ Failed to retrieve inspirations")
            return

        # Add metadata
        inspirations['_metadata'] = {
            'zip_code': zip_code,
            'location': location_data,
            'project_type': project_type,
            'retrieved_at': time.time(),
            'timing': {
                'location_extraction': location_time,
                'data_retrieval': inspire_time
            }
        }

        # Cache the result (without project_type since it's zip-specific)
        with _inspiration_cache_lock:
            cache_data = inspirations.copy()
            cache_data.pop('project_type', None)
            _inspiration_cache[zip_code] = cache_data
            print(f"[renovation_inspiration] 💾 Cached data for zip {zip_code}")

        # Store in database
        store_start = time.time()
        success = await store_renovation_inspirations(project_id, inspirations)
        store_time = time.time() - store_start

        elapsed = time.time() - start_time
        print(f"[renovation_inspiration] ⏱️  Database storage: {store_time:.2f}s")

        if success:
            print(f"[renovation_inspiration] ✅ Background task completed for project {project_id} | total time: {elapsed:.2f}s")
        else:
            print(f"[renovation_inspiration] ❌ Failed to store inspirations for project {project_id}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[renovation_inspiration] ❌ Background task failed after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()


def _run_async_in_thread(project_id: UUID, project_type: str, zip_code: str):
    """Run the async function in a new event loop in a separate thread."""
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            retrieve_and_store_inspirations_background(
                project_id=project_id,
                project_type=project_type,
                zip_code=zip_code
            )
        )
    finally:
        loop.close()


def start_inspiration_retrieval_background(
    project_id: UUID,
    project_type: str,
    zip_code: str
) -> None:
    """
    Start the background task to retrieve and store renovation inspirations.

    This is a TRULY non-blocking call that launches the task in a separate thread
    with its own event loop, so it doesn't interfere with FastAPI's main event loop.

    Args:
        project_id: UUID of the project
        project_type: Type of renovation
        zip_code: US zip code
    """
    # Start in a daemon thread so it doesn't block shutdown
    thread = threading.Thread(
        target=_run_async_in_thread,
        args=(project_id, project_type, zip_code),
        daemon=True,
        name=f"inspiration-{zip_code}"
    )
    thread.start()
    print(f"[renovation_inspiration] 🚀 Started background thread for project {project_id} | zip={zip_code}")


async def wait_for_inspirations(project_id: UUID, timeout: float = 25.0) -> Optional[Dict[str, Any]]:
    """
    Wait for inspiration data to be available for a project.

    This should be called by nodes that need inspiration data (suggestions, cost estimation).
    It will wait up to timeout seconds for the background task to complete.

    OPTIMIZED:
    - Reduced default timeout (25s) since parallel execution is faster
    - Progressive backoff: check frequently at first, less often later
    - Early return on first check if data already exists

    Args:
        project_id: UUID of the project
        timeout: Maximum time to wait in seconds (default: 25s)

    Returns:
        Inspiration data if available, None if timeout or not found
    """
    start_time = time.time()

    # Check immediately first (might be cached/already done)
    try:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project and project.renovation_inspirations:
                print(f"[renovation_inspiration] ⚡ Inspirations already available (instant)")
                return project.renovation_inspirations
        finally:
            db.close()
    except Exception as e:
        print(f"[renovation_inspiration] ⚠️  Initial check error: {e}")

    print(f"[renovation_inspiration] ⏳ Waiting for inspirations for project {project_id} (max {timeout}s)...")

    # Progressive backoff: start fast, slow down
    check_intervals = [0.3, 0.3, 0.5, 0.5, 1.0, 1.0, 2.0, 2.0, 3.0]  # Total: ~10.6s
    check_idx = 0

    while (time.time() - start_time) < timeout:
        # Use progressive interval or default to 3s after exhausting list
        interval = check_intervals[check_idx] if check_idx < len(check_intervals) else 3.0
        check_idx += 1

        await asyncio.sleep(interval)

        try:
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if project and project.renovation_inspirations:
                    elapsed = time.time() - start_time
                    print(f"[renovation_inspiration] ✅ Inspirations ready after {elapsed:.2f}s")
                    return project.renovation_inspirations
            finally:
                db.close()
        except Exception as e:
            print(f"[renovation_inspiration] ⚠️  Error checking inspirations: {e}")

    elapsed = time.time() - start_time
    print(f"[renovation_inspiration] ⏰ Timeout waiting for inspirations after {elapsed:.2f}s")
    return None
