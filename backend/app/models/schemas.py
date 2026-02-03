"""
Normalized Schemas for Omni-Flow Medspa AI
PRD v1.2 Compliance: Section 4.1 & 4.2
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime


# ============================================================================
# 4.1 Normalized Input Object
# ============================================================================


class NormalizedInput(BaseModel):
    """
    PRD 4.1: Standard format for all incoming messages.
    Converts WhatsApp/Instagram/Telegram/Web payloads into unified structure.
    """

    user_id: str = Field(..., description="Phone number or social handle")
    channel: Literal["web", "whatsapp", "instagram", "telegram"] = Field(
        ..., description="Source channel"
    )
    message: str = Field(..., description="User message text")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO 8601 timestamp",
    )
    # Optional metadata
    media_url: Optional[str] = Field(None, description="URL of attached media")
    media_type: Optional[Literal["image", "video", "audio", "document"]] = None
    reply_to_message_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Channel-specific context (page URL, etc.)"
    )


# ============================================================================
# 4.2 AI Output Object (The "Router" Payload)
# ============================================================================


class HandoffUIAction(BaseModel):
    """Channel-specific UI action for handoff scenarios."""

    type: Literal[
        "SLIDE_CALENDAR",
        "PRIORITY_BOOKING",
        "LIVE_AGENT",
        "BUTTONS",
        "INLINE_KEYBOARD",
        "TEXT_ONLY",
    ]
    variant: Optional[str] = None
    options: Optional[List[str]] = None
    url: Optional[str] = None


class ChannelUIActions(BaseModel):
    """PRD Module C: Different UI actions per channel."""

    web: Optional[HandoffUIAction] = None
    whatsapp: Optional[HandoffUIAction] = None
    instagram: Optional[HandoffUIAction] = None
    telegram: Optional[HandoffUIAction] = None


class AIOutputPayload(BaseModel):
    """
    PRD 4.2: Structured AI output for the Router.
    Enables backend to trigger specific UI logic per channel.
    """

    text_response: str = Field(..., description="The AI's text response to the user")
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        default="neutral", description="Detected sentiment of the conversation"
    )
    intent: Literal[
        "greeting",
        "booking",
        "inquiry",
        "complaint",
        "high_value",
        "ambiguous",
        "fallback",
    ] = Field(default="inquiry", description="Classified user intent")
    required_action: Literal[
        "NONE",
        "OPEN_CALENDAR",
        "PRIORITY_BOOKING",
        "HANDOFF_LIVE_AGENT",
        "SEND_PAYMENT_LINK",
        "SHOW_HYBRID_OPTIONS",
    ] = Field(default="NONE", description="Backend action to trigger")
    handoff_flag: bool = Field(
        default=False, description="Whether to escalate to human staff"
    )
    handoff_reason: Optional[
        Literal["ambiguity", "high_value", "complaint", "medical_risk", "fallback"]
    ] = None
    ui_actions: Optional[ChannelUIActions] = Field(
        None, description="Channel-specific UI instructions"
    )
    # Metadata for analytics
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="AI confidence score"
    )
    extracted_data: Optional[Dict[str, Any]] = Field(
        None, description="Extracted lead data (name, phone, service_interest)"
    )


# ============================================================================
# Handoff Reason Presets (PRD Module C)
# ============================================================================


def get_handoff_ui_actions(
    reason: str, channel: str = "web"
) -> Optional[ChannelUIActions]:
    """
    PRD Module C: Return channel-specific UI actions based on handoff reason.
    """
    presets = {
        "ambiguity": ChannelUIActions(
            web=HandoffUIAction(type="SLIDE_CALENDAR", variant="consultation"),
            whatsapp=HandoffUIAction(
                type="BUTTONS", options=["Book Now", "Chat Human"]
            ),
            instagram=HandoffUIAction(
                type="BUTTONS", options=["Book Now", "Chat Human"]
            ),
            telegram=HandoffUIAction(
                type="INLINE_KEYBOARD", options=["Book Now", "Chat Human"]
            ),
        ),
        "high_value": ChannelUIActions(
            web=HandoffUIAction(type="PRIORITY_BOOKING", variant="vip"),
            whatsapp=HandoffUIAction(
                type="BUTTONS",
                options=["VIP Booking"],
                url="https://luxemedspa.com/vip-booking",
            ),
            instagram=HandoffUIAction(
                type="BUTTONS",
                options=["VIP Booking"],
                url="https://luxemedspa.com/vip-booking",
            ),
            telegram=HandoffUIAction(
                type="INLINE_KEYBOARD",
                options=["VIP Booking"],
                url="https://luxemedspa.com/vip-booking",
            ),
        ),
        "complaint": ChannelUIActions(
            web=HandoffUIAction(type="LIVE_AGENT"),
            whatsapp=HandoffUIAction(type="TEXT_ONLY"),
            instagram=HandoffUIAction(type="TEXT_ONLY"),
            telegram=HandoffUIAction(type="TEXT_ONLY"),
        ),
        "medical_risk": ChannelUIActions(
            web=HandoffUIAction(type="LIVE_AGENT"),
            whatsapp=HandoffUIAction(type="TEXT_ONLY"),
            instagram=HandoffUIAction(type="TEXT_ONLY"),
            telegram=HandoffUIAction(type="TEXT_ONLY"),
        ),
        "fallback": ChannelUIActions(
            web=HandoffUIAction(
                type="BUTTONS", options=["Book Call", "Wait for Staff"]
            ),
            whatsapp=HandoffUIAction(
                type="BUTTONS", options=["Book Call", "Wait for Staff"]
            ),
            instagram=HandoffUIAction(
                type="BUTTONS", options=["Book Call", "Wait for Staff"]
            ),
            telegram=HandoffUIAction(
                type="INLINE_KEYBOARD", options=["Book Call", "Wait for Staff"]
            ),
        ),
    }

    return presets.get(reason)
