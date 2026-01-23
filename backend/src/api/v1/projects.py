"""
Project CRUD endpoints.

Handles:
- Save project and send email with token
- Get project by token
- Publish project to marketplace
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional

from src.core.logger import get_logger
from src.db.database import get_db

logger = get_logger(__name__)
from src.db.models import Project, ConversationState
from src.db.schemas import (
    ProjectSaveRequest,
    ProjectSaveResponse,
    ProjectResponse,
    ProjectPublish,
    ProjectBasicsRequest,
    ProjectBasicsResponse,
)
from src.services.email_service import email_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("/save", response_model=ProjectSaveResponse)
async def save_project(
    request: ProjectSaveRequest,
    db: Session = Depends(get_db)
):
    """
    Save project and send email with token to homeowner.
    
    This endpoint is called after user completes the chat estimation.
    It saves the homeowner's email and sends them their project token.
    
    Args:
        request: Contains email address
        project_token: Optional project token (if not provided, finds latest project)
        db: Database session
    
    Returns:
        ProjectSaveResponse with token and email status
    """
    # Find project by token if provided, otherwise find latest completed project
    if request.project_token:
        project = db.query(Project).filter(Project.token == request.project_token).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        # Find latest completed project for this email (if any)
        project = db.query(Project).filter(
            Project.homeowner_email == request.email,
            Project.status == "completed"
        ).order_by(Project.created_at.desc()).first()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail="No completed project found. Please complete the estimation first."
            )
    
    # Update project with homeowner details
    project.homeowner_email = request.email
    if request.homeowner_name:
        project.homeowner_name = request.homeowner_name
    if request.homeowner_phone:
        project.homeowner_phone = request.homeowner_phone
    
    # Check if email already sent (don't send duplicate)
    email_sent = False
    if not project.homeowner_email_sent:
        try:
            # Get project details from conversation state
            conv_state = db.query(ConversationState).filter(
                ConversationState.project_id == project.id
            ).first()
            
            state = conv_state.state if conv_state else {}
            
            project_type = project.project_type or state.get("project_type", "Renovation")
            total_price = float(project.total_price) if project.total_price else 0.0
            zip_code = project.zip_code or state.get("zip_code", "")
            
            # Send email
            email_service.send_project_saved(
                to=request.email,
                token=project.token,
                project_type=project_type,
                total_price=total_price,
                zip_code=zip_code
            )
            
            project.homeowner_email_sent = True
            email_sent = True
            
        except Exception as e:
            logger.warning(f"Email sending failed but project saved: {e}")
            # Don't fail the request if email fails
            email_sent = False
    
    # Update project status if needed
    if project.status == "draft":
        project.status = "completed"
    
    db.commit()
    db.refresh(project)
    
    return ProjectSaveResponse(
        token=project.token,
        email_sent=email_sent,
        message="Project saved successfully. Check your email for your project code."
    )


@router.get("/{token}", response_model=ProjectResponse)
async def get_project(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get project by token (PRJ- or UNL-).
    
    Args:
        token: Project token (PRJ-XXXXXX) or unlock token (UNL-XXXXXX)
        db: Database session
    
    Returns:
        Project details
    """
    # Check if it's a project token or unlock token
    if token.startswith("PRJ-"):
        project = db.query(Project).filter(Project.token == token).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectResponse.model_validate(project)
    
    elif token.startswith("UNL-"):
        # This will be handled by unlock endpoint
        raise HTTPException(
            status_code=400,
            detail="Use unlock endpoint for UNL- tokens"
        )
    
    else:
        raise HTTPException(status_code=400, detail="Invalid token format")


@router.post("/{token}/publish", response_model=ProjectResponse)
async def publish_project(
    token: str,
    data: ProjectPublish,
    db: Session = Depends(get_db)
):
    """
    Publish project to marketplace.
    
    Requires homeowner contact information.
    Once published, project becomes visible in marketplace.
    
    Args:
        token: Project token (PRJ-XXXXXX)
        data: Homeowner contact information
        db: Database session
    
    Returns:
        Updated project
    """
    project = db.query(Project).filter(Project.token == token).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if already published or unlocked
    if project.status == "published":
        raise HTTPException(status_code=400, detail="Project already published")
    if project.status == "unlocked":
        raise HTTPException(status_code=400, detail="Cannot publish unlocked project")
    
    # Update project with homeowner info
    project.homeowner_name = data.homeowner_name
    project.homeowner_email = data.homeowner_email
    project.homeowner_phone = data.homeowner_phone
    project.status = "published"
    
    db.commit()
    db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.post("/{token}/complete", response_model=ProjectResponse)
