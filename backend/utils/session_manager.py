"""
Session Manager for infinidom Framework

Handles session storage, retrieval, and context management per session.
"""
from __future__ import annotations
import uuid
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class SessionContext:
    """Represents a user session with its context."""
    session_id: str
    created_at: float
    last_accessed: float
    current_dom: Optional[dict] = None
    interaction_history: list = field(default_factory=list)
    ai_messages: list = field(default_factory=list)  # Conversation thread
    page_cache: Dict[str, List[dict]] = field(default_factory=dict)  # Cached pages by path
    
    def add_interaction(self, event: dict, response: dict, max_history: int = 20):
        """Add an interaction to the session history."""
        self.interaction_history.append({
            "timestamp": time.time(),
            "event": event,
            "response_summary": self._summarize_response(response)
        })
        # Keep only the last N interactions
        if len(self.interaction_history) > max_history:
            self.interaction_history = self.interaction_history[-max_history:]
    
    def _summarize_response(self, response: dict) -> dict:
        """Create a summary of the response for history."""
        return {
            "operation": response.get("operation"),
            "target": response.get("target"),
            "has_dom": "dom" in response
        }
    
    def update_dom(self, dom: dict):
        """Update the current DOM state."""
        self.current_dom = dom
        self.last_accessed = time.time()
    
    def touch(self):
        """Update last accessed time."""
        self.last_accessed = time.time()
    
    def cache_page(self, path: str, operations: List[dict]):
        """Cache the generated operations for a page."""
        self.page_cache[path] = operations
        self.last_accessed = time.time()
    
    def get_cached_page(self, path: str) -> Optional[List[dict]]:
        """Get cached operations for a page, or None if not cached."""
        return self.page_cache.get(path)
    
    def has_visited_path(self, path: str) -> bool:
        """Check if user has visited this path before."""
        return path in self.page_cache
    
    def add_context_message(self, content: str, role: str = "user"):
        """Add a context message to the conversation without triggering AI response.
        
        Used for navigation events when returning to cached pages.
        """
        self.ai_messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })


class SessionManager:
    """
    In-memory session manager for storing user session contexts.
    For production, this should be replaced with Redis or similar.
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_history: int = 20):
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._max_history = max_history
    
    def create_session(self) -> SessionContext:
        """Create a new session and return it."""
        session_id = str(uuid.uuid4())
        now = time.time()
        
        session = SessionContext(
            session_id=session_id,
            created_at=now,
            last_accessed=now
        )
        
        with self._lock:
            self._sessions[session_id] = session
            self._cleanup_expired()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get a session by ID, returning None if not found or expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            
            if session is None:
                return None
            
            # Check if expired
            if time.time() - session.last_accessed > self._ttl_seconds:
                del self._sessions[session_id]
                return None
            
            session.touch()
            return session
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionContext:
        """Get existing session or create a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        return self.create_session()
    
    def add_interaction(self, session_id: str, event: dict, response: dict):
        """Add an interaction to a session's history."""
        session = self.get_session(session_id)
        if session:
            session.add_interaction(event, response, self._max_history)
    
    def update_session_dom(self, session_id: str, dom: dict):
        """Update the DOM state for a session."""
        session = self.get_session(session_id)
        if session:
            session.update_dom(dom)
    
    def _cleanup_expired(self):
        """Remove expired sessions. Called within lock."""
        now = time.time()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_accessed > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
    
    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            self._cleanup_expired()
            return len(self._sessions)


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        from backend.config import get_settings
        settings = get_settings()
        _session_manager = SessionManager(
            ttl_seconds=settings.session_ttl_seconds,
            max_history=settings.max_session_history
        )
    return _session_manager

