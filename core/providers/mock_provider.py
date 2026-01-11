"""Mock AI provider for development and automated testing.

This provider avoids external network calls and returns deterministic responses.
It is only activated when `AI_PROVIDER=mock`.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class MockProvider(BaseAIProvider):
    """Deterministic provider that never calls external services."""

    def setup(self) -> None:
        # No external setup required.
        self.client = object()
        logger.warning(
            "MockProvider enabled (AI_PROVIDER=mock). Responses are synthetic and not model-generated."
        )

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        # This provider does not support native tool calling.
        return []

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
        # Keep this deliberately simple and stable so stress tests can run
        # without requiring OpenAI/Gemini/Ollama.
        _ = (history, system_instruction, temperature, top_p, top_k, max_tokens)

        text = (
            "(Mock AI) Running in offline test mode. "
            "I can still help with air quality questions, data summaries, and document analysis. "
            "To use a real model, switch `AI_PROVIDER` to `gemini`, `openai`, or `ollama` and configure provider credentials.\n\n"  # noqa: E501
            f"You asked: {message.strip()}"
        )

        return {
            "response": text,
            "tools_used": [],
        }
