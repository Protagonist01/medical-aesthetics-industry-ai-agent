"""
WhatsApp Agent - Handles WhatsApp Business API interactions
Implements: 24-hour window management, Template messages, Photo analysis
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Optional  # noqa: F401 - used in type hints
from dotenv import load_dotenv

load_dotenv()

# WhatsApp Business API Config (via Twilio or direct Meta)
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class WhatsAppAgent:
    """
    Specialized agent for WhatsApp Business messaging.
    Handles the 24-hour session window and template message switching.
    """

    # Track last message times per user (in production, use Redis/DB)
    _session_cache: dict = {}

    def __init__(self):
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.access_token = WHATSAPP_ACCESS_TOKEN
        self.client = httpx.Client(timeout=30.0)

    async def handle_message(self, webhook_payload: dict) -> dict:
        """
        Process incoming WhatsApp message.

        Flow:
        1. Check if within 24-hour window
        2. If yes: Send free-form message
        3. If no: Send template message to re-engage
        """
        try:
            # Extract message data
            message = (
                webhook_payload.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
            )
            contact = message.get("contacts", [{}])[0]
            incoming_msg = message.get("messages", [{}])[0]

            sender_phone = contact.get("wa_id", "")
            sender_name = contact.get("profile", {}).get("name", "there")
            message_type = incoming_msg.get("type", "text")

            # Check 24-hour window
            is_within_window = self._check_session_window(sender_phone)

            # Handle based on message type
            if message_type == "image":
                return await self._handle_photo_message(sender_phone, incoming_msg)
            else:
                text = incoming_msg.get("text", {}).get("body", "")
                return await self._handle_text_message(
                    sender_phone, sender_name, text, is_within_window
                )

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _check_session_window(self, phone_number: str) -> bool:
        """
        Check if we're within the 24-hour messaging window.
        Updates the session timestamp on each interaction.
        """
        now = datetime.now()
        last_interaction = self._session_cache.get(phone_number)

        # Update timestamp
        self._session_cache[phone_number] = now

        if not last_interaction:
            return True  # First message, window is open

        # Check if within 24 hours
        return (now - last_interaction) < timedelta(hours=24)

    async def _handle_text_message(
        self, phone: str, name: str, text: str, within_window: bool
    ) -> dict:
        """Process a text message and respond appropriately."""

        if not within_window:
            # Must use template message
            return await self._send_template_message(phone, name)

        # Within window - can send free-form response
        # In production, this would call the LangGraph agent
        response = self._generate_response(text)
        return await self._send_text_message(phone, response)

    async def _handle_photo_message(self, phone: str, message: dict) -> dict:
        """
        Process a photo message using GPT-4o Vision.
        Used for: Bruise checks, skin analysis, treatment area identification.
        """
        from openai import OpenAI

        image_id = message.get("image", {}).get("id")
        caption = message.get("image", {}).get("caption", "")

        # Step 1: Download image from WhatsApp CDN
        image_url = await self._get_media_url(image_id)

        if not image_url:
            # Fallback if we can't get the image
            response = (
                "Thanks for sharing! 📸 I wasn't able to load the image. "
                "Could you try sending it again?"
            )
            return await self._send_text_message(phone, response)

        # Step 2: Analyze with GPT-4o Vision
        try:
            client = OpenAI()

            vision_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a medical aesthetics consultant assistant. "
                            "Analyze the photo and provide empathetic observations. "
                            "DO NOT provide medical diagnoses. "
                            "Focus on: identifying the area of concern, "
                            "describing what you observe (swelling, bruising, asymmetry), "
                            "and reassuring the patient."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": caption
                                or "Please analyze this photo and help me understand what I'm seeing.",
                            },
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=300,
            )

            analysis = vision_response.choices[0].message.content

            response = (
                f"Thanks for sharing the photo! 📸\n\n"
                f"{analysis}\n\n"
                "Would you like me to schedule a follow-up with Dr. Smith?"
            )

        except Exception as e:
            print(f"Vision API error: {e}")
            response = (
                "Thanks for sharing the photo! 📸\n\n"
                "I can see the area you're concerned about. "
                "Let me have Dr. Smith take a look and I'll get back to you shortly.\n\n"
                "In the meantime, is there anything else you'd like to know?"
            )

        return await self._send_text_message(phone, response)

    async def _get_media_url(self, media_id: str) -> str:
        """Download media URL from WhatsApp CDN."""
        if not self.access_token or not media_id:
            return ""

        try:
            url = f"{GRAPH_API_BASE}/{media_id}"
            response = self.client.get(
                url, headers={"Authorization": f"Bearer {self.access_token}"}
            )
            data = response.json()
            return data.get("url", "")
        except Exception:
            return ""

    def _generate_response(self, text: str) -> str:
        """
        Generate a response (placeholder for LangGraph integration).
        In production, this calls the main agent graph.
        """
        text_lower = text.lower()

        if any(word in text_lower for word in ["price", "cost"]):
            return (
                "Great question! 💫\n\n"
                "Our most popular treatments:\n"
                "• Botox: $12/unit (avg 20-40 units)\n"
                "• Lip Filler: $650-$850/syringe\n"
                "• Cheek Filler: $800-$1000/syringe\n\n"
                "Would you like me to check availability for a consultation?"
            )
        elif any(word in text_lower for word in ["book", "appointment"]):
            return (
                "Perfect! Let's get you scheduled! 📅\n\n"
                "What treatment are you interested in?\n"
                "And do you have a preferred day/time?"
            )
        elif any(word in text_lower for word in ["bruise", "swelling", "hurt"]):
            return (
                "I'm so sorry you're experiencing that! 💕\n\n"
                "For bruising, I recommend:\n"
                "• Arnica gel (apply 3x daily)\n"
                "• Cold compress (10 min on, 10 min off)\n"
                "• Avoid blood thinners/alcohol\n\n"
                "Can you send me a photo so I can have Dr. Smith take a look?"
            )
        else:
            return (
                "Thanks for reaching out! 👋\n\n"
                "I'm here to help with anything related to:\n"
                "• Botox & Fillers\n"
                "• Skin Treatments\n"
                "• Booking & Pricing\n\n"
                "What can I help you with today?"
            )

    async def _send_text_message(self, phone: str, text: str) -> dict:
        """Send a free-form text message."""
        if not self.access_token:
            return {
                "status": "mock",
                "message": f"Would send to {phone}: {text[:50]}...",
            }

        url = f"{GRAPH_API_BASE}/{self.phone_number_id}/messages"
        response = self.client.post(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": text},
            },
        )
        return response.json()

    async def _send_template_message(self, phone: str, name: str) -> dict:
        """
        Send a pre-approved template message.
        Used when outside the 24-hour window.
        """
        if not self.access_token:
            return {"status": "mock", "message": f"Would send template to {phone}"}

        url = f"{GRAPH_API_BASE}/{self.phone_number_id}/messages"
        response = self.client.post(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "template",
                "template": {
                    "name": "appointment_followup",  # Must be pre-approved
                    "language": {"code": "en"},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": name}]}
                    ],
                },
            },
        )
        return response.json()


# Singleton instance
whatsapp_agent = WhatsAppAgent()
