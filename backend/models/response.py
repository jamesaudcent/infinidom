"""
Response models for infinidom Framework
"""
from __future__ import annotations
from typing import Optional, Any, Literal, Union, List, Dict
from pydantic import BaseModel, Field


class VirtualDOMNode(BaseModel):
    """
    Represents a virtual DOM node in Snabbdom-compatible format.
    """
    
    tag: str = Field(..., description="HTML tag name")
    props: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Element properties (attrs, class, style, on, etc.)"
    )
    children: Optional[List[Union[VirtualDOMNode, str]]] = Field(
        default_factory=list,
        description="Child nodes (can be VirtualDOMNode or text string)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tag": "div",
                "props": {
                    "attrs": {"id": "main"},
                    "class": {"container": True},
                    "style": {"backgroundColor": "#fff"}
                },
                "children": [
                    {"tag": "h1", "children": ["Hello World"]},
                    "Some text content"
                ]
            }
        }


# Allow recursive model
VirtualDOMNode.model_rebuild()


class DOMResponse(BaseModel):
    """
    Response containing virtual DOM update instructions.
    """
    
    dom: VirtualDOMNode = Field(..., description="The virtual DOM structure to apply")
    target: Optional[str] = Field(
        "body",
        description="CSS selector for where to apply the update (null = replace entire body)"
    )
    operation: Literal["replace", "append", "prepend", "update"] = Field(
        "replace",
        description="How to apply the DOM update"
    )
    session_id: str = Field(..., description="Session ID for the client to store")
    styles: Optional[str] = Field(None, description="Optional CSS styles to inject")
    scripts: Optional[str] = Field(None, description="Optional JavaScript to execute")
    meta: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata (page title, etc.)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "dom": {
                    "tag": "div",
                    "props": {"attrs": {"id": "app"}},
                    "children": [{"tag": "h1", "children": ["Welcome"]}]
                },
                "target": "body",
                "operation": "replace",
                "session_id": "abc-123",
                "meta": {"title": "Home Page"}
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    session_id: Optional[str] = Field(None, description="Session ID if available")

