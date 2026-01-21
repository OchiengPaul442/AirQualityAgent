"""
Token Management and Context Optimization Module

Implements intelligent context window management to:
- Prevent token overflow errors
- Maintain conversation coherence
- Prioritize relevant history
- Optimize for different model token limits
- Handle document uploads efficiently

Based on production best practices for long-running conversations.
"""

import logging
import re
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import tiktoken

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Manages token counting and context optimization for different AI models.
    
    Features:
    - Accurate token counting per model
    - Smart truncation strategies
    - Semantic importance scoring
    - Document handling
    - Emergency fallbacks
    """
    
    # Model token limits (input context windows)
    MODEL_LIMITS = {
        # OpenAI models
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16385,
        "gpt-3.5-turbo-16k": 16385,
        
        # Google models
        "gemini-pro": 32768,
        "gemini-1.5-pro": 1000000,  # 1M tokens!
        "gemini-1.5-flash": 1000000,
        "gemini-2.0-flash": 1000000,
        
        # Anthropic models
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-3.5-sonnet": 200000,
        
        # Local models (typical limits)
        "ollama": 8192,  # Default for most Ollama models
        "llama2": 4096,
        "mistral": 8192,
        
        # Default fallback
        "default": 8192
    }
    
    # Reserved tokens for system prompt and response
    SYSTEM_PROMPT_RESERVE = 1000  # tokens
    RESPONSE_RESERVE = 2048  # tokens for model output
    SAFETY_BUFFER = 500  # safety margin
    
    def __init__(self, model: str = "default", encoding_name: str = "cl100k_base"):
        """
        Initialize token manager.
        
        Args:
            model: Model identifier
            encoding_name: Tiktoken encoding name ("cl100k_base" for GPT-4/GPT-3.5)
        """
        self.model = model
        self.token_limit = self._get_model_limit(model)
        
        # Initialize tokenizer
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning(f"Failed to load tiktoken encoding {encoding_name}: {e}")
            logger.warning("Falling back to approximate token counting")
            self.encoding = None
        
        # Calculate available budget for conversation history
        self.history_budget = (
            self.token_limit 
            - self.SYSTEM_PROMPT_RESERVE 
            - self.RESPONSE_RESERVE 
            - self.SAFETY_BUFFER
        )
        
        logger.info(
            f"Token manager initialized for {model}: "
            f"limit={self.token_limit}, history_budget={self.history_budget}"
        )
    
    def _get_model_limit(self, model: str) -> int:
        """
        Get token limit for model.
        
        Args:
            model: Model identifier
            
        Returns:
            Token limit integer
        """
        model_lower = model.lower()
        
        # Check exact matches
        if model_lower in self.MODEL_LIMITS:
            return self.MODEL_LIMITS[model_lower]
        
        # Check partial matches
        for key, limit in self.MODEL_LIMITS.items():
            if key in model_lower:
                return limit
        
        # Default fallback
        logger.warning(f"Unknown model {model}, using default limit {self.MODEL_LIMITS['default']}")
        return self.MODEL_LIMITS["default"]
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Token count
        """
        if not text:
            return 0
        
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"Token encoding error: {e}, falling back to approximation")
        
        # Fallback: approximate token count (1 token ≈ 4 chars for English)
        return len(text) // 4
    
    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """
        Count tokens in message list.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            Total token count
        """
        total = 0
        for message in messages:
            # Count role overhead (approximately 4 tokens per message for formatting)
            total += 4
            
            # Count content
            content = message.get("content", "")
            total += self.count_tokens(content)
        
        return total
    
    def optimize_context(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: Optional[int] = None
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Optimize conversation context to fit within token budget.
        
        Implements intelligent truncation strategy:
        1. Always keep system prompt
        2. Always keep last N messages (recency)
        3. Semantic search for relevant history
        4. Compress older messages if needed
        
        Args:
            messages: List of conversation messages
            system_prompt: System prompt text
            max_tokens: Optional custom token limit (defaults to history_budget)
            
        Returns:
            Tuple of (optimized_messages, metadata)
        """
        if not messages:
            return [], {"truncated": False, "original_count": 0, "final_count": 0}
        
        budget = max_tokens or self.history_budget
        
        # Count system prompt tokens
        system_tokens = self.count_tokens(system_prompt)
        remaining_budget = budget - system_tokens
        
        if remaining_budget < 1000:
            logger.warning(
                f"Very limited token budget: {remaining_budget} tokens. "
                "System prompt may be too large."
            )
        
        # Count total message tokens
        total_tokens = self.count_messages(messages)
        
        # If within budget, return as-is
        if total_tokens <= remaining_budget:
            return messages, {
                "truncated": False,
                "original_count": len(messages),
                "final_count": len(messages),
                "original_tokens": total_tokens,
                "final_tokens": total_tokens
            }
        
        # Need to truncate - use smart strategy
        logger.info(
            f"Token budget exceeded: {total_tokens} > {remaining_budget}. "
            "Applying smart truncation."
        )
        
        optimized_messages = self._smart_truncate(messages, remaining_budget)
        final_tokens = self.count_messages(optimized_messages)
        
        return optimized_messages, {
            "truncated": True,
            "original_count": len(messages),
            "final_count": len(optimized_messages),
            "original_tokens": total_tokens,
            "final_tokens": final_tokens,
            "tokens_saved": total_tokens - final_tokens
        }
    
    def _smart_truncate(
        self,
        messages: List[Dict[str, str]],
        budget: int
    ) -> List[Dict[str, str]]:
        """
        Smart truncation that preserves important context.
        
        Strategy:
        1. Always keep last 3 turns (user + assistant + user)
        2. Keep first message if it contains user info
        3. Fill remaining budget with semantically important messages
        
        Args:
            messages: Full message list
            budget: Token budget
            
        Returns:
            Truncated message list
        """
        if not messages:
            return []
        
        # Reserve tokens for recency (last 3 turns = ~6 messages)
        recency_messages = messages[-6:] if len(messages) > 6 else messages
        recency_tokens = self.count_messages(recency_messages)
        
        # If recency alone exceeds budget, truncate even recent messages
        if recency_tokens > budget:
            logger.warning("Even recent messages exceed budget, applying aggressive truncation")
            return self._aggressive_truncate(recency_messages, budget)
        
        # Budget for historical messages
        history_budget = budget - recency_tokens
        
        # Get older messages (everything except recent)
        older_messages = messages[:-6] if len(messages) > 6 else []
        
        if not older_messages:
            # No older messages to add
            return recency_messages
        
        # Score and select important older messages
        selected_older = self._select_important_messages(older_messages, history_budget)
        
        # Combine: selected older + recent
        final_messages = selected_older + recency_messages
        
        logger.info(
            f"Smart truncation: kept {len(selected_older)} older + "
            f"{len(recency_messages)} recent = {len(final_messages)} total"
        )
        
        return final_messages
    
    def _select_important_messages(
        self,
        messages: List[Dict[str, str]],
        budget: int
    ) -> List[Dict[str, str]]:
        """
        Select most important messages within budget.
        
        Importance factors:
        - Contains user name/location (personalization)
        - Contains data/numbers (factual)
        - User questions (vs small talk)
        - Assistant responses with citations
        
        Args:
            messages: Message list to score
            budget: Token budget
            
        Returns:
            Selected important messages
        """
        # Score each message
        scored_messages = []
        for i, msg in enumerate(messages):
            score = self._score_message_importance(msg, i == 0)
            tokens = self.count_tokens(msg.get("content", ""))
            scored_messages.append({
                "message": msg,
                "score": score,
                "tokens": tokens,
                "index": i
            })
        
        # Sort by score (descending)
        scored_messages.sort(key=lambda x: x["score"], reverse=True)
        
        # Greedily select messages within budget
        selected = []
        used_tokens = 0
        
        for item in scored_messages:
            if used_tokens + item["tokens"] <= budget:
                selected.append(item)
                used_tokens += item["tokens"]
        
        # Sort selected by original index to maintain order
        selected.sort(key=lambda x: x["index"])
        
        return [item["message"] for item in selected]
    
    def _score_message_importance(self, message: Dict[str, str], is_first: bool) -> float:
        """
        Score message importance (0-10).
        
        Args:
            message: Message dictionary
            is_first: Whether this is the first message
            
        Returns:
            Importance score
        """
        content = message.get("content", "").lower()
        role = message.get("role", "")
        
        score = 5.0  # Base score
        
        # Boost for first message (often contains intro/context)
        if is_first:
            score += 2.0
        
        # Boost for user messages (user intent is important)
        if role == "user":
            score += 1.0
        
        # Boost for personalization indicators
        personalization_keywords = [
            "my name is", "i am", "i'm", "i live in", "my location"
        ]
        if any(keyword in content for keyword in personalization_keywords):
            score += 3.0
        
        # Boost for data/measurements
        if re.search(r'\d+(\.\d+)?\s*(µg/m³|pm2\.5|pm10|aqi|ppm)', content):
            score += 2.0
        
        # Boost for questions (user seeking information)
        if "?" in content:
            score += 1.0
        
        # Boost for citations/sources
        if any(word in content for word in ["according to", "source:", "data from", "study"]):
            score += 1.5
        
        # Penalize very short messages (likely small talk)
        if len(content) < 50:
            score -= 1.0
        
        # Penalize generic small talk
        small_talk = ["hello", "hi", "thanks", "thank you", "ok", "okay", "yes", "no"]
        if content.strip() in small_talk:
            score -= 2.0
        
        return max(score, 0.0)  # Min score is 0
    
    def _aggressive_truncate(
        self,
        messages: List[Dict[str, str]],
        budget: int
    ) -> List[Dict[str, str]]:
        """
        Aggressive truncation when even recent messages exceed budget.
        
        Simply keeps as many recent messages as fit within budget.
        
        Args:
            messages: Message list
            budget: Token budget
            
        Returns:
            Truncated messages
        """
        result = []
        used_tokens = 0
        
        # Process from most recent to oldest
        for message in reversed(messages):
            msg_tokens = self.count_tokens(message.get("content", ""))
            
            if used_tokens + msg_tokens <= budget:
                result.insert(0, message)  # Insert at beginning to maintain order
                used_tokens += msg_tokens
            else:
                break
        
        if not result and messages:
            # Emergency: truncate content of last message to fit
            last_message = messages[-1].copy()
            content = last_message.get("content", "")
            
            # Truncate content to fit budget (approximately)
            max_chars = budget * 4  # Rough approximation
            if len(content) > max_chars:
                last_message["content"] = content[:max_chars] + "... [truncated]"
            
            result = [last_message]
            logger.warning("Emergency truncation applied to fit within budget")
        
        return result
    
    def validate_input_size(
        self,
        text: str,
        max_tokens: int = 10000
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that input is not excessively large.
        
        Args:
            text: Input text to validate
            max_tokens: Maximum allowed tokens (default 10K)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        token_count = self.count_tokens(text)
        
        if token_count > max_tokens:
            return False, (
                f"Input is too large: {token_count} tokens (max: {max_tokens}). "
                f"Please provide a shorter message or split into multiple requests."
            )
        
        return True, None


# Global instance
_token_manager_instance = None


def get_token_manager(model: str = "default") -> TokenManager:
    """
    Get or create token manager instance.
    
    Args:
        model: Model identifier
        
    Returns:
        TokenManager instance
    """
    global _token_manager_instance
    if _token_manager_instance is None or _token_manager_instance.model != model:
        _token_manager_instance = TokenManager(model=model)
    return _token_manager_instance
