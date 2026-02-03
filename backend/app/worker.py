"""
Celery Worker - Event Processing Pipeline
Routes events to platform-specific agents

PRD v1.2 Compliance:
- FR-A1: Unified webhook processing
- Section 4.1: Normalized Input Object
- Section 4.2: AI Output Payload (Router)
"""

import os
import asyncio
from datetime import datetime
from celery import Celery
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from .agents.graph import app as graph_app
from .agents.instagram import instagram_agent
from .agents.whatsapp import whatsapp_agent
from .models.schemas import NormalizedInput, AIOutputPayload, get_handoff_ui_actions

load_dotenv()

# Configure Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("aesthetic_worker", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
)


def run_async(coro):
    """Helper to run async functions in sync Celery worker."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# PRD 4.1: Input Normalization Layer
# ============================================================================


def normalize_input(source: str, payload: dict) -> NormalizedInput:
    """
    PRD 4.1: Convert channel-specific payloads into unified format.
    Handles WhatsApp, Instagram, Telegram, and Web payloads.
    """
    # Extract user_id based on source
    user_id = (
        payload.get("user_id")
        or payload.get("from")
        or payload.get("sender_id")
        or payload.get("wa_id")
        or payload.get("instagram_user_id")
        or payload.get("telegram_user_id")
        or "anonymous"
    )

    # Extract message text
    message = (
        payload.get("message")
        or payload.get("text")
        or payload.get("content")
        or payload.get("body")
        or ""
    )

    # Handle nested message objects (WhatsApp/Instagram format)
    if isinstance(payload.get("message"), dict):
        message = payload["message"].get("text") or payload["message"].get("body", "")

    # Extract timestamp
    timestamp = payload.get("timestamp") or datetime.now().isoformat()

    # Extract media if present
    media_url = payload.get("media_url") or payload.get("image_url")
    media_type = None
    if media_url:
        if any(ext in media_url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif"]):
            media_type = "image"
        elif any(ext in media_url.lower() for ext in [".mp4", ".mov"]):
            media_type = "video"

    # Map source to channel enum
    channel_map = {
        "web": "web",
        "whatsapp": "whatsapp",
        "instagram": "instagram",
        "telegram": "telegram",
        "wa": "whatsapp",
        "ig": "instagram",
        "tg": "telegram",
    }
    channel = channel_map.get(source.lower(), "web")

    # Build context
    context = {}
    if payload.get("page_url"):
        context["page_url"] = payload["page_url"]
    if payload.get("referrer"):
        context["referrer"] = payload["referrer"]

    return NormalizedInput(
        user_id=str(user_id),
        channel=channel,
        message=str(message) if message else "",
        timestamp=str(timestamp),
        media_url=media_url,
        media_type=media_type,
        context=context,
    )


# ============================================================================
# Main Event Router
# ============================================================================


@celery_app.task(name="process_event")
def process_event(event_type: str, payload: dict):
    """
    Main event router (PRD FR-A1).
    Normalizes input and routes to platform-specific agents.
    """
    print(f"Processing event: {event_type}")

    try:
        # Step 1: Normalize input (PRD 4.1)
        normalized = normalize_input(event_type, payload)
        print(f"Normalized: user={normalized.user_id}, channel={normalized.channel}")

        # Step 2: Route to platform-specific agent
        if normalized.channel == "instagram":
            return process_instagram_event(payload, normalized)
        elif normalized.channel == "whatsapp":
            return process_whatsapp_event(payload, normalized)
        elif normalized.channel == "telegram":
            return process_telegram_event(payload, normalized)
        else:
            # Default: Web channel via generic LangGraph
            return process_web_event(normalized)

    except Exception as e:
        print(f"Error processing event: {e}")
        return {"status": "error", "error": str(e)}


def process_instagram_event(payload: dict, normalized: NormalizedInput) -> dict:
    """Handle Instagram-specific events (comments, DMs)."""
    print("Routing to Instagram Agent...")

    # Check if it's a comment or DM
    if "comment" in payload or payload.get("field") == "comments":
        result = run_async(instagram_agent.handle_comment_webhook(payload))
    else:
        # For DMs, use the generic graph with normalized input
        result = run_graph_with_normalized_input(normalized)

    return result


def process_whatsapp_event(payload: dict, normalized: NormalizedInput) -> dict:
    """Handle WhatsApp-specific events."""
    print("Routing to WhatsApp Agent...")
    result = run_async(whatsapp_agent.handle_message(payload))
    return result


def process_telegram_event(payload: dict, normalized: NormalizedInput) -> dict:
    """
    Handle Telegram-specific events.
    PRD Zone 1: Telegram Channel Adapter.
    """
    print("Routing to Telegram Agent...")

    # For now, route through generic graph
    # TODO: Implement telegram_agent for full Telegram API support
    return run_graph_with_normalized_input(normalized)


def process_web_event(normalized: NormalizedInput) -> dict:
    """Handle Web widget events."""
    print("Routing to Web Agent...")
    return run_graph_with_normalized_input(normalized)


# ============================================================================
# PRD 4.2: Structured Output Handler
# ============================================================================


def run_graph_with_normalized_input(normalized: NormalizedInput) -> dict:
    """
    Execute LangGraph with normalized input and return structured output.
    PRD 4.2: Returns AIOutputPayload format.
    """
    if not normalized.message:
        return {"status": "skipped", "reason": "No message content"}

    inputs = {
        "messages": [HumanMessage(content=normalized.message)],
        "lead_data": {
            "source": normalized.channel,
            "user_id": normalized.user_id,
        },
        "language": "EN",
        "channel": normalized.channel,
    }

    try:
        result = graph_app.invoke(inputs)
        last_message = result["messages"][-1]
        response_text = last_message.content

        # Build structured output (PRD 4.2)
        output = build_ai_output_payload(
            text_response=response_text,
            result=result,
            channel=normalized.channel,
        )

        print(f"Agent Response: {output.text_response[:100]}...")
        return {
            "status": "success",
            **output.model_dump(),
        }

    except Exception as e:
        print(f"Error executing graph: {e}")
        return {"status": "error", "error": str(e)}


def build_ai_output_payload(
    text_response: str,
    result: dict,
    channel: str,
) -> AIOutputPayload:
    """
    Build PRD 4.2 compliant AI output payload.
    Analyzes response to determine intent, sentiment, and required actions.
    """
    # Extract handoff info from result if available
    handoff_flag = result.get("handoff_flag", False)
    handoff_reason = result.get("handoff_reason")

    # Determine intent from response content
    intent = classify_intent(text_response)

    # Determine sentiment
    sentiment = classify_sentiment(text_response)

    # Determine required action
    required_action = determine_required_action(intent, handoff_flag)

    # Get channel-specific UI actions if handoff
    ui_actions = None
    if handoff_flag and handoff_reason:
        ui_actions = get_handoff_ui_actions(handoff_reason, channel)

    return AIOutputPayload(
        text_response=text_response,
        sentiment=sentiment,
        intent=intent,
        required_action=required_action,
        handoff_flag=handoff_flag,
        handoff_reason=handoff_reason,
        ui_actions=ui_actions,
        confidence=0.85,
    )


def classify_intent(response: str) -> str:
    """Classify the intent from AI response."""
    response_lower = response.lower()

    if any(
        word in response_lower for word in ["book", "appointment", "schedule", "slot"]
    ):
        return "booking"
    if any(
        word in response_lower for word in ["hello", "hi", "welcome", "how can i help"]
    ):
        return "greeting"
    if any(
        word in response_lower
        for word in ["sorry", "apologize", "understand your concern"]
    ):
        return "complaint"
    if any(
        word in response_lower for word in ["vip", "package", "premium", "makeover"]
    ):
        return "high_value"
    if any(
        word in response_lower
        for word in ["let me check", "i'm not sure", "could you clarify"]
    ):
        return "ambiguous"

    return "inquiry"


def classify_sentiment(response: str) -> str:
    """Classify sentiment from AI response."""
    response_lower = response.lower()

    positive_words = [
        "great",
        "wonderful",
        "excited",
        "happy",
        "love",
        "perfect",
        "fantastic",
    ]
    negative_words = [
        "sorry",
        "apologize",
        "unfortunately",
        "concern",
        "worried",
        "issue",
    ]

    if any(word in response_lower for word in positive_words):
        return "positive"
    if any(word in response_lower for word in negative_words):
        return "negative"

    return "neutral"


def determine_required_action(intent: str, handoff_flag: bool) -> str:
    """Determine the required backend action based on intent."""
    if handoff_flag:
        return "HANDOFF_LIVE_AGENT"

    action_map = {
        "booking": "OPEN_CALENDAR",
        "high_value": "PRIORITY_BOOKING",
        "complaint": "HANDOFF_LIVE_AGENT",
        "ambiguous": "SHOW_HYBRID_OPTIONS",
        "fallback": "SHOW_HYBRID_OPTIONS",
    }

    return action_map.get(intent, "NONE")
