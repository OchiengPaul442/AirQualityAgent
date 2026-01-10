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

from src.utils.result_formatters import format_tool_result_as_json

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

        # Sanitize all text inputs to prevent UTF-8 encoding errors
        system_instruction = self._sanitize_text(system_instruction)
        message = self._sanitize_text(message)

        # Build messages
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]
        for msg in history:
            sanitized_content = self._sanitize_text(msg.get("content", ""))
            messages.append({"role": msg["role"], "content": sanitized_content})
        messages.append({"role": "user", "content": message})

        # Debug: Log if documents are in system instruction
        if "UPLOADED DOCUMENTS" in system_instruction:
            doc_section_start = system_instruction.find("=== UPLOADED DOCUMENTS ===")
            doc_section_end = system_instruction.find("=== END DOCUMENTS ===")
            if doc_section_start >= 0 and doc_section_end >= 0:
                doc_section_length = doc_section_end - doc_section_start
                logger.info(
                    f"✅ Document section present in system instruction ({doc_section_length} chars)"
                )
            else:
                logger.warning("⚠️ Document markers found but section incomplete")

        tools_used: list[str] = []

        # FORCE TOOL CALLING for search/scraping/air quality queries
        force_search_tool = self._should_force_search_tool(message.lower())
        force_scrape_tool = self._should_force_scrape_tool(message.lower())
        force_air_quality_tool, cities_to_query = self._should_force_air_quality_tool(
            message.lower()
        )

        if force_search_tool:
            logger.info("FORCING search_web tool call for query")
            # Add a fake tool call to force the model to use search
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "forced_search_call",
                            "type": "function",
                            "function": {
                                "name": "search_web",
                                "arguments": '{"query": "current air quality regulations and policies 2025"}',
                            },
                        }
                    ],
                }
            )
            # Add fake tool result
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "forced_search_call",
                    "content": "Search results will be provided by the system.",
                }
            )
            tools_used.append("search_web")

        if force_scrape_tool:
            logger.info("FORCING scrape_website tool call for query")
            # Extract URL from message
            import re

            url_match = re.search(r"https?://[^\s]+", message)
            if url_match:
                url = url_match.group(0)
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "forced_scrape_call",
                                "type": "function",
                                "function": {
                                    "name": "scrape_website",
                                    "arguments": f'{{"url": "{url}"}}',
                                },
                            }
                        ],
                    }
                )
                # Add fake tool result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": "forced_scrape_call",
                        "content": "Website content will be extracted by the system.",
                    }
                )
                tools_used.append("scrape_website")

        if force_air_quality_tool and cities_to_query:
            logger.info(f"FORCING air quality tool calls for cities: {cities_to_query}")
            tool_calls = []

            # Create separate tool calls for each city (services work one at a time)
            call_id = 0

            # Simple classification for tool selection
            known_african_cities = [
                "kampala",
                "nairobi",
                "jinja",
                "gulu",
                "dar es salaam",
                "kigali",
                "mbale",
                "nakasero",
                "mombasa",
                "kisumu",
                "nakuru",
                "eldoret",
                "dodoma",
                "mwanza",
                "arusha",
                "mbeya",
                "butare",
                "musanze",
                "ruhengeri",
                "gisenyi",
                "mbarara",
            ]

            for city in cities_to_query:
                city_lower = city.lower()
                import json

                # Choose appropriate tool based on city
                if (
                    any(african_city in city_lower for african_city in known_african_cities)
                    or "africa" in city_lower
                ):
                    tool_calls.append(
                        {
                            "id": f"forced_aq_call_{call_id}",
                            "type": "function",
                            "function": {
                                "name": "get_african_city_air_quality",
                                "arguments": json.dumps({"city": city}),
                            },
                        }
                    )
                else:
                    tool_calls.append(
                        {
                            "id": f"forced_aq_call_{call_id}",
                            "type": "function",
                            "function": {
                                "name": "get_city_air_quality",
                                "arguments": json.dumps({"city": city}),
                            },
                        }
                    )
                call_id += 1

            # Add the tool calls to messages
            if tool_calls:
                messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

                # Add fake tool results
                for tc in tool_calls:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": "Air quality data will be retrieved by the system.",
                        }
                    )
                    tools_used.append(tc["function"]["name"])
            logger.info("FORCING search_web tool call for query")
            # Add a fake tool call to force the model to use search
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "forced_search_call",
                            "type": "function",
                            "function": {
                                "name": "search_web",
                                "arguments": '{"query": "current air quality regulations and policies 2025"}',
                            },
                        }
                    ],
                }
            )
            # Add fake tool result
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "forced_search_call",
                    "content": "Search results will be provided by the system.",
                }
            )
            tools_used.append("search_web")

        if force_scrape_tool:
            logger.info("FORCING scrape_website tool call for query")
            # Extract URL from message
            import re

            url_match = re.search(r"https?://[^\s]+", message)
            if url_match:
                url = url_match.group(0)
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "forced_scrape_call",
                                "type": "function",
                                "function": {
                                    "name": "scrape_website",
                                    "arguments": f'{{"url": "{url}"}}',
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": "forced_scrape_call",
                        "content": "Website content will be scraped by the system.",
                    }
                )
                tools_used.append("scrape_website")

        # Retry configuration for network resilience
        max_retries = 3
        base_delay = 1  # seconds
        response = None  # Initialize response to prevent NoneType errors

        # Use max_tokens directly - DO NOT multiply
        effective_max_tokens = max_tokens if max_tokens is not None else self.settings.AI_MAX_TOKENS

        for attempt in range(max_retries):
            try:
                # Prepare API call parameters
                api_params = {
                    "model": self.settings.AI_MODEL,
                    "messages": messages,
                    "tools": self.get_tool_definitions(),
                    "tool_choice": "auto",
                    "max_tokens": effective_max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                }

                # Create completion
                response = self.client.chat.completions.create(**api_params)
                break  # Success, exit retry loop
            except openai.APIConnectionError as e:
                logger.error(f"API connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
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
                    delay = base_delay * (2**attempt)
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
                if hasattr(e, "headers") and e.headers:
                    error_details.update(
                        {
                            "x_ratelimit_limit_requests": e.headers.get(
                                "x-ratelimit-limit-requests"
                            ),
                            "x_ratelimit_limit_tokens": e.headers.get("x-ratelimit-limit-tokens"),
                            "x_ratelimit_remaining_requests": e.headers.get(
                                "x-ratelimit-remaining-requests"
                            ),
                            "x_ratelimit_remaining_tokens": e.headers.get(
                                "x-ratelimit-remaining-tokens"
                            ),
                            "x_ratelimit_reset_requests": e.headers.get(
                                "x-ratelimit-reset-requests"
                            ),
                            "x_ratelimit_reset_tokens": e.headers.get("x-ratelimit-reset-tokens"),
                        }
                    )

                # Log structured rate limit information
                logger.warning("🚨 OPENAI RATE LIMIT EXCEEDED", extra=error_details)

                # Return user-friendly response with rate limit info
                reset_time = None
                if hasattr(e, "headers") and e.headers:
                    reset_requests = e.headers.get("x-ratelimit-reset-requests")
                    reset_tokens = e.headers.get("x-ratelimit-reset-tokens")
                    if reset_requests or reset_tokens:
                        reset_time = reset_requests or reset_tokens

                response_msg = "Aeris-AQ is currently experiencing high demand. Please wait a moment and try again."
                if reset_time:
                    response_msg += f" Expected reset in approximately {reset_time}."

                return {
                    "response": response_msg,
                    "tools_used": [],
                    "rate_limit_info": error_details,  # Include for debugging
                }
            except openai.BadRequestError as e:
                # Check for token limit errors
                error_msg = str(e).lower()
                if "token" in error_msg and (
                    "limit" in error_msg or "maximum" in error_msg or "exceed" in error_msg
                ):
                    logger.warning("⚠️ Token limit exceeded. Attempting intelligent truncation...")

                    # Try to intelligently truncate the context
                    messages = self._truncate_context_intelligently(messages, system_instruction)

                    # Retry with truncated context
                    try:
                        logger.info(
                            f"Retrying with truncated context ({len(messages)} messages)..."
                        )
                        api_params["messages"] = messages
                        response = self.client.chat.completions.create(**api_params)
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
                # Not a token limit error, raise it
                raise
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import time

                    time.sleep(delay)
                else:
                    # Log the full error for developers but provide user-friendly message
                    logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
                    return {
                        "response": (
                            "I apologize, but I'm experiencing technical difficulties at the moment. "
                            "This is likely a temporary issue. Please try again in a few moments, "
                            "or rephrase your question about air quality information."
                        ),
                        "tools_used": [],
                        "error_logged": True,  # Flag for internal tracking
                    }

        # Validate response before accessing
        if response is None:
            logger.error("Response is None after retry loop - all attempts failed")
            return {
                "response": "I was unable to process your request. Please try again.",
                "tools_used": [],
            }

        if not hasattr(response, "choices") or not response.choices:
            logger.error("Response missing choices attribute or choices is empty")
            return {
                "response": "I received an invalid response. Please try again.",
                "tools_used": [],
            }

        # Handle tool calls
        response_obj = response  # Store for reasoning extraction

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

            # Extract chart data if generate_chart was called
            chart_result = None
            for tool_result in tool_results:
                if tool_result["tool_call"].function.name == "generate_chart":
                    chart_result = tool_result["result"]
                    logger.info("📊 Chart generation detected in tool results")
                    break

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
                                "arguments": (
                                    tc.function.arguments
                                    if isinstance(tc.function.arguments, str)
                                    else str(tc.function.arguments)
                                ),
                            },
                        }
                        for tc in assistant_msg.tool_calls
                    ],
                }
            )

            # Add tool results
            for tool_result in tool_results:
                # Format the tool result as readable JSON string
                result_content = format_tool_result_as_json(tool_result["result"])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_result["tool_call"].id),
                        "content": result_content,  # Clean JSON format
                    }
                )

            # Get final response from model after tool execution
            for attempt in range(3):
                try:
                    final_response = self.client.chat.completions.create(
                        model=self.settings.AI_MODEL,
                        messages=messages,
                        max_tokens=effective_max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                    )
                    response_obj = final_response  # Update for reasoning extraction
                    response_text = final_response.choices[0].message.content
                    finish_reason = final_response.choices[0].finish_reason
                    logger.info(
                        f"Final response received. Length: {len(response_text) if response_text else 0}, Finish reason: {finish_reason}"
                    )

                    # Check if response was truncated due to length limit
                    if finish_reason == "length":
                        logger.warning("Response was truncated due to max_tokens limit - adding user-friendly notification")
                        truncation_note = (
                            "\n\n---\n"
                            "**📝 Note**: This response was truncated due to length limits. To continue:\n"
                            "• Ask for specific sections\n"
                            "• Break your question into smaller parts\n"
                            "• Request a focused summary"
                        )
                        response_text += truncation_note

                    response_text = self._clean_response(response_text)
                    break  # Success, exit retry loop
                except (openai.APIConnectionError, openai.APITimeoutError) as e:
                    logger.error(f"Final API call error (attempt {attempt + 1}/3): {e}")
                    if attempt < 2:
                        import time

                        time.sleep(1 * (2**attempt))  # Exponential backoff
                    else:
                        return {
                            "response": "I successfully gathered the information but encountered a network error generating the response. Please try asking again.",
                            "tools_used": tools_used,
                        }
                except Exception as e:
                    error_msg = str(e).lower()
                    logger.error(f"Final API call failed: {e}")

                    # If error occurs and chart was generated, provide helpful response
                    if "generate_chart" in tools_used:
                        return {
                            "response": (
                                "📊 Chart generated successfully! The visualization shows your data trends.\n\n"
                                "**Note**: Due to processing limits, I've kept the description brief. "
                                "The chart displays the key patterns in your data.\n\n"
                                "Need more details? Try:\n"
                                "• Ask about specific data points\n"
                                "• Request a smaller date range\n"
                                "• Ask for summary statistics"
                            ),
                            "tools_used": tools_used,
                            "chart_result": chart_result if chart_result else None,
                        }

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
            logger.warning(
                f"OpenAI returned empty or very short response (length: {len(response_text) if response_text else 0}). Tools used: {tools_used}"
            )

            # Check if tools were called but response is still short
            if tools_used:
                # Try to generate a basic response from tool results
                logger.info("Attempting to generate fallback response from tool results")
                try:
                    fallback_response = await self._generate_tool_based_response(
                        message, tools_used, history
                    )
                    if fallback_response and len(fallback_response.strip()) > 50:
                        response_text = fallback_response
                        logger.info("Successfully generated fallback response from tool results")
                    else:
                        response_text = (
                            "I retrieved air quality data for your query, but had trouble formatting the complete response. "
                            "The data shows current air quality information has been collected. "
                            "Please try asking about a specific city or location for detailed results."
                        )
                except Exception as fallback_error:
                    logger.error(f"Fallback response generation failed: {fallback_error}")
                    response_text = (
                        "I successfully retrieved air quality data, but encountered a formatting issue. "
                        "Please try your question again or specify a different location."
                    )
            else:
                response_text = await self._generate_fallback(message)

        # Add chart_result to response if available
        result = {
            "response": response_text
            or "I was unable to generate a response. Please try again.",
            "tools_used": tools_used,
        }

        if "chart_result" in locals() and chart_result:
            result["chart_result"] = chart_result
            logger.info("📊 Chart data added to OpenAI response")

        return result

    def _should_force_search_tool(self, message: str) -> bool:
        """Check if the message requires forcing search_web tool usage."""
        search_keywords = [
            "latest",
            "current",
            "recent",
            "update",
            "up-to-date",
            "2024",
            "2025",
            "2026",
            "policy",
            "regulation",
            "legislation",
            "government action",
            "research study",
            "who/epa guideline",
            "standard",
            "recommendation",
            "news",
            "breaking news",
            "staying informed",
            "monitoring change",
            "regulatory update",
        ]
        return any(keyword in message for keyword in search_keywords)

    def _should_force_scrape_tool(self, message: str) -> bool:
        """Check if the message requires forcing scrape_website tool usage."""
        scrape_keywords = ["scrape", "extract", "website", "url", "http://", "https://"]
        return any(keyword in message for keyword in scrape_keywords)

    def _should_force_air_quality_tool(self, message: str) -> tuple[bool, list[str]]:
        """Check if the message requires forcing air quality tool usage.

        Returns:
            tuple: (should_force, list_of_cities_to_query)
        """
        message_lower = message.lower()

        # Keywords that indicate air quality queries
        air_quality_keywords = [
            "air quality",
            "aqi",
            "pollution",
            "pm2.5",
            "pm10",
            "ozone",
            "no2",
            "so2",
            "co",
            "air pollution",
            "atmospheric quality",
            "clean air",
            "air monitoring",
        ]

        # Check if it's an air quality query
        is_air_quality_query = any(keyword in message_lower for keyword in air_quality_keywords)

        if not is_air_quality_query:
            return False, []

        # Extract city names for tool calls
        import re

        # Country to major cities mapping
        country_cities = {
            "uganda": ["Kampala", "Gulu", "Jinja", "Mbale", "Mbarara"],
            "kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"],
            "tanzania": ["Dar es Salaam", "Dodoma", "Mwanza", "Arusha", "Mbeya"],
            "rwanda": ["Kigali", "Butare", "Musanze", "Ruhengeri", "Gisenyi"],
            "uk": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
            "united kingdom": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
            "usa": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
            "united states": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
            "china": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu"],
            "india": ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata"],
            "germany": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"],
            "france": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
            "japan": ["Tokyo", "Osaka", "Nagoya", "Sapporo", "Fukuoka"],
            "australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
            "canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
            "brazil": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza"],
            "mexico": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana"],
            "south africa": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth"],
            "nigeria": ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt"],
            "egypt": ["Cairo", "Alexandria", "Giza", "Shubra El-Kheima", "Port Said"],
        }

        cities = []

        # Check for countries first
        for country, city_list in country_cities.items():
            if country in message_lower:
                # For countries, take the first 3-5 major cities to avoid overwhelming
                cities.extend(city_list[:5])
                break

        # If no country found, extract individual city names
        if not cities:
            # Common city extraction patterns
            city_patterns = [
                r"\b(?:in|at|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",  # "in London", "at New York"
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:air quality|aqi)\b",  # "London air quality"
                r"\b(compare|comparison)\s+(?:air quality|aqi)?\s*(?:between|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:and|vs|versus)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",  # "compare London and Paris"
            ]

            for pattern in city_patterns:
                matches = re.findall(pattern, message, re.IGNORECASE)
                if matches:
                    if isinstance(matches[0], tuple):
                        # For comparison patterns, extract all cities
                        cities.extend([city for match in matches for city in match if city])
                    else:
                        cities.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_cities = []
        for city in cities:
            city_lower = city.lower()
            if city_lower not in seen:
                seen.add(city_lower)
                unique_cities.append(city)

        # Limit to reasonable number (max 10 cities to avoid overwhelming)
        if len(unique_cities) > 10:
            unique_cities = unique_cities[:10]

        return len(unique_cities) > 0, unique_cities

    def _deduplicate_calls(self, tool_calls: list) -> list:
        """
        Remove duplicate tool calls (same function with same arguments).

        Allows multiple calls to the same function with DIFFERENT arguments
        (e.g., get_city_air_quality for London AND Paris).
        """
        seen = set()
        unique = []
        for tc in tool_calls:
            # Create key from function name AND normalized arguments
            # This ensures get_city_air_quality("London") != get_city_air_quality("Paris")
            try:
                # Parse arguments to ensure consistent ordering for comparison
                args_str = (
                    tc.function.arguments
                    if isinstance(tc.function.arguments, str)
                    else json.dumps(tc.function.arguments, sort_keys=True)
                )
                args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
                # Sort keys for consistent comparison
                normalized_args = json.dumps(args_dict, sort_keys=True)
                key = f"{tc.function.name}::{normalized_args}"
            except:
                # Fallback to string comparison if JSON parsing fails
                key = f"{tc.function.name}::{tc.function.arguments}"

            if key not in seen:
                seen.add(key)
                unique.append(tc)
            else:
                logger.info(
                    f"Skipping duplicate tool call: {tc.function.name} with args {tc.function.arguments}"
                )

        if len(unique) < len(tool_calls):
            logger.info(f"Deduplicated {len(tool_calls)} tool calls to {len(unique)} unique calls")

        return unique

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a short human-readable summary for common tool results.

        Currently focuses on AirQo measurement payloads so the assistant
        always has a clear, formatted snippet to include in the final reply.
        """
        try:
            if not isinstance(result, dict):
                return ""  # Nothing to summarize

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
                    summary = f"📊 Data file '{filename}' contains {len(rows)} rows with columns: {', '.join(headers[:5])}{'...' if len(headers) > 5 else ''}"
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
                summary = f"📊 {chart_type.title()} Chart Generated\n\n"
                summary += f"![{chart_type.title()} Chart]({chart_data})\n\n"
                summary += f"Chart created with {data_rows} data points"
                if data_sampled and original_rows > data_rows:
                    summary += f" (sampled from {original_rows} total rows for clarity)"
                summary += ".\n\nThe visualization above shows the data trends. Review it for key insights!"
                return summary

            # AirQo-style response with measurements
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

    async def _execute_tools(self, tool_calls: list, tools_used: list) -> list[dict[str, Any]]:
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
                    logger.warning(
                        f"Unexpected arguments type: {type(tool_call.function.arguments)}"
                    )
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
                    results.append(
                        {
                            "tool_call": tool_calls[i],
                            "result": {"error": f"Tool execution failed: {str(result)}"},
                        }
                    )
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
        # Keep proper code blocks intact
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
                    # Starting a table - ensure blank line before if previous line has content
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
                    if not prev_was_list:  # Don't add space if previous was a list
                        cleaned_lines.append("")

                cleaned_lines.append(line)
                prev_was_header = is_header
                prev_was_list = is_list

        content = "\n".join(cleaned_lines)

        # Ensure proper spacing in tables
        content = re.sub(r"\|([^|\n]*?)\|", r"| \1 |", content)
        content = re.sub(r"\| +\|", r"| |", content)

        return content.strip()

    async def _generate_tool_based_response(
        self, original_message: str, tools_used: list, history: list
    ) -> str:
        """Generate a response based on tool results when AI response is malformed."""
        try:
            # Check what tools were used and try to provide basic data
            tool_names = [
                tool.get("function", {}).get("name", "")
                for tool in tools_used
                if isinstance(tool, dict)
            ]

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
            return "I'm experiencing technical difficulties. Please try again in a moment."
