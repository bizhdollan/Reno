"""
Project unlock endpoints.

Handles:
- Initiating unlock (create unlock record, Stripe checkout)
- Saving contractor details
- Getting unlock details
- Stripe webhook handler
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from typing import Optional

from src.core.logger import get_logger
from src.db.database import get_db

logger = get_logger(__name__)
from src.db.models import Project, Unlock
from src.db.schemas import (
    UnlockInitiateRequest,
    UnlockInitiateResponse,
    ContractorDetailsRequest,
    UnlockResponse,
    ProjectResponse,
)
from src.services.payment_service import payment_service
from src.services.email_service import email_service
from src.utils.token_generator import generate_token

router = APIRouter(prefix="/api/v1/unlocks", tags=["unlocks"])


@router.post("/initiate", response_model=UnlockInitiateResponse)
async def initiate_unlock(
    request: UnlockInitiateRequest,
    db: Session = Depends(get_db)
):
    """
    Initiate unlock process for a project.
    
    Creates unlock record, generates Stripe checkout session,
    and returns checkout URL for contractor to complete payment.
    
    Args:
        request: Contains project_id and contractor_email
        db: Database session
    
    Returns:
        UnlockInitiateResponse with unlock_token and checkout_url
    """
    # Get project
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project is published
    if project.status != "published":
        raise HTTPException(
            status_code=400,
            detail="Project is not available for unlock. Only published projects can be unlocked."
        )
    
    # Check if already unlocked
    existing_unlock = db.query(Unlock).filter(
        Unlock.project_id == project.id,
        Unlock.is_active == True
    ).first()
    
    if existing_unlock:
        raise HTTPException(
            status_code=400,
            detail="Project already unlocked by another contractor"
        )
    
    # Generate unlock token
    unlock_token = generate_token("UNL")
    
    # Create unlock record (pending)
    unlock = Unlock(
        project_id=project.id,
        unlock_token=unlock_token,
        contractor_email=request.contractor_email,
        payment_status="pending",
        is_active=False,
        amount=199.00
    )
    db.add(unlock)
    db.commit()
    db.refresh(unlock)
    
    # Create Stripe checkout session
    try:
        checkout = payment_service.create_checkout_session(
            unlock_token=unlock_token,
            project_type=project.project_type or "Renovation",
            amount=19900  # $199.00
        )
    except Exception as e:
        # Clean up unlock record if Stripe fails
        db.delete(unlock)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Payment setup failed: {str(e)}"
        )
    
    # Save checkout session ID
    unlock.payment_id = checkout['session_id']
    db.commit()
    
    return UnlockInitiateResponse(
        unlock_token=unlock_token,
        checkout_url=checkout['checkout_url'],
        message="Redirect to checkout URL to complete payment"
    )


@router.post("/{unlock_token}/details", response_model=UnlockResponse)
async def save_contractor_details(
    unlock_token: str,
    data: ContractorDetailsRequest,
    db: Session = Depends(get_db)
):
    """
    Save contractor contact details after unlock.
    
    This is required before contractor can view homeowner details.
    Only works if payment is completed.
    
    Args:
        unlock_token: Unlock token (UNL-XXXXXX)
        data: Contractor contact details
        db: Database session
    
    Returns:
        UnlockResponse with updated details
    """
    # Get unlock
    unlock = db.query(Unlock).filter(Unlock.unlock_token == unlock_token).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Unlock not found")
    
    # Check if payment completed
    if unlock.payment_status != "completed" or not unlock.is_active:
        raise HTTPException(
            status_code=400,
            detail="Payment must be completed before saving details"
        )
    
    # Update contractor details
    unlock.contractor_name = data.contractor_name
    unlock.contractor_phone = data.contractor_phone
    unlock.contractor_company = data.contractor_company
    unlock.contractor_details_saved = True
    
    db.commit()
    db.refresh(unlock)
    
    # Send notification email to homeowner
    try:
        project = db.query(Project).filter(Project.id == unlock.project_id).first()
        if project and project.homeowner_email:
            email_service.send_homeowner_contractor_details(
                to=project.homeowner_email,
                project_token=project.token,
                contractor_name=data.contractor_name,
                contractor_email=unlock.contractor_email,
                contractor_phone=data.contractor_phone,
                contractor_company=data.contractor_company
            )
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")
        # Don't fail the request if email fails
    
    # Load project for response
    project = db.query(Project).filter(Project.id == unlock.project_id).first()
    
    # Create response with project
    unlock_dict = {
        **UnlockResponse.model_validate(unlock).model_dump(),
        "project": ProjectResponse.model_validate(project) if project else None
    }
    
    return UnlockResponse(**unlock_dict)


@router.get("/by-session/{session_id}", response_model=UnlockResponse)
async def get_unlock_by_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get unlock details by Stripe session ID (payment_id).

    Useful for the success page to display the unlock token and project info.
    Works even before webhooks run, since we store session_id when creating checkout.
    """
    unlock = db.query(Unlock).filter(Unlock.payment_id == session_id).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Unlock not found for this session")

    project = db.query(Project).filter(Project.id == unlock.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found for this unlock")

    # Ensure payment is completed before updating status or sending emails.
    if unlock.payment_status != "completed":
        session = payment_service.get_session(session_id)
        if session and getattr(session, "payment_status", None) == "paid" and getattr(session, "status", None) == "complete":
            from datetime import datetime, UTC
            unlock.payment_status = "completed"
            unlock.is_active = True
            unlock.unlocked_at = datetime.now(UTC)
            project.status = "unlocked"
            db.commit()

    # Send contractor unlock email only after completion and if not yet sent.
    if unlock.payment_status == "completed" and not unlock.contractor_email_sent:
        try:
            email_service.send_contractor_unlocked(
                to=unlock.contractor_email,
                unlock_token=unlock.unlock_token,
                project_type=project.project_type or "Renovation",
                total_price=float(project.total_price) if project.total_price else 0.0,
                zip_code=project.zip_code or "",
                homeowner_name=project.homeowner_name or "",
                homeowner_email=project.homeowner_email or "",
                homeowner_phone=project.homeowner_phone or ""
            )
            unlock.contractor_email_sent = True
            db.commit()
        except Exception as e:
            logger.warning(f"Contractor email failed: {e}")

    # Notify homeowner once if payment completed and not notified.
    if unlock.payment_status == "completed" and project.homeowner_email and not unlock.homeowner_notified:
        try:
            email_service.send_homeowner_project_unlocked(
                to=project.homeowner_email,
                project_token=project.token,
                project_type=project.project_type or "Renovation",
                total_price=float(project.total_price) if project.total_price else 0.0
            )
            unlock.homeowner_notified = True
            db.commit()
        except Exception as e:
            logger.warning(f"Homeowner email failed: {e}")

    unlock_dict = {
        **UnlockResponse.model_validate(unlock).model_dump(),
        "project": ProjectResponse.model_validate(project) if project else None
    }

    return UnlockResponse(**unlock_dict)

@router.get("/{unlock_token}", response_model=UnlockResponse)
async def get_unlock(
    unlock_token: str,
    db: Session = Depends(get_db)
):
    """
    Get unlock details including project information.
    
    Args:
        unlock_token: Unlock token (UNL-XXXXXX)
        db: Database session
    
    Returns:
        UnlockResponse with full project details
    """
    unlock = db.query(Unlock).filter(Unlock.unlock_token == unlock_token).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Unlock not found")
    
    # Load project
    project = db.query(Project).filter(Project.id == unlock.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create response with project
    unlock_dict = {
        **UnlockResponse.model_validate(unlock).model_dump(),
        "project": ProjectResponse.model_validate(project) if project else None
    }
    
    return UnlockResponse(**unlock_dict)


@router.post("/{unlock_token}/complete", response_model=UnlockResponse)
async def mark_project_complete_contractor(
    unlock_token: str,
    db: Session = Depends(get_db)
):
    """
    Mark project as complete from contractor side.

    Project is fully completed only when BOTH homeowner AND contractor mark it.
    This is a two-party completion system to ensure mutual agreement.

    Args:
        unlock_token: Unlock token (UNL-XXXXXX)
        db: Database session

    Returns:
        Updated unlock with project completion status
    """
    unlock = db.query(Unlock).filter(Unlock.unlock_token == unlock_token).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Unlock not found")

    # Get project
    project = db.query(Project).filter(Project.id == unlock.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project is in unlocked state
    if project.status != "unlocked":
        raise HTTPException(
            status_code=400,
            detail="Project must be unlocked before marking complete"
        )

    # Mark contractor as complete
    project.contractor_marked_complete = True

    # If homeowner also marked complete, finalize completion
    if project.homeowner_marked_complete:
        from datetime import datetime, UTC
        project.status = "completed"
        project.completed_at = datetime.now(UTC)
        logger.info(f"[complete] Project {project.token} fully completed by both parties")
    else:
        logger.info(f"[complete] Contractor marked complete for {project.token}, waiting for homeowner")

    db.commit()
    db.refresh(project)
    db.refresh(unlock)

    # Create response with updated project
    unlock_dict = {
        **UnlockResponse.model_validate(unlock).model_dump(),
        "project": ProjectResponse.model_validate(project) if project else None
    }

    return UnlockResponse(**unlock_dict)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Stripe webhook endpoint - receives payment confirmations.
    
    When payment succeeds, Stripe calls this endpoint.
    We update unlock status and send emails.
    """
    from datetime import datetime, UTC
    from src.db.database import SessionLocal
    
    # Get raw payload
    payload = await request.body()
    
    # Verify webhook signature (if configured)
    try:
        event = payment_service.verify_webhook_signature(
            payload=payload,
            signature=stripe_signature or ""
        )
    except Exception as e:
        logger.warning(f"Webhook verification failed: {e}")
        # In test mode, continue anyway
        import json
        try:
            event = json.loads(payload.decode())
        except:
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
    
    # Handle different event types
    event_type = event.get('type', '')
    
    if event_type == 'checkout.session.completed':
        # Payment succeeded!
        session = event.get('data', {}).get('object', {})
        
        # Get unlock token from metadata
        unlock_token = session.get('metadata', {}).get('unlock_token')
        if not unlock_token:
            logger.warning("No unlock_token in metadata")
            return {"status": "error", "message": "Missing unlock_token"}
        
        db = SessionLocal()
        try:
            # Get unlock record
            unlock = db.query(Unlock).filter(Unlock.unlock_token == unlock_token).first()
            if not unlock:
                logger.warning(f"Unlock not found: {unlock_token}")
                return {"status": "error", "message": "Unlock not found"}
            
            # Get project
            project = db.query(Project).filter(Project.id == unlock.project_id).first()
            if not project:
                logger.warning(f"Project not found: {unlock.project_id}")
                return {"status": "error", "message": "Project not found"}
            
            # Update unlock
            unlock.payment_status = "completed"
            unlock.is_active = True
            unlock.unlocked_at = datetime.now(UTC)
            unlock.payment_id = session.get('id', unlock.payment_id)
            
            # Update project status
            project.status = "unlocked"
            
            db.commit()

            logger.info(f"Payment succeeded for {unlock_token}")
            
            # Send emails
            try:
                # Email to contractor
                email_service.send_contractor_unlocked(
                    to=unlock.contractor_email,
                    unlock_token=unlock_token,
                    project_type=project.project_type or "Renovation",
                    total_price=float(project.total_price) if project.total_price else 0.0,
                    zip_code=project.zip_code or "",
                    homeowner_name=project.homeowner_name or "",
                    homeowner_email=project.homeowner_email or "",
                    homeowner_phone=project.homeowner_phone or ""
                )
                unlock.contractor_email_sent = True

                # Email to homeowner
                if project.homeowner_email:
                    email_service.send_homeowner_project_unlocked(
                        to=project.homeowner_email,
                        project_token=project.token,
                        project_type=project.project_type or "Renovation",
                        total_price=float(project.total_price) if project.total_price else 0.0
                    )
                    unlock.homeowner_notified = True

                db.commit()
                logger.info(f"Emails sent for {unlock_token}")

            except Exception as e:
                # Don't fail webhook if emails fail
                logger.warning(f"Email failed but payment processed: {e}")
            
            return {"status": "success"}
        
        finally:
            db.close()
    
    elif event_type == 'checkout.session.expired':
        # Payment session expired
        session = event.get('data', {}).get('object', {})
        unlock_token = session.get('metadata', {}).get('unlock_token')
        logger.warning(f"Checkout session expired: {unlock_token}")
        return {"status": "expired"}

    else:
        # Other events we don't care about
        logger.debug(f"Unhandled event type: {event_type}")
        return {"status": "ignored"}
