"""
Instagram Agent - Handles Instagram Graph API interactions
Implements: Comment interception, Public replies, DM sliding
"""

import os
import httpx
#from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Instagram Graph API Config
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class InstagramAgent:
    """
    Specialized agent for Instagram engagement.
    Handles the "Comment -> Public Reply -> DM Slide" flow.
    """

    def __init__(self):
        self.access_token = INSTAGRAM_ACCESS_TOKEN
        self.account_id = INSTAGRAM_ACCOUNT_ID
        self.client = httpx.Client(timeout=30.0)

    async def handle_comment_webhook(self, webhook_payload: dict) -> dict:
        """
        Process incoming comment webhook from Instagram.

        Flow:
        1. Extract comment details
        2. Post public reply (boosts algorithm)
        3. Send DM with icebreaker
        """
        try:
            # Extract comment data
            comment_id = webhook_payload.get("id")
            comment_text = webhook_payload.get("text", "")
            commenter_id = webhook_payload.get("from", {}).get("id")
            #media_id = webhook_payload.get("media", {}).get("id")

            if not commenter_id:
                return {"status": "error", "message": "No commenter ID found"}

            # Step 1: Analyze intent from comment
            intent = self._analyze_comment_intent(comment_text)

            # Step 2: Post public reply
            public_reply = self._generate_public_reply(intent)
            await self._post_comment_reply(comment_id, public_reply)

            # Step 3: Send DM with personalized icebreaker
            dm_message = self._generate_dm_icebreaker(intent, comment_text)
            await self._send_dm(commenter_id, dm_message)

            return {
                "status": "success",
                "intent": intent,
                "actions": ["public_reply", "dm_sent"],
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _analyze_comment_intent(self, comment_text: str) -> str:
        """
        Quick intent detection from comment text.
        In production, this could use an LLM for more nuance.
        """
        text_lower = comment_text.lower()

        if any(word in text_lower for word in ["price", "cost", "how much", "$"]):
            return "pricing_inquiry"
        elif any(
            word in text_lower
            for word in ["book", "appointment", "schedule", "available"]
        ):
            return "booking_intent"
        elif any(word in text_lower for word in ["hurt", "pain", "scared", "nervous"]):
            return "concern_fear"
        elif any(word in text_lower for word in ["results", "before", "after", "work"]):
            return "results_inquiry"
        else:
            return "general_interest"

    def _generate_public_reply(self, intent: str) -> str:
        """Generate algorithm-friendly public reply."""
        replies = {
            "pricing_inquiry": "Great question! 💫 Sent you all the details in DM!",
            "booking_intent": "Let's get you scheduled! 📅 Check your DMs!",
            "concern_fear": "Totally understand! 💕 DM'd you about our comfort options!",
            "results_inquiry": "Love that you asked! ✨ Sending you some amazing befores/afters!",
            "general_interest": "So glad you're interested! 💌 Check your DMs!",
        }
        return replies.get(intent, "Thanks for reaching out! 💕 Check your DMs!")

    def _generate_dm_icebreaker(self, intent: str, original_comment: str) -> str:
        """Generate personalized DM icebreaker based on intent."""
        icebreakers = {
            "pricing_inquiry": (
                "Hey! 👋 Saw your question about pricing.\n\n"
                "Our lip fillers start at $650/syringe and Botox is $12/unit.\n\n"
                "Are you looking for a subtle enhancement or more dramatic results?"
            ),
            "booking_intent": (
                "Hi there! 💫 Ready to get you booked!\n\n"
                "What treatment are you interested in? I can check our next available slots!"
            ),
            "concern_fear": (
                "Hey! 💕 I totally get the nervousness - it's super common!\n\n"
                "We have a Comfort Protocol with numbing cream and Pro-Nox (laughing gas) "
                "that makes it basically pain-free.\n\n"
                "What treatment were you thinking about?"
            ),
            "results_inquiry": (
                "Hi! ✨ So excited you're interested in results!\n\n"
                "What area are you looking to enhance? I can share some of our best "
                "before/afters for that specific treatment!"
            ),
            "general_interest": (
                "Hey! 👋 Thanks for engaging with our content!\n\n"
                "What treatment caught your eye? I'd love to help answer any questions!"
            ),
        }
        return icebreakers.get(intent, icebreakers["general_interest"])

    async def _post_comment_reply(self, comment_id: str, message: str) -> dict:
        """Post a reply to a comment via Instagram Graph API."""
        if not self.access_token:
            return {
                "status": "mock",
                "message": "No access token - would reply: " + message,
            }

        url = f"{GRAPH_API_BASE}/{comment_id}/replies"
        response = self.client.post(
            url, params={"message": message, "access_token": self.access_token}
        )
        return response.json()

    async def _send_dm(self, recipient_id: str, message: str) -> dict:
        """Send a DM via Instagram Messaging API."""
        if not self.access_token:
            return {
                "status": "mock",
                "message": "No access token - would DM: " + message[:50] + "...",
            }

        url = f"{GRAPH_API_BASE}/{self.account_id}/messages"
        response = self.client.post(
            url,
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": message},
                "access_token": self.access_token,
            },
        )
        return response.json()


# Singleton instance
instagram_agent = InstagramAgent()
