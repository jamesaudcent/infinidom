"""
AI Service for infinidom Framework

Handles AI API integration, prompt construction, and response parsing
for generating virtual DOM structures.

Uses atomic text streaming - each operation adds one element with an explicit
finish signal for reliable completion detection.
"""
from __future__ import annotations
import json
import time
from typing import Optional, AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI

try:
    from cerebras.cloud.sdk import AsyncCerebras
except ImportError:
    AsyncCerebras = None

from backend.config import get_settings
from backend.utils.session_manager import SessionContext
from backend.services.site_loader import Site
from backend.services.content_service import ContentService
from backend.services.system_prompt import STREAMING_SYSTEM_PROMPT


def get_content_mode_instructions() -> str:
    """Get content mode instruction based on config."""
    settings = get_settings()
    if settings.content_mode == "restrictive":
        return "\n\nOnly use information from the provided content. Do not invent content."
    return "\n\nUse the provided content as inspiration. Generate rich, explorable content with interactive elements."


# =============================================================================
# Context Builder
# =============================================================================

def build_context_message(
    session: SessionContext,
    event: dict,
    site: Site,
    site_content: Optional[str] = None,
    site_prompt: Optional[str] = None,
    is_initial: bool = False
) -> str:
    """Build the context message for the AI."""
    context_parts = []
    
    # Site information
    context_parts.append(f"""## Site
Name: {site.name}
Theme: {site.theme}""")
    
    # Include site-specific prompt if available
    if site_prompt:
        context_parts.append(f"""## Site Instructions
{site_prompt}""")
    
    # Session context (recent history)
    if session.interaction_history:
        recent = session.interaction_history[-3:]
        history_summary = []
        for item in recent:
            if item.get("type") == "interaction":
                history_summary.append(f"- User clicked: {item.get('target_text', 'unknown')}")
            elif item.get("type") == "page_load":
                history_summary.append(f"- User loaded: {item.get('path', '/')}")
        
        if history_summary:
            context_parts.append(f"""## Recent User Activity
{chr(10).join(history_summary)}""")
    
    # Current DOM content (what's currently rendered on the page)
    # NOTE: Disabled when using persistent conversations - AI tracks its own output
    # Uncomment if you need to provide DOM state checkpoints
    # current_dom = event.get("current_dom")
    # if current_dom:
    #     context_parts.append(f"""## Current Page Content
    # The following HTML is currently rendered on the page:
    # ```html
    # {current_dom}
    # ```""")
    
    # Current event
    event_type = event.get("event_type", "unknown")
    path = event.get("path", "/")
    context_parts.append(f"""## Current Event
Type: {event_type}
Path: {path}
Is Initial Load: {is_initial}""")
    
    if event_type == "click":
        context_parts.append(f"""Click Details:
- Target text: {event.get('target_text', 'N/A')}
- Target tag: {event.get('target_tag', 'N/A')}
- Href: {event.get('href', 'N/A')}
- Element Hierarchy: {json.dumps(event.get('element_hierarchy', []))}""")
    
    # Site content
    if site_content:
        context_parts.append(f"## Site Content\n{site_content}")
    
    return "\n\n".join(context_parts)


def build_event_message(event: dict) -> str:
    """Build a minimal event message for persistent conversations.
    
    Used for subsequent requests when the AI already has full context.
    """
    event_type = event.get("event_type", "unknown")
    path = event.get("path", "/")
    
    if event_type == "click":
        target_text = event.get('target_text', 'unknown')
        target_tag = event.get('target_tag', 'unknown')
        href = event.get('href', '')
        
        parts = [f"User clicked: \"{target_text}\" ({target_tag})"]
        if href:
            parts.append(f"Link href: {href}")
        parts.append(f"Current path: {path}")
        return "\n".join(parts)
    
    elif event_type == "page_load":
        return f"User navigated to: {path}"
    
    else:
        return f"Event: {event_type} at {path}"


# =============================================================================
# AI Service Class
# =============================================================================