async def mark_project_complete_homeowner(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Mark project as complete from homeowner side.

    Project is fully completed only when BOTH homeowner AND contractor mark it.
    This is a two-party completion system to ensure mutual agreement.

    Args:
        token: Project token (PRJ-XXXXXX)
        db: Database session

    Returns:
        Updated project with completion status
    """
    project = db.query(Project).filter(Project.token == token).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project is in unlocked state
    if project.status != "unlocked":
        raise HTTPException(
            status_code=400,
            detail="Project must be unlocked before marking complete"
        )

    # Mark homeowner as complete
    project.homeowner_marked_complete = True

    # If contractor also marked complete, finalize completion
    if project.contractor_marked_complete:
        from datetime import datetime, UTC
        project.status = "completed"
        project.completed_at = datetime.now(UTC)
        logger.info(f"[complete] Project {token} fully completed by both parties")
    else:
        logger.info(f"[complete] Homeowner marked complete for {token}, waiting for contractor")

    db.commit()
    db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.post("/{token}/basics", response_model=ProjectBasicsResponse)
async def submit_project_basics(
    token: str,
    request: ProjectBasicsRequest,
    db: Session = Depends(get_db)
):
    """
    Submit project basics form data directly (bypasses LLM).

    This endpoint saves project title, type, and location data
    directly to the database without LLM processing.
    Transitions the project to image_analysis_generation stage.

    Args:
        token: Project token (PRJ-XXXXXX)
        request: Project basics form data
        db: Database session

    Returns:
        ProjectBasicsResponse with updated state
    """
    from decimal import Decimal
    from src.core.services.location_service import validate_us_zip_code
    from src.core.services.renovation_inspiration_service import start_location_prefetch_background

    # Find project by token
    project = db.query(Project).filter(Project.token == token).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate zip code format
    if not validate_us_zip_code(request.zip_code):
        raise HTTPException(status_code=400, detail="Invalid US ZIP code format")

    # Update Project table with all location data
    project.project_title = request.project_title
    project.project_type = request.project_type
    project.zip_code = request.zip_code
    # Use top-level street_address, or fall back to location.street_address from geolocation
    project.street_address = request.street_address or (request.location.street_address if request.location else None)

    # Store comprehensive location data if provided
    if request.location:
        project.city = request.location.city
        project.state = request.location.state
        project.county = request.location.county
        project.country = request.location.country or "US"
        # Also use location.street_address if top-level is not set
        if not project.street_address and request.location.street_address:
            project.street_address = request.location.street_address
        if request.location.latitude:
            project.latitude = Decimal(str(request.location.latitude))
        if request.location.longitude:
            project.longitude = Decimal(str(request.location.longitude))

        # Check if NYC based on state and zip
        nyc_zip_prefixes = ['100', '101', '102', '103', '104', '110', '111', '112', '113', '114']
        is_nyc = (
            request.location.state in ['NY', 'New York'] and
            any(request.zip_code.startswith(prefix) for prefix in nyc_zip_prefixes)
        )
        project.is_nyc = is_nyc

        # Detect borough from city name for NYC
        if is_nyc and request.location.city:
            city_lower = request.location.city.lower()
            if 'manhattan' in city_lower or city_lower == 'new york':
                project.borough = 'Manhattan'
            elif 'brooklyn' in city_lower:
                project.borough = 'Brooklyn'
            elif 'queens' in city_lower:
                project.borough = 'Queens'
            elif 'bronx' in city_lower:
                project.borough = 'Bronx'
            elif 'staten island' in city_lower:
                project.borough = 'Staten Island'

    # Get or create ConversationState
    conv_state = db.query(ConversationState).filter(
        ConversationState.project_id == project.id
    ).first()

    if conv_state:
        # Update existing state
        state = conv_state.state or {}
        state["project_title"] = request.project_title
        state["project_type"] = request.project_type
        state["zip_code"] = request.zip_code
        state["current_stage"] = "image_analysis_generation"
        state["awaiting_user_input"] = True
        state["image_sub_state"] = "analyzing"  # Valid ImageSubState value

        # Don't add assistant message - the image upload UI is self-explanatory
        # Initialize messages array if it doesn't exist
        if "messages" not in state:
            state["messages"] = []

        # IMPORTANT: Reassign to trigger SQLAlchemy change detection for JSON column
        conv_state.state = dict(state)
        flag_modified(conv_state, "state")
    else:
        # Create new state
        state = {
            "project_id": token,
            "internal_project_id": str(project.id),
            "project_title": request.project_title,
            "project_type": request.project_type,
            "zip_code": request.zip_code,
            "current_stage": "image_analysis_generation",
            "awaiting_user_input": True,
            "image_sub_state": "analyzing",  # Valid ImageSubState value
            "messages": []  # Empty messages - no assistant greeting needed
        }
        conv_state = ConversationState(
            project_id=project.id,
            state=state
        )
        db.add(conv_state)

    db.commit()
    db.refresh(project)
    db.refresh(conv_state)

    # Start background location prefetch (Census + Climate data)
    # Only prefetch if we don't already have comprehensive location data from geolocation
    should_prefetch = True
    if request.location:
        # If we have geolocation data (city, state, lat/lng), skip redundant ZIP lookup
        # We still want Census/Climate data, so only skip if we already have those
        has_geolocation = (
            request.location.city and
            request.location.state and
            request.location.latitude is not None and
            request.location.longitude is not None
        )
        if has_geolocation:
            logger.info(f"[basics] Using geolocation data:")
            logger.info(f"[basics]   street_address: {request.location.street_address or 'N/A'}")
            logger.info(f"[basics]   city: {request.location.city}")
            logger.info(f"[basics]   state: {request.location.state}")
            logger.info(f"[basics]   county: {request.location.county or 'N/A'}")
            logger.info(f"[basics]   zip_code: {request.location.zip_code}")
            logger.info(f"[basics]   lat/lng: {request.location.latitude}, {request.location.longitude}")
            # Note: We still start prefetch for Census/Climate data, just log that we have geo data

    try:
        start_location_prefetch_background(
            project_id=project.id,
            zip_code=request.zip_code
        )
        logger.info(f"[basics] Started location prefetch for {request.zip_code}")
    except Exception as e:
        logger.warning(f"[basics] Failed to start location prefetch: {e}")

    logger.info(f"[basics] Project {token} basics saved: {request.project_type} in {request.zip_code}")

    # Debug: Log what we're returning
    logger.info(f"[basics] Returning state with current_stage: {conv_state.state.get('current_stage')}")
    logger.info(f"[basics] Full state keys: {list(conv_state.state.keys())}")

    return ProjectBasicsResponse(
        success=True,
        project_id=token,
        internal_id=str(project.id),
        current_stage="image_analysis_generation",
        message=f"Project basics saved. Ready for image upload.",
        state=conv_state.state
    )


@router.get("/{token}/suggestions")
async def get_pre_generated_suggestions(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get pre-generated suggestions for a project.

    Suggestions are auto-generated after Tavily + Cerebras extraction completes.
    This endpoint retrieves them for display in the popup.

    Args:
        token: Project token (PRJ-XXXXXX)
        db: Database session

    Returns:
        Dict with suggestions options, sources, and status
    """
    project = db.query(Project).filter(Project.token == token).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    inspirations = project.renovation_inspirations or {}
    suggestions_data = inspirations.get("suggestions", {})

    if not suggestions_data:
        # Check if suggestions are still being generated
        if inspirations.get("_tavily_pending"):
            return {
                "status": "pending",
                "message": "Suggestions are still being generated",
                "options": [],
                "sources": []
            }
        return {
            "status": "not_available",
            "message": "No suggestions available yet",
            "options": [],
            "sources": []
        }

    options = suggestions_data.get("options", [])
    sources = inspirations.get("_sources", [])

    return {
        "status": "ready",
        "options": options,
        "sources": sources,
        "generated_at": suggestions_data.get("generated_at"),
        "auto_generated": suggestions_data.get("auto_generated", False)
    }
