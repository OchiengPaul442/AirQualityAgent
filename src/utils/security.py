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

# CRITICAL patterns that MUST be blocked (actual attacks)
CRITICAL_PATTERNS = [
    # Multi-stage SQL injection with chaining
    r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s+(.*\s+)?(FROM|INTO|TABLE|DATABASE)",
    # Command chaining that could cause system damage
    r"(;|&&|\|\|)\s*(rm|del|format|shutdown|reboot|halt)\s+-[rRfF]",
    # Direct code execution attempts
    r"\b(eval|exec)\s*\(\s*(__import__|compile|input)\s*\(",
    r"__import__\s*\(\s*['\"]os['\"]\s*\)\s*\.\s*system",
    # Path traversal with file operations
    r"(\.\./){3,}",  # Multiple directory traversals
]

# Patterns to SANITIZE (remove but allow request)
SANITIZE_PATTERNS = [
    # SQL keywords in isolation (clean but don't block)
    r"\b(SELECT|DELETE)\s+.*\s+(FROM|WHERE)\b",
    r"\bINSERT\s+INTO\s+\w+\s+(VALUES|\()",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\b(DROP|CREATE|ALTER)\s+(TABLE|DATABASE|INDEX|VIEW|USER)\b",
    r"\bEXEC(UTE)?\s+\w+",
    r"\bUNION\s+(ALL\s+)?SELECT\b",
    r"--\s*$",  # SQL comments
    r"/\*.*\*/",  # SQL block comments
    # Shell commands in backticks (clean but allow markdown)
    r"`\s*(whoami|id|pwd|ps|rm|kill|sudo)\s*`",
    r"\$\((?:whoami|id|pwd|rm|kill|sudo)\)",
    # XSS patterns
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
    # Code execution (single attempts)
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
]

# Safe characters for different contexts (EXPANDED for international support)
SAFE_CHARS = re.compile(r"[^a-zA-Z0-9\s\.,!?\-\'\"():;°µ²³/]")


