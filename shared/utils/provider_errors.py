"""Provider error types and sanitization utilities.

Goal: ensure upstream API failures never leak internal details (tokens,
HTTP errors, stack traces) to user-facing responses.

Use `ProviderServiceError` in API clients, then catch it at boundaries
(REST routes, MCP tools) and return only `public_message`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderServiceError(Exception):
    """Error raised when an upstream provider fails.

    Attributes:
        provider: Short provider key (e.g., "airqo", "waqi").
        public_message: Safe, user-facing message.
        internal_message: Extra diagnostic detail for logs only.
        http_status: Optional HTTP status code observed.
    """

    provider: str
    public_message: str
    internal_message: str | None = None
    http_status: int | None = None

    def __str__(self) -> str:  # pragma: no cover
        # Never leak `internal_message` via implicit string conversions.
        return self.public_message


def provider_unavailable_message(provider_display_name: str) -> str:
    """Standard, professional, non-leaky message for provider failures."""

    return (
        f"Aeris-AQ is currently experiencing issues retrieving data from {provider_display_name}. "
        "Please try again in a few minutes."
    )


def aeris_unavailable_message() -> str:
    """Standard, professional, non-leaky message for internal/tool failures."""

    return "Aeris-AQ is currently experiencing issues. Please try again in a few minutes."
