"""
CRM Integration Service
PRD v1.2: Zone 6 CRM Sync

Provides abstract CRM interface with HubSpot and GoHighLevel adapters.
Auto-syncs lead status changes to external CRM systems.
"""

import os
import httpx
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from dotenv import load_dotenv

load_dotenv()


class CRMAdapter(ABC):
    """Abstract base class for CRM integrations"""

    @abstractmethod
    async def upsert_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a lead/contact in the CRM"""
        pass

    @abstractmethod
    async def update_deal_stage(
        self, contact_id: str, stage: str, value: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update deal stage for a contact"""
        pass

    @abstractmethod
    async def log_activity(
        self, contact_id: str, activity_type: str, notes: str
    ) -> Dict[str, Any]:
        """Log an activity/note against a contact"""
        pass


class HubSpotAdapter(CRMAdapter):
    """
    HubSpot CRM Adapter
    Uses HubSpot API v3 for contacts, deals, and notes
    """

    def __init__(self):
        self.api_key = os.getenv("HUBSPOT_API_KEY", "")
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def upsert_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update a HubSpot contact.
        Maps lead qualification fields to HubSpot properties.
        """
        if not self.api_key:
            return {"status": "skipped", "reason": "No HubSpot API key configured"}

        # Map internal fields to HubSpot properties
        properties = {
            "email": lead_data.get("email", ""),
            "firstname": lead_data.get("name", "").split()[0]
            if lead_data.get("name")
            else "",
            "lastname": " ".join(lead_data.get("name", "").split()[1:])
            if lead_data.get("name")
            else "",
            "phone": lead_data.get("phone", ""),
            "medspa_interest": lead_data.get("interests", ""),
            "lead_source": lead_data.get("channel", "web"),
            "qualification_status": lead_data.get("status", "new"),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Search for existing contact by email
                search_response = await client.post(
                    f"{self.base_url}/crm/v3/objects/contacts/search",
                    headers=self.headers,
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "EQ",
                                        "value": properties["email"],
                                    }
                                ]
                            }
                        ]
                    },
                )

                if (
                    search_response.status_code == 200
                    and search_response.json().get("total", 0) > 0
                ):
                    # Update existing contact
                    contact_id = search_response.json()["results"][0]["id"]
                    update_response = await client.patch(
                        f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                        headers=self.headers,
                        json={"properties": properties},
                    )
                    return {
                        "status": "updated",
                        "contact_id": contact_id,
                        "hubspot_response": update_response.json(),
                    }
                else:
                    # Create new contact
                    create_response = await client.post(
                        f"{self.base_url}/crm/v3/objects/contacts",
                        headers=self.headers,
                        json={"properties": properties},
                    )
                    return {
                        "status": "created",
                        "contact_id": create_response.json().get("id"),
                        "hubspot_response": create_response.json(),
                    }

            except Exception as e:
                return {"status": "error", "error": str(e)}

    async def update_deal_stage(
        self, contact_id: str, stage: str, value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create or update deal stage for a contact.
        Stages: appointmentscheduled, qualifiedtobuy, presentationscheduled, decisionmakerboughtin, closedwon, closedlost
        """
        if not self.api_key:
            return {"status": "skipped", "reason": "No HubSpot API key configured"}

        # Map internal stages to HubSpot deal stages
        stage_mapping = {
            "new": "appointmentscheduled",
            "qualified": "qualifiedtobuy",
            "booked": "presentationscheduled",
            "completed": "closedwon",
            "cancelled": "closedlost",
        }

        hubspot_stage = stage_mapping.get(stage.lower(), "appointmentscheduled")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create deal associated with contact
                deal_properties = {
                    "dealname": f"MedSpa Treatment - {contact_id}",
                    "dealstage": hubspot_stage,
                    "pipeline": "default",
                }
                if value:
                    deal_properties["amount"] = str(value)

                deal_response = await client.post(
                    f"{self.base_url}/crm/v3/objects/deals",
                    headers=self.headers,
                    json={"properties": deal_properties},
                )

                deal_id = deal_response.json().get("id")

                # Associate deal with contact
                if deal_id:
                    await client.put(
                        f"{self.base_url}/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/deal_to_contact",
                        headers=self.headers,
                    )

                return {
                    "status": "success",
                    "deal_id": deal_id,
                    "stage": hubspot_stage,
                }

            except Exception as e:
                return {"status": "error", "error": str(e)}

    async def log_activity(
        self, contact_id: str, activity_type: str, notes: str
    ) -> Dict[str, Any]:
        """Log a note against a HubSpot contact"""
        if not self.api_key:
            return {"status": "skipped", "reason": "No HubSpot API key configured"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                note_response = await client.post(
                    f"{self.base_url}/crm/v3/objects/notes",
                    headers=self.headers,
                    json={
                        "properties": {
                            "hs_note_body": f"[{activity_type}] {notes}",
                            "hs_timestamp": str(int(__import__("time").time() * 1000)),
                        }
                    },
                )

                note_id = note_response.json().get("id")

                # Associate note with contact
                if note_id:
                    await client.put(
                        f"{self.base_url}/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact",
                        headers=self.headers,
                    )

                return {"status": "success", "note_id": note_id}

            except Exception as e:
                return {"status": "error", "error": str(e)}


class GoHighLevelAdapter(CRMAdapter):
    """
    GoHighLevel (GHL) CRM Adapter
    Placeholder for future implementation
    """

    def __init__(self):
        self.api_key = os.getenv("GHL_API_KEY", "")
        self.location_id = os.getenv("GHL_LOCATION_ID", "")

    async def upsert_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Implement GHL contact creation
        return {"status": "not_implemented", "platform": "gohighlevel"}

    async def update_deal_stage(
        self, contact_id: str, stage: str, value: Optional[float] = None
    ) -> Dict[str, Any]:
        # TODO: Implement GHL opportunity stage update
        return {"status": "not_implemented", "platform": "gohighlevel"}

    async def log_activity(
        self, contact_id: str, activity_type: str, notes: str
    ) -> Dict[str, Any]:
        # TODO: Implement GHL activity logging
        return {"status": "not_implemented", "platform": "gohighlevel"}


class CRMService:
    """
    CRM Service - Factory pattern for CRM adapters.
    Automatically selects adapter based on env configuration.
    """

    def __init__(self):
        self.adapter = self._get_adapter()

    def _get_adapter(self) -> CRMAdapter:
        """Select CRM adapter based on configuration"""
        if os.getenv("HUBSPOT_API_KEY"):
            return HubSpotAdapter()
        elif os.getenv("GHL_API_KEY"):
            return GoHighLevelAdapter()
        else:
            # Return HubSpot as default (will skip operations if no key)
            return HubSpotAdapter()

    async def sync_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync lead data to configured CRM"""
        return await self.adapter.upsert_lead(lead_data)

    async def update_stage(
        self, contact_id: str, stage: str, value: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update deal stage in CRM"""
        return await self.adapter.update_deal_stage(contact_id, stage, value)

    async def log_interaction(
        self, contact_id: str, interaction_type: str, notes: str
    ) -> Dict[str, Any]:
        """Log interaction to CRM"""
        return await self.adapter.log_activity(contact_id, interaction_type, notes)


# Singleton instance
crm_service = CRMService()
