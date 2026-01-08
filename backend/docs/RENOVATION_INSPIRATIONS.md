# Renovation Inspirations Feature

## Overview

The Renovation Inspirations feature automatically retrieves location-based and project-type-specific design ideas, materials, and trends when a user provides their project basics (zip code and project type). This information is stored in the database for later use when generating suggestions or images.

**NEW: Hybrid Evidence-Based Approach**

The system now uses a hybrid approach combining:
1. **Evidence-based data sources** (when available):
   - US Census ACS: Demographics, housing age, budget indicators
   - NWS API: Climate data for design considerations
   - Tavily API: Web search for design trends with citations and confidence scores
2. **LLM synthesis**: Transforms structured data into comprehensive inspirations
3. **Fallback**: LLM-only approach when data sources unavailable

This provides more credible, evidence-backed recommendations with source citations.

## How It Works

### 1. User Flow

1. User provides project basics:
   - Project title (e.g., "Kitchen Remodel")
   - Project type (e.g., "kitchen", "bathroom", "bedroom")
   - US zip code (e.g., "90210")

2. When all three fields are collected, the system:
   - Validates the US zip code format
   - Extracts location information (city, state) from the zip code
   - **Starts a background task** to retrieve renovation inspirations
   - User can continue with their workflow without waiting

3. The background task:
   - Uses LLM to generate location-specific and project-type-specific inspiration data
   - Stores the data in the `projects.renovation_inspirations` JSONB column
   - Runs asynchronously without blocking the user

### 2. Database Schema

**New Field Added to `projects` Table:**

```sql
renovation_inspirations JSONB NULL
```

**Migration:**
- File: `alembic/versions/445948cb44c0_add_renovation_inspirations_to_projects.py`
- Adds the JSONB column to store inspiration data

**Data Structure:**

```json
{
  "location": {
    "city": "Beverly Hills",
    "state": "California",
    "state_code": "CA"
  },
  "project_type": "kitchen",
  "design_styles": [
    {
      "name": "Modern Luxury",
      "description": "Sleek lines, minimalistic designs...",
      "popularity": "high"
    }
  ],
  "materials": [
    {
      "category": "flooring",
      "options": [
        {
          "name": "Hardwood Oak",
          "description": "Premium hardwood...",
          "tier": "luxury"
        }
      ]
    }
  ],
  "climate_considerations": [
    "High humidity resistance recommended",
    "Energy-efficient cooling options"
  ],
  "color_palettes": [
    {
      "name": "Coastal Calm",
      "colors": ["white", "light blue", "sand"],
      "description": "For beach-inspired spaces"
    }
  ],
  "layout_trends": [
    {
      "name": "Open Concept",
      "description": "Combines kitchen with living space",
      "best_for": "Modern homes"
    }
  ],
  "fixtures_features": [
    {
      "name": "Smart Faucets",
      "description": "Touch-activated water control",
      "tier": "mid"
    }
  ],
  "regional_notes": "Additional regional considerations...",
  "_metadata": {
    "zip_code": "90210",
    "location": {...},
    "project_type": "kitchen",
    "retrieved_at": "12345.67"
  }
}
```

## Implementation Details

### 3. New Services

#### `location_service.py`

**Functions:**
- `validate_us_zip_code(zip_code: str) -> bool`
  - Validates US zip code format (5-digit or 5+4 format)
  - Examples: "90210", "10001-1234"

- `extract_location_from_zip(zip_code: str) -> Optional[Dict]`
  - Uses LLM to extract city, state, and state code from zip code
  - Returns: `{"city": "...", "state": "...", "state_code": "...", "zip_code": "..."}`

- `get_location_display(location_data: Dict) -> str`
  - Formats location data for display
  - Returns: "Los Angeles, CA"

#### `renovation_inspiration_service.py`

**Functions:**
- `retrieve_renovation_inspirations(project_type: str, zip_code: str, location_data: Optional[Dict]) -> Optional[Dict]`
  - Retrieves comprehensive renovation ideas using LLM
  - Generates location-specific and project-type-specific suggestions
  - Returns structured inspiration data (see schema above)

- `store_renovation_inspirations(project_id: UUID, inspirations: Dict) -> bool`
  - Stores inspiration data in the database
  - Updates `projects.renovation_inspirations` field

- `retrieve_and_store_inspirations_background(project_id: UUID, project_type: str, zip_code: str) -> None`
  - Async background task that combines retrieval and storage
  - Runs without blocking the main workflow

