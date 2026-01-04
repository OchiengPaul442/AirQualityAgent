"""
Shared utilities for AI providers.

Reduces code duplication across OpenAI, Gemini, and Ollama providers.
Provides both synchronous and asynchronous utilities for maximum flexibility.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Union

logger = logging.getLogger(__name__)


def retry_with_exponential_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    provider_name: str = "AI",
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> Any:
    """
    Retry a synchronous function with exponential backoff.

    Args:
        func: Function to retry (should raise exception on failure)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied each retry)
        provider_name: Name of provider for logging
        backoff_multiplier: Multiplier for exponential backoff (default 2.0)
        max_delay: Maximum delay between retries in seconds

    Returns:
        Result from successful function call

    Raises:
        Last exception encountered after all retries exhausted
    """
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")
    if base_delay <= 0:
        raise ValueError("base_delay must be positive")
    if backoff_multiplier <= 1:
        raise ValueError("backoff_multiplier must be greater than 1")

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:  # Don't log on final attempt
                delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                logger.warning(
                    f"{provider_name} error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.1f} seconds..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"{provider_name} failed after {max_retries + 1} attempts: {e}"
                )

    # This should never be reached due to the loop logic, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry logic error")


async def retry_with_exponential_backoff_async(
    func: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    provider_name: str = "AI",
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> Any:
    """
    Retry an asynchronous function with exponential backoff.

    Args:
        func: Async function to retry (should raise exception on failure)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied each retry)
        provider_name: Name of provider for logging
        backoff_multiplier: Multiplier for exponential backoff (default 2.0)
        max_delay: Maximum delay between retries in seconds

    Returns:
        Result from successful function call

    Raises:
        Last exception encountered after all retries exhausted
    """
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")
    if base_delay <= 0:
        raise ValueError("base_delay must be positive")
    if backoff_multiplier <= 1:
        raise ValueError("backoff_multiplier must be greater than 1")

    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:  # Don't log on final attempt
                delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                logger.warning(
                    f"{provider_name} error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.1f} seconds..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{provider_name} failed after {max_retries + 1} attempts: {e}"
                )

    # This should never be reached due to the loop logic, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry logic error")


def create_rate_limit_error_details(
    provider: str,
    model: str,
    error: Exception,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create structured rate limit error details for logging and monitoring.

    Args:
        provider: Provider name (openai, gemini, ollama)
        model: Model name
        error: Exception that occurred
        headers: Optional headers from API response (for OpenAI)

    Returns:
        Dictionary with structured error details

    Raises:
        ValueError: If provider or model is invalid
    """
    if not provider or not isinstance(provider, str):
        raise ValueError("provider must be a non-empty string")
    if not model or not isinstance(model, str):
        raise ValueError("model must be a non-empty string")
    if not error:
        raise ValueError("error cannot be None")

    error_details = {
        "provider": provider.lower().strip(),
        "error_type": "rate_limit",
        "timestamp": datetime.now().isoformat(),
        "model": model.strip(),
        "error_message": str(error),
        "error_class": error.__class__.__name__,
    }

    # Add provider-specific details
    if headers and isinstance(headers, dict):
        if provider.lower() == "openai":
            # OpenAI rate limit headers
            error_details.update({
                "x_ratelimit_limit_requests": headers.get("x-ratelimit-limit-requests"),
                "x_ratelimit_limit_tokens": headers.get("x-ratelimit-limit-tokens"),
                "x_ratelimit_remaining_requests": headers.get("x-ratelimit-remaining-requests"),
                "x_ratelimit_remaining_tokens": headers.get("x-ratelimit-remaining-tokens"),
                "x_ratelimit_reset_requests": headers.get("x-ratelimit-reset-requests"),
                "x_ratelimit_reset_tokens": headers.get("x-ratelimit-reset-tokens"),
            })
        elif provider.lower() == "gemini":
            # Gemini might have different headers in the future
            pass

    # Classify error type more precisely
    error_msg_lower = str(error).lower()

    # Check for different types of rate limiting
    if "quota" in error_msg_lower:
        error_details["quota_exceeded"] = True
        error_details["error_subtype"] = "quota"
    elif "rate" in error_msg_lower or "limit" in error_msg_lower:
        error_details["rate_limit_exceeded"] = True
        error_details["error_subtype"] = "rate_limit"
    elif "throttle" in error_msg_lower:
        error_details["throttled"] = True
        error_details["error_subtype"] = "throttling"
    else:
        error_details["error_subtype"] = "unknown_rate_limit"

    # Add severity assessment
    if error_details.get("x_ratelimit_remaining_requests") == "0":
        error_details["severity"] = "critical"
    elif error_details.get("x_ratelimit_remaining_tokens") == "0":
        error_details["severity"] = "high"
    else:
        error_details["severity"] = "medium"

    return error_details


