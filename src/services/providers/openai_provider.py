"""
OpenAI-compatible Provider Implementation.

Handles OpenAI, DeepSeek, Kimi, and OpenRouter provider setup and message processing.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import openai

from ..tool_definitions import openai_tools
from .base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """OpenAI-compatible AI provider implementation."""

    def setup(self) -> None:
        """
        Set up OpenAI client and tools.

        Raises:
            ValueError: If API key is missing
            ConnectionError: If unable to initialize client
        """
        api_key = self.settings.AI_API_KEY
        base_url = self.settings.OPENAI_BASE_URL

        if not api_key:
            raise ValueError("AI_API_KEY is required for OpenAI provider")

        try:
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
            logger.info(
                f"Initialized OpenAI provider with model: {self.settings.AI_MODEL}, base_url: {base_url}"
            )
        except Exception as e:
            logger.error(f"Failed to setup OpenAI: {e}")
            raise ConnectionError(f"Failed to initialize OpenAI client: {e}") from e

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get OpenAI tool definitions.

        Returns:
            List of tool dictionaries for OpenAI
        """
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
        Process a message with OpenAI.

        Args:
            message: User message
            history: Conversation history
            system_instruction: System instruction/prompt
            temperature: Response temperature
            top_p: Response top_p
            top_k: Top-k sampling (ignored for OpenAI)
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with response and tools_used
        """
        if not self.client:
            return {
                "response": "OpenAI client not initialized.",
                "tools_used": [],
            }

        # Build messages
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})
        
        # Debug: Log if documents are in system instruction
        if "UPLOADED DOCUMENTS" in system_instruction:
            doc_section_start = system_instruction.find("=== UPLOADED DOCUMENTS ===")
            doc_section_end = system_instruction.find("=== END DOCUMENTS ===")
            if doc_section_start >= 0 and doc_section_end >= 0:
                doc_section_length = doc_section_end - doc_section_start
                logger.info(f"✅ Document section present in system instruction ({doc_section_length} chars)")
            else:
                logger.warning("⚠️ Document markers found but section incomplete")
        
        tools_used: list[str] = []

        # Retry configuration for network resilience
        max_retries = 3
        base_delay = 1  # seconds
        response = None  # Initialize response to prevent NoneType errors
        
        for attempt in range(max_retries):
            try:
                # Create completion
                # Use higher max_tokens when tools are available (responses tend to be longer)
                effective_max_tokens = max_tokens if max_tokens is not None else (self.settings.AI_MAX_TOKENS * 3 if self.get_tool_definitions() else self.settings.AI_MAX_TOKENS)
                
                response = self.client.chat.completions.create(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    tools=self.get_tool_definitions(),
                    tool_choice="auto",
                    max_tokens=effective_max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                break  # Success, exit retry loop
            except openai.APIConnectionError as e:
                logger.error(f"API connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    import time
                    time.sleep(delay)
                else:
                    return {
                        "response": "I'm having trouble connecting to the AI service. Please check your internet connection and try again in a moment.",
                        "tools_used": [],
                    }
            except openai.APITimeoutError as e:
                logger.error(f"API timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import time
                    time.sleep(delay)
                else:
                    return {
                        "response": "The AI service is taking too long to respond. Please try again with a simpler question or check back in a moment.",
                        "tools_used": [],
                    }
            except openai.RateLimitError as e:
                # Extract detailed rate limit information for monitoring
                error_details = {
                    "provider": "openai",
                    "error_type": "rate_limit",
                    "timestamp": datetime.now().isoformat(),
                    "model": self.settings.AI_MODEL,
                    "error_message": str(e),
                }

                # Try to extract rate limit details from error
                if hasattr(e, 'headers') and e.headers:
                    error_details.update({
                        "x_ratelimit_limit_requests": e.headers.get("x-ratelimit-limit-requests"),
                        "x_ratelimit_limit_tokens": e.headers.get("x-ratelimit-limit-tokens"),
                        "x_ratelimit_remaining_requests": e.headers.get("x-ratelimit-remaining-requests"),
                        "x_ratelimit_remaining_tokens": e.headers.get("x-ratelimit-remaining-tokens"),
                        "x_ratelimit_reset_requests": e.headers.get("x-ratelimit-reset-requests"),
                        "x_ratelimit_reset_tokens": e.headers.get("x-ratelimit-reset-tokens"),
                    })

                # Log structured rate limit information
                logger.warning("🚨 OPENAI RATE LIMIT EXCEEDED", extra=error_details)

                # Return user-friendly response with rate limit info
                reset_time = None
                if hasattr(e, 'headers') and e.headers:
                    reset_requests = e.headers.get("x-ratelimit-reset-requests")
                    reset_tokens = e.headers.get("x-ratelimit-reset-tokens")
                    if reset_requests or reset_tokens:
                        reset_time = reset_requests or reset_tokens

                response_msg = "Aeris is currently experiencing high demand. Please wait a moment and try again."
                if reset_time:
                    response_msg += f" Expected reset in approximately {reset_time}."

                return {
                    "response": response_msg,
                    "tools_used": [],
                    "rate_limit_info": error_details,  # Include for debugging
                }
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import time
                    time.sleep(delay)
                else:
                    return {
                        "response": f"I encountered an unexpected error: {str(e)}. Please try again.",
                        "tools_used": [],
                    }

        # Validate response before accessing
        if response is None:
            logger.error("Response is None after retry loop - all attempts failed")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "tools_used": [],
            }
        
        if not hasattr(response, 'choices') or not response.choices:
            logger.error("Response missing choices attribute or choices is empty")
            return {
                "response": "I apologize, but I received an invalid response. Please try again.",
                "tools_used": [],
            }

        # Handle tool calls
        if response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls

            # Safety: Limit concurrent tools
            MAX_CONCURRENT = 5
            if len(tool_calls) > MAX_CONCURRENT:
                logger.warning(f"Limiting {len(tool_calls)} tool calls to {MAX_CONCURRENT}")
                tool_calls = tool_calls[:MAX_CONCURRENT]

            # Deduplicate
            tool_calls = self._deduplicate_calls(tool_calls)

            # Execute tools
            tool_results = await self._execute_tools(tool_calls, tools_used)

            # Add assistant message with tool calls
            assistant_msg = response.choices[0].message
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else str(tc.function.arguments),
                            },
                        }
                        for tc in assistant_msg.tool_calls
                    ],
                }
            )

            # Add tool results
            for tool_result in tool_results:
                # Attach raw tool output
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_result["tool_call"].id),
                        "content": json.dumps({"result": tool_result["result"]}),
                    }
                )

                # Also attach a short human-readable summary to help the model
                summary = self._summarize_tool_result(tool_result.get("result"))
                if summary:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": str(tool_result["tool_call"].id) + "_summary",
                            "content": json.dumps({"summary": summary}),
                        }
                    )

            # Get final response with retry logic
            # Before finalizing, add an explicit assistant message that summarizes
            # the tool results (human-readable). This gives the model a concrete
            # formatted snippet to expand into a full user-facing reply.
            combined_summaries = []
            for tr in tool_results:
                s = self._summarize_tool_result(tr.get("result"))
                if s:
                    combined_summaries.append(s)

            if combined_summaries:
                assistant_summary = "\n\n".join(combined_summaries)
                assistant_summary = (
                    "TOOL RESULTS SUMMARY:\n\n" + assistant_summary + "\n\n"
                    "Please use the summary above to craft a complete, professional, and self-contained response to the user."
                )
                messages.append({"role": "assistant", "content": assistant_summary})

            for attempt in range(3):  # 3 attempts
                try:
                    final_response = self.client.chat.completions.create(
                        model=self.settings.AI_MODEL,
                        messages=messages,
                        max_tokens=effective_max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                    )
                    response_text = final_response.choices[0].message.content
                    finish_reason = final_response.choices[0].finish_reason
                    logger.info(
                        f"Final response received. Length: {len(response_text) if response_text else 0}, Finish reason: {finish_reason}"
                    )
                    
                    # Check if response was truncated due to length limit
                    if finish_reason == "length":
                        logger.warning("Response was truncated due to max_tokens limit")
                        response_text += "\n\n*Response was truncated due to length limits. Please ask for more specific information or break your question into smaller parts.*"
                    
                    response_text = self._clean_response(response_text)
                    break  # Success, exit retry loop
                except (openai.APIConnectionError, openai.APITimeoutError) as e:
                    logger.error(f"Final API call error (attempt {attempt + 1}/3): {e}")
                    if attempt < 2:
                        import time
                        time.sleep(1 * (2 ** attempt))  # Exponential backoff
                    else:
                        return {
                            "response": "I successfully gathered the information but encountered a network error generating the response. Please try asking again.",
                            "tools_used": tools_used,
                        }
                except Exception as e:
                    logger.error(f"Final API call failed: {e}")
                    return {
                        "response": f"I executed the tools successfully but encountered an error generating the final response: {str(e)}",
                        "tools_used": tools_used,
                    }
        else:
            response_text = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            logger.info(
                f"Direct response (no tools). Length: {len(response_text) if response_text else 0}, Finish reason: {finish_reason}"
            )
            
            # Check if response was truncated due to length limit
            if finish_reason == "length":
                logger.warning("Response was truncated due to max_tokens limit")
                response_text += "\n\n*Response was truncated due to length limits. Please ask for more specific information or break your question into smaller parts.*"
            
            response_text = self._clean_response(response_text)

        # Handle empty or very short responses
        if not response_text or not response_text.strip() or len(response_text.strip()) < 20:
            logger.warning(f"OpenAI returned empty or very short response (length: {len(response_text) if response_text else 0}). Tools used: {tools_used}")
            
            # Check if tools were called but response is still short
            if tools_used:
                response_text = (
                    "I retrieved the data successfully, but encountered an issue formatting the response. "
                    "Let me provide you with the key information:\n\n"
                    "The data was fetched, but I need you to ask your question again, and I'll provide a complete, detailed response with air quality metrics, health implications, and recommendations."
                )
            else:
                response_text = await self._generate_fallback(message)

        return {
            "response": response_text or "I apologize, but I couldn't generate a response. Please try again.",
            "tools_used": tools_used,
        }

    def _deduplicate_calls(self, tool_calls: list) -> list:
        """Remove duplicate tool calls."""
        seen = set()
        unique = []
        for tc in tool_calls:
            key = f"{tc.function.name}_{tc.function.arguments}"
            if key not in seen:
                seen.add(key)
                unique.append(tc)
            else:
                logger.info(f"Skipping duplicate tool call: {tc.function.name}")
        return unique

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a short human-readable summary for common tool results.

        Currently focuses on AirQo measurement payloads so the assistant
        always has a clear, formatted snippet to include in the final reply.
        """
        try:
            if not isinstance(result, dict):
                return ""  # Nothing to summarize

            # AirQo-style response with measurements
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

            # Generic fallbacks
            if "data" in result and isinstance(result["data"], dict):
                keys = list(result["data"].keys())[:3]
                return f"Returned data keys: {', '.join(keys)}"

            # For other dicts, show top-level keys
            top_keys = list(result.keys())[:4]
            if top_keys:
                return f"Result keys: {', '.join(top_keys)}"

        except Exception:
            pass

        return ""

    async def _execute_tools(
        self, tool_calls: list, tools_used: list
    ) -> list[dict[str, Any]]:
        """Execute tool calls in parallel with timeout protection."""

        async def execute_single(tool_call):
            """Execute a single tool call."""
            function_name = tool_call.function.name

            try:
                if isinstance(tool_call.function.arguments, str):
                    function_args = json.loads(tool_call.function.arguments)
                elif isinstance(tool_call.function.arguments, dict):
                    function_args = tool_call.function.arguments
                else:
                    function_args = {}
                    logger.warning(f"Unexpected arguments type: {type(tool_call.function.arguments)}")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing tool arguments: {e}")
                function_args = {}

            tools_used.append(function_name)
            logger.info(f"OpenAI requested tool: {function_name} with args: {function_args}")

            try:
                task = asyncio.create_task(
                    self.tool_executor.execute_async(function_name, function_args)
                )
                result = await asyncio.wait_for(task, timeout=30.0)
            except TimeoutError:
                logger.error(f"Tool {function_name} timed out")
                result = {"error": f"Tool {function_name} timed out"}
            except Exception as e:
                logger.error(f"Tool {function_name} failed: {e}")
                result = {"error": f"Tool execution failed: {str(e)}"}

            if isinstance(result, dict) and "error" in result:
                logger.warning(f"Tool {function_name} failed: {result['error']}")
                result = {
                    "error": result["error"],
                    "message": f"The tool '{function_name}' encountered an error. Please provide an informative response explaining what went wrong and suggest alternatives.",
                }

            return {"tool_call": tool_call, "result": result}

        # Execute with semaphore
        MAX_CONCURRENT = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def execute_with_semaphore(tc):
            async with semaphore:
                return await execute_single(tc)

        try:
            tasks = [execute_with_semaphore(tc) for tc in tool_calls]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to proper result format
            results: list[dict[str, Any]] = []
            for i, result in enumerate(raw_results):
                if isinstance(result, Exception):
                    logger.error(f"Tool execution exception: {result}")
                    results.append({
                        "tool_call": tool_calls[i],
                        "result": {"error": f"Tool execution failed: {str(result)}"},
                    })
                else:
                    results.append(result)  # type: ignore
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            results = [
                {"tool_call": tc, "result": {"error": "Parallel execution failed"}}
                for tc in tool_calls
            ]

        return results

    def _clean_response(self, content: str) -> str:
        """Clean response content while preserving markdown structure."""
        if not content:
            return ""

        import re

        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)

        # Remove code markers ONLY if they're not part of proper code blocks
        # Keep proper code blocks intact
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
                    # Starting a table - ensure blank line before if previous line has content
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
                    if not prev_was_list:  # Don't add space if previous was a list
                        cleaned_lines.append('')
                
                cleaned_lines.append(line)
                prev_was_header = is_header
                prev_was_list = is_list

        content = '\n'.join(cleaned_lines)

        # Ensure proper spacing in tables
        content = re.sub(r'\|([^|\n]*?)\|', r'| \1 |', content)
        content = re.sub(r'\| +\|', r'| |', content)

        return content.strip()

    async def _generate_fallback(self, original_message: str) -> str:
        """Generate fallback response when primary response is empty."""
        try:
            fallback_prompt = f"""The user asked: "{original_message}"

I attempted to get information using available tools, but the response was empty or incomplete.

Please provide a helpful response that:
1. Acknowledges the user question
2. Explains that the specific data they requested may not be available at the moment
3. Suggests alternative approaches or locations they could try
4. Offers to help with related questions

Be professional, empathetic, and solution-oriented."""

            response = self.client.chat.completions.create(
                model=self.settings.AI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional air quality and environmental health consultant. When data is unavailable, provide helpful alternatives and maintain a positive, solution-oriented tone.",
                    },
                    {"role": "user", "content": fallback_prompt},
                ],
                max_tokens=self.settings.AI_MAX_TOKENS,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Fallback generation failed: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again in a moment."
