"""
infinidom Framework - Main Application

A paradigm-shifting web framework where AI dynamically determines DOM responses
to user interactions.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.config import get_settings
from backend.routes import router
from backend.middleware import SiteMiddleware
from backend.services.site_loader import get_site_loader

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="A framework where AI determines what DOM to return based on user interactions",
    version="0.1.0",
    debug=settings.debug
)

# Middleware stack (order matters - last added runs first)
app.add_middleware(SiteMiddleware)  # Routes requests to sites
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files before router
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# Include API routes
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    site_loader = get_site_loader()
    sites = site_loader.list_sites()
    
    print("∞ infinidom Framework starting...")
    print(f"🤖 AI: {settings.ai_provider} / {settings.ai_model}")
    print(f"📁 Sites configured: {len(sites)}")
    for site in sites:
        print(f"   • {site.name} ({', '.join(site.domains[:2])}{'...' if len(site.domains) > 2 else ''})")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("∞ infinidom Framework shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