class AIService:
    """Service for AI-powered DOM generation."""
    
    def __init__(self, site: Site):
        self.site = site
        self.settings = get_settings()
        self.content_service = ContentService(site)

        # Initialize AI client based on provider
        if not self.settings.ai_api_key:
            raise ValueError("AI_API_KEY is required")
        
        if self.settings.ai_provider == "cerebras":
            if AsyncCerebras is None:
                raise ImportError("cerebras-cloud-sdk is not installed. Run: pip install cerebras-cloud-sdk")
            self.client = AsyncCerebras(api_key=self.settings.ai_api_key)
        else:  # openai (default)
            self.client = AsyncOpenAI(api_key=self.settings.ai_api_key)
    
    async def stream_dom_operations(
        self,
        session: SessionContext,
        event: dict,
        is_initial: bool = False,
        cache_path: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream DOM operations for progressive page building.
        
        Always uses persistent conversation - the conversation thread is maintained
        across all interactions for context continuity.
        
        Args:
            session: The user's session context
            event: The event that triggered this request
            is_initial: Whether this is the first request in the session
            cache_path: If provided, cache the generated operations under this path
        """
        messages = await self._build_messages(session, event, is_initial)
        
        # Extract just role/content for API call (exclude timestamps)
        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        # Configure streaming request based on provider
        if self.settings.ai_provider == "cerebras":
            stream = await self.client.chat.completions.create(
                model=self.settings.ai_model,
                messages=api_messages,
                max_completion_tokens=self.settings.ai_max_tokens,
                temperature=1,
                stream=True
            )
        else:  # openai
            stream = await self.client.chat.completions.create(
                model=self.settings.ai_model,
                messages=api_messages,
                max_tokens=self.settings.ai_max_tokens,
                temperature=0.7,
                stream=True
            )
        
        buffer = ""
        full_response = ""  # Collect full response
        operations_list = []  # Collect operations for caching
        finished = False
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                buffer += content
                full_response += content
                
                while buffer and not finished:
                    json_obj, remaining = self._extract_json_object(buffer)
                    if json_obj is not None:
                        buffer = remaining
                        
                        # Check for finish signal
                        if json_obj.get("type") == "finish":
                            finished = True
                            # Store response and cache
                            self._store_response(session, messages, full_response)
                            if cache_path:
                                session.cache_page(cache_path, operations_list)
                            return  # Exit immediately on finish
                        
                        operations_list.append(json_obj)
                        yield json_obj
                    else:
                        break
            
            if finished:
                break
        
        # Try to parse any remaining buffer
        if buffer.strip() and not finished:
            try:
                operation = json.loads(buffer.strip())
                if operation.get("type") != "finish":
                    operations_list.append(operation)
                    yield operation
            except json.JSONDecodeError:
                print(f"Warning: Could not parse final buffer: {buffer[:200]}")
        
        # Store response and cache
        self._store_response(session, messages, full_response)
        if cache_path:
            session.cache_page(cache_path, operations_list)
    
    async def _build_messages(
        self,
        session: SessionContext,
        event: dict,
        is_initial: bool
    ) -> List[Dict[str, Any]]:
        """Build the messages list for the AI request.
        
        Always uses persistent conversation - reuses existing history if available,
        otherwise builds full context for first request.
        """
        current_time = time.time()
        
        # If we have existing conversation, just add the new event
        if session.ai_messages:
            event_content = build_event_message(event)
            new_message = {
                "role": "user",
                "content": event_content,
                "timestamp": current_time
            }
            # Return existing messages plus the new event
            return session.ai_messages + [new_message]
        
        # First request - build full context
        site_content = await self.content_service.get_relevant_content(event)
        site_prompt = await self.content_service.get_site_prompt()
        
        context_message = build_context_message(
            session=session,
            event=event,
            site=self.site,
            site_content=site_content,
            site_prompt=site_prompt,
            is_initial=is_initial
        )
        
        system_prompt = STREAMING_SYSTEM_PROMPT + get_content_mode_instructions()
        
        messages = [
            {"role": "system", "content": system_prompt, "timestamp": current_time},
            {"role": "user", "content": context_message, "timestamp": current_time}
        ]
        
        # Store initial messages
        session.ai_messages = messages.copy()
        
        return messages
    
    def _store_response(
        self,
        session: SessionContext,
        messages: List[Dict[str, Any]],
        response_content: str
    ):
        """Store the AI response in the session for conversation continuity."""
        current_time = time.time()
        
        # If we added a new user message, make sure it's in the session
        if len(messages) > len(session.ai_messages):
            # The last message is the new user event
            session.ai_messages.append(messages[-1])
        
        # Add the assistant response
        session.ai_messages.append({
            "role": "assistant",
            "content": response_content,
            "timestamp": current_time
        })
    
    def add_navigation_context(self, session: SessionContext, path: str, from_cache: bool = False):
        """Add a navigation context message without triggering AI response.
        
        Used when user navigates to a cached page - keeps AI aware of current state.
        """
        if from_cache:
            content = f"[System: User navigated back to {path} (served from cache)]"
        else:
            content = f"[System: User navigated to {path}]"
        
        session.add_context_message(content, role="user")
    
    def _extract_json_object(self, text: str) -> tuple:
        """Extract a complete JSON object from the beginning of text."""
        text = text.lstrip()
        if not text or text[0] != '{':
            idx = text.find('{')
            if idx == -1:
                return (None, text)
            text = text[idx:]
        
        depth = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
                
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    json_str = text[:i+1]
                    remaining = text[i+1:].lstrip()
                    try:
                        obj = json.loads(json_str)
                        return (obj, remaining)
                    except json.JSONDecodeError:
                        return (None, text)
        
        return (None, text)


# =============================================================================
# Module-level Functions
# =============================================================================

# Cache AI service instances per site
_ai_services: dict[str, AIService] = {}


def get_ai_service(site: Site) -> AIService:
    """Get or create an AI service instance for the given site."""
    if site.id not in _ai_services:
        _ai_services[site.id] = AIService(site)
    return _ai_services[site.id]
