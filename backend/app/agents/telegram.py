"""
Telegram Agent - Handles Telegram Bot API interactions
PRD Zone 1: Telegram Channel Adapter

Implements: Inline keyboards, Bot commands, Message handling
"""

import os
import httpx
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot API Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TelegramAgent:
    """
    Specialized agent for Telegram Bot messaging.
    PRD Zone 1: Telegram Channel Adapter
    Supports: Text, Quick Replies, Inline Keyboards, Links
    """

    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.client = httpx.AsyncClient(timeout=30.0)

    async def handle_message(self, webhook_payload: dict) -> dict:
        """
        Process incoming Telegram update.
        Handles text messages, commands, and callback queries.
        """
        try:
            # Extract message or callback query
            message = webhook_payload.get("message", {})
            callback_query = webhook_payload.get("callback_query", {})

            if callback_query:
                return await self._handle_callback_query(callback_query)

            if message:
                return await self._handle_text_message(message)

            return {"status": "skipped", "reason": "Unknown update type"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_text_message(self, message: dict) -> dict:
        """Process a text message and respond."""
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        user = message.get("from", {})
        first_name = user.get("first_name", "there")

        if not chat_id:
            return {"status": "error", "message": "No chat_id"}

        # Check if it's a command
        if text.startswith("/"):
            return await self._handle_command(chat_id, text, first_name)

        # Generate response (in production, routes through LangGraph)
        response = self._generate_response(text)
        return await self._send_message(chat_id, response)

    async def _handle_command(
        self, chat_id: int, command: str, first_name: str
    ) -> dict:
        """Handle bot commands like /start, /book, /help."""
        cmd = command.split()[0].lower()

        if cmd == "/start":
            response = (
                f"Welcome to Luxe MedSpa, {first_name}! ✨\n\n"
                "I'm your personal aesthetic concierge. I can help you with:\n"
                "• Treatment information & pricing\n"
                "• Booking consultations\n"
                "• Aftercare support\n\n"
                "What would you like to know about today?"
            )
            keyboard = self._build_inline_keyboard(
                [
                    [("💉 Botox & Fillers", "category_injectables")],
                    [("✨ Skin Treatments", "category_skin")],
                    [("📅 Book Consultation", "action_book")],
                ]
            )
            return await self._send_message(chat_id, response, keyboard)

        elif cmd == "/book":
            response = (
                "Let's get you scheduled! 📅\n\nWhich treatment are you interested in?"
            )
            keyboard = self._build_inline_keyboard(
                [
                    [("Botox Consultation", "book_botox")],
                    [("Filler Consultation", "book_filler")],
                    [("Skin Analysis", "book_skin")],
                    [("General Consultation", "book_general")],
                ]
            )
            return await self._send_message(chat_id, response, keyboard)

        elif cmd == "/help":
            response = (
                "Here's how I can help you:\n\n"
                "/start - Main menu\n"
                "/book - Schedule an appointment\n"
                "/prices - View treatment prices\n"
                "/help - Show this message\n\n"
                "Or just type your question and I'll assist you!"
            )
            return await self._send_message(chat_id, response)

        elif cmd == "/prices":
            response = (
                "💫 Our Popular Treatments:\n\n"
                "**Injectables:**\n"
                "• Botox: $12/unit (avg 20-40 units)\n"
                "• Lip Filler: $650-$850/syringe\n"
                "• Cheek Filler: $800-$1000/syringe\n\n"
                "**Skin Treatments:**\n"
                "• HydraFacial: $189\n"
                "• Chemical Peel: $150-$300\n"
                "• Microneedling: $299\n\n"
                "Would you like to book a consultation?"
            )
            keyboard = self._build_inline_keyboard(
                [[("📅 Book Now", "action_book"), ("💬 Ask Question", "action_chat")]]
            )
            return await self._send_message(chat_id, response, keyboard)

        else:
            return await self._send_message(
                chat_id, "I didn't recognize that command. Try /help for options!"
            )

    async def _handle_callback_query(self, callback_query: dict) -> dict:
        """Handle inline keyboard button presses."""
        query_id = callback_query.get("id")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        data = callback_query.get("data", "")

        # Answer the callback to remove loading state
        await self._answer_callback_query(query_id)

        if data.startswith("category_"):
            category = data.replace("category_", "")
            return await self._send_category_info(chat_id, category)

        elif data.startswith("book_"):
            treatment = data.replace("book_", "")
            return await self._send_booking_options(chat_id, treatment)

        elif data == "action_book":
            return await self._handle_command(chat_id, "/book", "")

        elif data == "action_chat":
            response = (
                "Of course! 💬\n\n"
                "What questions do you have? I'm here to help with:\n"
                "• Treatment details\n"
                "• Recovery expectations\n"
                "• Pre/post care instructions"
            )
            return await self._send_message(chat_id, response)

        return await self._send_message(chat_id, "I'll help you with that!")

    async def _send_category_info(self, chat_id: int, category: str) -> dict:
        """Send information about a treatment category."""
        if category == "injectables":
            response = (
                "💉 **Injectables at Luxe MedSpa**\n\n"
                "**Botox / Dysport**\n"
                "Smooth wrinkles & prevent new ones. Results in 3-5 days.\n\n"
                "**Dermal Fillers**\n"
                "Restore volume, enhance lips, sculpt cheekbones.\n\n"
                "All treatments performed by board-certified providers."
            )
            keyboard = self._build_inline_keyboard(
                [
                    [("Book Botox", "book_botox"), ("Book Filler", "book_filler")],
                    [("🔙 Main Menu", "action_start")],
                ]
            )
        elif category == "skin":
            response = (
                "✨ **Skin Treatments at Luxe MedSpa**\n\n"
                "**HydraFacial**\n"
                "Deep cleanse + hydration. No downtime!\n\n"
                "**Chemical Peels**\n"
                "Reveal fresh, glowing skin layers.\n\n"
                "**Microneedling**\n"
                "Boost collagen for smoother texture."
            )
            keyboard = self._build_inline_keyboard(
                [
                    [("Book Skin Treatment", "book_skin")],
                    [("🔙 Main Menu", "action_start")],
                ]
            )
        else:
            response = "What treatment are you interested in?"
            keyboard = None

        return await self._send_message(chat_id, response, keyboard)

    async def _send_booking_options(self, chat_id: int, treatment: str) -> dict:
        """Send booking confirmation and next steps."""
        treatment_names = {
            "botox": "Botox Consultation",
            "filler": "Filler Consultation",
            "skin": "Skin Analysis",
            "general": "General Consultation",
        }
        name = treatment_names.get(treatment, "Consultation")

        response = (
            f"Great choice! 🎉\n\n"
            f"You selected: **{name}**\n\n"
            "To complete your booking, click below to select a date & time:"
        )
        keyboard = self._build_inline_keyboard(
            [
                [
                    (
                        "📅 Select Date & Time",
                        f"https://luxemedspa.com/book?treatment={treatment}",
                    )
                ],
                [("💬 Talk to Someone", "action_chat")],
            ]
        )
        return await self._send_message(chat_id, response, keyboard)

    def _generate_response(self, text: str) -> str:
        """Generate a response for free-form text."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["price", "cost", "how much"]):
            return (
                "Great question! 💫\n\n"
                "Our most popular treatments:\n"
                "• Botox: $12/unit\n"
                "• Lip Filler: $650-$850\n\n"
                "Type /prices for the full list!"
            )
        elif any(word in text_lower for word in ["book", "appointment", "schedule"]):
            return "Wonderful! Type /book to see available options!"
        elif any(word in text_lower for word in ["pain", "hurt", "bruise"]):
            return (
                "I'm so sorry you're experiencing that! 💕\n\n"
                "For aftercare concerns, I recommend:\n"
                "• Arnica gel 3x daily\n"
                "• Cold compress 10 min on/off\n\n"
                "Would you like me to have someone from our team reach out?"
            )
        else:
            return (
                "Thanks for your message! 👋\n\n"
                "I'm here to help with treatments, booking, and pricing.\n"
                "Type /start to see all options!"
            )

    def _build_inline_keyboard(self, buttons: List[List[tuple]]) -> Dict[str, Any]:
        """Build Telegram inline keyboard markup."""
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for text, data in row:
                if data.startswith("http"):
                    keyboard_row.append({"text": text, "url": data})
                else:
                    keyboard_row.append({"text": text, "callback_data": data})
            keyboard.append(keyboard_row)

        return {"inline_keyboard": keyboard}

    async def _send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict] = None,
    ) -> dict:
        """Send a text message via Telegram API."""
        if not self.bot_token:
            return {
                "status": "mock",
                "message": f"Would send to {chat_id}: {text[:50]}...",
            }

        url = f"{TELEGRAM_API_BASE}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = await self.client.post(url, json=payload)
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _answer_callback_query(self, query_id: str) -> dict:
        """Answer callback query to remove loading indicator."""
        if not self.bot_token:
            return {"status": "mock"}

        url = f"{TELEGRAM_API_BASE}/answerCallbackQuery"
        try:
            response = await self.client.post(url, json={"callback_query_id": query_id})
            return response.json()
        except Exception:
            return {"status": "error"}


# Singleton instance
telegram_agent = TelegramAgent()
