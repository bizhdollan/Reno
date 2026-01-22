# Simplified Multi-Agent Architecture for Renovation Estimation

## The Core Problem with the Previous Architecture Document

The previous architecture document described a complex system with:
- 5 fully autonomous agents with pub/sub messaging
- Shared knowledge graphs with event-driven coordination
- Conflict resolution protocols
- Parallel execution with supervisor orchestration

**This is overengineered for our needs.**

The reality is: we need 5 **capability domains** (not 5 autonomous agents), each with specialized **tools** that get called at predictable points in a deterministic flow.

---

## Fundamental Principle: Tools, Not Knowledge

**Wrong approach:** "The LLM knows about NYC building codes"
**Right approach:** "The LLM calls a `search_building_codes` tool that returns relevant sections"

**Wrong approach:** "The agent figures out when permits are needed"
**Right approach:** "The `check_permit_requirements` tool takes scope inputs and returns deterministic permit requirements"

**Every piece of external knowledge must come from a tool, not LLM training data.**

---

## The Five Capability Domains (Not Agents)

Think of these as **tool bundles** that get invoked at specific workflow stages:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY DOMAIN 1                               │
│                 Location & Property Intelligence                     │
│  ─────────────────────────────────────────────────────────────────  │
│  Tools:                                                              │
│  • validate_address(address) → normalized address + BBL              │
│  • get_property_data(bbl) → lot size, year built, building class    │
│  • get_dob_records(bbl) → permits, violations, filings              │
│  • get_market_data(zip) → price/sqft, trends, comps                 │
│  • get_climate_data(zip) → temperature, seasons                     │
│  • get_census_data(zip) → demographics, income levels               │
│  • search_local_trends(zip, room_type) → design trends, contractors │
│                                                                     │
│  WHEN CALLED: Project basics stage (background prefetch)             │
│  OUTPUT: property_context dict stored in DB                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY DOMAIN 2                               │
│                    Space Understanding                               │
│  ─────────────────────────────────────────────────────────────────   │
│  Tools:                                                              │
│  • analyze_image(image_url) → materials, colors, style, fixtures    │
│  • extract_measurements(image_url) → rough dimensions               │
│  • detect_structural_elements(image_url) → walls, beams, columns    │
│  • detect_mep_elements(image_url) → electrical, plumbing, hvac     │
│  • detect_hazards(image_url, year_built) → asbestos, lead risks    │
│  • assess_image_coverage(images[]) → what's missing, guidance      │
│                                                                      │
│  WHEN CALLED: After image upload                                     │
│  OUTPUT: space_analysis dict stored in DB                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY DOMAIN 3                               │
│                       The Designer                                   │
│  ─────────────────────────────────────────────────────────────────  │
│  Tools:                                                              │
│  • detect_user_intent(message) → intent classification              │
│  • extract_preferences(conversation) → style, budget, needs        │
│  • generate_suggestions(space_analysis, preferences) → 3-5 options │
│  • generate_image(original, specs, features_to_retain) → preview   │
│  • generate_variations(specs, count) → multiple options             │
│  • apply_feedback(current_image, feedback) → refined image          │
│                                                                      │
│  WHEN CALLED: During chat+canvas interaction                         │
│  OUTPUT: generated_images, design_decisions stored in DB             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY DOMAIN 4                               │
│                 The Architect (Compliance)                           │
│  ─────────────────────────────────────────────────────────────────  │
│  Tools:                                                              │
│  • check_permit_requirements(scope) → permits needed, PE/RA req     │
│  • validate_structural_change(wall_info) → safe/requires PE        │
│  • check_zoning_compliance(bbl, proposed_changes) → issues         │
│  • estimate_permit_timeline(permit_type) → weeks                   │
│  • search_building_codes(query) → relevant code sections            │
│  • flag_compliance_risks(design_decisions) → risk list             │
│                                                                      │
│  WHEN CALLED: After design decisions that trigger flags             │
│  OUTPUT: compliance_findings stored in DB                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY DOMAIN 5                               │
│                  The Contractor/Estimator                            │
│  ─────────────────────────────────────────────────────────────────  │
│  Tools:                                                              │
│  • calculate_quantities(space_analysis, design) → material list    │
│  • estimate_labor_hours(scope, trade) → hours by trade             │
│  • get_material_prices(materials, zip) → local pricing             │
│  • get_labor_rates(trades, zip) → hourly rates                     │
│  • generate_timeline(scope) → gantt-style schedule                 │
│  • format_estimate(all_data) → professional estimate document      │
│                                                                      │
│  WHEN CALLED: Cost estimation stage                                  │
│  OUTPUT: cost_estimate stored in DB                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Workflow: Linear with Tool Calls

