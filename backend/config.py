"""
infinidom Framework Configuration
"""
from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AI Configuration
    ai_provider: str = "openai"  # "openai" or "cerebras"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 16384
    
    # Content Generation Mode: "restrictive" or "expansive"
    # - "restrictive": AI strictly adheres to provided content only
    # - "expansive": AI uses content as foundation, generates rich explorable content
    content_mode: str = "expansive"
    
    # Session Persistence
    # If True, session survives browser refresh and returns (via localStorage session_id)
    # Pages are cached and conversation thread is maintained across visits
    persist_session: bool = True
    
    # Application Configuration
    app_name: str = "infinidom Framework"
    debug: bool = True

    # Session Configuration
    session_ttl_seconds: int = 3600  # 1 hour
    max_session_history: int = 20  # Max interactions to keep in history
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Configuration
    cors_origins: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
