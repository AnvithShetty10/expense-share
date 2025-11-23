"""Generic Redis cache operations"""
from typing import Optional, List
import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()


class CacheService:
    """Generic service for Redis cache operations"""

    _redis_client: Optional[redis.Redis] = None

    @classmethod
    async def get_redis_client(cls) -> redis.Redis:
        """
        Get or create Redis client singleton.

        Returns:
            Redis client instance
        """
        if cls._redis_client is None:
            cls._redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return cls._redis_client

    @classmethod
    async def close_redis_client(cls):
        """Close Redis connection"""
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists, None otherwise
        """
        try:
            client = await cls.get_redis_client()
            return await client.get(key)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Cache get error for key '{key}': {e}")
            return None

    @classmethod
    async def set(cls, key: str, value: str, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 3600 = 1 hour)

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await cls.get_redis_client()
            await client.setex(key, ttl, value)
            return True
        except Exception as e:
            # Log error but don't fail the request
            print(f"Cache set error for key '{key}': {e}")
            return False

    @classmethod
    async def delete(cls, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await cls.get_redis_client()
            await client.delete(key)
            return True
        except Exception as e:
            # Log error but don't fail the request
            print(f"Cache delete error for key '{key}': {e}")
            return False

    @classmethod
    async def delete_multiple(cls, keys: List[str]) -> bool:
        """
        Delete multiple values from cache using pipeline.

        Args:
            keys: List of cache keys

        Returns:
            True if successful, False otherwise
        """
        if not keys:
            return True

        try:
            client = await cls.get_redis_client()
            pipeline = client.pipeline()

            for key in keys:
                pipeline.delete(key)

            await pipeline.execute()
            return True
        except Exception as e:
            # Log error but don't fail the request
            print(f"Cache delete multiple error: {e}")
            return False

    @classmethod
    async def exists(cls, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        try:
            client = await cls.get_redis_client()
            result = await client.exists(key)
            return bool(result)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Cache exists error for key '{key}': {e}")
            return False

    @classmethod
    async def health_check(cls) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            client = await cls.get_redis_client()
            await client.ping()
            return True
        except Exception:
            return False
