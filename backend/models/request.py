"""
Request models for infinidom Framework
"""
from __future__ import annotations
from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field


class UserEvent(BaseModel):
    """Represents a user interaction event from the frontend."""
    
    event_type: str = Field(..., description="Type of event (click, input, submit, etc.)")
    target_selector: Optional[str] = Field(None, description="CSS selector of the target element")
    target_tag: Optional[str] = Field(None, description="Tag name of the target element")
    target_text: Optional[str] = Field(None, description="Text content of the target element")
    target_id: Optional[str] = Field(None, description="ID of the target element")
    target_classes: Optional[List[str]] = Field(None, description="Classes of the target element")
    input_value: Optional[str] = Field(None, description="Value for input events")
    href: Optional[str] = Field(None, description="href attribute for link clicks")
    data_attributes: Optional[Dict[str, str]] = Field(None, description="Data attributes on the element")
    extra: Optional[Dict[str, Any]] = Field(None, description="Any additional event data")


class InteractionRequest(BaseModel):
    """Request body for user interactions."""
    
    session_id: Optional[str] = Field(None, description="Session ID for context continuity")
    event: UserEvent = Field(..., description="The user event that triggered this interaction")
    current_url: Optional[str] = Field(None, description="Current page URL/path")
    viewport: Optional[Dict[str, int]] = Field(None, description="Viewport dimensions")
    current_dom: Optional[str] = Field(None, description="Current DOM content of the page body")


class InitialLoadRequest(BaseModel):
    """Request for initial page load."""
    
    session_id: Optional[str] = Field(None, description="Session ID if returning user")
    path: str = Field("/", description="Requested path")
    viewport: Optional[Dict[str, int]] = Field(None, description="Viewport dimensions")

