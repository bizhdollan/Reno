# LangGraph Implementation Analysis & Architecture

## 📋 Overview

The LangGraph implementation provides a conversational renovation estimation flow with a streamlined 4-stage architecture:

1. **Project Basics** - Collect basic project information
2. **Image Analysis & Generation** - Analyze images, confirm information, generate renovation preview
3. **Final Review** - Review all confirmed information and generated image
4. **Cost Estimation** - Generate final cost estimate

## 🏗️ Architecture

### Stage 1: Project Basics
**Purpose**: Collect essential project information

**Data Collected**:
- Project title
- Project type (kitchen, bathroom, etc.)
- Zip code (for location-based pricing)

**Flow**:
- Extract information from user messages
- Ask for missing fields one at a time
- Move to next stage when all basics are collected

---

### Stage 2: Image Analysis & Generation
**Purpose**: Analyze user images, extract renovation information, confirm details, and generate renovation preview

**Sub-steps**:

#### 2.1 Image Analysis
- User uploads one or more images
- AI analyzes images comprehensively in **single pass**:
  - Materials (type, finish, condition, dimensions)
  - Measurements (room dimensions, cabinet sizes, countertop area, etc.)
  - Colors and visual information
  - Style and condition assessment
  - Fixtures and appliances
  - Any other renovation-relevant details (extracted dynamically based on project type)
- Store all extracted data in state

#### 2.2 Information Confirmation Loop
- AI presents extracted information to user
- User and AI confirm/correct information **back and forth**
- Continue until both are satisfied
- Handle corrections dynamically (materials, measurements, colors, etc.)

#### 2.3 Image Generation (Placeholder for now)
- Once information is confirmed, generate renovation preview image
- For now: Use placeholder image
- Future: Generate actual renovation preview based on:
  - Original images
  - Confirmed renovation changes
  - Materials and colors selected

#### 2.4 Image Confirmation
- User reviews generated/placeholder image
- User confirms satisfaction
- Move to final review

---

### Stage 3: Final Review
**Purpose**: Present complete summary of all confirmed information and generated image

**Content**:
- Project basics (title, type, location)
- All confirmed materials
- All confirmed measurements
- All confirmed colors and visual details
- Generated renovation preview image
- Summary of renovation scope

**Flow**:
- AI presents comprehensive summary
- User can:
  - Confirm everything and proceed to cost estimation
  - Request changes to specific sections (go back to confirmation loop)
- Once user confirms, move to cost estimation

---

### Stage 4: Cost Estimation
**Purpose**: Generate 3-tier cost estimates based on confirmed information

**Inputs**:
- Project basics (type, zip code)
- Confirmed materials
- Confirmed measurements
- All confirmed renovation details

**Process**:
- AI analyzes all project inputs
- AI constructs 3-tier cost breakdown:
  - **Low Tier**: Budget-friendly, quality work at best value
  - **Mid Tier**: Best balance of quality and price (recommended)
  - **High Tier**: Top-tier materials and finishes
- Each tier includes:
  - Total cost estimate (COGS + markup)
  - COGS (Cost of Goods Sold) amount
  - Markup percentage (Low: ~20%, Mid: ~35%, High: ~50%)
  - Included items list (Framing, Insulation, Drywall, Electrical, Plumbing, Flooring, HVAC, Egress Window, Painting, etc.)
  - Badge label (Budget-Friendly, Recommended, Premium)
  - Detailed breakdown table (shown when tier is selected):
    - Category
    - Description
    - Materials cost
    - Labor cost
    - Total per category
    - Summary: Subtotal (COGS), Markup, Total Estimate

**Outputs**:
- 3-tier cards data structure (for frontend rendering)
- Each tier with:
  - Tier ID: "low", "mid", "high"
  - Tier name: "Low Tier", "Mid Tier", "High Tier"
  - Badge: "Budget-Friendly", "Recommended", "Premium"
  - Description
  - Total price (COGS + markup)
  - COGS amount
  - Markup percentage
  - Included items list (with checkmarks)
  - Detailed breakdown table (category-by-category):
    - Category name
    - Description
    - Materials cost
    - Labor cost
    - Total per category
