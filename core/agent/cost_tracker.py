"""
Cost tracking module for AI API usage.

Tracks token usage, costs, and enforces daily limits to prevent unexpected charges.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CostTracker:
    """Tracks API costs and enforces limits."""

    max_daily_cost: float = 10.0  # $10 per day default
    max_daily_requests: int = 100  # 100 requests per day default
    total_tokens: int = 0
    total_cost: float = 0.0
    requests_today: int = 0
    last_reset: date = field(default_factory=lambda: datetime.now().date())

    def check_limits(self) -> tuple[bool, str | None]:
        """
        Check if we're within cost limits.

        Returns:
            Tuple of (within_limits, error_message)
        """
        # Reset daily counters if it's a new day
        today = datetime.now().date()
        if self.last_reset != today:
            self.requests_today = 0
            self.total_cost = 0.0
            self.last_reset = today
            logger.info("Cost tracker reset for new day")

        # Check cost limit
        if self.total_cost >= self.max_daily_cost:
            return False, f"Daily cost limit reached (${self.max_daily_cost:.2f})"

        # Check request limit
        if self.requests_today >= self.max_daily_requests:
            return False, f"Daily request limit reached ({self.max_daily_requests} requests)"

        return True, None

    def track_usage(self, tokens_used: int, estimated_cost: float) -> None:
        """
        Track API usage.

        Args:
            tokens_used: Number of tokens consumed
            estimated_cost: Estimated cost in dollars
        """
        self.total_tokens += tokens_used
        self.total_cost += estimated_cost
        self.requests_today += 1

        logger.info(
            f"Cost tracking - Tokens: {tokens_used}, Cost: ${estimated_cost:.4f}, "
            f"Total today: ${self.total_cost:.4f}, Requests: {self.requests_today}"
        )

    def get_status(self) -> dict[str, Any]:
        """
        Get current cost tracking status.

        Returns:
            Dictionary with current tracking metrics
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "requests_today": self.requests_today,
            "last_reset": self.last_reset.isoformat(),
            "max_daily_cost": self.max_daily_cost,
            "max_daily_requests": self.max_daily_requests,
            "remaining_cost": max(0, self.max_daily_cost - self.total_cost),
            "remaining_requests": max(0, self.max_daily_requests - self.requests_today),
        }

    def reset(self) -> None:
        """Reset all counters manually."""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.requests_today = 0
        self.last_reset = datetime.now().date()
        logger.info("Cost tracker manually reset")