**This maps directly to the current frontend:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND VIEW 1: Project Basics Form                                │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  User inputs:                                                        │
│  • Project title                                                     │
│  • Project type (kitchen, bathroom, etc.)                           │
│  • Address (NEW: full address, not just zip)                        │
│  • Budget range (optional)                                           │
│                                                                      │
│  BACKEND (Stage 1):                                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 1. Validate address → get BBL                                │    │
│  │ 2. Background fetch (parallel):                              │    │
│  │    • get_property_data(bbl)                                  │    │
│  │    • get_dob_records(bbl)                                    │    │
│  │    • get_market_data(zip)                                    │    │
│  │    • get_climate_data(zip)                                   │    │
│  │    • search_local_trends(zip, project_type)                  │    │
│  │ 3. Store property_context in DB                              │    │
│  │ 4. Return: ready for images                                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  User action: Upload images →                                        │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND VIEW 2: Chat + Canvas                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  BACKEND (Stage 2): Image Analysis                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ On image upload:                                             │    │
│  │ 1. analyze_image(url) → materials, colors, style, fixtures   │    │
│  │ 2. extract_measurements(url) → dimensions                    │    │
│  │ 3. detect_structural_elements(url) → walls, load-bearing?    │    │
│  │ 4. detect_mep_elements(url) → electrical, plumbing           │    │
│  │ 5. detect_hazards(url, year_built) → risks                   │    │
│  │ 6. Merge results → space_analysis                            │    │
│  │ 7. Store in DB, show to user                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  BACKEND (Stage 3): Design Conversation                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Loop (user sends message):                                   │    │
│  │ 1. detect_user_intent(message) → intent                      │    │
│  │                                                              │    │
│  │ If intent = "ask_question":                                  │    │
│  │   → Answer using space_analysis + property_context           │    │
│  │                                                              │    │
│  │ If intent = "request_suggestions":                           │    │
│  │   → generate_suggestions(space_analysis, preferences)        │    │
│  │   → Show 3-5 design options                                  │    │
│  │                                                              │    │
│  │ If intent = "generate_image":                                │    │
│  │   → check_permit_requirements(scope)  ← ARCHITECT TOOL       │    │
│  │   → If compliance_flags: warn user                           │    │
│  │   → generate_image(original, specs)                          │    │
│  │   → Store generated_image in DB                              │    │
│  │                                                              │    │
│  │ If intent = "modify_image":                                  │    │
│  │   → apply_feedback(current_image, feedback)                  │    │
│  │   → check_permit_requirements(new_scope)                     │    │
│  │   → Store updated image                                      │    │
│  │                                                              │    │
│  │ If intent = "confirm_design":                                │    │
│  │   → flag_compliance_risks(design_decisions)                  │    │
│  │   → Show final compliance summary                            │    │
│  │   → Move to cost estimation                                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  User action: Confirm design →                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND VIEW 3: Cost Estimation                                    │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  BACKEND (Stage 4): Estimation                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 1. calculate_quantities(space_analysis, design)              │    │
│  │ 2. estimate_labor_hours(scope, trade) for each trade         │    │
│  │ 3. get_material_prices(materials, zip)                       │    │
│  │ 4. get_labor_rates(trades, zip)                              │    │
│  │ 5. Add permit costs from compliance_findings                 │    │
│  │ 6. Generate 3-tier estimate (Low/Mid/Premium)                │    │
│  │ 7. generate_timeline(scope)                                  │    │
│  │ 8. format_estimate(all_data) → professional format           │    │
│  │ 9. Store cost_estimate in DB                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Show: Tier cards + detailed breakdown + timeline                    │
│  User action: Select tier → Project saved                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Differences from Previous Architecture

