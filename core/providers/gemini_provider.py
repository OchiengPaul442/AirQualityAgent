"""
Gemini AI Provider Implementation.

Handles Gemini-specific setup and message processing with tool calling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

from core.tools.definitions import gemini_tools
from shared.utils.markdown_formatter import MarkdownFormatter

from .base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider implementation."""

    def setup(self) -> None:
        """
        Set up Gemini client and tools.

        Raises:
            ValueError: If API key is missing
            ConnectionError: If unable to initialize Gemini client
        """
        api_key = self.settings.AI_API_KEY
        if not api_key:
            raise ValueError("AI_API_KEY is required for Gemini provider")

        try:
            self.client = genai.Client(api_key=api_key)
            logger.info(f"Initialized Gemini provider with model: {self.settings.AI_MODEL}")
        except Exception as e:
            logger.error(f"Failed to setup Gemini: {e}")
            raise ConnectionError(f"Failed to initialize Gemini client: {e}") from e

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        Sanitize text to handle problematic Unicode characters that cause UTF-8 encoding errors.

        This fixes the 'surrogates not allowed' error by:
        1. Encoding to UTF-8 with error handling
        2. Decoding back to string
        3. Replacing unpaired surrogates with safe characters

        Args:
            text: Text that may contain problematic Unicode

        Returns:
            Sanitized text safe for UTF-8 encoding
        """
        if not text:
            return text

        try:
            # Try to encode/decode to catch problematic characters
            # Use 'surrogatepass' to handle unpaired surrogates, then replace them
            encoded = text.encode("utf-8", errors="surrogatepass")
            return encoded.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Text sanitization fallback used: {e}")
            # Fallback: remove any characters that can't be encoded
            return text.encode("utf-8", errors="ignore").decode("utf-8")

    def get_tool_definitions(self) -> list[types.Tool]:
        """
        Get Gemini tool definitions.

        Returns:
            List of Tool objects for Gemini
        """
        return gemini_tools.get_all_tools()

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
        Process a message with Gemini and show reasoning process.

        Args:
            message: User message
            history: Conversation history
            system_instruction: System instruction/prompt
            temperature: Response temperature
            top_p: Response top_p
            top_k: Top-k sampling parameter
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with response, tools_used, and reasoning_steps
        """
        if not self.client:
            return {
                "response": "Gemini client not initialized.",
                "tools_used": [],
            }

        # Sanitize all text inputs to prevent UTF-8 encoding errors
        system_instruction = self._sanitize_text(system_instruction)
        message = self._sanitize_text(message)

        # Initialize simple reasoning tracker (optional feature)
        class SimpleReasoning:
            def __init__(self):
                self.steps = []
            def add_step(self, title, description, step_type):
                self.steps.append({"title": title, "description": description, "type": step_type})
            def get_all_steps(self):
                return self.steps

        reasoning = SimpleReasoning()

        # Convert history to Gemini format
        chat_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            sanitized_content = self._sanitize_text(msg.get("content", ""))
            chat_history.append(
                types.Content(role=role, parts=[types.Part(text=sanitized_content)])
            )

        # Get tools only for supported models
        tools = None
        if self.settings.AI_MODEL in [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-pro",
        ]:
            tools = self.get_tool_definitions()
            if tools:
                tool_names = [
                    t.function_declarations[0].name for t in tools if t.function_declarations
                ]
                reasoning.add_step(
                    "Tools Available",
                    f"I have access to {len(tool_names)} tools for data retrieval",
                    "planning",
                )

        # Create chat session
        config_params = {
            "tools": tools,  # type: ignore
            "system_instruction": system_instruction,
            "temperature": temperature,
            "top_p": top_p,
        }

        # Add optional parameters if provided
        if top_k is not None:
            config_params["top_k"] = top_k

        # Use max_tokens directly - DO NOT multiply
        effective_max_tokens = max_tokens if max_tokens is not None else self.settings.AI_MAX_TOKENS
        if effective_max_tokens is not None:
            config_params["max_output_tokens"] = effective_max_tokens

        # Retry configuration for network resilience
        max_retries = 3
        base_delay = 1
        response = None
        chat = None

        reasoning.add_step(
            "Initiating Communication",
            "Connecting to Gemini AI to process your request",
            "executing",
        )

        for attempt in range(max_retries):
            try:
                chat = self.client.chats.create(
                    model=self.settings.AI_MODEL,
                    config=types.GenerateContentConfig(**config_params),
                    history=chat_history,
                )

                # Send message
                response = chat.send_message(message)
                reasoning.add_step(
                    "Response Received",
                    "Successfully received response from AI model",
                    "validating",
                )
                break  # Success, exit retry loop
            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}")

                # Check for token limit errors
                if (
                    "token" in error_msg
                    and ("limit" in error_msg or "maximum" in error_msg or "exceed" in error_msg)
                ) or "context length" in error_msg:
                    logger.warning("⚠️ Token limit exceeded. Attempting intelligent truncation...")

                    # Convert messages back to dict format for truncation
                    messages_dict = [{"role": "system", "content": system_instruction}]
                    for msg in chat_history:
                        messages_dict.append(
                            {
                                "role": "user" if msg.role == "user" else "assistant",
                                "content": msg.parts[0].text if msg.parts else "",
                            }
                        )
                    messages_dict.append({"role": "user", "content": message})

                    # Truncate
                    truncated = self._truncate_context_intelligently(
                        messages_dict, system_instruction
                    )

                    # Convert back to Gemini format
                    chat_history = []
                    for msg in truncated[1:-1]:  # Skip system and current user message
                        role = "user" if msg["role"] == "user" else "model"
                        chat_history.append(
                            types.Content(
                                role=role, parts=[types.Part(text=msg.get("content", ""))]
                            )
                        )

                    # Retry with truncated context
                    try:
                        logger.info(
                            f"Retrying with truncated context ({len(chat_history)} messages)..."
                        )
                        chat = self.client.chats.create(
                            model=self.settings.AI_MODEL,
                            config=types.GenerateContentConfig(**config_params),
                            history=chat_history,
                        )
                        response = chat.send_message(message)
                        logger.info("✅ Successfully processed with truncated context")
                        break  # Success, exit retry loop
                    except Exception as retry_error:
                        logger.error(f"Truncation retry failed: {retry_error}")
                        return {
                            "response": (
                                "I apologize, but the conversation has become too long for my current context window. "
                                "To continue, please start a new conversation or ask your question more concisely. "
                                "I can still help with air quality information - just phrase it in a shorter way."
                            ),
                            "tools_used": [],
                            "context_truncated": True,
                        }

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import time

                    time.sleep(delay)
                else:
                    error_msg = str(e)
                    if "connection" in error_msg.lower() or "network" in error_msg.lower():
                        return {
                            "response": "I'm having trouble connecting to the AI service. Please check your internet connection and try again.",
                            "tools_used": [],
                        }
                    elif "timeout" in error_msg.lower():
                        return {
                            "response": "The AI service is taking too long to respond. Please try again with a simpler question.",
                            "tools_used": [],
                        }
                    elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
                        # Extract detailed rate limit information for monitoring
                        error_details = {
                            "provider": "gemini",
                            "error_type": "rate_limit",
                            "timestamp": datetime.now().isoformat(),
                            "model": self.settings.AI_MODEL,
                            "error_message": error_msg,
                        }

                        # Try to extract quota information from error message
                        if "quota" in error_msg.lower():
                            error_details["quota_exceeded"] = True
                        if "rate" in error_msg.lower():
                            error_details["rate_limit_exceeded"] = True

                        # Log structured rate limit information
                        logger.warning("🚨 GEMINI RATE LIMIT EXCEEDED", extra=error_details)

                        return {
                            "response": "Aeris-AQ is currently experiencing high demand. Please wait a moment and try again.",
                            "tools_used": [],
                            "rate_limit_info": error_details,  # Include for debugging
                        }
                    else:
                        # Log the full error for developers but provide user-friendly message
                        logger.error(
                            f"Unexpected Gemini error (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        return {
                            "response": (
                                "I'm experiencing technical difficulties at the moment. "
                                "This is likely temporary. Please try again in a few moments or rephrase your question."
                            ),
                            "tools_used": [],
                            "error_logged": True,
                        }

        # Validate response before accessing
        if response is None:
            logger.error("Gemini response is None after retry loop - all attempts failed")
            return {
                "response": "I was unable to process your request. The AI service did not respond. Please try again.",
                "tools_used": [],
            }

        if chat is None:
            logger.error("Gemini chat is None - cannot continue")
            return {
                "response": "I was unable to create a chat session. Please try again.",
                "tools_used": [],
            }

        tools_used: list[str] = []

        # Handle function calls
        if tools and response.candidates and response.candidates[0].content.parts:
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if part.function_call
            ]

            if function_calls:
                # Add reasoning step for tool usage
                tool_names = [fc.name for fc in function_calls]
                reasoning.add_step(
                    "Calling Tools", f"Retrieving data using: {', '.join(tool_names)}", "executing"
                )

                # Safety: Limit concurrent functions
                MAX_CONCURRENT = 5
                if len(function_calls) > MAX_CONCURRENT:
                    logger.warning(
                        f"Limiting {len(function_calls)} function calls to {MAX_CONCURRENT}"
                    )
                    function_calls = function_calls[:MAX_CONCURRENT]

                # Deduplicate function calls
                function_calls = self._deduplicate_calls(function_calls)

                # Execute functions in parallel
                function_results = await self._execute_functions(function_calls, tools_used)

                # Record tool execution in reasoning
                for tool_name in tools_used:
                    reasoning.record_tool_execution(
                        tool_name, "success", "Data retrieved successfully"
                    )

                # Extract chart data if generate_chart was called
                chart_result = None
                for result in function_results:
                    if result["function_call"].name == "generate_chart":
                        chart_result = result["result"]
                        logger.info("📊 Chart generation detected in tool results")
                        break

                # Send function results back as text message
                function_results_text = "\n".join(
                    [
                        f"Function {result['function_call'].name} result: {result['result']}"
                        for result in function_results
                    ]
                )

                reasoning.add_step(
                    "Processing Retrieved Data",
                    "Analyzing and formatting the data for your response",
                    "processing",
                )

                response = chat.send_message(function_results_text)

        # Get final response text
        final_response = response.text if response.text else ""

        # Check if response was truncated
        if response.candidates and response.candidates[0].finish_reason:
            finish_reason = response.candidates[0].finish_reason
            logger.info(f"Gemini response finish reason: {finish_reason}")

            if finish_reason == "MAX_TOKENS":
                logger.warning("Gemini response reached max tokens - adding truncation notification")
                truncation_note = (
                    "\n\n---\n"
                    "**📝 Note**: This response was truncated due to length limits. To continue:\n"
                    "• Ask for specific sections\n"
                    "• Break your question into smaller parts\n"
                    "• Request a focused summary"
                )
                # Only add if not already present
                if "truncated due to length" not in final_response.lower():
                    final_response = final_response + truncation_note

        # Handle empty or very short responses
        if not final_response or not final_response.strip() or len(final_response.strip()) < 20:
            logger.warning(
                f"Gemini returned empty or very short response (length: {len(final_response) if final_response else 0}). Tools used: {tools_used}"
            )

            if tools_used:
                logger.info("Attempting to generate fallback response from tool results")
                try:
                    fallback_response = await self._generate_tool_based_response(
                        message, tools_used, history
                    )
                    if fallback_response and len(fallback_response.strip()) > 50:
                        final_response = fallback_response
                        logger.info("Successfully generated fallback response from tool results")
                    else:
                        final_response = (
                            "I retrieved air quality data for your query, but had trouble formatting the complete response. "
                            "The data shows current air quality information has been collected. "
                            "Please try asking about a specific city or location for detailed results."
                        )
                except Exception as fallback_error:
                    logger.error(f"Fallback response generation failed: {fallback_error}")
                    final_response = (
                        "I successfully retrieved air quality data, but encountered a formatting issue. "
                        "Please try your question again or specify a different location."
                    )
            else:
                final_response = (
                    "I apologize, but I wasn't able to retrieve the requested information at this time. "
                    "This could be due to data unavailability or connectivity issues. Please try:\n\n"
                    "1. Asking about a different location\n"
                    "2. Rephrasing your question\n"
                    "3. Checking back in a few moments\n\n"
                    "Is there anything else I can help you with?"
                )

        # Clean and format the response with proper markdown
        final_response = self._clean_response(final_response)
        final_response = MarkdownFormatter.format_response(final_response)

        # Validate response quality
        has_data = len(final_response) > 100 and any(
            indicator in final_response.lower()
            for indicator in ["aqi", "pm2.5", "pm10", "good", "moderate", "data"]
        )
        quality = "high" if has_data else "basic"
        reasoning.validate_response(quality, has_data)

        # Extract thinking steps if available
        thinking_steps = self._extract_thinking_steps(response)

        # Combine reasoning with thinking steps
        all_reasoning = reasoning.get_all_steps()

        # Prepend reasoning to response (collapsible format)
        reasoning_markdown = reasoning.to_compact_markdown()
        if reasoning_markdown:
            final_response = reasoning_markdown + "\n\n" + final_response

        result_data = {
            "response": final_response,
            "tools_used": tools_used,
            "thinking_steps": thinking_steps,
            "reasoning_steps": [step.to_dict() for step in all_reasoning],
            "reasoning_content": reasoning.to_markdown(include_header=False),
            "finish_reason": finish_reason if 'finish_reason' in locals() else "stop",  # Add finish_reason for consistency
        }

        # Add chart data if present
        if "chart_result" in locals() and chart_result:
            result_data["chart_result"] = chart_result
            logger.info("📊 Chart data added to response")

        return result_data

    def _extract_thinking_steps(self, response) -> list[str]:
        """
        Extract thinking/reasoning steps from Gemini response.

        Args:
            response: Gemini response object

        Returns:
            List of thinking steps
        """
        thinking_steps = []

        try:
            if not response or not response.candidates:
                return thinking_steps

            # Get the first candidate
            candidate = response.candidates[0]

            if not candidate.content or not candidate.content.parts:
                return thinking_steps

            # Extract thoughts from parts
            for part in candidate.content.parts:
                # Check for thought attribute
                if hasattr(part, "thought") and part.thought:
                    thinking_steps.append(str(part.text if part.text else part.thought))
                    logger.info("Extracted thinking step from Gemini thought part")

        except Exception as e:
            logger.debug(f"Failed to extract thinking steps from Gemini: {e}")

        return thinking_steps

    def _deduplicate_calls(self, function_calls: list) -> list:
        """Remove duplicate function calls."""
        seen = set()
        unique = []
        for fc in function_calls:
            key = f"{fc.name}_{fc.args}"
            if key not in seen:
                seen.add(key)
                unique.append(fc)
            else:
                logger.info(f"Skipping duplicate function call: {fc.name}")
        return unique

    async def _generate_tool_based_response(
        self, original_message: str, tools_used: list, history: list
    ) -> str:
        """Generate a response based on tool results when AI response is malformed."""
        try:
            # Check what tools were used and try to provide basic data
            tool_names = [tool for tool in tools_used if isinstance(tool, str)]

            # If air quality tools were used, try to get basic data
            if any("air_quality" in name or "city" in name for name in tool_names):
                # Extract city names from the original message
                cities = []
                message_lower = original_message.lower()

                # Common cities that might be in the query
                common_cities = [
                    "london",
                    "paris",
                    "new york",
                    "tokyo",
                    "beijing",
                    "mumbai",
                    "sydney",
                    "cairo",
                    "mexico city",
                    "sao paulo",
                ]
                for city in common_cities:
                    if city in message_lower:
                        cities.append(city.title())

                if cities:
                    response = f"I retrieved air quality data for {', '.join(cities)}. Here's a summary:\n\n"

                    for city in cities[:3]:  # Limit to 3 cities
                        response += f"**{city}**: Air quality data was retrieved successfully. For detailed AQI values, pollutant levels, and health recommendations, please try your question again.\n"

                    response += "\nFor more detailed information including health recommendations and pollutant breakdown, please try your question again."
                    return response

            # Generic fallback for other tool usage
            return f"I successfully retrieved data for your query about '{original_message}', but had trouble formatting the complete response. The information has been collected and is available. Please try asking again for the full details."

        except Exception as e:
            logger.error(f"Tool-based response generation failed: {e}")
            return ""

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a short human-readable summary for common tool results (AirQo focused)."""
        try:
            if not isinstance(result, dict):
                return ""

            # Handle scan_document results (file upload analysis)
            if result.get("success") and result.get("file_type") and result.get("content"):
                filename = result.get("filename", "document")
                file_type = result.get("file_type", "file")
                content = result.get("content", "")

                # Try to extract meaningful information from content
                if isinstance(content, str):
                    lines = content.split('\n')[:10]  # First 10 lines
                    preview = '\n'.join(lines)
                    summary = f"📄 Document '{filename}' ({file_type}) uploaded and scanned successfully!\n\nPreview:\n{preview}..."
                elif isinstance(content, dict):
                    # Structured data (CSV/Excel)
                    rows = content.get("rows", [])
                    headers = content.get("headers", [])
                    summary = f"Data file '{filename}' contains {len(rows)} rows with columns: {', '.join(headers[:5])}{'...' if len(headers) > 5 else ''}"
                else:
                    summary = f"📄 Document '{filename}' ({file_type}) processed successfully."

                return summary

            # Handle chart generation results
            if result.get("chart_data") and result.get("chart_type"):
                chart_type = result.get("chart_type", "chart")
                data_rows = result.get("data_rows", 0)
                original_rows = result.get("original_rows", data_rows)
                data_sampled = result.get("data_sampled", False)
                chart_data = result.get("chart_data", "")

                # CRITICAL: Embed chart in markdown response
                summary = f"{chart_type.title()} Chart Generated\n\n"
                summary += f"![{chart_type.title()} Chart]({chart_data})\n\n"
                summary += f"Chart created with {data_rows} data points"
                if data_sampled and original_rows > data_rows:
                    summary += f" (sampled from {original_rows} total rows for clarity)"
                summary += ".\n\nThe visualization above shows the data trends. Review it for key insights!"
                return summary

            if result.get("success") and result.get("measurements"):
                measurements = result.get("measurements", [])
                if measurements:
                    m = measurements[0]
                    site = m.get("siteDetails") or {}
                    site_name = (
                        site.get("name")
                        or site.get("formatted_name")
                        or result.get("search_location")
                        or "Unknown site"
                    )
                    site_id = m.get("site_id") or site.get("site_id") or "Unknown"
                    time = m.get("time") or m.get("timestamp") or "Unknown time"
                    pm25 = m.get("pm2_5", {})
                    pm10 = m.get("pm10", {})
                    aqi = m.get("aqi") or m.get("pm2_5", {}).get("aqi") or m.get("aqi_category")

                    summary_lines = [f"# Air Quality — {site_name}", ""]
                    # Removed site ID display for security
                    if isinstance(pm25, dict):
                        summary_lines.append(
                            f"- PM2.5: {pm25.get('value', 'N/A')} µg/m³ (AQI: {pm25.get('aqi', 'N/A')})"
                        )
                    if isinstance(pm10, dict):
                        summary_lines.append(
                            f"- PM10: {pm10.get('value', 'N/A')} µg/m³ (AQI: {pm10.get('aqi', 'N/A')})"
                        )
                    if aqi:
                        summary_lines.append(f"- Overall AQI/Category: {aqi}")

                    return "\n".join(summary_lines)

            # Try extracting WAQI data with new structure (pm25_ugm3/pm10_ugm3)
            if "pm25_ugm3" in result or "pm10_ugm3" in result or "overall_aqi" in result:
                city = result.get("city_name", "Unknown city")
                aqi = result.get("overall_aqi", "N/A")
                pm25_conc = result.get("pm25_ugm3")
                pm10_conc = result.get("pm10_ugm3")
                time = result.get("timestamp", "Unknown time")
                dominant = result.get("dominant_pollutant", "")

                summary_lines = [
                    f"# Air Quality — {city}",
                    "",
                    f"- Overall AQI: {aqi}" + (f" (Dominant: {dominant})" if dominant else ""),
                ]
                
                if pm25_conc is not None:
                    summary_lines.append(f"- PM2.5: {pm25_conc} µg/m³")
                if pm10_conc is not None:
                    summary_lines.append(f"- PM10: {pm10_conc} µg/m³")
                    
                summary_lines.append(f"- Time: {time}")

                return "\n".join(summary_lines)

            top_keys = list(result.keys())[:4]
            if top_keys:
                return f"Result keys: {', '.join(top_keys)}"
        except Exception:
            pass
        return ""

    async def _execute_functions(
        self, function_calls: list, tools_used: list
    ) -> list[dict[str, Any]]:
        """
        Execute function calls in parallel with timeout protection.

        Args:
            function_calls: List of function calls to execute
            tools_used: List to append executed tool names to

        Returns:
            List of function execution results
        """

        async def execute_single(function_call):
            """Execute a single function call with timeout."""
            function_name = function_call.name
            function_args = function_call.args

            tools_used.append(function_name)
            logger.info(f"Gemini requested tool: {function_name}")

            try:
                # Execute with 30-second timeout
                task = asyncio.create_task(
                    self.tool_executor.execute_async(function_name, function_args)
                )
                result = await asyncio.wait_for(task, timeout=30.0)
            except TimeoutError:
                logger.error(f"Function {function_name} timed out")
                result = {"error": f"Function {function_name} timed out"}
            except Exception as e:
                logger.error(f"Function {function_name} failed: {e}")
                result = {"error": f"Function execution failed: {str(e)}"}

            # Handle errors gracefully
            if isinstance(result, dict) and "error" in result:
                logger.warning(f"Tool {function_name} failed: {result['error']}")
                result = {
                    "error": result["error"],
                    "message": f"The tool '{function_name}' encountered an error. Please provide an informative response explaining what went wrong and suggest alternatives.",
                }

            return {"function_call": function_call, "result": result}

        # Execute with semaphore to limit concurrency
        MAX_CONCURRENT = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def execute_with_semaphore(fc):
            async with semaphore:
                return await execute_single(fc)

        try:
            tasks = [execute_with_semaphore(fc) for fc in function_calls]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to proper result format
            results: list[dict[str, Any]] = []
            for i, result in enumerate(raw_results):
                if isinstance(result, Exception):
                    logger.error(f"Function execution exception: {result}")
                    results.append(
                        {
                            "function_call": function_calls[i],
                            "result": {"error": f"Function execution failed: {str(result)}"},
                        }
                    )
                else:
                    results.append(result)  # type: ignore
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            results = [
                {"function_call": fc, "result": {"error": "Parallel execution failed"}}
                for fc in function_calls
            ]

        return results

    def _clean_response(self, content: str) -> str:
        """Clean response content while preserving markdown structure."""
        if not content:
            return ""

        import re

        # CRITICAL: Remove any leaked tool call syntax or internal function calls
        # Remove JSON-like function call patterns
        content = re.sub(r'\{"type":\s*"function".*?\}', "", content, flags=re.DOTALL)
        content = re.sub(r'\{"name":\s*".*?".*?\}', "", content, flags=re.DOTALL)
        content = re.sub(r'\{"parameters":\s*\{.*?\}\}', "", content, flags=re.DOTALL)

        # Remove function call syntax like (city="Gulu")
        content = re.sub(r'\(\w+="[^"]*"\)', "", content)

        # Remove any remaining JSON objects that look like tool calls
        content = re.sub(r'\{[^}]*"type"[^}]*"function"[^}]*\}', "", content, flags=re.DOTALL)

        # Remove raw JSON data that might leak from tool results
        content = re.sub(r'\{[^}]*"code"[^}]*\}', "", content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"id"[^}]*\}', "", content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"name"[^}]*\}', "", content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"location"[^}]*\}', "", content, flags=re.DOTALL)

        # Remove escaped JSON
        content = re.sub(r'\\"[^"]*\\":', "", content)
        content = re.sub(r"\\n", " ", content)

        # Remove HTML tags
        content = re.sub(r"<[^>]+>", "", content)

        # Remove code markers ONLY if they're not part of proper code blocks
        unwanted_patterns = [
            "```markdown\n",
            "```md\n",
            "```text\n",
        ]

        for pattern in unwanted_patterns:
            content = content.replace(pattern, "```\n")

        # Ensure proper spacing after markdown elements
        lines = content.split("\n")
        cleaned_lines = []
        prev_was_header = False
        prev_was_list = False
        in_table = False
        table_header_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for headers
            is_header = stripped.startswith("#") and " " in stripped[:7]

            # Check for list items
            is_list = bool(re.match(r"^[\s]*[-*+]\s", line) or re.match(r"^[\s]*\d+\.\s", line))

            # Check if this is a table row
            is_table_row = "|" in stripped and stripped.startswith("|") and stripped.endswith("|")

            if is_table_row:
                if not in_table:
                    # Starting a table - ensure blank line before
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append("")
                    in_table = True
                    table_header_count = stripped.count("|") - 1
                    cleaned_lines.append(line)
                else:
                    current_count = stripped.count("|") - 1
                    if current_count == table_header_count:
                        cleaned_lines.append(line)
                    else:
                        logger.warning(f"Skipping malformed table row: {stripped}")
                        continue
            else:
                if in_table and stripped:
                    # End of table - ensure blank line after
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append("")
                    in_table = False

                # Ensure proper spacing after headers
                if prev_was_header and stripped and not is_header:
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append("")

                # Ensure proper spacing before headers
                if is_header and cleaned_lines and cleaned_lines[-1].strip():
                    if not prev_was_list:
                        cleaned_lines.append("")

                cleaned_lines.append(line)
                prev_was_header = is_header
                prev_was_list = is_list

        content = "\n".join(cleaned_lines)

        # Ensure proper spacing in tables
        content = re.sub(r"\|([^|\n]*?)\|", r"| \1 |", content)
        content = re.sub(r"\| +\|", r"| |", content)

        return content.strip()
