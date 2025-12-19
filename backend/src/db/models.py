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
    
    # Model details
    model = Column(String(100), nullable=False, index=True)  # e.g., "gemini-2.5-flash"
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost = Column(Numeric(10, 4), nullable=False, default=0.0000)  # Cost in USD
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    project = relationship("Project", back_populates="llm_costs")
    
    # Indexes for analytics queries
    __table_args__ = (
        Index('idx_llm_costs_project', 'project_id'),
        Index('idx_llm_costs_date', 'created_at'),
        Index('idx_llm_costs_model', 'model'),
    )
    
    def __repr__(self):
        return f"<LLMCost(id={self.id}, model={self.model}, cost={self.cost})>"
