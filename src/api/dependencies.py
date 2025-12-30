from functools import lru_cache

from src.config import get_settings


@lru_cache
def get_cached_settings():
    return get_settings()
