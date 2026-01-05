"""
Ollama Provider Implementation.

Handles local Ollama deployment for air quality agent with enhanced error handling and rate limit detection.
"""

import asyncio
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
                    "timeout": 30,  # 30 seconds timeout
                }

                # Add optional parameters if provided
                if top_p is not None:
                    options["top_p"] = top_p
                if top_k is not None:
                    options["top_k"] = top_k
                if max_tokens is not None:
                    options["num_predict"] = max_tokens

                logger.info(f"Calling Ollama chat with model {self.settings.AI_MODEL}, messages count: {len(messages)}")

                response = ollama.chat(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    options=options,
                )

                print(f"Ollama response: {response}")

                if response is None:
                    logger.error("Ollama chat returned None")
                    return {
                        "response": "I apologize, but the AI service returned no response. Please try again.",
                        "tools_used": [],
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                    }

                logger.info(f"Ollama response type: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'not dict'}")
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
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
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
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
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
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
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
                            "tokens_used": 0,
                            "cost_estimate": 0.0,
                        }
                    elif "model" in error_msg:
                        return {
                            "response": f"The requested model '{self.settings.AI_MODEL}' is not available. Please pull the model first with: ollama pull {self.settings.AI_MODEL}",
                            "tools_used": [],
                            "tokens_used": 0,
                            "cost_estimate": 0.0,
                        }
                    else:
                        # Log the full error for developers but provide user-friendly message
                        logger.error(f"Unexpected Ollama error (attempt {attempt + 1}/{max_retries}): {e}")
                        return {
                            "response": (
                                "I apologize, but I'm experiencing technical difficulties with the local AI service. "
                                "Please ensure Ollama is running and the model is available, then try again."
                            ),
                            "tools_used": [],
                            "error_logged": True,  # Flag for internal tracking
                            "tokens_used": 0,
                            "cost_estimate": 0.0,
                        }

        # Validate response before accessing (outside retry loop)
        if response is None:
            logger.error("Ollama response is None after retry loop - all attempts failed")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "tools_used": [],
                "tokens_used": 0,
                "cost_estimate": 0.0,
            }

        # If the response object is not a dict-like with .get(), try to adapt
        try:
            has_message = response.get("message") if isinstance(response, dict) else getattr(response, 'message', None)
        except Exception:
            has_message = None

        if not has_message:
            logger.error(f"Ollama response message is None or empty: {response}")
            return {
                "response": "I apologize, but I received an invalid response from the AI service. Please try again.",
                "tools_used": [],
                "tokens_used": 0,
                "cost_estimate": 0.0,
            }

        # Normalize message object access
        message_obj = response.get("message") if isinstance(response, dict) else getattr(response, 'message')

        # Handle tool calls
        if getattr(message_obj, 'tool_calls', None):
            tool_calls = message_obj.tool_calls
            logger.info(f"Ollama requested {len(tool_calls)} tool calls")

            tool_results = []

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

                tool_results.append(tool_result)

                # Add tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(tool_result),
                    }
                )

                # Also append a short summary to help the model
                summary = self._summarize_tool_result(tool_result)
                if summary:
                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps({"summary": summary}),
                        }
                    )

            # Get final response with tool results
            # Add explicit assistant summary messages
            try:
                combined = []
                for tr in tool_results:
                    s = self._summarize_tool_result(tr)
                    if s:
                        combined.append(s)
                if combined:
                    assistant_summary = "TOOL RESULTS SUMMARY:\n\n" + "\n\n".join(combined) + "\n\nPlease use the summary above to craft a complete, professional, and self-contained response to the user."
                    messages.append({"role": "assistant", "content": assistant_summary})
            except Exception:
                pass

            # Get final response with tool results
            try:
                final_response = ollama.chat(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "top_p": top_p,
                    },
                )
                final_message = final_response.get("message") if isinstance(final_response, dict) else getattr(final_response, 'message', None)
                if not final_message:
                    logger.error(f"Ollama final response message is None: {final_response}")
                    return {
                        "response": "I apologize, but I encountered an error processing the tool results. Please try again.",
                        "tools_used": tools_used,
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                    }
                response_text = final_message.content
            except Exception as e:
                logger.error(f"Ollama final response error: {e}")
                return {
                    "response": "I apologize, but I encountered an error processing the tool results. Please try again.",
                    "tools_used": tools_used,
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                }
        else:
            # Direct response, no tools
            try:
                response_text = message_obj.content
            except (TypeError, KeyError, AttributeError) as e:
                logger.error(f"Invalid response structure: {response}, error: {e}")
                return {
                    "response": "I apologize, but I received an invalid response from the AI service. Please try again.",
                    "tools_used": tools_used,
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                }

        # Clean response
        response_text = self._clean_response(response_text)

        return {
            "response": response_text or "I apologize, but I couldn't generate a response.",
            "tools_used": tools_used,
            "tokens_used": 0,  # Ollama doesn't provide token counts
            "cost_estimate": 0.0,  # Local model, no cost
        }

    def _clean_response(self, content: str) -> str:
        """
        Clean response content from Ollama while preserving markdown structure.

        Removes code markers and unwanted formatting.
        """
        if not content:
            return ""

        import re

        # CRITICAL: Remove any leaked tool call syntax or internal function calls
        # Remove JSON-like function call patterns
        content = re.sub(r'\{"type":\s*"function".*?\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\{"name":\s*".*?".*?\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\{"parameters":\s*\{.*?\}\}', '', content, flags=re.DOTALL)
        
        # Remove function call syntax like (city="Gulu")
        content = re.sub(r'\(\w+="[^"]*"\)', '', content)
        
        # Remove any remaining JSON objects that look like tool calls
        content = re.sub(r'\{[^}]*"type"[^}]*"function"[^}]*\}', '', content, flags=re.DOTALL)
        
        # Remove raw JSON data that might leak from tool results
        content = re.sub(r'\{[^}]*"code"[^}]*\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"id"[^}]*\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"name"[^}]*\}', '', content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"location"[^}]*\}', '', content, flags=re.DOTALL)
        
        # Remove escaped JSON
        content = re.sub(r'\\"[^"]*\\":', '', content)
        content = re.sub(r'\\n', ' ', content)
        
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

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a short human-readable summary for common tool results (AirQo)."""
        try:
            if not isinstance(result, dict):
                return ""

            if result.get("success") and result.get("measurements"):
                measurements = result.get("measurements", [])
                if measurements:
                    m = measurements[0]
                    site = m.get("siteDetails") or {}
                    site_name = site.get("name") or site.get("formatted_name") or result.get("search_location") or "Unknown site"
                    site_id = m.get("site_id") or site.get("site_id") or "Unknown"
                    time = m.get("time") or m.get("timestamp") or "Unknown time"
                    pm25 = m.get("pm2_5", {})
                    pm10 = m.get("pm10", {})
                    aqi = m.get("aqi") or m.get("pm2_5", {}).get("aqi") or m.get("aqi_category")

                    summary_lines = [f"# Air Quality — {site_name}", ""]
                    summary_lines.append(f"**Site ID**: {site_id} — **Time**: {time}")
                    if isinstance(pm25, dict):
                        summary_lines.append(f"- PM2.5: {pm25.get('value', 'N/A')} µg/m³ (AQI: {pm25.get('aqi', 'N/A')})")
                    if isinstance(pm10, dict):
                        summary_lines.append(f"- PM10: {pm10.get('value', 'N/A')} µg/m³ (AQI: {pm10.get('aqi', 'N/A')})")
                    if aqi:
                        summary_lines.append(f"- Overall AQI/Category: {aqi}")

                    return "\n".join(summary_lines)

            top_keys = list(result.keys())[:4]
            if top_keys:
                return f"Result keys: {', '.join(top_keys)}"
        except Exception:
            pass
        return ""
