"""
Base provider abstraction for AI model providers.

Defines the interface that all provider implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, settings, tool_executor):
        """
        Initialize the provider.

        Args:
            settings: Application settings
            tool_executor: Tool executor instance
        """
        self.settings = settings
        self.tool_executor = tool_executor
        self.client = None

    @abstractmethod
    def setup(self) -> None:
        """
        Set up the provider client and configuration.

        Raises:
            ValueError: If configuration is invalid or API key is missing
            ConnectionError: If unable to connect to the provider
        """
        pass

    @abstractmethod
    async def process_message(
        self,
        message: str,
        history: list[dict[str, str]],
        system_instruction: str,
        temperature: float = 0.45,
        top_p: float = 0.9,
        top_k: int | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Process a message and return a response.

        Args:
            message: User message
            history: Conversation history
            system_instruction: System instruction/prompt
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling parameter (0.0 to 1.0)
            top_k: Top-k sampling parameter (optional, provider-specific)
            max_tokens: Maximum tokens to generate (optional)

        Returns:
            Dictionary with keys:
                - response: The text response
                - tools_used: List of tools that were called
        """
        pass

    @abstractmethod
    def get_tool_definitions(self) -> Any:
        """
        Get provider-specific tool definitions.

        Returns:
            Tool definitions in the format required by the provider
        """
        pass

    def cleanup(self) -> None:
        """
        Clean up resources (optional).

        Override this if your provider needs to perform cleanup.
        """
        pass

    def _truncate_context_intelligently(
        self, messages: list[dict], system_instruction: str
    ) -> list[dict]:
        """
        Intelligently truncate conversation context when token limit is exceeded.

        Strategy:
        1. Keep system instruction (required)
        2. Keep most recent user message (required)
        3. Keep most recent 2-3 exchanges
        4. Summarize or remove older messages
        5. Keep tool results from recent exchanges

        This is a shared method that all providers can use.

        Args:
            messages: List of message dictionaries
            system_instruction: System instruction text

        Returns:
            Truncated list of messages
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Separate system, user, assistant, and tool messages
            system_msgs = [m for m in messages if m.get("role") == "system"]
            user_msgs = [m for m in messages if m.get("role") == "user"]
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            tool_msgs = [m for m in messages if m.get("role") in ["tool", "function"]]

            # Keep system instruction (always first)
            truncated = (
                system_msgs[:1]
                if system_msgs
                else [{"role": "system", "content": system_instruction}]
            )

            # Keep last 3 user-assistant exchanges (6 messages)
            recent_exchanges = []
            min_keep = min(3, len(user_msgs))

            for i in range(min_keep):
                # Add user message
                if len(user_msgs) > i:
                    recent_exchanges.append(user_msgs[-(i + 1)])

                # Add corresponding assistant message if exists
                if len(assistant_msgs) > i:
                    recent_exchanges.append(assistant_msgs[-(i + 1)])

            # Reverse to maintain chronological order
            recent_exchanges.reverse()

            # Add recent tool messages (last 3)
            recent_tools = tool_msgs[-3:] if len(tool_msgs) > 0 else []

            # Combine: system + recent exchanges + recent tools + current user message
            truncated.extend(recent_exchanges)
            truncated.extend(recent_tools)

            # Ensure the very last user message is included (if not already)
            if user_msgs and user_msgs[-1] not in truncated:
                truncated.append(user_msgs[-1])

            logger.info(f"Context truncated from {len(messages)} to {len(truncated)} messages")
            return truncated

        except Exception as e:
            logger.error(f"Error truncating context: {e}")
            # Fallback: keep system + last 2 messages
            return [
                {"role": "system", "content": system_instruction},
                messages[-2] if len(messages) >= 2 else messages[0],
                messages[-1],
            ]
