"""
Contractor marketplace endpoints.

Handles browsing and filtering published projects.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional
from decimal import Decimal

from src.db.database import get_db
from src.db.models import Project
from src.db.schemas import ProjectMarketplaceCard, MarketplaceFilters

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


@router.get("/", response_model=list[ProjectMarketplaceCard])
async def get_marketplace_projects(
    zip_code: Optional[str] = Query(None, description="Filter by ZIP code"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    min_price: Optional[Decimal] = Query(None, description="Minimum price filter"),
    max_price: Optional[Decimal] = Query(None, description="Maximum price filter"),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """
    Get published projects for marketplace browsing.
    
    Only returns projects with status="published".
    Filters available: zip_code, project_type, price range.
    Supports pagination with limit and offset.
    
    Args:
        zip_code: Filter by ZIP code
        project_type: Filter by project type (kitchen, bathroom, etc.)
        min_price: Minimum project price
        max_price: Maximum project price
        limit: Number of results (1-100, default 20)
        offset: Skip N results for pagination
        db: Database session
    
    Returns:
        List of published projects (minimal public data only)
    """
    # Start with base query - only published projects, not deleted
    # Also ensure required fields exist (project_type, zip_code, total_price)
    query = db.query(Project).filter(
        Project.status == "published",
        Project.deleted_at.is_(None),
        Project.project_type.isnot(None),  # Must have project type
        Project.zip_code.isnot(None),       # Must have zip code
        Project.total_price.isnot(None)     # Must have price
    )
    
    # Apply filters
    if zip_code:
        query = query.filter(Project.zip_code == zip_code)
    
    if project_type:
        query = query.filter(Project.project_type == project_type)
    
    if min_price is not None:
        query = query.filter(Project.total_price >= min_price)
    
    if max_price is not None:
        query = query.filter(Project.total_price <= max_price)
    
    # Order by newest first
    query = query.order_by(Project.created_at.desc())
    
    # Apply pagination
    projects = query.offset(offset).limit(limit).all()
    
    # Convert to response format (exclude sensitive data)
    return [ProjectMarketplaceCard.model_validate(p) for p in projects]


@router.get("/stats")
async def get_marketplace_stats(
    db: Session = Depends(get_db)
):
    """
    Get marketplace statistics.
    
    Returns counts by project type, average prices, etc.
    Useful for frontend filters.
    """
    # Count total published projects
    total = db.query(Project).filter(
        Project.status == "published",
        Project.deleted_at.is_(None)
    ).count()
    
    # Count by type
    from sqlalchemy import func
    type_counts = db.query(
        Project.project_type,
        func.count(Project.id).label('count')
    ).filter(
        Project.status == "published",
        Project.deleted_at.is_(None)
    ).group_by(Project.project_type).all()
    
    # Average price
    avg_price = db.query(
        func.avg(Project.total_price)
    ).filter(
        Project.status == "published",
        Project.deleted_at.is_(None),
        Project.total_price.isnot(None)
    ).scalar()
    
    return {
        "total_projects": total,
        "by_type": {ptype: count for ptype, count in type_counts if ptype},
        "average_price": float(avg_price) if avg_price else 0.0
    }
