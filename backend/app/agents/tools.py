"""
Real Integration Tools for Aesthetic-OS
- Stripe: Payment Links for Deposits
- Cal.com: Appointment Scheduling
- CRM: Lead qualification and sync
"""

import os
import stripe
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Tool definitions for LangGraph (OpenAI function calling format)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to check (e.g., '2024-01-15' or 'tomorrow').",
                    }
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment slot for a client. Call this after checking availability and collecting lead details. Include treatment details so the doctor knows what to expect.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_time": {
                        "type": "string",
                        "description": "The time slot to book (e.g., '10:00 AM' or ISO datetime).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Client's full name.",
                    },
                    "email": {
                        "type": "string",
                        "description": "Client's email address.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Client's phone number.",
                    },
                    "service": {
                        "type": "string",
                        "description": "The treatment being booked (e.g., 'Botox', 'Lip Filler').",
                    },
                    "treatment_area": {
                        "type": "string",
                        "description": "Specific area for treatment (e.g., 'Forehead', 'Lips', 'Jawline', 'Full Face').",
                    },
                    "client_concerns": {
                        "type": "string",
                        "description": "What the client mentioned they want to address (e.g., 'forehead wrinkles', 'lip volume', 'fine lines').",
                    },
                    "conversation_summary": {
                        "type": "string",
                        "description": "Brief summary of the conversation for the doctor's reference.",
                    },
                },
                "required": ["slot_time", "name", "email", "service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_lead_details",
            "description": "Capture and validate lead contact details. Use this to collect name, email, and phone before booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Client's full name.",
                    },
                    "email": {
                        "type": "string",
                        "description": "Client's email address.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Client's phone number (optional).",
                    },
                    "service_interest": {
                        "type": "string",
                        "description": "What treatment they're interested in.",
                    },
                },
                "required": ["name", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_payment_link",
            "description": "Generate a Stripe payment link for a deposit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "description": "The deposit amount in USD (e.g., 50 for $50).",
                    },
                    "service": {
                        "type": "string",
                        "description": "The service being booked (e.g., 'Botox Consultation').",
                    },
                },
                "required": ["amount", "service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "qualify_lead",
            "description": "Qualify a lead based on their answers to medical screening questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_interest": {
                        "type": "string",
                        "description": "The treatment they're interested in.",
                    },
                    "timeline": {
                        "type": "string",
                        "description": "When they want treatment (ASAP, This Month, Just Browsing).",
                    },
                    "pregnant": {
                        "type": "boolean",
                        "description": "Whether the patient is pregnant.",
                    },
                    "recent_surgery": {
                        "type": "boolean",
                        "description": "Whether they had recent facial surgery.",
                    },
                },
                "required": ["service_interest", "timeline", "pregnant"],
            },
        },
    },
]


def check_availability(date: str = None):
    """
    Check available appointment slots via Cal.com.
    Falls back to mock data if Cal.com is not configured.
    """
    from ..services.calendar import calendar_service
    import asyncio

    # Run async function synchronously
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create new loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run, calendar_service.get_available_slots(date)
                ).result()
                return result
        else:
            return asyncio.run(calendar_service.get_available_slots(date))
    except Exception:
        # Fallback to mock on any error
        return calendar_service._get_mock_availability(date)


def book_appointment(
    slot_time: str,
    name: str,
    email: str,
    phone: str = "",
    service: str = "Consultation",
    treatment_area: str = "",
    client_concerns: str = "",
    conversation_summary: str = "",
):
    """
    Book an appointment slot for a client.
    Uses Cal.com API if configured, otherwise creates mock booking.
    Includes full treatment context for the doctor.
    Also syncs lead to CRM.
    """
    from ..services.calendar import calendar_service
    from ..services.crm import crm_service
    import asyncio

    # Create booking in calendar with full context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                booking_result = pool.submit(
                    asyncio.run,
                    calendar_service.create_booking(
                        slot_time=slot_time,
                        name=name,
                        email=email,
                        phone=phone,
                        notes="",
                        service=service,
                        conversation_summary=conversation_summary,
                        treatment_area=treatment_area,
                        client_concerns=client_concerns,
                    ),
                ).result()
        else:
            booking_result = asyncio.run(
                calendar_service.create_booking(
                    slot_time=slot_time,
                    name=name,
                    email=email,
                    phone=phone,
                    notes="",
                    service=service,
                    conversation_summary=conversation_summary,
                    treatment_area=treatment_area,
                    client_concerns=client_concerns,
                )
            )
    except Exception:
        booking_result = calendar_service._create_mock_booking(
            slot_time, name, email, service, conversation_summary
        )

    # Sync to CRM if booking successful
    if booking_result.get("success"):
        try:
            lead_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "interests": service,
                "status": "booked",
                "channel": "web",
            }
            # Fire and forget CRM sync
            asyncio.create_task(crm_service.sync_lead(lead_data))
        except Exception:
            pass  # Don't fail booking if CRM sync fails

    return booking_result