- Summary totals:
  - Subtotal (COGS)
  - Markup amount
  - Total Estimate
- **Note**: Frontend will render these as selectable cards (implementation pending)
- User can select a tier, view its detailed breakdown, then "Accept [Tier] & Submit"

**Future Enhancement**:
- Replace AI calculation with formula-based calculation
- Use tools/functions for precise cost calculations
- For now: AI analyzes inputs and constructs tiers intelligently

**User Selection Flow**:
1. System displays 3 tier cards (Low, Mid, High)
2. User can click to select a tier
3. Selected tier shows detailed breakdown table:
   - Category-by-category breakdown (Materials, Labor, Total)
   - Summary: Subtotal (COGS), Markup, Total Estimate
4. User reviews breakdown
5. User clicks "Accept [Tier] & Submit"
6. Selected tier becomes the final estimate
7. Project marked as completed

---

## 🚨 Critical Improvements Required

### 1. **Comprehensive Image Analysis (Single Pass)**
**Problem**: Need to extract ALL information from images in one VLM call to avoid duplicate costs.

**Solution**: 
- Create comprehensive image analysis prompt that extracts:
  - Materials (with full specifications)
  - Measurements (all dimensions)
  - Colors and visual information
  - Style, condition, quality
  - Fixtures and appliances
  - Any other renovation-relevant details (dynamic based on project type)
- Use structured JSON output
- Store everything in state immediately

**Implementation**:
```python
# Enhanced image analysis - extract everything in one pass
async def analyze_image_comprehensive(image_url: str, project_type: str) -> dict:
    """Extract ALL renovation-relevant information from image in single VLM call."""
    prompt = COMPREHENSIVE_IMAGE_ANALYSIS_PROMPT.format(
        project_type=project_type,
        # No hardcoded values - all from config
    )
    
    # Single VLM call extracts everything
    response = await provider.complete(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    return parse_json(response)
```

---

### 2. **Dynamic Information Extraction**
**Problem**: Different project types need different information extracted.

**Solution**:
- Make extraction prompts dynamic based on project type
- Kitchen: focus on cabinets, countertops, appliances, flooring
- Bathroom: focus on fixtures, tiles, vanity, shower
- Bedroom: focus on flooring, paint, lighting, built-ins
- Extract what's relevant to the specific renovation type

---

### 3. **Confirmation Loop Design**
**Problem**: Need efficient back-and-forth confirmation without being overwhelming.

**Solution**:
- Present information in organized sections
- Allow user to:
  - Confirm all at once ("everything looks good")
  - Confirm section by section ("materials look good")
  - Correct specific items ("change countertop to quartz")
  - Add missing items
- Track what's confirmed vs. what needs attention
- Continue loop until all information is confirmed

**Flow**:
```
AI: "I found these materials: [list]. Does this look correct?"
User: "Change countertop to quartz"
AI: "Updated. Here's the revised list: [list]. Anything else?"
User: "Everything looks good"
AI: "Great! Now let's verify measurements: [list]"
...
```

---

### 4. **Image Generation Placeholder**
**Problem**: Image generation feature not yet implemented.

**Solution**:
- Add placeholder image generation step
- Store placeholder image URL in state
- Structure code to easily swap in real image generation later
- User can still confirm placeholder to proceed

**Future Implementation**:
- Use image-to-image generation (e.g., Stable Diffusion, DALL-E)
- Input: Original image + renovation changes
- Output: Renovated preview image

---

### 5. **Improve Prompt Engineering**
**Problem**: Prompts have hardcoded values, inconsistent quality.

**Solution**:
- Remove ALL hardcoded values (move to configuration)
- Create purpose-specific prompts for each step
- Use structured output (JSON mode) consistently
- Make prompts context-aware and dynamic
- Document prompt rationale

---

## 📊 State Schema Updates Needed

