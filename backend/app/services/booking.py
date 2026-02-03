"""
Booking Service - Handles appointment confirmations and Stripe webhooks
"""

import os
import stripe
from datetime import datetime
from dotenv import load_dotenv
from .supabase_client import supabase

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


async def handle_stripe_webhook(payload: bytes, signature: str) -> dict:
    """
    Process Stripe webhook events.
    Called when payment is completed, failed, or expired.
    """
    try:
        # Verify webhook signature
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
        else:
            # Dev mode - parse without verification
            import json

            event = json.loads(payload)

        event_type = event.get("type", "")

        if event_type == "checkout.session.completed":
            return await _handle_payment_success(event["data"]["object"])
        elif event_type == "checkout.session.expired":
            return await _handle_payment_expired(event["data"]["object"])
        else:
            return {"status": "ignored", "event_type": event_type}

    except stripe.error.SignatureVerificationError:
        return {"status": "error", "message": "Invalid signature"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _handle_payment_success(session: dict) -> dict:
    """
    Called when a deposit payment is completed.
    Confirms the booking in the database.
    """
    session_id = session.get("id")

    # Update booking status in Supabase
    try:
        _result = (
            supabase.table("bookings")
            .update(
                {"deposit_status": "paid", "updated_at": datetime.now().isoformat()}
            )
            .eq("stripe_session_id", session_id)
            .execute()
        )

        # TODO: Call Zenoti/Mindbody API to confirm appointment
        # TODO: Send confirmation message to patient via WhatsApp/SMS

        return {
            "status": "success",
            "action": "booking_confirmed",
            "session_id": session_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _handle_payment_expired(session: dict) -> dict:
    """
    Called when a payment link expires without payment.
    Releases the held slot.
    """
    session_id = session.get("id")

    try:
        _result = (
            supabase.table("bookings")
            .update(
                {"deposit_status": "expired", "updated_at": datetime.now().isoformat()}
            )
            .eq("stripe_session_id", session_id)
            .execute()
        )

        # TODO: Release the held slot in booking system
        # TODO: Send follow-up message to lead

        return {
            "status": "success",
            "action": "slot_released",
            "session_id": session_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def create_pending_booking(
    lead_id: str,
    service: str,
    appointment_time: datetime,
    stripe_session_id: str,
    deposit_amount: int,
    treatment_area: str = "",
    client_concerns: str = "",
    conversation_summary: str = "",
) -> dict:
    """
    Create a pending booking record when payment link is generated.
    Includes full conversation context for staff reference.
    """
    try:
        result = (
            supabase.table("bookings")
            .insert(
                {
                    "lead_id": lead_id,
                    "service_interested": service,
                    "treatment_area": treatment_area,
                    "client_concerns": client_concerns,
                    "conversation_summary": conversation_summary,
                    "appointment_time": appointment_time.isoformat(),
                    "stripe_session_id": stripe_session_id,
                    "deposit_amount": deposit_amount,
                    "deposit_status": "pending",
                }
            )
            .execute()
        )

        return {"status": "success", "booking_id": result.data[0]["id"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