def capture_lead_details(
    name: str, email: str, phone: str = "", service_interest: str = ""
):
    """
    Capture and validate lead contact details.
    Syncs to CRM and returns confirmation.
    """
    from ..services.crm import crm_service
    import asyncio
    import re

    # Validate email format
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return {
            "success": False,
            "error": "Invalid email format",
            "message": "Could you please provide a valid email address?",
        }

    # Clean phone number
    if phone:
        phone = re.sub(r"[^\d+]", "", phone)

    lead_data = {
        "name": name,
        "email": email,
        "phone": phone,
        "interests": service_interest,
        "status": "new",
        "channel": "web",
    }

    # Sync to CRM
    try:
        asyncio.create_task(crm_service.sync_lead(lead_data))
    except Exception:
        pass  # Don't fail if CRM sync fails

    return {
        "success": True,
        "lead": lead_data,
        "message": f"Perfect, I have your details {name}. Let me check available times for you.",
    }


def generate_payment_link(amount: int = 50, service: str = "Consultation Deposit"):
    """
    Generate a real Stripe Payment Link for deposits.
    Uses Stripe API to create a checkout session.
    """
    if not stripe.api_key or stripe.api_key == "sk_test_REPLACE_WITH_YOUR_KEY":
        # Fallback to mock if no API key configured
        return {
            "url": f"https://checkout.stripe.com/demo/{service.replace(' ', '_')}",
            "amount": amount,
            "status": "mock_mode",
            "message": "Configure STRIPE_SECRET_KEY for real payments",
        }

    try:
        # Create a Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": service,
                            "description": f"Deposit for {service} at Luxe MedSpa",
                        },
                        "unit_amount": amount * 100,  # Stripe uses cents
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url="https://luxemedspa.com/booking-confirmed?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://luxemedspa.com/booking-cancelled",
            expires_at=int((datetime.now() + timedelta(minutes=10)).timestamp()),
        )

        return {
            "url": session.url,
            "session_id": session.id,
            "amount": amount,
            "expires_in": "10 minutes",
            "status": "live",
        }

    except stripe.error.StripeError as e:
        return {"error": str(e), "status": "failed"}


def qualify_lead(
    service_interest: str = None,
    timeline: str = None,
    pregnant: bool = False,
    recent_surgery: bool = False,
    answers: dict = None,  # Legacy support
):
    """
    Qualify a lead based on medical screening answers.
    Returns qualification status and any flags for human review.
    Also syncs qualified leads to CRM.
    """
    from ..services.crm import crm_service
    import asyncio

    # Support legacy dict format
    if answers:
        service_interest = answers.get("service_interest", service_interest)
        timeline = answers.get("timeline", timeline)
        pregnant = answers.get("pregnant", pregnant)
        recent_surgery = answers.get("recent_surgery", recent_surgery)

    # Safety Disqualifications (require human handoff)
    if pregnant:
        return {
            "qualified": False,
            "reason": "Medical Contraindication: Pregnancy",
            "action": "ESCALATE_TO_HUMAN",
            "message": "I'll connect you with our medical team to discuss safe alternatives.",
        }

    if recent_surgery:
        return {
            "qualified": False,
            "reason": "Recent Surgery - Requires Medical Clearance",
            "action": "ESCALATE_TO_HUMAN",
            "message": "Let me have our nurse practitioner review your case first.",
        }

    # Timeline-based prioritization
    priority = "normal"
    if timeline and timeline.lower() in ["asap", "this week", "urgent"]:
        priority = "high"
    elif timeline and timeline.lower() in ["just browsing", "researching", "not sure"]:
        priority = "low"

    # Sync qualified lead to CRM
    try:
        lead_data = {
            "interests": service_interest,
            "status": "qualified",
            "channel": "web",
        }
        asyncio.create_task(crm_service.sync_lead(lead_data))
    except Exception:
        pass

    return {
        "qualified": True,
        "priority": priority,
        "service": service_interest,
        "action": "PROCEED_TO_BOOKING",
        "message": f"Great choice with {service_interest}! Let's find you an appointment.",
    }
