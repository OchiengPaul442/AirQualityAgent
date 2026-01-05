"""
Security utilities for input sanitization and protection against attacks.

Provides comprehensive protection against:
- SQL injection
- XSS (Cross-Site Scripting)
- Command injection
- Path traversal
- Malicious code execution
"""

import html
import re
import unicodedata
from typing import Any, Dict, List, Union

# Dangerous patterns that should be blocked
DANGEROUS_PATTERNS = [
    # SQL injection patterns
    r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|JOIN)\b',
    r';\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)',
    r'--\s*$',  # SQL comments
    r'/\*.*\*/',  # SQL block comments

    # Command injection patterns
    r'[;&|`$()<>]',  # Shell metacharacters
    r'\b(rm|del|format|shutdown|reboot|halt|poweroff)\b',
    r'\b(cmd|bash|sh|powershell|exe)\b',

    # Path traversal
    r'\.\./',  # Directory traversal
    r'\\\.\\\.\\',  # Windows path traversal

    # XSS patterns
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',

    # Code execution patterns
    r'\b(eval|exec|compile|__import__|importlib|subprocess|os\.system|os\.popen)\b',
    r'\b(open|file|input)\s*\(',
]

# Safe characters for different contexts
SAFE_CHARS = re.compile(r'[^a-zA-Z0-9\s\.,!?\-\'\"():;]')

class InputSanitizer:
    """Comprehensive input sanitization and validation."""

    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 10000) -> str:
        """
        Sanitize text input for general use.

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string")

        # Limit length
        if len(text) > max_length:
            text = text[:max_length]

        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)

        # Remove null bytes and other control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

        # Remove dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)

        # HTML escape
        text = html.escape(text, quote=True)

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @staticmethod
    def validate_message_content(message: str) -> bool:
        """
        Validate message content for potential security issues.

        Args:
            message: Message to validate

        Returns:
            True if message appears safe, False if potentially dangerous
        """
        if not isinstance(message, str):
            return False

        # Check length limits
        if len(message) > 50000:  # 50KB limit
            return False

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                return False

        # Check for excessive special characters
        special_chars = sum(1 for char in message if not char.isalnum() and char not in ' \n\r\t.,!?-')
        if special_chars > len(message) * 0.3:  # More than 30% special chars
            return False

        return True

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        if not isinstance(filename, str):
            raise ValueError("Filename must be a string")

        # Remove path separators
        filename = re.sub(r'[\/\\]', '', filename)

        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)

        # Limit length
        if len(filename) > 255:
            filename = filename[:255]

        # Ensure it's not empty
        if not filename.strip():
            filename = "unnamed_file"

        return filename

    @staticmethod
    def sanitize_sql_like_input(input_str: str) -> str:
        """
        Sanitize input that might be used in SQL LIKE queries.

        Args:
            input_str: Input to sanitize

        Returns:
            Sanitized input safe for SQL LIKE
        """
        if not isinstance(input_str, str):
            raise ValueError("Input must be a string")

        # Escape SQL LIKE wildcards
        input_str = input_str.replace('%', '\\%').replace('_', '\\_')

        # Remove other dangerous SQL characters
        input_str = re.sub(r'[;\'\"]', '', input_str)

        return input_str


class ResponseFilter:
    """Filter and clean AI responses to hide implementation details."""

    # Patterns to remove from responses
    TOOL_MENTION_PATTERNS = [
        r'\b(get_african_city_air_quality|get_city_air_quality|get_weather_forecast|search_web)\b',
        r'\b(API call|function call|tool call|retrieved through)\b',
        r'\b(using the|via the|through the)\s+\w+_?\w*\s+(API|service|function)\b',
        r'\b(called|executed|invoked)\s+(the\s+)?\w+_?\w*\s+(function|API|tool)\b',
    ]

    # Source name mappings
    SOURCE_MAPPINGS = {
        'get_african_city_air_quality': 'AirQo',
        'get_city_air_quality': 'WAQI',
        'get_weather_forecast': 'Open-Meteo',
        'search_web': 'web search',
        'get_openmeteo_current_air_quality': 'Open-Meteo',
        'get_multiple_african_cities_air_quality': 'AirQo',
    }

    @staticmethod
    def clean_response(response: str) -> str:
        """
        Clean AI response to remove tool mentions and implementation details.

        Args:
            response: Raw AI response

        Returns:
            Cleaned response suitable for users
        """
        if not isinstance(response, str):
            return str(response)

        # Remove tool function names
        for pattern in ResponseFilter.TOOL_MENTION_PATTERNS:
            response = re.sub(pattern, '', response, flags=re.IGNORECASE)

        # Replace technical source mentions with user-friendly names
        for tech_name, user_name in ResponseFilter.SOURCE_MAPPINGS.items():
            response = re.sub(
                rf'\b{re.escape(tech_name)}\b',
                user_name,
                response,
                flags=re.IGNORECASE
            )

        # Clean up any resulting awkward phrasing BUT PRESERVE NEWLINES
        # Split by lines first to preserve markdown structure
        lines = response.split('\n')
        cleaned_lines = []
        for line in lines:
            # Only collapse multiple spaces within a line, NOT newlines
            line = re.sub(r'  +', ' ', line)  # Multiple spaces (not single space)
            line = re.sub(r'\s*\.\s*\.', '.', line)  # Double periods
            line = re.sub(r'\s*,\s*,', ',', line)  # Double commas
            cleaned_lines.append(line.strip())
        
        # Rejoin with newlines to preserve markdown structure
        response = '\n'.join(cleaned_lines)
        return response.strip()

    @staticmethod
    def sanitize_for_display(data: Any) -> Any:
        """
        Recursively sanitize data for display to users.

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Skip internal fields
                if key.startswith('_') or key in ['tools_used', 'internal_data']:
                    continue
                sanitized[key] = ResponseFilter.sanitize_for_display(value)
            return sanitized
        elif isinstance(data, list):
            return [ResponseFilter.sanitize_for_display(item) for item in data]
        elif isinstance(data, str):
            return ResponseFilter.clean_response(data)
        else:
            return data


def validate_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize request data.

    Args:
        data: Request data dictionary

    Returns:
        Validated and sanitized data

    Raises:
        ValueError: If validation fails
    """
    sanitized = {}

    for key, value in data.items():
        if key == 'message':
            if not isinstance(value, str):
                raise ValueError("Message must be a string")
            if not InputSanitizer.validate_message_content(value):
                raise ValueError("Message contains potentially dangerous content")
            sanitized[key] = InputSanitizer.sanitize_text_input(value)
        elif key == 'session_id':
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("Session ID must be a string")
                # Basic UUID validation
                if not re.match(r'^[a-f0-9\-]{36}$', value):
                    raise ValueError("Invalid session ID format")
            # Always include session_id in sanitized data, even if None
            sanitized[key] = value
        elif key == 'file':
            # File validation is handled separately in the route
            sanitized[key] = value
        else:
            # For other fields, basic sanitization
            if isinstance(value, str):
                sanitized[key] = InputSanitizer.sanitize_text_input(value, max_length=1000)
            else:
                sanitized[key] = value

    return sanitized


def sanitize_response(response: str) -> str:
    """
    Sanitize AI response content to prevent XSS attacks.

    Args:
        response: Raw response string

    Returns:
        Sanitized response string safe for HTML display
    """
    if not isinstance(response, str):
        return str(response)

    # HTML escape dangerous characters
    import html
    sanitized = html.escape(response, quote=True)

    return sanitized