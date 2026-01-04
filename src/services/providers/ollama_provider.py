"""
Ollama Provider Implementation.

Handles local Ollama deployment for air quality agent.
"""

import json
import logging
from typing import Any

import ollama

from .base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """Ollama local AI provider implementation."""

    def setup(self) -> None:
        """
        Set up Ollama client.

        Note: Ollama is stateless, no authentication required.
        """
        # Ollama is stateless, just log the configuration
        logger.info(
            f"Initialized Ollama provider. Host: {self.settings.OLLAMA_BASE_URL}, Model: {self.settings.AI_MODEL}"
        )

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get Ollama tool definitions.

        Ollama uses OpenAI-compatible format for tools.
        
        Returns:
            List of tool dictionaries
        """
        from ..tool_definitions import openai_tools

        return openai_tools.get_all_tools()

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
        Process a message with Ollama.

        Args:
            message: User message
            history: Conversation history
            system_instruction: System instruction/prompt
            temperature: Response temperature
            top_p: Response top_p
            top_k: Top-k sampling parameter
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with response and tools_used
        """
        # Build messages
        messages = [{"role": "system", "content": system_instruction}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        tools_used = []

        try:
            # Call Ollama with tools
            options = {
                "temperature": temperature,
                "top_p": top_p,
            }

            # Add optional parameters if provided
            if top_k is not None:
                options["top_k"] = top_k
            # Use higher max_tokens when tools are available
            effective_max_tokens = max_tokens if max_tokens is not None else (self.settings.AI_MAX_TOKENS * 2 if self.get_tool_definitions() else self.settings.AI_MAX_TOKENS)
            if effective_max_tokens is not None:
                options["num_predict"] = effective_max_tokens

            response = ollama.chat(
                model=self.settings.AI_MODEL,
                messages=messages,
                tools=self.get_tool_definitions(),
                options=options,
            )

            # Handle tool calls
            if response.get("message", {}).get("tool_calls"):
                tool_calls = response["message"]["tool_calls"]
                logger.info(f"Ollama requested {len(tool_calls)} tool calls")

                # Execute each tool
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = tool_call["function"]["arguments"]

                    tools_used.append(function_name)
                    logger.info(f"Executing tool: {function_name}")

                    # Execute tool
                    try:
                        tool_result = self.tool_executor.execute(function_name, function_args)
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        tool_result = {"error": str(e)}

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(tool_result),
                        }
                    )

                # Get final response with tool results
                final_response = ollama.chat(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "top_p": top_p,
                        "num_predict": effective_max_tokens,
                    },
                )
                response_text = final_response["message"]["content"]
            else:
                # Direct response, no tools
                response_text = response["message"]["content"]

            # Clean response
            response_text = self._clean_response(response_text)

            return {
                "response": response_text or "I apologize, but I couldn't generate a response.",
                "tools_used": tools_used,
            }

        except Exception as e:
            logger.error(f"Ollama processing failed: {e}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "tools_used": tools_used,
            }

    def _clean_response(self, content: str) -> str:
        """
        Clean response content from Ollama.

        Removes code markers and unwanted formatting.
        """
        if not content:
            return ""

        import re

        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)

        # Remove code markers
        unwanted_patterns = [
            "```markdown\n",
            "\n```",
            "```md\n",
            "```text\n",
            "```\n",
            "```",
        ]

        for pattern in unwanted_patterns:
            content = content.replace(pattern, "")

        # Fix common Markdown issues
        # Ensure tables have proper separators
        lines = content.split('\n')
        cleaned_lines = []
        in_table = False
        table_header_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check if this is a table row
            if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_header_count = stripped.count('|') - 1  # Number of columns
                    cleaned_lines.append(line)
                else:
                    current_count = stripped.count('|') - 1
                    if current_count == table_header_count:
                        cleaned_lines.append(line)
                    else:
                        # Skip malformed table rows
                        logger.warning(f"Skipping malformed table row: {stripped}")
                        continue
            else:
                if in_table and stripped and not stripped.startswith('|'):
                    # End of table
                    in_table = False
                cleaned_lines.append(line)

        content = '\n'.join(cleaned_lines)

        # Ensure proper spacing in tables
        content = re.sub(r'\|([^|\n]*?)\|', r'| \1 |', content)
        content = re.sub(r'\| +\|', r'| |', content)  # Remove extra spaces in empty cells

        return content.strip()