- `start_inspiration_retrieval_background(project_id: UUID, project_type: str, zip_code: str) -> None`
  - Non-blocking function to start the background task
  - Called from `project_basics_node`

### 4. Integration in LangGraph

**Modified File:** `src/core/langgraph/nodes/project_basics.py`

**Integration Point:**
- After all project basics are collected (title, type, zip code)
- Before showing the summary to the user
- Lines 219-244

**Flow:**
```python
if not missing:  # All fields collected
    # Get final values
    final_zip = updates.get("zip_code") or state.get("zip_code")
    final_type = updates.get("project_type") or state.get("project_type")
    project_id_token = state.get("project_id")

    # Start background task
    if project_id_token and final_zip and final_type:
        if validate_us_zip_code(final_zip):
            # Query database for project UUID
            project = db.query(Project).filter(Project.token == project_id_token).first()
            if project:
                # Start async background task
                start_inspiration_retrieval_background(
                    project_id=project.id,
                    project_type=final_type,
                    zip_code=final_zip
                )

    # Show summary and continue (user doesn't wait)
    response = "Here's what I have: ..."
```

## Usage

### Integration with Suggestion Generation

**Automatic Integration:**

When users ask for renovation suggestions (e.g., "suggest me", "what do you recommend?"), the system now automatically:

1. **Retrieves inspirations** from the database with smart wait logic:
   - If inspirations exist → uses them immediately
   - If project is new (<60s old) → waits up to 30 seconds for background task
   - If background task failed → proceeds without inspirations

2. **Generates location-aware suggestions** using the inspirations:
   - Design styles popular in that location
   - Materials commonly used by contractors in that area
   - Color palettes trending in that region
   - Climate-specific considerations
   - Regional notes and best practices

**Example Flow:**
```
User: "suggest me"
System:
  → Checks database for inspirations
  → If not available and project is new, waits up to 30s
  → Generates 2-3 suggestions using regional data
  → Suggests "Modern Minimalism" (popular in NYC) with specific materials
```

### For Developers

**Accessing Inspiration Data:**

```python
from src.db.database import SessionLocal
from src.db.models import Project

db = SessionLocal()
project = db.query(Project).filter(Project.token == "PRJ-ABC123").first()

if project.renovation_inspirations:
    # Access the data
    design_styles = project.renovation_inspirations.get("design_styles", [])
    materials = project.renovation_inspirations.get("materials", [])
    location = project.renovation_inspirations.get("location", {})
```

**Using Wait Logic in Code:**

```python
from src.core.langgraph.nodes.image_analysis_generation.node import get_renovation_inspirations_with_wait

# Retrieve with automatic retry
inspirations = await get_renovation_inspirations_with_wait(
    project_id_token="PRJ-ABC123",
    max_wait_seconds=30.0  # Optional, defaults to 30s
)
```

**Manual Retrieval:**

```python
from src.core.services.renovation_inspiration_service import retrieve_renovation_inspirations

inspirations = await retrieve_renovation_inspirations(
    project_type="kitchen",
    zip_code="90210"
)
```

## Testing

All tests pass successfully:

1. **Zip Code Validation** ✓
   - Valid formats: "90210", "10001-1234"
   - Invalid formats: "1234", "abcde", ""

2. **Location Extraction** ✓
   - Correctly extracts city and state from zip codes
   - Example: "90210" → Beverly Hills, CA

3. **Inspiration Retrieval** ✓
   - Generates comprehensive, structured inspiration data
   - Location-specific and project-type-specific

4. **Database Storage** ✓
   - Successfully stores and retrieves from database
   - Data persists across sessions

## Implementation Details (Updated)

### Suggestion Generation Flow

When a user requests suggestions:

1. **Intent Detection**: System detects `ask_suggestions` intent
2. **Inspiration Retrieval**: `get_renovation_inspirations_with_wait()` is called
   - Checks database for existing inspirations
   - If not found and project is recent, waits up to 30s
   - Returns inspirations or None
3. **Context Building**: If inspirations exist, formats them into context:
   - Design styles with popularity ratings
   - Materials by category and tier
   - Climate considerations
   - Color palettes
   - Regional notes
4. **LLM Generation**: `generate_expert_suggestions()` receives:
   - Project type and current state
   - User preferences
   - Expertise level
   - **Inspirations context** (new!)
5. **Response Formatting**: Suggestions are formatted and returned to user

### Code Locations

