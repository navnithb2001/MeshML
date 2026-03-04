"""
Redis cache configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    """Redis cache configuration settings."""
    
    # Connection settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str
    redis_db: int = 0
    redis_max_connections: int = 50
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5
    
    # TTL settings (in seconds)
    heartbeat_ttl: int = 30  # 30 seconds
    global_weights_ttl: int = 3600  # 1 hour
    version_map_ttl: int = 86400  # 24 hours
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


settings = CacheSettings()
