"""Configuration management for the enterprise search application."""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google OAuth2
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    
    # Gemini API (optional - local embeddings are used by default)
    GEMINI_API_KEY: Optional[str] = None
    
    # Application
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Vector Store
    EMBEDDING_MODEL: str = "models/embedding-001"  # Free tier model
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K: int = 5
    
    # LLM Model (Free tier: gemini-2.5-flash, gemini-pro, Paid: gemini-1.5-pro)
    LLM_MODEL: str = "gemini-2.5-flash"  # Latest free tier model
    
    # Token limits for text generation (to avoid rate limits)
    MAX_CONTEXT_TOKENS: int = 2000  # Maximum tokens to send as context (reduced to avoid rate limits)
    MAX_CHUNK_LENGTH: int = 500  # Maximum characters per chunk in context
    
    # MVP Limits (to keep token usage low)
    MAX_FILES_TO_INDEX: int = 5  # Limit to 5 PDFs for MVP
    FILE_TYPES: str = "application/pdf"  # Comma-separated MIME types, default: PDFs only
    
    @field_validator('FILE_TYPES')
    @classmethod
    def parse_file_types(cls, v: str) -> List[str]:
        """Parse comma-separated file types into a list."""
        if isinstance(v, list):
            return v
        return [ft.strip() for ft in v.split(',') if ft.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

