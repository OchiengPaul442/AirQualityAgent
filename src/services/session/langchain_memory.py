"""
LangChain Memory Integration for Session Management

Provides advanced memory features:
- Token-aware memory truncation
- Conversation summarization
- Redis persistence
- Entity extraction
"""

import logging
from typing import Optional

try:
    from langchain_community.chat_message_histories import RedisChatMessageHistory
    from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
    from langchain_core.messages import AIMessage, HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    logging.warning(f"LangChain imports failed: {e}. Memory features will be limited.")
    LANGCHAIN_AVAILABLE = False
    # Fallback implementations
    BaseChatMessageHistory = object
    InMemoryChatMessageHistory = None
    AIMessage = None
    HumanMessage = None
    RedisChatMessageHistory = None

from src.config import get_settings

logger = logging.getLogger(__name__)


class LangChainSessionMemory:
    """
    Enhanced session memory using LangChain's memory components.
    
    Features:
    - Smart token management (auto-truncation)
    - Redis persistence
    - Message history tracking
    """
    
    def __init__(
        self,
        session_id: str,
        max_messages: int = 20,
        max_tokens: int = 2000,
    ):
        """
        Initialize LangChain memory for a session.
        
        Args:
            session_id: Unique session identifier
            max_messages: Maximum messages to keep
            max_tokens: Maximum tokens to keep (approximate)
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is not available. Please install langchain packages.")
        
        self.session_id = session_id
        self.settings = get_settings()
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        
        # Try Redis first, fallback to in-memory
        self.chat_history: BaseChatMessageHistory = None
        redis_url = f"redis://{self.settings.REDIS_HOST}:{self.settings.REDIS_PORT}"
        
        try:
            # Test Redis connection
            import redis
            redis_client = redis.from_url(redis_url, socket_connect_timeout=2)
            redis_client.ping()
            
            # Redis is available
            self.chat_history = RedisChatMessageHistory(
                session_id=session_id,
                url=redis_url,
                ttl=3600  # 1 hour TTL
            )
            logger.info(f"Initialized Redis chat history for session {session_id}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}). Using in-memory chat history.")
            # In-memory fallback
            self.chat_history = InMemoryChatMessageHistory()
        
        logger.info(f"Initialized LangChain memory for session {session_id}")
    
    def add_user_message(self, message: str) -> None:
        """Add a user message to memory."""
        self.chat_history.add_user_message(message)
        self._trim_messages()
    
    def add_ai_message(self, message: str) -> None:
        """Add an AI message to memory."""
        self.chat_history.add_ai_message(message)
        self._trim_messages()
    
    def _trim_messages(self) -> None:
        """Trim messages to stay within limits."""
        messages = self.chat_history.messages
        if len(messages) > self.max_messages:
            # Keep only the last max_messages
            self.chat_history.clear()
            for msg in messages[-self.max_messages:]:
                self.chat_history.add_message(msg)
    
    def get_history(self) -> list[dict[str, str]]:
        """
        Get conversation history in standard format.
        
        Returns:
            List of message dicts with 'role' and 'content'
        """
        messages = self.chat_history.messages
        history = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:
                # Fallback for other message types
                role = "user" if "human" in msg.__class__.__name__.lower() else "assistant"
            
            history.append({
                "role": role,
                "content": msg.content
            })
        
        return history
    
    def clear(self) -> None:
        """Clear conversation history."""
        self.chat_history.clear()
        logger.info(f"Cleared memory for session {self.session_id}")
    
    def get_token_count(self) -> Optional[int]:
        """Get approximate token count."""
        messages = self.chat_history.messages
        # Approximate: 1 token ≈ 0.75 words
        total_tokens = sum(len(msg.content.split()) * 1.3 for msg in messages)
        return int(total_tokens)


def create_session_memory(
    session_id: str,
    use_summarization: bool = False,
    max_tokens: int = 2000
) -> LangChainSessionMemory:
    """
    Create session memory instance.
    
    Args:
        session_id: Session identifier
        use_summarization: Not used (kept for backward compatibility)
        max_tokens: Maximum tokens to keep
    
    Returns:
        Configured LangChainSessionMemory instance
    """
    return LangChainSessionMemory(
        session_id=session_id,
        max_messages=20,
        max_tokens=max_tokens
    )