- **Inspiration retrieval**: `src/core/langgraph/nodes/image_analysis_generation/node.py:72-136`
- **Suggestion generation**: `src/core/langgraph/nodes/image_analysis_generation/intent_detection.py:221-295`
- **Prompt template**: `src/core/langgraph/prompts/suggestions.py:37-88`
- **Integration point**: `src/core/langgraph/nodes/image_analysis_generation/node.py:528-555`

## Hybrid Evidence-Based Approach (NEW)

### Data Sources

#### 1. US Census ACS (American Community Survey)
**Purpose:** Provides demographic and housing data at the ZIP Code Tabulation Area (ZCTA) level.

**Data Retrieved:**
- Median household income
- Median home value
- Median gross rent
- Owner vs renter occupancy rates
- Housing age distribution (year built)

**Derived Insights:**
- **Budget Tier**: `luxury`, `upper-mid`, or `mid` based on income and home values
- **Renovation Intensity**: `high`, `medium`, or `low` based on owner occupancy and housing age
- **Systems Upgrade Priority**: Based on percentage of pre-1960s housing
- **Likely Project Types**: Kitchen/bath renovations, layout modernization, energy upgrades, etc.

**Example Output:**
```json
{
  "budget_indicators": {
    "finish_tier": "luxury",
    "median_household_income": 125000,
    "median_home_value": 850000
  },
  "renovation_context": {
    "intensity": "high",
    "owner_occupancy_pct": 0.82,
    "housing_age_pre_1980_pct": 0.65,
    "likely_project_types": ["kitchen and bathroom renovations", "layout modernization"],
    "systems_upgrade_priority": "medium"
  }
}
```

#### 2. NWS (National Weather Service) API
**Purpose:** Provides climate data for design considerations.

**Data Retrieved:**
- Temperature range (7-day forecast)
- Weather patterns (rain, snow, heat, cold)

**Derived Insights:**
- Moisture-resistant finishes needed
- Cooling efficiency considerations
- Insulation and air sealing priorities

**Example Output:**
```json
{
  "climate": {
    "temp_range_f": {"min": 45, "max": 85},
    "considerations": [
      "Moisture-prone climate: prioritize ventilation and moisture-resistant finishes",
      "Hot climate: consider cooling efficiency and durable heat-friendly flooring"
    ]
  }
}
```

#### 3. Tavily API (Web Search)
**Purpose:** Discovers design trends, materials, and constraints with evidence and citations.

**Search Strategy:**
- Interior designer portfolios in the location
- Home renovation trends and before/after examples
- Building permit requirements
- Historic district guidelines
- ADU regulations

**Data Retrieved:**
- Popular design styles with confidence scores (0-1)
- Popular materials and finishes
- Permit requirements and constraints
- Official government sources

**Example Output:**
```json
{
  "design_trends": {
    "popular_styles": [
      {
        "name": "modern",
        "confidence": 1.0,
        "citations": [
          {
            "url": "https://example.com/portfolio",
            "title": "Beverly Hills Modern Kitchen Remodel",
            "snippet": "Sleek modern design with...",
            "is_official": false
          }
        ]
      }
    ],
    "popular_materials": [
      {
        "name": "quartz",
        "confidence": 0.95,
        "citations": [...]
      }
    ]
  },
  "constraints": {
    "signals": [
      {
        "name": "permit_required",
        "confidence": 0.85,
        "citations": [
          {
            "url": "https://cityofbeverlyhills.gov/permits",
            "title": "Building Permit Requirements",
            "is_official": true
          }
        ]
      }
    ],
    "official_sources": [...]
  }
}
```

### Implementation Files

#### New Service: `zip_structured_data_service.py`
**Location:** `src/core/services/zip_structured_data_service.py`

**Main Function:**
```python
async def get_zip_structured_data(
    zip_code: str,
    tavily_api_key: Optional[str] = None,
    year: int = 2023,
) -> Dict[str, Any]:
    """
    Fetch all structured data for a zip code.
    Returns: location, budget_indicators, renovation_context, climate, design_trends, constraints
    """
```

**Key Features:**
- Validates US zip codes (5-digit format)
- Fetches Census data with DNS fallback (handles api.census.gov connectivity issues)
- Derives actionable insights from raw demographic data
- Fetches climate essentials from NWS
- Runs Tavily searches for design trends and constraints
- Returns streamlined output optimized for LLM consumption (~16KB vs 100KB+ raw data)

