"""
Memory Manager - In-Memory Chat History
Manages session-based conversation history.
"""

from typing import List, Dict


class MemoryManager:
    """Manages chat history per session."""
    
    def __init__(self):
        self._storage: Dict[str, List[dict]] = {}
    
    def get_history(self, session_id: str) -> List[dict]:
        """Get chat history for a session."""
        return self._storage.get(session_id, [])
    
    def add_message(self, session_id: str, message: dict):
        """Add a message to session history."""
        if session_id not in self._storage:
            self._storage[session_id] = []
        self._storage[session_id].append(message)
    
    def clear(self, session_id: str):
        """Clear history for a session."""
        self._storage[session_id] = []


# Global singleton
memory = MemoryManager()
