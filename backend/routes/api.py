"""
API Routes for infinidom Framework

Handles initial page load and user interactions via streaming.
"""
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from typing import Optional, AsyncGenerator
from pathlib import Path
import json
import mimetypes

from backend.models.request import InteractionRequest
from backend.utils.session_manager import get_session_manager
from backend.services.ai_service import get_ai_service
from backend.config import get_settings

router = APIRouter()

# Image file extensions we support
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico'}


def get_site_or_404(request: Request):
    """Get site from request state or raise 404."""
    site = getattr(request.state, 'site', None)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found for this domain")
    return site


def get_frontend_html() -> str:
    """Get the frontend HTML content."""
    frontend_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    
    if frontend_path.exists():
        return frontend_path.read_text()
    
    return """
<!DOCTYPE html>
<html>
<head>
    <title>infinidom</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div id="app">Site not configured</div>
</body>
</html>
    """


@router.get("/", response_class=HTMLResponse)
async def serve_frontend_root(request: Request):
    """Serve the frontend HTML shell for the root path."""
    get_site_or_404(request)  # Ensure site exists
    return HTMLResponse(content=get_frontend_html())


@router.get("/api/stream/init")
async def stream_initial_load(
    request: Request,
    session_id: Optional[str] = Query(None),
    path: str = Query("/")
):
    """Handle initial page load with streaming DOM operations."""
    site = get_site_or_404(request)
    session_manager = get_session_manager()
    ai_service = get_ai_service(site)
    
    session = session_manager.get_or_create_session(session_id)
    
    init_event = {
        "event_type": "page_load",
        "path": path,
        "is_initial": True
    }
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"
            
            async for operation in ai_service.stream_dom_operations(
                session=session,
                event=init_event,
                is_initial=True
            ):
                yield f"data: {json.dumps(operation)}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/api/stream/interact")
async def stream_interaction(request: Request, interaction: InteractionRequest):
    """Handle user interaction with streaming DOM operations."""
    site = get_site_or_404(request)
    session_manager = get_session_manager()
    ai_service = get_ai_service(site)
    
    session = session_manager.get_or_create_session(interaction.session_id)
    
    event_data = interaction.event.model_dump()
    event_data["current_url"] = interaction.current_url
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            async for operation in ai_service.stream_dom_operations(
                session=session,
                event=event_data,
                is_initial=False
            ):
                yield f"data: {json.dumps(operation)}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/api/config")
async def get_config(request: Request):
    """Get client-side configuration."""
    site = get_site_or_404(request)
    settings = get_settings()
    return {
        "content_mode": settings.content_mode,
        "site_name": site.name,
        "site_theme": site.theme,
        "framework": "infinidom"
    }


@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    session_manager = get_session_manager()
    return {
        "status": "healthy",
        "framework": "infinidom",
        "active_sessions": session_manager.get_session_count()
    }


@router.get("/site-styles.css")
async def serve_site_styles(request: Request):
    """Serve site-specific CSS file."""
    site = get_site_or_404(request)
    
    # Serve site's custom styles.css if it exists
    if site.styles_path.exists():
        return FileResponse(
            path=site.styles_path,
            media_type="text/css"
        )
    
    # Fallback to default framework styles
    default_styles = Path(__file__).parent.parent.parent / "frontend" / "css" / "styles.css"
    if default_styles.exists():
        return FileResponse(
            path=default_styles,
            media_type="text/css"
        )
    
    # Return empty CSS if nothing exists
    from fastapi.responses import Response
    return Response(content="/* No styles */", media_type="text/css")


@router.get("/{path:path}")
async def serve_frontend_catchall(request: Request, path: str):
    """Serve the frontend HTML shell for any path, or images from site folder."""
    if path.startswith("static/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    
    site = get_site_or_404(request)
    
    # Check if this is an image request
    path_obj = Path(path)
    if path_obj.suffix.lower() in IMAGE_EXTENSIONS:
        # Try to serve from site's content folder (supports subfolders)
        # First try exact path, then try just the filename
        image_path = site.content_path / path
        if not (image_path.exists() and image_path.is_file()):
            # Fallback: search for file by name anywhere in content folder
            for candidate in site.content_path.rglob(path_obj.name):
                if candidate.is_file():
                    image_path = candidate
                    break
        
        if image_path.exists() and image_path.is_file():
            media_type, _ = mimetypes.guess_type(str(image_path))
            return FileResponse(
                path=image_path,
                media_type=media_type or "application/octet-stream"
            )
        # Image not found - return 404
        raise HTTPException(status_code=404, detail=f"Image not found: {path}")
    
    return HTMLResponse(content=get_frontend_html())
