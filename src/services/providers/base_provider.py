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
        self, message: str, history: list[dict[str, str]], system_instruction: str
    ) -> dict[str, Any]:
        """
        Process a message and return a response.

        Args:
            message: User message
            history: Conversation history
            system_instruction: System instruction/prompt

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
