"""Redis client for caching and real-time data"""

import os
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Global Redis client
redis_client: redis.Redis = None


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    
    try:
        redis_client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection established")
        
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


def get_redis() -> redis.Redis:
    """
    Dependency for getting Redis client
    
    Usage:
        @app.get("/cache")
        async def get_cache(redis: Redis = Depends(get_redis)):
            ...
    """
    return redis_client
