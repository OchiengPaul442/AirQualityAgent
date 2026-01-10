"""
Base Service Class for API Services

Centralizes common initialization and utility methods to reduce code duplication.
All API-based services should inherit from this class.
"""

import logging
from typing import Any

import requests

from ..config import get_settings
from .cache import get_cache

logger = logging.getLogger(__name__)


class BaseAPIService:
    """
    Base class for all API-based services.
    
    Provides:
    - Standardized initialization
    - Session management
    - Cache integration
    - Token sanitization utilities
    - Common HTTP patterns
    
    Example:
        class MyAPIService(BaseAPIService):
            def __init__(self):
                super().__init__(
                    api_key_setting='MY_API_KEY',
                    base_url='https://api.example.com'
                )
    """

    def __init__(self, api_key_setting: str | None = None, base_url: str | None = None):
        """
        Initialize base API service.
        
        Args:
            api_key_setting: Name of the settings attribute for API key (e.g., 'AIRQO_API_TOKEN')
            base_url: Base URL for the API
        """
        settings = get_settings()

        # API configuration
        self.api_key = getattr(settings, api_key_setting, None) if api_key_setting else None
        self.base_url = base_url

        # HTTP session for connection pooling
        self.session = requests.Session()

        # Cache configuration
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

        # Logger for this service
        self.logger = logger

    def _get_headers(self) -> dict[str, str]:
        """
        Get default request headers.
        Override in subclass for custom headers.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _sanitize_data(self, data: Any, tokens_to_redact: list[str] | None = None) -> Any:
        """
        Remove sensitive information from data structures.
        
        Args:
            data: Data to sanitize (dict, list, or primitive)
            tokens_to_redact: Additional token strings to redact
            
        Returns:
            Sanitized copy of data
        """
        # Build list of tokens to redact
        tokens = tokens_to_redact or []
        if self.api_key:
            tokens.append(self.api_key)

        def sanitize_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                sanitized = {}
                for key, value in obj.items():
                    # Redact known sensitive keys
                    if key.lower() in ('token', 'api_key', 'apikey', 'password', 'secret'):
                        sanitized[key] = "[REDACTED]"
                    # Redact values containing tokens
                    elif isinstance(value, str) and any(token in value for token in tokens if token):
                        sanitized[key] = value
                        for token in tokens:
                            if token:
                                sanitized[key] = sanitized[key].replace(token, "[REDACTED]")
                    # Recursively sanitize nested structures
                    elif isinstance(value, (dict, list)):
                        sanitized[key] = sanitize_recursive(value)
                    else:
                        sanitized[key] = value
                return sanitized
            elif isinstance(obj, list):
                return [sanitize_recursive(item) for item in obj]
            else:
                return obj

        return sanitize_recursive(data)

    def _make_cached_request(
        self,
        namespace: str,
        cache_key: str,
        request_func,
        cache_ttl: int | None = None,
    ) -> Any:
        """
        Make a request with caching support.
        
        Args:
            namespace: Cache namespace (e.g., 'waqi', 'airqo')
            cache_key: Unique key for caching this request
            request_func: Function that performs the actual request
            cache_ttl: Cache TTL in seconds (uses default if None)
            
        Returns:
            Response data (from cache or fresh request)
        """
        # Try cache first
        cached = self.cache_service.get(namespace, cache_key)
        if cached is not None:
            self.logger.debug(f"Cache hit for {namespace}:{cache_key}")
            return cached

        # Make fresh request
        self.logger.debug(f"Cache miss for {namespace}:{cache_key}")
        result = request_func()

        # Cache the result
        ttl = cache_ttl or self.cache_ttl
        self.cache_service.set(namespace, cache_key, result, ttl=ttl)

        return result

    def __del__(self):
        """Clean up session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()
