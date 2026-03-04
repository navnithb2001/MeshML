"""
Configuration management for API Gateway.
Loads settings from environment variables.
"""

import os
import secrets
from typing import List, Optional


class Settings:
    """Application settings loaded from environment variables."""
    
    # API Configuration
    PROJECT_NAME: str = "MeshML API Gateway"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://meshml:meshml@localhost:5432/meshml"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 minutes
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))  # 30 days
    
    # CORS
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000"
    ).split(",")
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_AUTHENTICATED: int = int(os.getenv("RATE_LIMIT_AUTHENTICATED", "1000"))  # per hour
    RATE_LIMIT_UNAUTHENTICATED: int = int(os.getenv("RATE_LIMIT_UNAUTHENTICATED", "100"))  # per hour
    
    # File Upload
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "104857600"))  # 100 MB in bytes
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/meshml/uploads")
    
    # Google Cloud Storage
    GCS_BUCKET_MODELS: str = os.getenv("GCS_BUCKET_MODELS", "meshml-models")
    GCS_BUCKET_DATASETS: str = os.getenv("GCS_BUCKET_DATASETS", "meshml-datasets")
    GCS_BUCKET_ARTIFACTS: str = os.getenv("GCS_BUCKET_ARTIFACTS", "meshml-artifacts")
    
    # Email (for invitations)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@meshml.dev")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "json"  # "json" or "text"
    
    # Workers
    WORKER_HEARTBEAT_TIMEOUT: int = int(os.getenv("WORKER_HEARTBEAT_TIMEOUT", "60"))  # seconds
    
    # Jobs
    MAX_CONCURRENT_JOBS_PER_GROUP: int = int(os.getenv("MAX_CONCURRENT_JOBS_PER_GROUP", "10"))
    JOB_TIMEOUT: int = int(os.getenv("JOB_TIMEOUT", "86400"))  # 24 hours in seconds


# Global settings instance
settings = Settings()
