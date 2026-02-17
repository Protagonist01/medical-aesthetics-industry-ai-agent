from pydantic import BaseModel
from typing import List, Optional, Literal


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    source: Optional[Literal["web", "instagram", "whatsapp"]] = "web"
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    source: str = "web"  # web, instagram, whatsapp
    session_id: Optional[str] = None
    language: Optional[str] = "English"
    user_id: Optional[str] = None
