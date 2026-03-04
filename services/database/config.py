"""
Database configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    database_url: str
    database_echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


settings = DatabaseSettings()
