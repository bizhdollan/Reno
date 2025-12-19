"""
Pydantic schemas for API request/response validation.

These are separate from SQLAlchemy models and define the API contract.
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal


# ============================================================================
# PROJECT SCHEMAS
# ============================================================================

class ProjectBase(BaseModel):
    """Base project fields"""
    project_type: Optional[str] = None
    zip_code: Optional[str] = None
    accepted_tier: Optional[str] = Field(None, pattern="^(low|mid|high)$")
    total_price: Optional[Decimal] = None
    brief_scope: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a new project"""
    # All fields optional at creation (built up during chat)
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating project fields"""
    homeowner_name: Optional[str] = None
    homeowner_email: Optional[EmailStr] = None
    homeowner_phone: Optional[str] = None
    project_type: Optional[str] = None
    zip_code: Optional[str] = None
    accepted_tier: Optional[str] = None
    total_price: Optional[Decimal] = None
    brief_scope: Optional[str] = None
    full_estimate: Optional[dict[str, Any]] = None
    images: Optional[list[dict[str, Any]]] = None
    extracted_data: Optional[dict[str, Any]] = None
    renovation_vision: Optional[dict[str, Any]] = None
    generated_image_url: Optional[str] = None


class ProjectPublish(BaseModel):
    """Schema for publishing project to marketplace"""
    homeowner_name: str = Field(..., min_length=1, max_length=255)
    homeowner_email: EmailStr
    homeowner_phone: str = Field(..., min_length=1, max_length=50)


class ProjectResponse(ProjectBase):
    """Schema for project responses (API output)"""
    id: UUID
    token: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    homeowner_name: Optional[str] = None
    homeowner_email: Optional[str] = None
    homeowner_phone: Optional[str] = None
    
    full_estimate: Optional[dict[str, Any]] = None
    images: Optional[list[dict[str, Any]]] = None
    extracted_data: Optional[dict[str, Any]] = None
    renovation_vision: Optional[dict[str, Any]] = None
    generated_image_url: Optional[str] = None
    
    homeowner_marked_complete: bool
    contractor_marked_complete: bool
    completed_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class ProjectMarketplaceCard(BaseModel):
    """Minimal project data for marketplace cards (public view)"""
    id: UUID
    token: str  # Not shown in UI, but useful for API
    project_type: Optional[str] = None
    zip_code: Optional[str] = None
    total_price: Optional[Decimal] = None
    brief_scope: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ProjectSaveRequest(BaseModel):
    """Request to save project and get token"""
    email: EmailStr
    project_token: Optional[str] = None  # Optional: if not provided, finds latest project for email


class ProjectSaveResponse(BaseModel):
    """Response after saving project"""
    token: str
    email_sent: bool
    message: str


# ============================================================================
# UNLOCK SCHEMAS
# ============================================================================

class UnlockBase(BaseModel):
    """Base unlock fields"""
    contractor_email: EmailStr


class UnlockInitiateRequest(UnlockBase):
    """Request to initiate unlock (before payment)"""
    project_id: UUID


class UnlockInitiateResponse(BaseModel):
    """Response with Stripe checkout URL"""
    unlock_token: str
    checkout_url: str
    message: str


class ContractorDetailsRequest(BaseModel):
    """Request to save contractor details"""
    contractor_name: str = Field(..., min_length=1, max_length=255)
    contractor_phone: str = Field(..., min_length=1, max_length=50)
    contractor_company: str = Field(..., min_length=1, max_length=255)


class UnlockResponse(BaseModel):
    """Full unlock details (for contractor view)"""
    id: UUID
    unlock_token: str
    project_id: UUID
    contractor_email: str
    contractor_name: Optional[str] = None
    contractor_phone: Optional[str] = None
    contractor_company: Optional[str] = None
    contractor_details_saved: bool
    payment_status: str
    is_active: bool
    created_at: datetime
    unlocked_at: Optional[datetime] = None
    
    # Include project details
    project: Optional[ProjectResponse] = None
    
    model_config = {"from_attributes": True}


# ============================================================================
# CONVERSATION STATE SCHEMAS
# ============================================================================

class ConversationStateUpdate(BaseModel):
    """Request to update conversation state"""
    state: dict[str, Any]


class ConversationStateResponse(BaseModel):
    """Conversation state response"""
    project_id: UUID
    state: dict[str, Any]
    updated_at: datetime
    
    model_config = {"from_attributes": True}


# ============================================================================
# TOKEN VALIDATION
# ============================================================================

class TokenValidationRequest(BaseModel):
    """Request to validate a token"""
    token: str = Field(..., pattern="^(PRJ|UNL)-[A-Z0-9]{6}$")


class TokenValidationResponse(BaseModel):
    """Token validation response"""
    valid: bool
    token_type: Optional[str] = None  # "project" or "unlock"
    exists: bool
    message: str


# ============================================================================
# MARKETPLACE FILTERS
# ============================================================================

class MarketplaceFilters(BaseModel):
    """Filters for marketplace browsing"""
    zip_code: Optional[str] = None
    project_type: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ============================================================================
# LLM COST SCHEMAS (Optional - Analytics)
# ============================================================================

class LLMCostCreate(BaseModel):
    """Create LLM cost record"""
    project_id: Optional[UUID] = None
    session_id: Optional[str] = None
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: Decimal = Field(ge=0)


class LLMCostResponse(BaseModel):
    """LLM cost response"""
    id: UUID
    project_id: Optional[UUID] = None
    session_id: Optional[str] = None
    model: str
    input_tokens: int
    output_tokens: int
    cost: Decimal
    created_at: datetime
    
    model_config = {"from_attributes": True}


# ============================================================================
# COMPLETION SCHEMAS
# ============================================================================

class MarkCompleteRequest(BaseModel):
    """Request to mark project as complete"""
    token: str = Field(..., pattern="^(PRJ|UNL)-[A-Z0-9]{6}$")


class MarkCompleteResponse(BaseModel):
    """Response after marking complete"""
    success: bool
    message: str
    both_marked_complete: bool
    completed_at: Optional[datetime] = None

