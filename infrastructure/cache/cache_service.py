"""
Redis Cache Service for AI Agent

Provides high-performance caching with Redis for API responses,
analysis results, and session data.
"""

import hashlib
import json
import pickle
from typing import Any

import redis

from shared.config.settings import get_settings


class RedisCache:
    """Redis-based cache for AI agent data"""

    def __init__(self):
        """Initialize Redis connection"""
        settings = get_settings()
        self.enabled = settings.REDIS_ENABLED
        self.ttl = settings.CACHE_TTL_SECONDS  # Always set TTL

        if self.enabled:
            try:
                self.client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                    decode_responses=False,  # We'll handle encoding
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                self.client.ping()
            except (redis.ConnectionError, redis.TimeoutError) as e:
                print(f"Redis connection failed: {e}. Falling back to memory cache.")
                self.enabled = False
                self._memory_cache = {}
        else:
            self._memory_cache = {}

    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced cache key"""
        return f"airquality:{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Any | None:
        """
        Get value from cache

        Args:
            namespace: Cache namespace (e.g., 'waqi', 'airqo', 'analysis')
            key: Cache key

        Returns:
            Cached value or None
        """
        cache_key = self._make_key(namespace, key)

        if self.enabled:
            try:
                value = self.client.get(cache_key)
                if value is not None:
                    # Redis returns bytes when decode_responses=False
                    if isinstance(value, bytes):
                        return pickle.loads(value)
                    else:
                        # Fallback for unexpected types
                        return None
            except Exception as e:
                print(f"Redis get error: {e}")
        else:
            return self._memory_cache.get(cache_key)

        return None

    def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Set value in cache

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: from config)

        Returns:
            True if successful
        """
        cache_key = self._make_key(namespace, key)
        ttl = ttl or self.ttl

        if self.enabled:
            try:
                serialized = pickle.dumps(value)
                self.client.setex(cache_key, ttl, serialized)
                return True
            except Exception as e:
                print(f"Redis set error: {e}")
                return False
        else:
            self._memory_cache[cache_key] = value
            return True

    def delete(self, namespace: str, key: str) -> bool:
        """Delete key from cache"""
        cache_key = self._make_key(namespace, key)

        if self.enabled:
            try:
                self.client.delete(cache_key)
                return True
            except Exception as e:
                print(f"Redis delete error: {e}")
                return False
        else:
            self._memory_cache.pop(cache_key, None)
            return True

    def clear_namespace(self, namespace: str) -> bool:
        """Clear all keys in a namespace"""
        if self.enabled:
            try:
                pattern = self._make_key(namespace, "*")
                keys = self.client.keys(pattern)
                if keys and isinstance(keys, list):
                    # Ensure all keys are bytes (as expected with decode_responses=False)
                    valid_keys = [k for k in keys if isinstance(k, (str, bytes))]
                    if valid_keys:
                        self.client.delete(*valid_keys)
                return True
            except Exception as e:
                print(f"Redis clear error: {e}")
                return False
        else:
            prefix = self._make_key(namespace, "")
            keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._memory_cache[key]
            return True

    def clear(self, namespace: str) -> bool:
        """Alias for clear_namespace for backward compatibility"""
        return self.clear_namespace(namespace)

    def hash_params(self, **kwargs: Any) -> str:
        """Create hash from parameters for cache key"""
        # Sort keys for consistent hashing
        sorted_items = sorted(kwargs.items())
        param_str = json.dumps(sorted_items, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()

    def get_api_response(self, service: str, endpoint: str, params: dict) -> Any | None:
        """Get cached API response"""
        key = self.hash_params(endpoint=endpoint, **params)
        return self.get(f"api:{service}", key)

    def set_api_response(
        self, service: str, endpoint: str, params: dict, response: Any, ttl: int | None = None
    ) -> bool:
        """Cache API response"""
        key = self.hash_params(endpoint=endpoint, **params)
        return self.set(f"api:{service}", key, response, ttl)

    def get_analysis(self, analysis_type: str, data_hash: str) -> Any | None:
        """Get cached analysis result"""
        return self.get("analysis", f"{analysis_type}:{data_hash}")

    def set_analysis(
        self, analysis_type: str, data_hash: str, result: Any, ttl: int | None = None
    ) -> bool:
        """Cache analysis result"""
        return self.set("analysis", f"{analysis_type}:{data_hash}", result, ttl)

    def close(self):
        """Close Redis connection"""
        if self.enabled:
            try:
                self.client.close()
            except Exception:
                pass


# Global cache instance
_cache_instance: RedisCache | None = None


def get_cache() -> RedisCache:
    """Get or create global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance
