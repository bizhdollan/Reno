"""
Email service using Resend.

Handles sending emails for project tokens, unlock notifications, etc.
"""
import os
from typing import Optional
from pathlib import Path

# Initialize Resend only if API key is available
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

if RESEND_API_KEY:
    import resend
    resend.api_key = RESEND_API_KEY
else:
    resend = None  # Will check this before using


class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        self.from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
        self.base_url = os.getenv("BASE_URL", "http://localhost:3000")
    
    def send_email(
        self,
        to: str,
        subject: str,
        html: str
    ) -> dict:
        """
        Send an email via Resend.
        
        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML email content
        
        Returns:
            Response dict from Resend API
        """
        if not RESEND_API_KEY or resend is None:
            print(f"⚠️ RESEND_API_KEY not set, skipping email to {to}")
            return {"id": "skipped", "message": "Email service not configured"}
        
        try:
            params = {
                "from": self.from_email,
                "to": [to],
                "subject": subject,
                "html": html
            }
            response = resend.Emails.send(params)
            print(f"✅ Email sent to {to}: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            # Log error but don't raise - allow endpoint to continue
            error_msg = str(e)
            print(f"⚠️ Email failed to {to}: {error_msg}")
            # Return error dict instead of raising
            return {"id": "error", "message": error_msg}
    
    def send_project_saved(
        self,
        to: str,
        token: str,
        project_type: str,
        total_price: float,
        zip_code: str
    ) -> dict:
        """
        Send project saved email to homeowner.
        
        Args:
            to: Homeowner email
            token: Project token (PRJ-XXXXXX)
            project_type: Type of project
            total_price: Selected tier price
            zip_code: Project location
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code-box {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 2px; margin: 20px 0; border-radius: 5px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🏠 RenovationTech</h1>
                <p>Your Project Has Been Saved!</p>
            </div>
            
            <div class="content">
                <p>Hi there!</p>
                
                <p>Your renovation estimate has been successfully saved.</p>
                
                <div class="code-box">
                    {token}
                </div>
                
                <p style="text-align: center; color: #666;">
                    <strong>Save this code!</strong> You'll need it to access your project.
                </p>
                
                <div class="details">
                    <h3>📋 Project Details:</h3>
                    <ul>
                        <li><strong>Type:</strong> {project_type}</li>
                        <li><strong>Estimated Cost:</strong> ${total_price:,.0f}</li>
                        <li><strong>Location:</strong> ZIP {zip_code}</li>
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <a href="{self.base_url}/projects?token={token}" class="button">
                        View Your Project
                    </a>
                </div>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                
                <h3>📤 Ready to find contractors?</h3>
                <p>To publish your project to the marketplace:</p>
                <ol>
                    <li>Visit "My Projects"</li>
                    <li>Enter your project code</li>
                    <li>Click "Publish to Marketplace"</li>
                </ol>
                
                <p>Your project will be visible to qualified contractors in your area.</p>
            </div>
            
            <div class="footer">
                <p>Questions? Reply to this email or visit our Help Center.</p>
                <p>© 2024 RenovationTech. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=to,
            subject=f"Your Project Code - {token}",
            html=html
        )
    
    def send_contractor_unlocked(
        self,
        to: str,
        unlock_token: str,
        project_type: str,
        total_price: float,
        zip_code: str,
        homeowner_name: str,
        homeowner_email: str,
        homeowner_phone: str
    ):
        """Send unlock notification to contractor"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code-box {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 2px; margin: 20px 0; border-radius: 5px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔓 Project Unlocked!</h1>
            </div>
            
            <div class="content">
                <p>Congratulations! You've unlocked a renovation project.</p>
                
                <div class="code-box">
                    {unlock_token}
                </div>
                
                <p style="text-align: center; color: #666;">
                    <strong>Save this code!</strong> You'll use it to access the project details.
                </p>
                
                <div class="details">
                    <h3>📋 Project Summary:</h3>
                    <ul>
                        <li><strong>Type:</strong> {project_type}</li>
                        <li><strong>Budget:</strong> ${total_price:,.0f}</li>
                        <li><strong>Location:</strong> ZIP {zip_code}</li>
                    </ul>
                </div>
                
                <div class="details">
                    <h3>🏠 Homeowner Contact:</h3>
                    <ul>
                        <li><strong>Name:</strong> {homeowner_name}</li>
                        <li><strong>Email:</strong> {homeowner_email}</li>
                        <li><strong>Phone:</strong> {homeowner_phone}</li>
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <a href="{self.base_url}/projects?token={unlock_token}" class="button">
                        View Full Details
                    </a>
                </div>
                
                <p style="color: #d32f2f; font-weight: bold;">
                    ⚠️ You must save your contact details so the homeowner can reach you!
                </p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=to,
            subject=f"Project Unlocked - {unlock_token}",
            html=html
        )
    
    def send_homeowner_project_unlocked(
        self,
        to: str,
        project_token: str,
        project_type: str,
        total_price: float
    ):
        """Notify homeowner that contractor unlocked their project"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Good News!</h1>
            </div>
            
            <div class="content">
                <p>A contractor has unlocked your renovation project!</p>
                
                <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                    <h3>Project: {project_type}</h3>
                    <p><strong>Budget:</strong> ${total_price:,.0f}</p>
                </div>
                
                <p>The contractor can now see your contact details and will reach out soon.</p>
                
                <div style="text-align: center;">
                    <a href="{self.base_url}/projects?token={project_token}" class="button">
                        View Your Project
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=to,
            subject=f"A Contractor Has Unlocked Your Project!",
            html=html
        )
    
    def send_homeowner_contractor_details(
        self,
        to: str,
        project_token: str,
        contractor_name: str,
        contractor_email: str,
        contractor_phone: str,
        contractor_company: str
    ):
        """Notify homeowner that contractor saved their details"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>👷 Contractor Details Available</h1>
            </div>
            
            <div class="content">
                <p>The contractor who unlocked your project has saved their contact details.</p>
                
                <div class="details">
                    <h3>Contractor Information:</h3>
                    <ul>
                        <li><strong>Name:</strong> {contractor_name}</li>
                        <li><strong>Email:</strong> {contractor_email}</li>
                        <li><strong>Phone:</strong> {contractor_phone}</li>
                        <li><strong>Company:</strong> {contractor_company}</li>
                    </ul>
                </div>
                
                <p>They can see your details and may contact you directly.</p>
                
                <div style="text-align: center;">
                    <a href="{self.base_url}/projects?token={project_token}" class="button">
                        View Full Project
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=to,
            subject=f"Contractor Details Available",
            html=html
        )


# Singleton instance
email_service = EmailService()