#### Updated Service: `renovation_inspiration_service.py`
**Location:** `src/core/services/renovation_inspiration_service.py`

**Hybrid Approach Logic:**
```python
# 1. Check if Tavily API key available
tavily_api_key = os.getenv("TAVILY_API_KEY")

if HAS_STRUCTURED_DATA_SERVICE and tavily_api_key:
    # 2. Fetch structured evidence-based data
    structured_data = await get_zip_structured_data(zip_code, tavily_api_key)

    # 3. Transform to inspiration format using LLM
    inspirations = await transform_structured_data_to_inspirations(
        structured_data, project_type
    )

    if inspirations:
        return inspirations  # Evidence-based result with citations

# 4. Fallback to LLM-only approach
return await retrieve_llm_only_inspirations(...)
```

**New Function:**
```python
async def transform_structured_data_to_inspirations(
    structured_data: Dict[str, Any],
    project_type: str
) -> Optional[Dict[str, Any]]:
    """
    Transform structured data into inspiration format.
    Uses LLM with low temperature (0.3) for faithful transformation.
    Preserves citations and evidence sources in the output.
    """
```

### Test Suite

**Test File:** `tests/test_zip_claude.py`

**Test Coverage:**
- Zip code validation
- Place lookup (Zippopotam.us)
- Census ACS data fetching
- Design insights derivation
- Climate essentials (NWS)
- Full pipeline for multiple locations (Beverly Hills, NYC, McDonough GA)
- Output completeness check
- Citations presence verification
- Output size comparison

**Running Tests:**
```bash
cd backend
source .venv/bin/activate
python tests/test_zip_claude.py
```

**Expected Results:**
```
✓ PASS: Validate zip code format
✓ PASS: Place lookup from zip
✓ PASS: Fetch Census ACS data
✓ PASS: Derive design insights from ACS
✓ PASS: Fetch climate essentials from NWS
✓ PASS: Full pipeline for Beverly Hills (90210)
  Output size: 16.3KB
✓ PASS: Output completeness check
  All 22 required fields present
✓ PASS: Citations presence check
  Found 24 total citations across styles and materials
```

### Benefits of Hybrid Approach

1. **Evidence-Based Recommendations**
   - Census data provides objective budget tier classification
   - Housing age informs systems upgrade priorities
   - Climate data ensures appropriate material selection

2. **Source Citations**
   - Design trends include URLs to portfolios and articles
   - Constraint information links to official government sources
   - Users can verify claims and explore further

3. **Confidence Scores**
   - Each design trend has a confidence score (0-1)
   - Based on frequency of mentions and source quality
   - Helps prioritize the most relevant recommendations

4. **Cost Efficiency**
   - Reduces reliance on expensive LLM calls
   - Census and NWS data are free APIs
   - Tavily provides structured search results (cheaper than multiple LLM queries)

5. **Backward Compatibility**
   - Falls back to LLM-only approach if data sources unavailable
   - Maintains same output format
   - Existing code continues to work

### Configuration

**Required Environment Variables:**
```bash
# For evidence-based approach
TAVILY_API_KEY=tvly-dev-...  # Required for web discovery

# For LLM synthesis and fallback
LLM_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

**Without Tavily API Key:**
- System automatically falls back to LLM-only approach
- No web discovery or citations
- Still uses Census and NWS for budget/climate data

## Future Enhancements

Possible improvements:
1. ~~Cache location lookups to reduce LLM calls~~ ✓ Now using Zippopotam.us API
2. ~~Use a zip code API instead of LLM for location extraction~~ ✓ Implemented
3. ~~Add evidence-based data sources~~ ✓ Implemented (Census, NWS, Tavily)
4. Add more granular regional data (neighborhoods, design districts)
5. Support for international locations (currently US-only)
6. Periodic refresh of inspiration data (trends change over time)
7. Track suggestion quality metrics (user selection rates by region)
8. Cache Tavily search results to reduce API costs
9. Add user feedback loop to improve confidence scores over time

## Notes

- **Background Task:** The inspiration retrieval runs asynchronously and doesn't block the user
- **US Only:** Currently only supports US zip codes
- **Hybrid Powered:** Uses Census ACS + NWS + Tavily + LLM synthesis when available, falls back to LLM-only
- **Cost Tracking:** All LLM calls are logged with operation_type for cost tracking
- **Error Handling:** Failures in background task don't affect the main user flow
- **DNS Fallback:** Census API has DNS resolution fallback using curl + nslookup for reliability
