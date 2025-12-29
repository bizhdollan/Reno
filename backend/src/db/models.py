"""
SQLAlchemy ORM models for RenovationTech database.

Tables:
- projects: Renovation project data
- unlocks: Contractor unlock records
- conversation_states: LangGraph state persistence
- llm_costs: AI model usage analytics
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Numeric, Integer, ForeignKey, Index, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .database import Base


class Project(Base):
    """
    Renovation projects table.
    
    Stores all project data including homeowner info, estimates, and status.
    """
    __tablename__ = "projects"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Homeowner access token (PRJ-XXXXXX)
    token = Column(String(20), unique=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Status: draft, completed, published, unlocked, completed, closed
    status = Column(String(20), nullable=False, default="draft", index=True)
    
    # Homeowner information
    homeowner_name = Column(String(255), nullable=True)
    homeowner_email = Column(String(255), nullable=True)
    homeowner_phone = Column(String(50), nullable=True)
    homeowner_email_sent = Column(Boolean, default=False, nullable=False)
    
    # Project basics (for marketplace preview)
    project_type = Column(String(100), nullable=True, index=True)  # kitchen, bathroom, etc.
    zip_code = Column(String(10), nullable=True, index=True)
    accepted_tier = Column(String(10), nullable=True)  # low, mid, high
    total_price = Column(Numeric(10, 2), nullable=True)  # Selected tier price
    brief_scope = Column(Text, nullable=True)  # Short description for marketplace
    
    # Full project data (JSON columns)
    full_estimate = Column(JSONB, nullable=True)  # Complete 3-tier breakdown
    images = Column(JSONB, nullable=True)  # Array of image objects
    extracted_data = Column(JSONB, nullable=True)  # Materials, measurements, etc.
    renovation_vision = Column(JSONB, nullable=True)  # Homeowner's vision/preferences
    generated_image_url = Column(Text, nullable=True)  # AI-generated preview image
    
    # Completion tracking (two-party system)
    homeowner_marked_complete = Column(Boolean, default=False, nullable=False)
    contractor_marked_complete = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)  # Set when both mark complete
    
    # Relationships
    unlocks = relationship("Unlock", back_populates="project", cascade="all, delete-orphan")
    conversation_state = relationship("ConversationState", back_populates="project", uselist=False, cascade="all, delete-orphan")
    llm_costs = relationship("LLMCost", back_populates="project", cascade="all, delete-orphan")
    
    # Composite index for marketplace queries
    __table_args__ = (
        Index('idx_marketplace', 'status', 'zip_code', 'project_type', 'total_price'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, token={self.token}, status={self.status})>"


class Unlock(Base):
    """
    Contractor unlock records table.
    
    Tracks which contractors unlocked which projects and their payment status.
    """
    __tablename__ = "unlocks"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to project
    project_id = Column(
        UUID(as_uuid=True), 
        ForeignKey('projects.id', ondelete='RESTRICT'),  # Don't allow project deletion if unlock exists
        nullable=False,
        index=True
    )
    
    # Contractor unlock token (UNL-XXXXXX)
    unlock_token = Column(String(20), unique=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    unlocked_at = Column(DateTime, nullable=True)  # When payment completed
    invalidated_at = Column(DateTime, nullable=True)  # Future: if republish feature added
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Payment information
    payment_status = Column(String(20), nullable=False, default="pending")  # pending, completed, failed
    payment_id = Column(String(100), nullable=True, index=True)  # Stripe payment/checkout session ID
    amount = Column(Numeric(10, 2), nullable=False, default=199.00)
    
    # Contractor details
    contractor_email = Column(String(255), nullable=False, index=True)
    contractor_name = Column(String(255), nullable=True)
    contractor_phone = Column(String(50), nullable=True)
    contractor_company = Column(String(255), nullable=True)
    contractor_details_saved = Column(Boolean, default=False, nullable=False)
    
    # Email tracking
    contractor_email_sent = Column(Boolean, default=False, nullable=False)
    homeowner_notified = Column(Boolean, default=False, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="unlocks")
    
    # Constraint: Only one active unlock per project
    __table_args__ = (
        Index('idx_unlock_token', 'unlock_token'),
        Index('idx_payment_id', 'payment_id'),
        Index('idx_contractor_email', 'contractor_email'),
        # PostgreSQL unique constraint with WHERE clause
        # This ensures only ONE active unlock per project at a time
    )
    
    def __repr__(self):
        return f"<Unlock(id={self.id}, token={self.unlock_token}, status={self.payment_status})>"


class ConversationState(Base):
    """
    LangGraph conversation state persistence table.
    
    Stores the full chat state for each project to allow resume after refresh.
    """
    __tablename__ = "conversation_states"
    
    # Primary key (also foreign key)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),  # Delete state if project deleted
        primary_key=True
    )
    
    # Full LangGraph state as JSON
    state = Column(JSONB, nullable=False)
    
    # Timestamp
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="conversation_state")
    
    # Index for queries
    __table_args__ = (
        Index('idx_conversation_updated', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<ConversationState(project_id={self.project_id})>"


class LLMCost(Base):
    """
    LLM usage and cost tracking table.

    Optional analytics table to track AI model usage and costs.
    Enhanced with api_call_id, operation_type, and cost_usd for per-call tracking.
    """
    __tablename__ = "llm_costs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to project (nullable - can track costs without project)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Session identifier
    session_id = Column(String(100), nullable=True)

    # NEW: Unique API call identifier for per-call tracking
    api_call_id = Column(UUID(as_uuid=True), nullable=True, unique=True)

    # NEW: Operation type for categorizing calls
    operation_type = Column(Text, nullable=True)  # analysis, generation, classification, etc.

    # Model details
    model = Column(String(100), nullable=False, index=True)  # e.g., "gemini-2.5-flash"
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost = Column(Numeric(10, 4), nullable=False, default=0.0000)  # Cost in USD (legacy)

    # NEW: More precise cost tracking
    cost_usd = Column(Numeric(10, 6), nullable=True)  # Calculated cost with higher precision

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    project = relationship("Project", back_populates="llm_costs")

    # Indexes for analytics queries
    __table_args__ = (
        Index('idx_llm_costs_project', 'project_id'),
        Index('idx_llm_costs_date', 'created_at'),
        Index('idx_llm_costs_model', 'model'),
        Index('idx_llm_costs_api_call', 'api_call_id', unique=True),
        Index('idx_llm_costs_operation', 'operation_type'),
    )

    def __repr__(self):
        return f"<LLMCost(id={self.id}, model={self.model}, cost={self.cost})>"


# =============================================================================
# NEW TABLES FOR IMAGE ANALYSIS & GENERATION REFACTOR
# =============================================================================

class ImageAnalysis(Base):
    """
    Store extracted features and critical elements per image.

    This replaces storing analysis data in the state object,
    reducing browser state bloat and enabling multi-perspective tracking.
    """
    __tablename__ = "image_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    image_url = Column(Text, nullable=False)
    room_type = Column(Text, nullable=True)  # kitchen, bathroom, bedroom, living_room
    extracted_features = Column(JSONB, nullable=True)  # {materials: [...], measurements: {...}, colors: [...]}
    critical_elements = Column(JSONB, nullable=True)  # {windows: {count: 2, wall: "east"}, doors: {...}}
    confidence_score = Column(Numeric(3, 2), nullable=True)  # Overall confidence 0.00-1.00
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="image_analyses")
    image_metadata = relationship("ImageMetadata", back_populates="analysis", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_image_analysis_project', 'project_id'),
        Index('idx_image_analysis_url', 'image_url'),
    )

    def __repr__(self):
        return f"<ImageAnalysis(id={self.id}, room_type={self.room_type})>"


class ImageMetadata(Base):
    """
    Store perspective and consistency metadata for images.

    Tracks camera angle (front/side/top-down/close-up) and
    room consistency hash for grouping related images.
    """
    __tablename__ = "image_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    image_analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey('image_analysis.id', ondelete='CASCADE'),
        nullable=False
    )
    image_url = Column(Text, nullable=False)
    perspective_type = Column(Text, nullable=True)  # front, side, top_down, close_up
    perspective_confidence = Column(Numeric(3, 2), nullable=True)  # Confidence 0.00-1.00
    room_consistency_hash = Column(Text, nullable=True)  # Hash to group images of same room
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="project_image_metadata")
    analysis = relationship("ImageAnalysis", back_populates="image_metadata")
    perspective_changes = relationship("PerspectiveChange", back_populates="image_metadata", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_image_metadata_project', 'project_id'),
        Index('idx_image_metadata_analysis', 'image_analysis_id'),
    )

    def __repr__(self):
        return f"<ImageMetadata(id={self.id}, perspective={self.perspective_type})>"


class GenerationHistory(Base):
    """
    Track all generated images with metadata.

    Stores generation type (initial/additive/restart), prompts used,
    critical elements injected, and user feedback.
    """
    __tablename__ = "generation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    source_image_id = Column(UUID(as_uuid=True), nullable=True)  # Original or previous generation
    generation_type = Column(Text, nullable=False)  # initial, additive, restart
    prompt_data = Column(JSONB, nullable=True)  # Full prompt sent to VGM
    critical_elements = Column(JSONB, nullable=True)  # Critical elements injected
    perspective_constraint = Column(Text, nullable=True)  # front, side, etc.
    result_image_url = Column(Text, nullable=True)  # Generated image URL
    user_feedback = Column(Text, nullable=True)  # User's response
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="generation_history")
    perspective_changes = relationship("PerspectiveChange", back_populates="generation", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_generation_history_project', 'project_id'),
        Index('idx_generation_history_source', 'source_image_id'),
    )

    def __repr__(self):
        return f"<GenerationHistory(id={self.id}, type={self.generation_type})>"


class BudgetContext(Base):
    """
    Store detected budget sentiment (NO prices).

    During ideation/generation, we detect budget level and suggest
    appropriate materials. Prices are only shown in cost estimation.
    """
    __tablename__ = "budget_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    budget_sentiment = Column(Text, nullable=False)  # low, medium, high
    detected_from_message = Column(Text, nullable=True)  # User message that triggered detection
    suggested_materials = Column(JSONB, nullable=True)  # {floor: [...], walls: [...]}
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="budget_contexts")

    __table_args__ = (
        Index('idx_budget_context_project', 'project_id'),
    )

    def __repr__(self):
        return f"<BudgetContext(id={self.id}, sentiment={self.budget_sentiment})>"


class CorrectionHistory(Base):
    """
    Track user corrections with undo capability.

    Stores the last 10 corrections per project, allowing users
    to undo accidental changes to extraction or vision data.
    """
    __tablename__ = "correction_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    correction_type = Column(Text, nullable=False)  # extraction, vision, feedback
    field_changed = Column(Text, nullable=False)  # e.g., "materials.floor"
    old_value = Column(JSONB, nullable=True)  # Previous value
    new_value = Column(JSONB, nullable=True)  # New value
    user_message = Column(Text, nullable=True)  # User's correction message
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="correction_history")

    __table_args__ = (
        Index('idx_correction_history_project', 'project_id'),
        Index('idx_correction_history_timestamp', 'created_at'),
    )

    def __repr__(self):
        return f"<CorrectionHistory(id={self.id}, type={self.correction_type}, field={self.field_changed})>"


class PerspectiveChange(Base):
    """
    Track which regions changed in which perspective.

    Links changes to specific image perspectives and generations,
    enabling detailed tracking of what was modified where.
    """
    __tablename__ = "perspective_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    image_metadata_id = Column(
        UUID(as_uuid=True),
        ForeignKey('image_metadata.id', ondelete='CASCADE'),
        nullable=True
    )
    generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('generation_history.id', ondelete='CASCADE'),
        nullable=True
    )
    change_category = Column(Text, nullable=False)  # floor, walls, ceiling, fixtures, furniture
    change_description = Column(Text, nullable=True)  # Human-readable description
    applied_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", backref="perspective_changes")
    image_metadata = relationship("ImageMetadata", back_populates="perspective_changes")
    generation = relationship("GenerationHistory", back_populates="perspective_changes")

    __table_args__ = (
        Index('idx_perspective_changes_project', 'project_id'),
        Index('idx_perspective_changes_generation', 'generation_id'),
    )

    def __repr__(self):
        return f"<PerspectiveChange(id={self.id}, category={self.change_category})>"
