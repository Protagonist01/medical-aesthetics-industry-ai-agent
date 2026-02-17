"""
Calendar Integration Service
Provides real scheduling via Cal.com API.

Cal.com is a free, open-source scheduling tool with a robust API.
https://cal.com/docs/enterprise-features/api
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class CalendarService:
    """
    Cal.com API integration for appointment scheduling.
    Handles availability checking and booking creation.
    """

    def __init__(self):
        self.api_key = os.getenv("CAL_API_KEY", "")
        self.event_type_id = os.getenv("CAL_EVENT_TYPE_ID", "")
        self.base_url = "https://api.cal.com/v1"

    @property
    def is_configured(self) -> bool:
        """Check if Cal.com is properly configured"""
        return bool(self.api_key and self.event_type_id)

    async def get_available_slots(
        self, date: str = None, days_ahead: int = 7
    ) -> Dict[str, Any]:
        """
        Get available appointment slots from Cal.com.

        Args:
            date: Specific date (YYYY-MM-DD) or None for next available
            days_ahead: Number of days to look ahead

        Returns:
            Dict with date, available_slots list, and timezone
        """
        if not self.is_configured:
            return self._get_mock_availability(date)

        # Calculate date range
        if date:
            try:
                start_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                start_date = datetime.now()
        else:
            start_date = datetime.now()

        end_date = start_date + timedelta(days=days_ahead)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/availability",
                    params={
                        "apiKey": self.api_key,
                        "eventTypeId": self.event_type_id,
                        "dateFrom": start_date.strftime("%Y-%m-%d"),
                        "dateTo": end_date.strftime("%Y-%m-%d"),
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._format_cal_response(data)
                else:
                    # Fallback to mock on API error
                    return self._get_mock_availability(date)

        except Exception as e:
            print(f"Cal.com API error: {e}")
            return self._get_mock_availability(date)

    async def create_booking(
        self,
        slot_time: str,
        name: str,
        email: str,
        phone: str = "",
        notes: str = "",
        service: str = "Consultation",
        conversation_summary: str = "",
        treatment_area: str = "",
        client_concerns: str = "",
    ) -> Dict[str, Any]:
        """
        Create a booking in Cal.com with full treatment context for the doctor.

        Args:
            slot_time: ISO datetime string for the slot
            name: Client's full name
            email: Client's email
            phone: Client's phone number
            notes: Additional notes
            service: Service being booked (e.g., "Botox", "Lip Filler")
            conversation_summary: AI-generated summary of the chat
            treatment_area: Specific area (e.g., "Forehead", "Lips", "Jawline")
            client_concerns: What the client mentioned they want to address

        Returns:
            Dict with booking confirmation details
        """
        if not self.is_configured:
            return self._create_mock_booking(
                slot_time, name, email, service, conversation_summary
            )

        # Build detailed notes for the doctor
        doctor_notes = self._build_doctor_notes(
            service=service,
            treatment_area=treatment_area,
            client_concerns=client_concerns,
            conversation_summary=conversation_summary,
            additional_notes=notes,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/bookings",
                    params={"apiKey": self.api_key},
                    json={
                        "eventTypeId": int(self.event_type_id),
                        "start": slot_time,
                        "responses": {
                            "name": name,
                            "email": email,
                            "phone": phone,
                            "notes": doctor_notes,
                        },
                        "metadata": {
                            "source": "ai_agent",
                            "service": service,
                            "treatment_area": treatment_area,
                            "has_summary": bool(conversation_summary),
                        },
                        "timeZone": "America/New_York",
                    },
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    return {
                        "success": True,
                        "booking_id": data.get("id"),
                        "uid": data.get("uid"),
                        "start_time": data.get("startTime"),
                        "end_time": data.get("endTime"),
                        "attendee": name,
                        "email": email,
                        "status": "confirmed",
                        "calendar_link": data.get("eventLinks", {}).get("calendar"),
                        "service": service,
                        "doctor_notes": doctor_notes,
                    }
                else:
                    error_msg = response.json().get("message", "Unknown error")
                    return {
                        "success": False,
                        "error": error_msg,
                        "status": "failed",
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status": "failed",
            }

    def _build_doctor_notes(
        self,
        service: str,
        treatment_area: str,
        client_concerns: str,
        conversation_summary: str,
        additional_notes: str,
    ) -> str:
        """Build structured notes that the doctor will see in their calendar."""
        sections = []

        # Treatment header
        sections.append(f"📋 TREATMENT: {service}")

        if treatment_area:
            sections.append(f"📍 AREA: {treatment_area}")

        if client_concerns:
            sections.append(f"💬 CLIENT CONCERNS: {client_concerns}")

        if conversation_summary:
            sections.append(f"\n📝 CONVERSATION SUMMARY:\n{conversation_summary}")

        if additional_notes:
            sections.append(f"\n📌 NOTES: {additional_notes}")

        sections.append("\n🤖 Booked via AI Assistant")

        return "\n".join(sections)

    def _format_cal_response(self, data: Dict) -> Dict[str, Any]:
        """Format Cal.com API response into our standard format"""
        slots = []
        # Cal.com returns busy times and working hours - dateRanges are the available slots
        date_ranges = data.get("dateRanges", [])

        for slot in date_ranges[:6]:  # Limit to 6 slots
            start = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            slots.append(
                {
                    "time": start.strftime("%I:%M %p"),
                    "datetime": slot["start"],
                    "provider": "Available",
                }
            )

        return {
            "date": datetime.now().strftime("%A, %B %d"),
            "available_slots": slots if slots else self._get_default_slots(),
            "timezone": data.get("timeZone", "America/New_York"),
            "source": "cal.com",
        }

    def _get_mock_availability(self, date: str = None) -> Dict[str, Any]:
        """Return mock availability when Cal.com is not configured"""
        if date and date.lower() == "tomorrow":
            target_date = datetime.now() + timedelta(days=1)
        elif date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                target_date = datetime.now() + timedelta(days=1)
        else:
            target_date = datetime.now() + timedelta(days=1)

        return {
            "date": target_date.strftime("%A, %B %d"),
            "available_slots": self._get_default_slots(),
            "timezone": "America/New_York",
            "source": "mock",
            "note": "Configure CAL_API_KEY for real availability",
        }

    def _get_default_slots(self) -> List[Dict]:
        """Default mock slots"""
        return [
            {"time": "10:00 AM", "datetime": None, "provider": "Dr. Smith"},
            {"time": "2:00 PM", "datetime": None, "provider": "Dr. Johnson"},
            {"time": "4:30 PM", "datetime": None, "provider": "Nurse Lee"},
        ]

    def _create_mock_booking(
        self,
        slot_time: str,
        name: str,
        email: str,
        service: str,
        conversation_summary: str = "",
    ) -> Dict[str, Any]:
        """Create mock booking when Cal.com is not configured"""
        import uuid

        booking_id = str(uuid.uuid4())[:8]

        # Build notes even for mock
        doctor_notes = self._build_doctor_notes(
            service=service,
            treatment_area="",
            client_concerns="",
            conversation_summary=conversation_summary,
            additional_notes="",
        )

        return {
            "success": True,
            "booking_id": f"mock_{booking_id}",
            "uid": booking_id,
            "start_time": slot_time,
            "attendee": name,
            "email": email,
            "service": service,
            "status": "confirmed",
            "source": "mock",
            "doctor_notes": doctor_notes,
            "note": "Configure CAL_API_KEY for real bookings",
        }


# Singleton instance
calendar_service = CalendarService()
