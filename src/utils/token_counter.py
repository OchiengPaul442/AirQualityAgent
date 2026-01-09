"""
Token Counter Utility - World-standard accurate token counting using tiktoken.

Provides precise token counting for different models to ensure accurate cost tracking
and prevent token limit issues.
"""

import logging
from typing import Any

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning("tiktoken not installed. Token counting will be less accurate.")

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    World-standard accurate token counter using tiktoken.

    Supports multiple model encodings:
    - GPT-3.5/GPT-4: cl100k_base
    - GPT-3: p50k_base
    - Gemini: Approximates using cl100k_base (similar tokenization)
    - Ollama: Falls back to word-based estimation
    """

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize token counter.

        Args:
            model: Model name for encoding selection
        """
        self.model = model
        self.encoding = None

        if TIKTOKEN_AVAILABLE:
            try:
                # Map model names to encodings
                if "gpt-4" in model.lower() or "gpt-3.5" in model.lower():
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                elif "gpt-3" in model.lower():
                    self.encoding = tiktoken.get_encoding("p50k_base")
                elif "gemini" in model.lower():
                    # Gemini uses similar tokenization to GPT-4
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                else:
                    # Default to cl100k_base for unknown models
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                    logger.debug(f"Using default cl100k_base encoding for model: {model}")
            except Exception as e:
                logger.warning(f"Failed to initialize tiktoken encoding: {e}")
                self.encoding = None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text with high accuracy.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        if self.encoding and TIKTOKEN_AVAILABLE:
            try:
                tokens = self.encoding.encode(text)
                return len(tokens)
            except Exception as e:
                logger.warning(f"tiktoken encoding failed, falling back to estimation: {e}")

        # Fallback: word-based estimation (less accurate)
        # Average token-to-word ratio is approximately 1.3
        words = len(text.split())
        chars = len(text)
        # More accurate estimation: consider both words and characters
        estimated_tokens = int((words * 1.3) + (chars / 5))
        return estimated_tokens

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """
        Count tokens in a list of messages (conversation format).

        Args:
            messages: List of message dictionaries with 'role' and 'content'

        Returns:
            Total number of tokens including message overhead
        """
        if not messages:
            return 0

        total_tokens = 0

        for message in messages:
            # Count tokens in content
            content = message.get("content", "")
            total_tokens += self.count_tokens(content)

            # Add overhead for message structure
            # Typical overhead: 4 tokens per message for structure
            total_tokens += 4

            # Add tokens for role
            role = message.get("role", "")
            total_tokens += self.count_tokens(role)

        # Add overhead for message array (3 tokens)
        total_tokens += 3

        return total_tokens

    def count_document_tokens(self, document: dict[str, Any]) -> int:
        """
        Count tokens in a document.

        Args:
            document: Document dictionary with 'content' and optional metadata

        Returns:
            Number of tokens in document
        """
        if not document:
            return 0

        total_tokens = 0

        # Count content tokens
        content = document.get("content", "")
        total_tokens += self.count_tokens(str(content))

        # Count metadata tokens (filename, file_type, etc.)
        metadata_text = ""
        for key, value in document.items():
            if key != "content" and value:
                metadata_text += f"{key}: {value} "

        total_tokens += self.count_tokens(metadata_text)

        return total_tokens

    def estimate_cost(self, tokens: int, model: str = "gpt-4", is_input: bool = True) -> float:
        """
        Estimate cost based on token count.

        Args:
            tokens: Number of tokens
            model: Model name
            is_input: True for input tokens, False for output tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1K tokens (as of 2024)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "gemini-pro": {"input": 0.00025, "output": 0.0005},
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "ollama": {"input": 0.0, "output": 0.0},  # Local, free
        }

        # Find matching pricing
        model_lower = model.lower()
        price_per_1k = 0.0

        for model_key, prices in pricing.items():
            if model_key in model_lower:
                price_per_1k = prices["input"] if is_input else prices["output"]
                break

        if price_per_1k == 0.0:
            # Default to GPT-4 pricing for unknown models
            price_per_1k = pricing["gpt-4"]["input"] if is_input else pricing["gpt-4"]["output"]

        cost = (tokens / 1000) * price_per_1k
        return cost

    def analyze_context_window(
        self,
        messages: list[dict[str, str]],
        documents: list[dict[str, Any]] | None = None,
        system_instruction: str = "",
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """
        Analyze if context fits within token limit.

        Args:
            messages: Conversation messages
            documents: Optional documents
            system_instruction: System instruction text
            max_tokens: Maximum token limit

        Returns:
            Analysis dictionary with token counts and recommendations
        """
        # Count tokens for each component
        messages_tokens = self.count_messages_tokens(messages)
        system_tokens = self.count_tokens(system_instruction)

        documents_tokens = 0
        if documents:
            for doc in documents:
                documents_tokens += self.count_document_tokens(doc)

        total_tokens = messages_tokens + system_tokens + documents_tokens

        # Reserve tokens for response (typically 20-30% of max)
        response_reserve = int(max_tokens * 0.25)
        available_for_context = max_tokens - response_reserve

        within_limit = total_tokens <= available_for_context
        utilization = (total_tokens / available_for_context) * 100

        analysis = {
            "total_tokens": total_tokens,
            "messages_tokens": messages_tokens,
            "system_tokens": system_tokens,
            "documents_tokens": documents_tokens,
            "response_reserve": response_reserve,
            "max_tokens": max_tokens,
            "available_for_context": available_for_context,
            "within_limit": within_limit,
            "utilization_percent": round(utilization, 1),
            "tokens_over_limit": max(0, total_tokens - available_for_context),
        }

        # Add recommendations
        if not within_limit:
            analysis["recommendation"] = "Reduce conversation history or document size"
        elif utilization > 80:
            analysis["recommendation"] = (
                "Context usage is high, consider starting a new conversation soon"
            )
        else:
            analysis["recommendation"] = "Context usage is healthy"

        return analysis


# Global instance for easy access
_default_counter = None


def get_token_counter(model: str = "gpt-4") -> TokenCounter:
    """
    Get or create a token counter instance.

    Args:
        model: Model name

    Returns:
        TokenCounter instance
    """
    global _default_counter
    if _default_counter is None or _default_counter.model != model:
        _default_counter = TokenCounter(model)
    return _default_counter


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Quick helper to count tokens in text.

    Args:
        text: Text to count
        model: Model name

    Returns:
        Number of tokens
    """
    counter = get_token_counter(model)
    return counter.count_tokens(text)