### Current State Issues:
- Separate fields for materials, measurements, etc.
- No field for generated image
- No tracking of confirmation status
- No 3-tier cost structure

### Required Updates:
```python
class CategoryBreakdown(TypedDict, total=False):
    """Breakdown for a single category."""
    category: str  # "Framing", "Insulation", "Drywall", etc.
    description: str
    materials_cost: float
    labor_cost: float
    total: float

class CostTier(TypedDict, total=False):
    """Single tier in 3-tier cost structure."""
    id: str  # "low", "mid", "high"
    name: str  # "Low Tier", "Mid Tier", "High Tier"
    badge: str  # "Budget-Friendly", "Recommended", "Premium"
    description: str
    total_cost: float  # COGS + markup
    cogs: float  # Cost of Goods Sold
    markup_percentage: float  # 20, 35, 50
    markup_amount: float
    included_items: list[str]  # ["Framing", "Insulation", "Drywall", ...]
    detailed_breakdown: list[CategoryBreakdown]  # Category-by-category breakdown

class ProjectState(TypedDict, total=False):
    # Project basics
    project_title: str | None
    project_type: str | None
    zip_code: str | None
    
    # Image analysis results (comprehensive)
    images: list[ImageData]  # Original user images
    extracted_data: dict  # All extracted info (materials, measurements, colors, etc.)
    confirmation_status: dict  # Track what's confirmed
    
    # Generated image
    generated_image_url: str | None  # Placeholder for now
    
    # Cost estimation
    estimate: CostEstimate | None  # Legacy single estimate (for backward compat)
    cost_tiers: list[CostTier] | None  # 3-tier cards (Basic, Premium, Luxury)
    selected_tier: str | None  # User-selected tier ID
    
    # Control
    current_stage: Stage
    awaiting_user_input: bool
    messages: Annotated[list[dict], add_messages]
```

---

## 🔄 Graph Structure

### Simplified Flow:
```
START → project_basics → image_analysis_generation → final_review → cost_estimation → END
```

### Image Analysis & Generation Node:
This is a **single node** that handles:
1. Image analysis (if new images uploaded)
2. Information confirmation loop (back and forth)
3. Image generation (when confirmed)
4. Image confirmation (before moving to cost estimation)

**Internal State Machine**:
- `analyzing` - Processing images
- `confirming` - In confirmation loop
- `generating` - Generating preview image
- `image_confirmation` - User reviewing generated image
- `complete` - Ready for cost estimation

---

## 💰 Cost Optimization

### Current (Inefficient):
- Multiple VLM calls for different aspects
- Re-processing images for materials, measurements separately

### Target (Optimized):
- **1 VLM call per image** - extract everything in one pass
- Confirmation loop uses minimal LLM (only for parsing user responses)
- Image generation: placeholder (no cost) → future: 1 image generation call

### Expected Savings:
- **50-70% reduction** in VLM/LLM calls
- Faster user experience
- Better data quality (comprehensive extraction)

---

## 🎯 Implementation Priority

### Phase 1: Core Architecture
1. Update state schema for new architecture (add cost_tiers, selected_tier)
2. Create comprehensive image analysis prompt
3. Implement confirmation loop logic (support both one-by-one and batch)
4. Add image generation placeholder
5. Implement final review node (show all confirmed info + generated image)
6. Implement cost estimation node with 3-tier output
   - AI analyzes project inputs freely (based on context, no strict formulas)
   - AI constructs 3 tiers (Low/Mid/High)
   - Calculate COGS and markup for each tier
   - Generate detailed breakdown table (category-by-category)
   - Output structured data for frontend cards (rendering pending)
   - Handle tier selection and "Accept & Submit"
7. Update graph structure

### Phase 2: Optimization
6. Remove hardcoded values from prompts
7. Add dynamic extraction based on project type
8. Improve confirmation UX
9. Add validation for extracted data

