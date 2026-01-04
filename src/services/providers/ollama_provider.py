"""
Ollama Provider Implementation.

Handles local Ollama deployment for air quality agent with enhanced error handling and rate limit detection.
"""

import json
import logging
import time
from datetime import datetime
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

        # Retry configuration for network resilience
        max_retries = 3
        base_delay = 1
        response = None  # Initialize response to prevent NoneType errors
        
        for attempt in range(max_retries):
            try:
                # Call Ollama with tools
                options = {
                    "temperature": temperature,
                    "top_p": top_p,
                }

                # Add optional parameters if provided
                if top_k is not None:
                    options["top_k"] = top_k
                # Use higher max_tokens when tools are available (tool responses need more space)
                effective_max_tokens = max_tokens if max_tokens is not None else (self.settings.AI_MAX_TOKENS * 3 if self.get_tool_definitions() else self.settings.AI_MAX_TOKENS)
                if effective_max_tokens is not None:
                    options["num_predict"] = effective_max_tokens

                response = ollama.chat(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    tools=self.get_tool_definitions(),
                    options=options,
                )
                break  # Success, exit retry loop
                
            except ConnectionError as e:
                logger.error(f"Ollama connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    return {
                        "response": "Unable to connect to the local Ollama service. Please ensure Ollama is running.",
                        "tools_used": [],
                    }
                    
            except TimeoutError as e:
                logger.error(f"Ollama timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    return {
                        "response": "The Ollama service is taking too long to respond. Please try again with a simpler question.",
                        "tools_used": [],
                    }
                    
            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"Ollama error (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Check for rate limiting or quota issues
                if "rate" in error_msg or "limit" in error_msg or "quota" in error_msg:
                    # Extract detailed rate limit information for monitoring
                    error_details = {
                        "provider": "ollama",
                        "error_type": "rate_limit",
                        "timestamp": datetime.now().isoformat(),
                        "model": self.settings.AI_MODEL,
                        "error_message": str(e),
                    }

                    if "rate" in error_msg:
                        error_details["rate_limit_exceeded"] = True
                    if "quota" in error_msg:
                        error_details["quota_exceeded"] = True

                    # Log structured rate limit information
                    logger.warning("🚨 OLLAMA RATE LIMIT EXCEEDED", extra=error_details)

                    return {
                        "response": "Aeris is currently experiencing high demand. Please wait a moment and try again.",
                        "tools_used": [],
                        "rate_limit_info": error_details,
                    }
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # Return user-friendly errors
                    if "connection" in error_msg:
                        return {
                            "response": "Unable to connect to the local Ollama service. Please ensure Ollama is running.",
                            "tools_used": [],
                        }
                    elif "model" in error_msg:
                        return {
                            "response": f"The requested model '{self.settings.AI_MODEL}' is not available. Please pull the model first with: ollama pull {self.settings.AI_MODEL}",
                            "tools_used": [],
                        }
                    else:
                        return {
                            "response": f"I encountered an error: {str(e)}. Please check your Ollama installation and try again.",
                            "tools_used": [],
                        }

            # Validate response before accessing
            if response is None:
                logger.error("Ollama response is None after retry loop - all attempts failed")
                return {
                    "response": "I apologize, but I encountered an error processing your request. Please try again.",
                    "tools_used": [],
                }

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

    def _clean_response(self, content: str) -> str:
        """
        Clean response content from Ollama while preserving markdown structure.

        Removes code markers and unwanted formatting.
        """
        if not content:
            return ""

        import re

        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)

        # Remove code markers ONLY if they're not part of proper code blocks
        unwanted_patterns = [
            "```markdown\n",
            "```md\n",
            "```text\n",
        ]

        for pattern in unwanted_patterns:
            content = content.replace(pattern, "```\n")

        # Ensure proper spacing after markdown elements
        lines = content.split('\n')
        cleaned_lines = []
        prev_was_header = False
        prev_was_list = False
        in_table = False
        table_header_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for headers
            is_header = stripped.startswith('#') and ' ' in stripped[:7]
            
            # Check for list items
            is_list = bool(re.match(r'^[\s]*[-*+]\s', line) or re.match(r'^[\s]*\d+\.\s', line))
            
            # Check if this is a table row
            is_table_row = '|' in stripped and stripped.startswith('|') and stripped.endswith('|')
            
            if is_table_row:
                if not in_table:
                    # Starting a table - ensure blank line before
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append('')
                    in_table = True
                    table_header_count = stripped.count('|') - 1
                    cleaned_lines.append(line)
                else:
                    current_count = stripped.count('|') - 1
                    if current_count == table_header_count:
                        cleaned_lines.append(line)
                    else:
                        logger.warning(f"Skipping malformed table row: {stripped}")
                        continue
            else:
                if in_table and stripped:
                    # End of table - ensure blank line after
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append('')
                    in_table = False
                
                # Ensure proper spacing after headers
                if prev_was_header and stripped and not is_header:
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append('')
                
                # Ensure proper spacing before headers
                if is_header and cleaned_lines and cleaned_lines[-1].strip():
                    if not prev_was_list:
                        cleaned_lines.append('')
                
                cleaned_lines.append(line)
                prev_was_header = is_header
                prev_was_list = is_list

        content = '\n'.join(cleaned_lines)

        # Ensure proper spacing in tables
        content = re.sub(r'\|([^|\n]*?)\|', r'| \1 |', content)
        content = re.sub(r'\| +\|', r'| |', content)

        return content.strip()
