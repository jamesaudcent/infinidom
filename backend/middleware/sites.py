"""
Site Routing Middleware for infinidom Framework

Routes requests to the appropriate site based on the Host header.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.services.site_loader import get_site_loader


class SiteMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches site context to each request."""
    
    async def dispatch(self, request: Request, call_next):
        # Get domain from Host header
        host = request.headers.get("host", "localhost")
        
        # Find matching site
        site_loader = get_site_loader()
        site = site_loader.get_site_by_domain(host)
        
        # Attach to request state
        request.state.site = site
        
        return await call_next(request)