### Phase 3: Future Features
10. Implement real image generation
11. Replace AI-based tier calculation with formula-based calculation
    - Create cost calculation tools/functions
    - Use precise formulas for labor, materials, overhead
    - Maintain 3-tier structure but with calculated values
12. Location-based pricing improvements
13. Frontend: Implement tier cards rendering and selection

---

## 📝 Resolved Decisions

1. **Confirmation Loop**: ✅ Support both one-by-one and batch confirmation
2. **Image Storage**: ✅ Store generated image URL in state (full image storage later)
3. **Final Review**: ✅ Required - shows all confirmed information + generated image before cost estimation

---

## 🔧 Code Structure

### New Node: `image_analysis_generation_node`
```python
async def image_analysis_generation_node(state: ProjectState) -> dict:
    """
    Handles entire image analysis and generation flow.
    
    Sub-states:
    - analyzing: Process new images
    - confirming: Confirmation loop
    - generating: Generate preview image
    - image_confirmation: User reviews generated image
    """
    sub_state = state.get("image_sub_state", "analyzing")
    
    if sub_state == "analyzing":
        # Analyze images, extract everything
        # Move to confirming
        
    elif sub_state == "confirming":
        # Handle confirmation loop
        # Move to generating when all confirmed
        
    elif sub_state == "generating":
        # Generate image (placeholder for now)
        # Move to image_confirmation
        
    elif sub_state == "image_confirmation":
        # User confirms generated image
        # Move to final_review stage
```

### Final Review Node:
```python
async def final_review_node(state: ProjectState) -> dict:
    """
    Present complete summary before cost estimation.
    
    Shows:
    - Project basics
    - All confirmed materials
    - All confirmed measurements
    - All confirmed colors/details
    - Generated renovation preview image
    """
    # Format comprehensive summary
    # Present to user
    # Allow confirmation or going back to edit
    # Move to cost_estimation when confirmed
```

---

## ✅ Next Steps

1. ✅ Architecture approved
2. Update state schema (add final_review stage, generated_image_url, confirmation_status, cost_tiers, selected_tier)
3. Create comprehensive image analysis prompt
4. Implement confirmation loop (support both one-by-one and batch)
5. Add image generation placeholder
6. Implement final review node
7. Implement cost estimation with 3-tier output
   - AI-based calculation (analyze inputs, construct tiers)
   - Output structured tier data for frontend cards
   - Handle user tier selection
8. Update graph structure (4 stages)
9. Test end-to-end flow

## 💰 3-Tier Cost Calculation Approach

### Current Implementation (AI-Based)
**Method**: AI analyzes project inputs and intelligently constructs 3 tiers

**Approach**: AI analyzes freely based on project context (no strict formulas yet)

**Process**:
1. AI receives all confirmed project data:
   - Project type, zip code, measurements
   - Confirmed materials, colors, style
   - Generated image (if available)
   - All renovation scope details

2. AI analyzes project context and constructs tiers:
   - **Low Tier**: 
     - Budget-friendly materials
     - Standard fixtures and finishes
     - Standard labor rates
     - ~20% markup
     - Badge: "Budget-Friendly"
   
   - **Mid Tier**:
     - Balanced quality materials
     - Good fixtures and finishes
     - Skilled labor rates
     - ~35% markup
     - Badge: "Recommended" (popular choice)
   
   - **High Tier**:
     - Top-tier/premium materials
     - High-end fixtures and finishes
     - Expert labor rates
     - ~50% markup
     - Badge: "Premium"

3. AI calculates costs for each tier:
   - Material costs per category (based on quality level)
   - Labor costs per category (based on complexity and skill level)
   - COGS (Cost of Goods Sold) = sum of all materials + labor
   - Markup percentage (Low: ~20%, Mid: ~35%, High: ~50%)
   - Markup amount = COGS × markup_percentage
   - Total cost = COGS + markup_amount

4. AI generates:
   - Included items list (same items across all tiers, but different quality)
   - Detailed breakdown table (category-by-category with materials, labor, total)
   - Summary totals (Subtotal/COGS, Markup, Total Estimate)