| Previous (Overengineered) | New (Practical) |
|---------------------------|-----------------|
| 5 autonomous agents with supervisor | 5 tool bundles called at specific points |
| Pub/sub event bus | Direct function calls |
| Shared knowledge graph (Redis) | PostgreSQL + simple state dict |
| Conflict resolution protocols | Deterministic tool sequencing |
| Agent-to-agent communication | Data flows through state/DB |
| Parallel agent execution | Parallel tool calls within stages |
| "Architect agent listens in background" | Compliance tools called at decision points |

---

## The Architect Domain: When and How

The "Architect" isn't a background listener. It's a set of validation tools called at specific trigger points:

```
TRIGGER POINTS (deterministic):

1. User mentions "removing wall" or "opening up space"
   → call: validate_structural_change(wall_info)
   → if load-bearing: warn + add PE requirement to scope

2. User confirms design with layout changes
   → call: check_permit_requirements(scope)
   → add permit costs/timeline to estimate

3. User asks about permits or regulations
   → call: search_building_codes(query)
   → return relevant code sections

4. Before final cost estimation
   → call: flag_compliance_risks(all_decisions)
   → show user summary of risks and requirements
```

**Trigger detection is simple keyword/intent matching, not LLM inference:**

```python
STRUCTURAL_TRIGGERS = [
    "remove wall", "knock down", "open up", "combine rooms",
    "load-bearing", "structural", "open floor plan"
]

PERMIT_TRIGGERS = [
    "permit", "legal", "code", "dob", "filing",
    "move plumbing", "move sink", "add bathroom"
]

def should_call_architect_tools(message: str) -> list[str]:
    """Deterministic trigger detection"""
    triggers = []
    message_lower = message.lower()

    if any(kw in message_lower for kw in STRUCTURAL_TRIGGERS):
        triggers.append("validate_structural_change")

    if any(kw in message_lower for kw in PERMIT_TRIGGERS):
        triggers.append("check_permit_requirements")

    return triggers
```

---

## Tool Implementation Strategy

### Phase 1: Wrapper Tools (Use What Exists)

Many "tools" are wrappers around existing services:

```python
# Location Intelligence Tools
async def get_property_data(bbl: str) -> dict:
    """Wrapper around existing location service + new property API"""
    # If we don't have property API yet, return minimal data
    return await property_service.fetch_or_default(bbl)

async def search_local_trends(zip_code: str, room_type: str) -> dict:
    """Wrapper around existing Tavily search with smart query"""
    query = f"{room_type} renovation trends {zip_code} NYC 2024"
    return await tavily_service.search(query)
```

### Phase 2: Data-Backed Tools

Add real data sources incrementally:

```python
# Currently: Returns "unknown" or estimates
# Future: NYC DOB API integration
async def get_dob_records(bbl: str) -> dict:
    if dob_api_available:
        return await dob_service.fetch_records(bbl)
    else:
        return {"status": "not_available", "note": "DOB integration pending"}

# Currently: Uses Tavily + LLM extraction
# Future: RSMeans API or local database
async def get_material_prices(materials: list, zip_code: str) -> dict:
    if rsmeans_available:
        return await rsmeans_service.get_prices(materials, zip_code)
    else:
        # Fallback: Use cached data + web search
        return await estimate_prices_from_search(materials, zip_code)
```

### Phase 3: Smart Tools (LLM + Data)

Combine LLM reasoning with factual data:

```python
async def check_permit_requirements(scope: dict) -> dict:
    """
    NOT: Ask LLM "do I need a permit?"
    YES: Use decision tree + code database
    """
    permits_needed = []

    # Rule-based checks (deterministic)
    if scope.get("structural_changes"):
        permits_needed.append({
            "type": "Alt-2",
            "reason": "Structural modification",
            "requires_pe": True,
            "code_reference": "NYC BC 106.1"
        })

    if scope.get("plumbing_relocation") and scope.get("plumbing_distance_ft", 0) > 10:
        permits_needed.append({
            "type": "Plumbing Permit",
            "reason": "Plumbing relocation > 10 ft",
            "code_reference": "NYC PC 106.2"
        })

    # Only use LLM to explain in natural language
    if permits_needed:
        explanation = await llm.generate(
            f"Explain why these permits are needed: {permits_needed}"
        )
        return {"permits": permits_needed, "explanation": explanation}

    return {"permits": [], "explanation": "No permits required for this scope"}
```

