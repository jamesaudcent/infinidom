#!/usr/bin/env python3
"""
infinidom Framework - Quick Start Script

Run this script to start the infinidom server.
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from backend.config import get_settings
    
    settings = get_settings()
    
    print("=" * 50)
    print("∞ infinidom")
    print("=" * 50)
    print(f"Server starting at http://{settings.host}:{settings.port}")
    print(f"AI: {settings.ai_provider} / {settings.ai_model}")
    print("=" * 50)
    
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