**Advantages**:
- Flexible and adaptive
- Can handle complex scenarios
- Understands context and project nuances
- No rigid formulas needed initially
- Can adapt to different project types naturally

**Limitations**:
- Less precise than formula-based
- May have inconsistencies
- Higher LLM costs
- Results may vary between runs

**Note**: This is the initial approach. Will be replaced with formula-based calculation later for consistency and precision.

### Future Implementation (Formula-Based)
**Method**: Replace AI calculation with precise formulas and tools

**Timeline**: Will be implemented later (after initial AI-based approach is working)

**Process**:
1. Use structured formulas:
   - Material cost = (quantity × unit_cost) × quality_multiplier
   - Labor cost = (area × labor_rate) × complexity_multiplier × location_factor
   - COGS = sum of all materials + labor
   - Markup = COGS × markup_percentage (varies by tier)
   - Total = COGS + markup

2. Apply tier multipliers and markup:
   - Low Tier: Standard materials/labor, ~20% markup
   - Mid Tier: Quality materials/labor, ~35% markup
   - High Tier: Premium materials/labor, ~50% markup

3. Use tools/functions for calculations:
   - Material cost calculator
   - Labor cost calculator
   - Location-based pricing lookup (using zip code)
   - COGS calculator
   - Markup calculator

**Advantages**:
- More precise and consistent
- Lower costs (no LLM for calculation)
- Reproducible results
- Easier to audit and adjust
- Predictable pricing

**Implementation Plan**:
- Create calculation functions/tools
- Use LangGraph tools for precise calculations
- Keep AI for feature list generation and explanations (optional)
- Maintain 3-tier structure
- Replace AI calculation logic with formula-based approach

**Migration Strategy**:
- Start with AI-based (current)
- Test and validate with real projects
- Develop formulas based on patterns and data
- Gradually migrate to formula-based
- Keep AI as fallback or for edge cases

---

## 🎨 Frontend Integration (Future)

### 3-Tier Cards Rendering
- **Status**: Pending implementation
- **Structure**: Backend sends `cost_tiers` array in message
- **Rendering**: Frontend will render as selectable cards
- **Selection**: User selects tier → sends selection back to backend
- **Display**: Show selected tier's details and final estimate

### Message Format for Cards:
```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Here are your renovation options:"
    },
    {
      "type": "tier_cards",
      "tiers": [
        {
          "id": "low",
          "name": "Low Tier",
          "badge": "Budget-Friendly",
          "description": "Quality work at the best value",
          "total_cost": 24000,
          "cogs": 20000,
          "markup_percentage": 20,
          "markup_amount": 4000,
          "included_items": ["Framing", "Insulation", "Drywall", "Electrical", "Plumbing", "Flooring", "HVAC", "Egress Window", "Painting"],
          "detailed_breakdown": [
            {
              "category": "Framing",
              "description": "Framing - Standard grade materials",
              "materials_cost": 1333,
              "labor_cost": 889,
              "total": 2222
            },
            // ... more categories
          ]
        },
        {
          "id": "mid",
          "name": "Mid Tier",
          "badge": "Recommended",
          "description": "Best balance of quality and price",
          "total_cost": 33750,
          "cogs": 25000,
          "markup_percentage": 35,
          "markup_amount": 8750,
          "included_items": ["Framing", "Insulation", "Drywall", "Electrical", "Plumbing", "Flooring", "HVAC", "Egress Window", "Painting"],
          "detailed_breakdown": [...]
        },
        {
          "id": "high",
          "name": "High Tier",
          "badge": "Premium",
          "description": "Top-tier materials and finishes",
          "total_cost": 45000,
          "cogs": 30000,
          "markup_percentage": 50,
          "markup_amount": 15000,
          "included_items": ["Framing", "Insulation", "Drywall", "Electrical", "Plumbing", "Flooring", "HVAC", "Egress Window", "Painting"],
          "detailed_breakdown": [...]
        }
      ]
    }
  ]
}
```