def get_user_friendly_error_message(
    error: Exception,
    provider: str,
    error_details: dict[str, Any] | None = None,
) -> str:
    """
    Convert technical errors to user-friendly messages.

    Args:
        error: Exception that occurred
        provider: Provider name for context
        error_details: Optional structured error details

    Returns:
        User-friendly error message

    Raises:
        ValueError: If provider is invalid
    """
    if not provider or not isinstance(provider, str):
        raise ValueError("provider must be a non-empty string")

    provider = provider.lower().strip()
    error_msg_lower = str(error).lower() if error else ""

    # Connection and network errors
    if is_connection_error(error):
        if provider == "ollama":
            return "Unable to connect to the local Ollama service. Please ensure Ollama is running and accessible."
        else:
            return "I'm having trouble connecting to the AI service. Please check your internet connection and try again."

    # Timeout errors
    if "timeout" in error_msg_lower or "timed out" in error_msg_lower:
        return "The AI service is taking too long to respond. Please try again with a simpler question or try again later."

    # Rate limit and quota errors
    if is_rate_limit_error(error):
        base_msg = "Aeris is currently experiencing high demand. Please wait a moment and try again."

        # Add reset time info if available (OpenAI)
        if error_details and provider == "openai":
            reset_time = (
                error_details.get("x_ratelimit_reset_requests") or
                error_details.get("x_ratelimit_reset_tokens")
            )
            if reset_time:
                base_msg += f" Expected reset in approximately {reset_time}."

        # Add provider-specific guidance
        if provider == "ollama":
            base_msg += " Consider using a different model or checking your Ollama configuration."
        elif provider == "gemini":
            base_msg += " Consider upgrading your Gemini quota or using a different model."

        return base_msg

    # Provider-specific errors
    if provider == "ollama":
        if "model" in error_msg_lower or "not found" in error_msg_lower:
            model_name = error_details.get("model", "the requested model") if error_details else "the requested model"
            return f"The model '{model_name}' is not available in Ollama. Please pull the model first with: ollama pull {model_name}"
        if "refused" in error_msg_lower:
            return "Connection refused by Ollama service. Please check that Ollama is running on the correct port."

    elif provider == "openai":
        if "authentication" in error_msg_lower or "api key" in error_msg_lower:
            return "Authentication failed. Please check your OpenAI API key configuration."
        if "insufficient_quota" in error_msg_lower:
            return "Your OpenAI account has insufficient quota. Please check your billing settings or upgrade your plan."

    elif provider == "gemini":
        if "authentication" in error_msg_lower or "credentials" in error_msg_lower:
            return "Authentication failed. Please check your Gemini API key configuration."
        if "permission" in error_msg_lower:
            return "Permission denied. Please check your Gemini API permissions and quota."

    # Model-specific errors
    if "model" in error_msg_lower and ("not found" in error_msg_lower or "does not exist" in error_msg_lower):
        return f"The requested model is not available. Please check your model configuration."

    # Content policy/filtering errors
    if "content" in error_msg_lower and ("policy" in error_msg_lower or "filter" in error_msg_lower):
        return "Your request was filtered due to content policies. Please rephrase your question."

    # Generic fallback with more context
    error_class = error.__class__.__name__ if error else "Unknown"
    return f"I encountered an error ({error_class}). Please try again or contact support if the issue persists."


def calculate_effective_max_tokens(
    max_tokens: int | None,
    default_max_tokens: int,
    has_tools: bool,
    multiplier: float = 3.0,
    max_allowed_tokens: int = 128000,  # Conservative upper limit
) -> int:
    """
    Calculate effective max_tokens based on context.

    When tools are available, responses tend to be longer, so we increase the token limit.
    Includes validation and safety limits.

    Args:
        max_tokens: Explicit max_tokens override (if provided)
        default_max_tokens: Default max_tokens from settings
        has_tools: Whether tools are available for this request
        multiplier: Token multiplier when tools are available (default 3x)
        max_allowed_tokens: Absolute maximum allowed tokens (safety limit)

    Returns:
        Effective max_tokens to use (guaranteed to be positive and within limits)

    Raises:
        ValueError: If parameters are invalid
    """
    if default_max_tokens <= 0:
        raise ValueError("default_max_tokens must be positive")
    if multiplier <= 1:
        raise ValueError("multiplier must be greater than 1")
    if max_allowed_tokens <= 0:
        raise ValueError("max_allowed_tokens must be positive")

    # Use explicit max_tokens if provided
    if max_tokens is not None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive if provided")
        effective_tokens = max_tokens
    else:
        # Calculate based on tools availability
        if has_tools:
            effective_tokens = int(default_max_tokens * multiplier)
        else:
            effective_tokens = default_max_tokens

    # Apply safety limits
    if effective_tokens > max_allowed_tokens:
        logger.warning(
            f"Requested tokens ({effective_tokens}) exceeds safety limit ({max_allowed_tokens}). "
            f"Capping at {max_allowed_tokens}."
        )
        effective_tokens = max_allowed_tokens

    # Ensure minimum viable tokens
    min_tokens = 1000  # Minimum for coherent responses
    if effective_tokens < min_tokens:
        logger.warning(
            f"Effective tokens ({effective_tokens}) below minimum ({min_tokens}). "
            f"Increasing to {min_tokens}."
        )
        effective_tokens = min_tokens

    return effective_tokens


def log_rate_limit_event(provider: str, error_details: dict[str, Any]) -> None:
    """
    Log structured rate limit event for monitoring.

    Args:
        provider: Provider name
        error_details: Structured error details
    """
    logger.warning(f"🚨 {provider.upper()} RATE LIMIT EXCEEDED", extra=error_details)


def is_rate_limit_error(error: Exception) -> bool:
    """
    Check if an error is a rate limit error.

    Args:
        error: Exception to check

    Returns:
        True if error indicates rate limiting
    """
    error_msg = str(error).lower()
    return any(keyword in error_msg for keyword in ["rate", "limit", "quota", "throttle"])


def is_connection_error(error: Exception) -> bool:
    """
    Check if an error is a connection error.

    Args:
        error: Exception to check

    Returns:
        True if error indicates connection issue
    """
    error_msg = str(error).lower()
    return any(keyword in error_msg for keyword in ["connection", "network", "refused", "timeout"])