---

## Data Model (Minimal Extension to Current)

### Current Tables (Keep)
- `projects` - project metadata
- `conversation_states` - LangGraph state persistence
- `image_analyses` - per-image analysis results
- `generation_history` - generated images
- `llm_costs` - cost tracking

### New Tables (Add)

```sql
-- Property intelligence (Domain 1)
CREATE TABLE property_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    address TEXT,
    bbl TEXT,  -- Borough-Block-Lot
    property_data JSONB,  -- year_built, building_class, lot_size, etc.
    dob_records JSONB,    -- permits, violations, filings
    market_data JSONB,    -- price/sqft, trends
    climate_data JSONB,   -- from existing
    census_data JSONB,    -- from existing
    created_at TIMESTAMP DEFAULT NOW()
);

-- Compliance findings (Domain 4)
CREATE TABLE compliance_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    finding_type TEXT,  -- permit_required, structural_concern, code_violation
    severity TEXT,      -- info, warning, critical
    trigger TEXT,       -- what triggered this finding
    details JSONB,      -- permits needed, code references, etc.
    user_acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Detailed estimates (Domain 5)
CREATE TABLE cost_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    tier TEXT,  -- low, mid, premium
    quantities JSONB,     -- material quantities
    labor_hours JSONB,    -- hours by trade
    material_costs JSONB, -- itemized materials
    labor_costs JSONB,    -- itemized labor
    permit_costs JSONB,   -- from compliance_findings
    timeline JSONB,       -- gantt-style schedule
    total_cost DECIMAL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Mapping to Current Implementation

### What We Keep (Works Well)

| Current Component | Status | Notes |
|-------------------|--------|-------|
| LangGraph 4-stage flow | Keep | Add tool calls within stages |
| Project basics extraction | Keep | Add address validation tool |
| Image analysis VLM | Keep | Wrap as `analyze_image` tool |
| Feature extraction | Keep | This IS the Space Understanding tool |
| Hallucination prevention | Keep | Critical for quality |
| Tavily search | Keep | Wrap as location intelligence tools |
| Intent detection | Keep | Add compliance trigger detection |
| Image generation | Keep | Wrap as Designer tool |
| 3-tier cost estimation | Keep | Enhance with Contractor tools |
| SSE progress events | Keep | Frontend real-time updates |

### What We Modify

| Current Component | Modification |
|-------------------|--------------|
| Zip code only | → Full address with validation |
| 8 sub-states | → Simplify to 4-5 clear sub-states |
| State-heavy approach | → More DB-backed, lighter state |
| Implicit compliance | → Explicit tool calls with triggers |
| Generic cost estimates | → Quantity-based with local pricing |

### What We Add

| New Component | Priority | Dependency |
|---------------|----------|------------|
| Address validation tool | P1 | None |
| Property data tool (basic) | P1 | Address validation |
| Compliance trigger detection | P1 | None |
| Permit requirements tool | P2 | Compliance triggers |
| Structural validation tool | P2 | Space analysis |
| Quantity calculation tool | P2 | Space analysis |
| Material pricing tool | P3 | External API (RSMeans) |
| DOB records tool | P3 | External API (NYC DOB) |
| Timeline generation tool | P3 | Quantity calculation |

---

## Simplified State Structure

```python
class SimplifiedState(TypedDict):
    # Core (always present)
    messages: Annotated[list[BaseMessage], add_messages]
    project_id: str           # PRJ-XXXXXX for frontend
    internal_project_id: str  # UUID for DB

    # Stage tracking
    current_stage: Literal["basics", "analysis", "design", "estimation", "completed"]
    sub_state: Optional[str]  # within-stage tracking

    # Tool outputs (references to DB records)
    property_context_id: Optional[str]    # → property_context table
    space_analysis_ids: list[str]         # → image_analyses table
    compliance_findings_ids: list[str]    # → compliance_findings table
    cost_estimate_id: Optional[str]       # → cost_estimates table

    # Active design (for canvas)
    active_generation_id: Optional[str]   # → generation_history table

    # Flags
    awaiting_user_input: bool
    pending_action: Optional[str]  # what we're waiting for
