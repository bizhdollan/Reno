"""
Project CRUD endpoints.

Handles:
- Save project and send email with token
- Get project by token
- Publish project to marketplace
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from src.db.database import get_db
from src.db.models import Project, ConversationState
from src.db.schemas import (
    ProjectSaveRequest,
    ProjectSaveResponse,
    ProjectResponse,
    ProjectPublish,
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
            print(f"⚠️ Email sending failed but project saved: {e}")
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
        print(f"[complete] Project {token} fully completed by both parties")
    else:
        print(f"[complete] Homeowner marked complete for {token}, waiting for contractor")

    db.commit()
    db.refresh(project)

    return ProjectResponse.model_validate(project)
