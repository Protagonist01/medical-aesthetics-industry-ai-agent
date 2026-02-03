from typing import Dict, List


class MemoryManager:
    def __init__(self):
        # In-memory store: {session_id: [messages]}
        self._sessions: Dict[str, List[dict]] = {}

    def get_history(self, session_id: str) -> List[dict]:
        return self._sessions.get(session_id, [])

    def add_message(self, session_id: str, message: dict):
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def clear_history(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]


# Global instance
memory = MemoryManager()