```

**State is ~100 bytes, all real data in DB.**

---

## The Graph (Simplified)

```python
def build_simplified_graph():
    graph = StateGraph(SimplifiedState)

    # Nodes (one per stage)
    graph.add_node("basics", basics_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("design", design_node)
    graph.add_node("estimation", estimation_node)

    # Linear flow with conditional loops
    graph.set_entry_point("basics")

    graph.add_conditional_edges("basics", route_from_basics, {
        "continue": "basics",      # Still collecting info
        "analysis": "analysis",    # Got images, move on
    })

    graph.add_conditional_edges("analysis", route_from_analysis, {
        "continue": "analysis",    # Still analyzing
        "design": "design",        # Analysis complete
    })

    graph.add_conditional_edges("design", route_from_design, {
        "continue": "design",      # Iterating on design
        "analysis": "analysis",    # User wants to add images
        "estimation": "estimation" # Design confirmed
    })

    graph.add_conditional_edges("estimation", route_from_estimation, {
        "continue": "estimation",  # User asking questions
        "design": "design",        # User wants changes
        "complete": END
    })

    return graph.compile()
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
- [ ] Create tool interface pattern (base class, async, error handling)
- [ ] Implement address validation tool (using geocoding API)
- [ ] Wrap existing VLM analysis as `analyze_image` tool
- [ ] Wrap existing Tavily as location intelligence tools
- [ ] Create `property_context` table and service
- [ ] Add compliance trigger detection (keyword-based)

### Phase 2: Core Tools (Week 3-4)
- [ ] Implement `check_permit_requirements` tool (rule-based)
- [ ] Implement `validate_structural_change` tool
- [ ] Create `compliance_findings` table and service
- [ ] Integrate compliance tools into design flow
- [ ] Add compliance warnings to frontend

### Phase 3: Estimation Tools (Week 5-6)
- [ ] Implement `calculate_quantities` tool
- [ ] Implement `estimate_labor_hours` tool
- [ ] Create `cost_estimates` table and service
- [ ] Enhance cost estimation with quantity-based approach
- [ ] Add timeline visualization

### Phase 4: Data Integration (Week 7-8)
- [ ] Research NYC DOB API or scraping options
- [ ] Implement `get_dob_records` tool (basic version)
- [ ] Research RSMeans or alternative pricing data
- [ ] Implement `get_material_prices` tool (basic version)
- [ ] Add property data to context

### Phase 5: Polish (Week 9-10)
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Error handling and fallbacks
- [ ] Documentation

---

## Decision: Same Branch or New Branch?

**Recommendation: Same branch, incremental changes**

Reasons:
1. Current architecture is good - we're adding tools, not replacing
2. LangGraph flow is correct - we're enriching nodes
3. Database schema extends naturally
4. Frontend doesn't need changes initially
5. Risk of new branch: duplicate effort, merge conflicts

**Approach:**
1. Add tool interfaces alongside existing code
2. Wrap existing functions as tools
3. Call new tools from existing nodes
4. Gradually migrate from state-heavy to DB-backed
5. Add new tables without touching existing ones

---

## Questions to Resolve

1. **Address input**: Do we require full address, or is zip code + building type enough for MVP?

2. **DOB integration priority**: Critical for accuracy or nice-to-have?

3. **Permit rules source**: Build manual decision tree or find existing database?

4. **Pricing data**: RSMeans subscription ($$$) or alternative approach?

5. **Structural analysis confidence**: Always recommend PE, or try to be smart about it?

---

## Summary

**The five "agents" are five tool bundles:**
1. Location tools → called during basics
2. Space tools → called during analysis
3. Designer tools → called during chat
4. Architect tools → called at trigger points
5. Contractor tools → called during estimation

**The flow remains linear and deterministic.**

**LLMs are used for:**
- Intent detection (what does user want?)
- Natural language generation (explain findings)
- Image generation (create previews)
- NOT for knowing facts (that's what tools are for)

**Data comes from tools, not LLM knowledge.**

This is simpler, testable, and incrementally buildable on top of the existing system.
