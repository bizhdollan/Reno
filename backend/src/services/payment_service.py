"""
Payment service using Stripe.

Handles Stripe Checkout session creation and webhook verification.
"""
import os
import stripe
from typing import Dict, Optional

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


class PaymentService:
    """Payment service for Stripe integration"""
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        if self.api_key:
            stripe.api_key = self.api_key
        self.base_url = os.getenv("BASE_URL", "http://localhost:3000")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    def create_checkout_session(
        self,
        unlock_token: str,
        project_type: str,
        amount: int = 19900  # $199.00 in cents
    ) -> Dict:
        """
        Create a Stripe Checkout session for project unlock.
        
        Args:
            unlock_token: The UNL-XXXXX token
            project_type: Type of project (for description)
            amount: Amount in cents (default $199.00)
        
        Returns:
            Dict with checkout session URL and ID
        """
        if not self.api_key:
            # Return mock checkout URL for testing
            print(f"⚠️ STRIPE_SECRET_KEY not set, returning mock checkout URL")
            return {
                'checkout_url': f"{self.base_url}/unlock/success?unlock_token={unlock_token}",
                'session_id': f'mock_session_{unlock_token}'
            }
        
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f'Unlock {project_type} Project',
                                'description': 'Access to full project details and homeowner contact',
                            },
                            'unit_amount': amount,
                        },
                        'quantity': 1,
                    }
                ],
                mode='payment',
                success_url=f"{self.base_url}/unlock/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.base_url}/marketplace",
                metadata={
                    'unlock_token': unlock_token,
                },
            )
            
            return {
                'checkout_url': session.url,
                'session_id': session.id
            }
        
        except stripe.error.StripeError as e:
            print(f"Stripe error: {str(e)}")
            raise
        except Exception as e:
            print(f"Payment setup error: {str(e)}")
            raise
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> stripe.Event:
        """
        Verify that webhook came from Stripe (security!)
        """
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if not webhook_secret:
            print("⚠️ STRIPE_WEBHOOK_SECRET not set, skipping verification")
            # For testing, create a mock event
            import json
            return json.loads(payload.decode())
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            print(f"Webhook signature verification failed: {str(e)}")
            raise
    
    def get_session(self, session_id: str) -> Optional[stripe.checkout.Session]:
        """
        Retrieve checkout session details
        """
        if not self.api_key:
            return None
        
        try:
            return stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            print(f"Error retrieving session: {str(e)}")
            return None


# Singleton
payment_service = PaymentService()

