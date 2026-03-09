"""
Configuration for Dataset Sharder Service
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service info
    SERVICE_NAME: str = "dataset-sharder"
    SERVICE_PORT: int = 8001
    
    # Storage settings
    LOCAL_STORAGE_PATH: str = os.getenv("LOCAL_STORAGE_PATH", "/app/datasets")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "meshml-datasets")
    GCS_PROJECT_ID: str = os.getenv("GCS_PROJECT_ID", "")
    USE_GCS: bool = os.getenv("USE_GCS", "false").lower() == "true"
    
    # Sharding settings
    DEFAULT_BATCH_SIZE: int = 32
    MAX_SHARDS: int = 1000
    
    # Distribution settings
    CHUNK_SIZE: int = 8192  # 8KB chunks for streaming
    MAX_CONCURRENT_DOWNLOADS: int = 10
    
    # Database (for batch metadata)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://meshml:meshml_password@localhost:5432/meshml"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