class InputSanitizer:
    """Comprehensive input sanitization and validation."""

    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 50000, html_escape: bool = False) -> str:
        """
        Sanitize text input - removes dangerous patterns while allowing technical content.
        
        Two-stage approach:
        1. Check for CRITICAL attacks → raise exception
        2. Clean SANITIZE patterns → allow request

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length (default 50KB)
            html_escape: Whether to HTML escape (default False)

        Returns:
            Sanitized text
            
        Raises:
            ValueError: If critical attack pattern detected
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string")

        # Limit length
        if len(text) > max_length:
            text = text[:max_length]

        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)

        # Remove null bytes and control characters (keep newlines, tabs)
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\r\t")

        # STAGE 1: Check for CRITICAL attacks
        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                raise ValueError("Critical security threat detected and blocked")

        # STAGE 2: Sanitize non-critical patterns (clean but allow)
        for pattern in SANITIZE_PATTERNS:
            text = re.sub(pattern, " [removed] ", text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)

        # HTML escape only if requested
        if html_escape:
            text = html.escape(text, quote=True)

        # Remove excessive whitespace
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    @staticmethod
    def validate_message_content(message: str) -> bool:
        """
        Validate message content - only blocks CRITICAL attacks.
        Most patterns are sanitized rather than rejected.

        Args:
            message: Message to validate

        Returns:
            True if safe or sanitizable, False only if critical attack
        """
        if not isinstance(message, str):
            return False

        # Check length limits
        if len(message) > 100000:  # 100KB limit
            return False

        # Only block CRITICAL attack patterns
        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                return False

        # Allow high ratio of special chars for technical content
        allowed_special = " \n\r\t.,!?-'\"():;°µ²³/[]{}<>=@#$%&*+~`|"
        special_chars = sum(
            1 for char in message if not char.isalnum() and char not in allowed_special
        )
        if special_chars > len(message) * 0.7:  # 70% threshold
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
        filename = re.sub(r"[\/\\]", "", filename)

        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', "", filename)

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
        input_str = input_str.replace("%", "\\%").replace("_", "\\_")

        # Remove other dangerous SQL characters
        input_str = re.sub(r"[;\'\"]", "", input_str)

        return input_str


class ResponseFilter:
    """Filter and clean AI responses to hide implementation details."""

    # Patterns to remove from responses
    TOOL_MENTION_PATTERNS = [
        r"\b(get_african_city_air_quality|get_city_air_quality|get_weather_forecast|search_web)\b",
        r"\b(API call|function call|tool call|retrieved through)\b",
        r"\b(using the|via the|through the)\s+\w+_?\w*\s+(API|service|function)\b",
        r"\b(called|executed|invoked)\s+(the\s+)?\w+_?\w*\s+(function|API|tool)\b",
    ]

    # Source name mappings
    SOURCE_MAPPINGS = {
        "get_african_city_air_quality": "AirQo",
        "get_city_air_quality": "WAQI",
        "get_weather_forecast": "Open-Meteo",
        "search_web": "web search",
        "get_openmeteo_current_air_quality": "Open-Meteo",
        "get_multiple_african_cities_air_quality": "AirQo",
    }

    @staticmethod
    def clean_response(response: str) -> str:
        """
        Clean AI response to remove tool mentions, API keys, tokens, and implementation details.

        Args:
            response: Raw AI response

        Returns:
            Cleaned response suitable for users
        """
        if not isinstance(response, str):
            return str(response)

        # Remove API keys and tokens (more aggressive patterns)
        # Pattern 1: "API key is abc123" or "token is def456"
        response = re.sub(
            r"(?i)(api\s*key|token|secret|password|auth\s*key)\s+(is|are|:|=)\s+[a-zA-Z0-9_\-]+",
            r"\1 [FILTERED]",
            response,
        )
        # Pattern 2: key="abc123" or token="def456"
        response = re.sub(
            r'(?i)(api[-_]?key|token|secret|password|auth[-_]?key)\s*[:=]\s*[\'"]?([a-zA-Z0-9_\-]{8,})[\'"]?',
            r"\1=[FILTERED]",
            response,
        )
        # Pattern 3: Plain alphanumeric keys/tokens after mention
        response = re.sub(r"(?i)\b(key|token)\s+[a-zA-Z0-9_\-]{20,}\b", r"\1 [FILTERED]", response)

        # Remove tool function names
        for pattern in ResponseFilter.TOOL_MENTION_PATTERNS:
            response = re.sub(pattern, "", response, flags=re.IGNORECASE)

        # Replace technical source mentions with user-friendly names
        for tech_name, user_name in ResponseFilter.SOURCE_MAPPINGS.items():
            response = re.sub(
                rf"\b{re.escape(tech_name)}\b", user_name, response, flags=re.IGNORECASE
            )

        # Clean up any resulting awkward phrasing BUT PRESERVE NEWLINES
        # Split by lines first to preserve markdown structure
        lines = response.split("\n")
        cleaned_lines = []
        for line in lines:
            # Only collapse multiple spaces within a line, NOT newlines
            line = re.sub(r"  +", " ", line)  # Multiple spaces (not single space)
            line = re.sub(r"\s*\.\s*\.", ".", line)  # Double periods
            line = re.sub(r"\s*,\s*,", ",", line)  # Double commas
            cleaned_lines.append(line.strip())

        # Rejoin with newlines to preserve markdown structure
        response = "\n".join(cleaned_lines)
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
                if key.startswith("_") or key in ["tools_used", "internal_data"]:
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
    
    Strategy: Sanitize first, then check only for critical attacks.
    This allows technical content to be cleaned and accepted.

    Args:
        data: Request data dictionary

    Returns:
        Validated and sanitized data

    Raises:
        ValueError: If critical attack detected
    """
    sanitized = {}

    for key, value in data.items():
        if key == "message":
            if not isinstance(value, str):
                raise ValueError("Message must be a string")
            
            # Check length limit first
            if len(value) > 100000:
                raise ValueError("Message too long (max 100KB)")
            
            # Check for CRITICAL patterns only (before sanitization)
            for pattern in CRITICAL_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                    raise ValueError("Critical security threat detected")
            
            # Sanitize the message (cleans dangerous patterns)
            try:
                sanitized[key] = InputSanitizer.sanitize_text_input(value, html_escape=False)
            except ValueError as e:
                # If sanitization fails due to critical pattern, block it
                raise ValueError(f"Message contains dangerous content: {str(e)}")
        elif key == "session_id":
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("Session ID must be a string")
                # Basic UUID validation
                if not re.match(r"^[a-f0-9\-]{36}$", value):
                    raise ValueError("Invalid session ID format")
            # Always include session_id in sanitized data, even if None
            sanitized[key] = value
        elif key == "file":
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
