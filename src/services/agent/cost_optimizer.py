"""
Cost Optimization Manager for AI Agent

Implements strategies to minimize AI API costs while maintaining quality:
- Response caching with intelligent invalidation
- Request deduplication
- Token usage monitoring and limits
- Query complexity analysis for model selection
- Streaming for long responses
"""

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CostOptimizer:
    """
    Manages cost optimization strategies for AI operations.

    Implements caching, deduplication, and smart model selection
    to minimize API costs without sacrificing quality.
    """

    def __init__(self, cache_ttl_seconds: int = 3600, max_tokens_per_session: int = 100000):
        """
        Initialize cost optimizer.

        Args:
            cache_ttl_seconds: Time-to-live for cached responses (default 1 hour)
            max_tokens_per_session: Maximum tokens per session before warning
        """
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_tokens_per_session = max_tokens_per_session

        # Extended TTL for sessions with uploaded documents (persist for session lifetime)
        self.document_cache_ttl_seconds = 86400  # 24 hours for document sessions
        self.document_sessions: set[str] = set()  # Track sessions with documents

        # Token usage tracking per session
        self.session_tokens: dict[str, int] = defaultdict(int)
        self.session_costs: dict[str, float] = defaultdict(float)

        # Request deduplication
        self.active_requests: dict[str, Any] = {}

        # Statistics
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.deduplicated_requests = 0

        logger.info(f"Cost optimizer initialized with {cache_ttl_seconds}s cache TTL")

    def _generate_cache_key(self, query: str, context: Optional[dict] = None) -> str:
        """
        Generate cache key from query and context.

        Args:
            query: User query
            context: Additional context (location, session_id, has_document, etc.)

        Returns:
            Cache key hash
        """
        content = query.lower().strip()

        if context:
            # Include session ID for document sessions to maintain session-specific cache
            if "session_id" in context:
                content += f"|session:{context['session_id']}"
            if "location" in context:
                content += f"|loc:{context['location']}"
            if "language" in context:
                content += f"|lang:{context['language']}"

        return hashlib.md5(content.encode()).hexdigest()

    def mark_document_session(self, session_id: str) -> None:
        """Mark a session as having uploaded documents for extended cache TTL."""
        self.document_sessions.add(session_id)
        logger.info(f"Session {session_id} marked as document session (extended cache TTL)")

    def get_cached_response(self, query: str, context: Optional[dict] = None) -> Optional[dict]:
        """
        Get cached response if available and not expired.
        Document sessions have extended TTL to persist content throughout conversation.

        Args:
            query: User query
            context: Additional context (include session_id and has_document flag)

        Returns:
            Cached response or None
        """
        self.total_requests += 1
        cache_key = self._generate_cache_key(query, context)

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            cached_time = cached["timestamp"]
            age = (datetime.now() - cached_time).total_seconds()

            # Check if this is a document session (extended TTL)
            session_id = context.get("session_id") if context else None
            is_document_session = session_id in self.document_sessions if session_id else False
            ttl = self.document_cache_ttl_seconds if is_document_session else self.cache_ttl_seconds

            if age < ttl:
                self.cache_hits += 1
                hit_rate = (self.cache_hits / self.total_requests) * 100
                ttl_type = "document session" if is_document_session else "normal"
                logger.info(f"Cache HIT ({ttl_type}): age {age:.0f}s, hit rate {hit_rate:.1f}%")
                return cached["response"]
            else:
                # Expired - remove from cache
                del self.cache[cache_key]
                logger.debug(f"Cache entry expired after {age:.0f}s")

        self.cache_misses += 1
        logger.debug(f"Cache MISS (hit rate: {self.get_cache_hit_rate():.1f}%)")
        return None

    def cache_response(self, query: str, response: dict, context: Optional[dict] = None) -> None:
        """
        Cache a response for future use.
        If context includes has_document=True, mark as document session.

        Args:
            query: User query
            response: AI response to cache
            context: Additional context (session_id, has_document, etc.)
        """
        cache_key = self._generate_cache_key(query, context)

        # Mark as document session if document was uploaded
        if context and context.get("has_document") and context.get("session_id"):
            self.mark_document_session(context["session_id"])

        self.cache[cache_key] = {"response": response, "timestamp": datetime.now(), "query": query}

        logger.debug(f"Cached response (total: {len(self.cache)})")

    def track_token_usage(
        self, session_id: str, tokens_used: int, cost: float = 0.0
    ) -> dict[str, Any]:
        """
        Track token usage per session.

        Args:
            session_id: Session identifier
            tokens_used: Number of tokens consumed
            cost: Estimated cost in USD

        Returns:
            Usage stats with warnings if approaching limits
        """
        self.session_tokens[session_id] += tokens_used
        self.session_costs[session_id] += cost

        total_tokens = self.session_tokens[session_id]
        total_cost = self.session_costs[session_id]

        # Calculate usage percentage
        usage_pct = (total_tokens / self.max_tokens_per_session) * 100

        # Generate user-friendly warnings
        warning = None
        recommendation = None

        if usage_pct >= 90:
            warning = f"Your conversation is at {usage_pct:.0f}% of the token limit ({total_tokens:,}/{self.max_tokens_per_session:,} tokens)"
            recommendation = "Please start a new chat to continue with optimal performance"
        elif usage_pct >= 75:
            warning = f"Your conversation has used {usage_pct:.0f}% of tokens ({total_tokens:,}/{self.max_tokens_per_session:,})"
            recommendation = "Consider starting a new chat soon"

        if warning:
            logger.warning(f"Session {session_id}: {warning}. {recommendation}")

        return {
            "session_id": session_id,
            "tokens_used": tokens_used,
            "total_tokens": total_tokens,
            "max_tokens": self.max_tokens_per_session,
            "usage_percentage": usage_pct,
            "total_cost_usd": total_cost,
            "warning": warning,
            "recommendation": recommendation,
        }

    def should_use_cheaper_model(self, query: str) -> bool:
        """
        Analyze query complexity to determine if cheaper model is sufficient.

        Args:
            query: User query

        Returns:
            True if query is simple enough for cheaper model
        """
        # Simple heuristics for query complexity
        query_lower = query.lower()

        # Simple queries that don't need advanced models
        simple_patterns = [
            "what is",
            "what's the",
            "current",
            "latest",
            "how is",
            "how's the",
            "show me",
            "get",
        ]

        # Complex queries that need advanced models
        complex_patterns = [
            "analyze",
            "compare",
            "explain why",
            "what if",
            "calculate",
            "predict",
            "recommend",
        ]

        # Check for complex patterns first
        for pattern in complex_patterns:
            if pattern in query_lower:
                return False

        # Check for simple patterns
        for pattern in simple_patterns:
            if pattern in query_lower and len(query.split()) < 15:
                return True

        # Default: use advanced model for safety
        return False

    def deduplicate_request(self, request_key: str) -> bool:
        """
        Check if same request is already in progress.

        Args:
            request_key: Unique identifier for request

        Returns:
            True if request is duplicate (should wait)
        """
        current_time = time.time()

        # Clean up old entries (>30s)
        expired_keys = [
            k for k, v in self.active_requests.items() if current_time - v["start_time"] > 30
        ]
        for k in expired_keys:
            del self.active_requests[k]

        # Check if request is already active
        if request_key in self.active_requests:
            self.deduplicated_requests += 1
            logger.info(f"Duplicate request detected: {request_key}")
            return True

        # Mark as active
        self.active_requests[request_key] = {"start_time": current_time}
        return False

    def complete_request(self, request_key: str) -> None:
        """
        Mark request as complete.

        Args:
            request_key: Request identifier
        """
        if request_key in self.active_requests:
            del self.active_requests[request_key]

    def get_cache_hit_rate(self) -> float:
        """Get cache hit rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    def get_statistics(self) -> dict[str, Any]:
        """
        Get cost optimization statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate_pct": self.get_cache_hit_rate(),
            "cached_entries": len(self.cache),
            "deduplicated_requests": self.deduplicated_requests,
            "active_requests": len(self.active_requests),
            "total_sessions": len(self.session_tokens),
            "total_tokens_all_sessions": sum(self.session_tokens.values()),
            "total_cost_usd_all_sessions": sum(self.session_costs.values()),
        }

    def clear_session(self, session_id: str) -> None:
        """
        Clear session data.

        Args:
            session_id: Session to clear
        """
        if session_id in self.session_tokens:
            del self.session_tokens[session_id]
        if session_id in self.session_costs:
            del self.session_costs[session_id]

    def clear_expired_cache(self) -> int:
        """
        Clear expired cache entries.

        Returns:
            Number of entries cleared
        """
        current_time = datetime.now()
        expired_keys = []

        for key, cached in self.cache.items():
            age = (current_time - cached["timestamp"]).total_seconds()
            if age >= self.cache_ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")

        return len(expired_keys)


# Global cost optimizer instance
_cost_optimizer: Optional[CostOptimizer] = None


def get_cost_optimizer() -> CostOptimizer:
    """
    Get or create global cost optimizer instance.

    Returns:
        CostOptimizer singleton
    """
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer
