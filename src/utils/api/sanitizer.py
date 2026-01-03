"""
API data sanitization utilities.

Provides functions to remove sensitive data like API tokens from responses.
"""

from typing import Any


def sanitize_sensitive_data(data: Any, sensitive_keys: list[str] | None = None, tokens: list[str] | None = None) -> Any:
    """
    Remove sensitive information from data structures.

    Args:
        data: Data structure to sanitize (dict, list, or primitive)
        sensitive_keys: List of key names to redact (default: ["token", "api_key", "password"])
        tokens: List of token strings to replace in values

    Returns:
        Sanitized copy of the data structure
    """
    if sensitive_keys is None:
        sensitive_keys = ["token", "api_key", "password", "apikey", "api-key"]

    if tokens is None:
        tokens = []

    def _sanitize_value(value: Any) -> Any:
        """Sanitize a single value."""
        if isinstance(value, str):
            result = value
            for token in tokens:
                if token and token in result:
                    result = result.replace(token, "[REDACTED]")
            return result
        elif isinstance(value, dict):
            return _sanitize_dict(value)
        elif isinstance(value, list):
            return [_sanitize_value(item) for item in value]
        else:
            return value

    def _sanitize_dict(d: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a dictionary."""
        sanitized = {}
        for key, value in d.items():
            # Check if key is sensitive
            if any(sensitive_key.lower() in key.lower() for sensitive_key in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize_value(value)
        return sanitized

    if isinstance(data, dict):
        return _sanitize_dict(data)
    elif isinstance(data, list):
        return [_sanitize_value(item) for item in data]
    else:
        return _sanitize_value(data)
