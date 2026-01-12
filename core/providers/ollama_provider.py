"""
Ollama Provider Implementation.

Handles local Ollama deployment for air quality agent with enhanced error handling and rate limit detection.
Now includes ModelAdapter support for models with weak or no tool-calling capabilities.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any

import ollama

from core.agent.model_adapter import ModelAdapter

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

        Args:
            messages: List of message dictionaries
            system_instruction: System instruction text

        Returns:
            Truncated list of messages
        """
        try:
            # Separate system, user, assistant, and tool messages
            system_msgs = [m for m in messages if m.get("role") == "system"]
            user_msgs = [m for m in messages if m.get("role") == "user"]
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            tool_msgs = [m for m in messages if m.get("role") == "tool"]

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

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get Ollama tool definitions.

        Ollama uses OpenAI-compatible format for tools.

        Returns:
            List of tool dictionaries
        """
        from core.tools.definitions import openai_tools

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
        Optimized for low-end models like qwen2.5:3b.

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
        # Detect low-end model and apply optimizations
        model_name = self.settings.AI_MODEL.lower()
        is_low_end_model = any(size in model_name for size in [":1b", ":3b", ":0.5b"])

        if is_low_end_model:
            logger.info(f"📊 Low-end model detected ({self.settings.AI_MODEL}) - applying optimizations")
            # Optimize parameters for stability
            max_tokens = min(max_tokens or 1200, 800)
            temperature = min(temperature, 0.35)
            top_p = min(top_p, 0.8)
            top_k = top_k or 40
            # Reduce history aggressively for low-end models
            if len(history) > 8:
                logger.info(f"Truncating history from {len(history)} to 8 messages for low-end model")
                history = history[-8:]

        # Sanitize all text inputs to prevent UTF-8 encoding errors
        system_instruction = self._sanitize_text(system_instruction)
        message = self._sanitize_text(message)

        # Build messages
        messages = [{"role": "system", "content": system_instruction}]
        for msg in history:
            sanitized_content = self._sanitize_text(msg.get("content", ""))
            messages.append({"role": msg["role"], "content": sanitized_content})
        messages.append({"role": "user", "content": message})

        tools_used = []

        # Track truncation status
        was_truncated = False

        # Retry configuration with longer delays for low-end models
        max_retries = 3
        base_delay = 2.0 if is_low_end_model else 1.0
        response = None  # Initialize response to prevent NoneType errors

        for attempt in range(max_retries):
            try:
                # Call Ollama with tools
                options = {
                    "temperature": temperature,
                    "timeout": 45,  # Reduced to 45 seconds for faster responses
                }

                # Add optional parameters if provided
                if top_p is not None:
                    options["top_p"] = top_p
                if top_k is not None:
                    options["top_k"] = top_k
                if max_tokens is not None:
                    options["num_predict"] = max_tokens

                logger.info(
                    f"Calling Ollama chat with model {self.settings.AI_MODEL}, messages count: {len(messages)}"
                )

                # Get tools for Ollama (uses OpenAI-compatible format)
                tools = self.get_tool_definitions()
                logger.info(f"Ollama calling with {len(tools)} tools available")

                response = ollama.chat(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    tools=tools,  # CRITICAL: Pass tools to Ollama
                    options=options,
                )

                # Only log response details in development, not the full response
                if self.settings.ENVIRONMENT == "development":
                    logger.debug(f"Ollama response received: {type(response)}")
                else:
                    logger.info("Ollama response received successfully")

                # DEBUG: Log the full response to see what DeepSeek R1 returns
                logger.info(f"DEBUG: Full Ollama response: {response}")
                if "message" in response and "content" in response["message"]:
                    logger.info(
                        f"DEBUG: Response content preview: {response['message']['content'][:200]}..."
                    )

                logger.info(
                    f"Ollama response type: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'not dict'}"
                )

                # Check if response was truncated
                if isinstance(response, dict):
                    done_reason = response.get("done_reason")
                    if done_reason == "length":
                        logger.warning("Response was truncated due to max_tokens limit - will add notification")
                        was_truncated = True

                break  # Success, exit retry loop

            except ConnectionError as e:
                logger.error(f"Ollama connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    import asyncio
                    await asyncio.sleep(delay)
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
                    delay = base_delay * (2**attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import asyncio
                    await asyncio.sleep(delay)
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

                # Check for token limit issues (prompt too long)
                if (
                    "prompt too long" in error_msg
                    or "limit is" in error_msg
                    or "token" in error_msg
                    and "limit" in error_msg
                ):
                    logger.warning("⚠️ Token limit exceeded. Attempting intelligent truncation...")

                    # Try to intelligently truncate the context
                    messages = self._truncate_context_intelligently(messages, system_instruction)

                    # Retry with truncated context
                    try:
                        logger.info(
                            f"Retrying with truncated context ({len(messages)} messages)..."
                        )
                        response = ollama.chat(
                            model=self.settings.AI_MODEL,
                            messages=messages,
                            tools=tools,
                            options=options,
                        )
                        logger.info("✅ Successfully processed with truncated context")
                        break  # Success, exit retry loop
                    except Exception as retry_error:
                        logger.error(f"Truncation retry failed: {retry_error}")
                        # Fall through to return user-friendly error
                        return {
                            "response": (
                                "I apologize, but the conversation has become too long for my current context window. "
                                "To continue, please start a new conversation or ask your question more concisely. "
                                "I can still help with air quality information - just phrase it in a shorter way."
                            ),
                            "tools_used": [],
                            "tokens_used": 0,
                            "cost_estimate": 0.0,
                            "context_truncated": True,
                        }

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
                        "response": "Aeris-AQ is currently experiencing high demand. Please wait a moment and try again.",
                        "tools_used": [],
                        "rate_limit_info": error_details,
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                    }

                # Check for 500 Internal Server Error from Ollama
                if "500" in error_msg or "Internal Server Error" in error_msg:
                    logger.error(f"Ollama returned 500 error: {e}")
                    return {
                        "response": "I was unable to process your request due to a temporary service issue. Please try again in a moment or rephrase your question.",
                        "tools_used": [],
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                        "error_type": "ollama_500",
                    }

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    import asyncio
                    await asyncio.sleep(delay)
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
                        logger.error(
                            f"Unexpected Ollama error (attempt {attempt + 1}/{max_retries}): {e}"
                        )
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
                "response": "I was unable to process your request. The AI service did not respond. Please try again or rephrase your question.",
                "tools_used": [],
                "tokens_used": 0,
                "cost_estimate": 0.0,
            }

        # If the response object is not a dict-like with .get(), try to adapt
        try:
            has_message = (
                response.get("message")
                if isinstance(response, dict)
                else getattr(response, "message", None)
            )
        except Exception:
            has_message = None

        if not has_message:
            logger.error(f"Ollama response message is None or empty: {response}")
            return {
                "response": "I was unable to generate a response. The AI service returned invalid data. Please try again.",
                "tools_used": [],
                "tokens_used": 0,
                "cost_estimate": 0.0,
            }

        # Normalize message object access
        message_obj = (
            response.get("message") if isinstance(response, dict) else response.message
        )

        # Handle tool calls
        chart_result = None  # Track chart generation
        if getattr(message_obj, "tool_calls", None):
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

                    # CRITICAL: Capture chart result if generate_chart was called
                    if function_name == "generate_chart" and isinstance(tool_result, dict):
                        chart_result = tool_result
                        logger.info("📊 Chart generation detected - captured result")

                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    tool_result = {
                        "error": "Aeris-AQ is currently experiencing issues executing a required service. Please try again in a few minutes."
                    }

                tool_results.append(tool_result)

                # CRITICAL FIX: Only send summary to avoid token overflow
                # Don't send full tool_result (which may contain large CSV data)
                summary = self._summarize_tool_result(tool_result)
                if summary:
                    # Send only the summary as tool response
                    messages.append(
                        {
                            "role": "tool",
                            "content": summary,
                        }
                    )
                else:
                    # Fallback: truncate tool result if no summary available
                    result_str = json.dumps(tool_result)
                    if len(result_str) > 2000:
                        result_str = result_str[:2000] + "... [truncated]"
                    messages.append(
                        {
                            "role": "tool",
                            "content": result_str,
                        }
                    )

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
                final_message = (
                    final_response.get("message")
                    if isinstance(final_response, dict)
                    else getattr(final_response, "message", None)
                )
                if not final_message:
                    logger.error(f"Ollama final response message is None: {final_response}")
                    return {
                        "response": "I was unable to process the data retrieved. Please try again or rephrase your question.",
                        "tools_used": tools_used,
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                    }
                response_text = final_message.content
            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"Ollama final response error: {e}")

                # CRITICAL FIX: Handle common errors and return tool results if available
                # 1. Handle token limit errors (prompt too long)
                if "too long" in error_msg or "limit" in error_msg:
                    logger.warning("⚠️ Token limit exceeded - returning tool results directly")

                    # Build response from tool summaries
                    response_parts = []
                    for tool_result in tool_results:
                        summary = self._summarize_tool_result(tool_result)
                        if summary:
                            response_parts.append(summary)

                    if response_parts:
                        response_text = "\n\n".join(response_parts)
                    else:
                        response_text = "I've processed your request, but the response was too large. Please try a more specific query or smaller dataset."

                    result = {
                        "response": response_text,
                        "tools_used": tools_used,
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                    }

                    # Include chart_result if it was captured
                    if chart_result:
                        result["chart_result"] = chart_result
                        result["chart_generated"] = True
                        logger.info("📊 Chart data included in token limit error recovery")

                    return result

                # 2. Handle 500 errors but preserve chart results
                if ("500" in error_msg or "internal server" in error_msg) and "generate_chart" in tools_used:
                    logger.warning("⚠️ Ollama 500 error but chart was generated - returning chart result")

                    # Build result dict with chart_result
                    result = {
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
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                        "chart_generated": True,
                    }

                    # Include chart_result if it was captured
                    if chart_result:
                        result["chart_result"] = chart_result
                        logger.info("📊 Chart data included in 500 error recovery response")

                    return result

                return {
                    "response": "I was unable to process the data retrieved. Please try again with a different question.",
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
                    "response": "I was unable to generate a valid response. The AI service returned unexpected data. Please try again.",
                    "tools_used": tools_used,
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                }

        # Clean response
        response_text = self._clean_response(response_text)

        # Add truncation notification if response was truncated
        if was_truncated:
            truncation_note = (
                "\n\n---\n"
                "**📝 Note**: This response was truncated due to length limits. To continue:\n"
                "• Ask for specific sections\n"
                "• Break your question into smaller parts\n"
                "• Request a focused summary"
            )
            response_text += truncation_note

        # Debug: Log raw response for reasoning extraction debugging
        logger.info(f"Raw response text length: {len(response_text) if response_text else 0}")
        if response_text and len(response_text) > 0:
            logger.debug(f"Raw response preview: {response_text[:500]}...")
        else:
            logger.warning("⚠️ Ollama returned EMPTY response text after tool execution!")

        # Extract thinking/reasoning steps if present
        thinking_steps, cleaned_response = self._extract_thinking_steps(response_text)

        # CRITICAL FIX: If response is empty but tools were used successfully, generate fallback response
        if not cleaned_response and tools_used:
            logger.warning("⚠️ AI returned empty response after tool calls - generating fallback from tool results")

            # Generate a basic response from tool results
            fallback_parts = []
            for i, tool_result in enumerate(tool_results):
                # Handle cases where tool_result might be a list or dict
                if isinstance(tool_result, dict):
                    if tool_result.get("success"):
                        summary = self._summarize_tool_result(tool_result)
                        if summary:
                            fallback_parts.append(summary)
                elif isinstance(tool_result, list):
                    # Handle list of results
                    for sub_result in tool_result:
                        if isinstance(sub_result, dict) and sub_result.get("success"):
                            summary = self._summarize_tool_result(sub_result)
                            if summary:
                                fallback_parts.append(summary)

            if fallback_parts:
                cleaned_response = "Here's the information I found:\n\n" + "\n\n".join(fallback_parts)
                logger.info("✅ Generated fallback response from tool results")
            else:
                cleaned_response = "I was unable to find the data needed to answer your question. Please try rephrasing or asking about a different topic."

        # CRITICAL FIX: If no tools were used and response is empty/generic, provide helpful message
        if not tools_used and (not cleaned_response or len(cleaned_response) < 50):
            logger.warning("⚠️ No tools called and response is empty/short - may need data retrieval")
            if not cleaned_response:
                cleaned_response = "I was unable to find the specific data needed to answer your question. Please try rephrasing or providing more details."

        # Build final result dict
        result = {
            "response": cleaned_response or "I was unable to generate a response. Please try again with a different question.",
            "tools_used": tools_used,
            "thinking_steps": thinking_steps,
            "reasoning_content": "\n".join(thinking_steps) if thinking_steps else None,
            "tokens_used": 0,  # Ollama doesn't provide token counts
            "cost_estimate": 0.0,  # Local model, no cost
        }

        # Add chart_result if chart was generated
        if chart_result:
            result["chart_result"] = chart_result
            logger.info("📊 Chart data included in Ollama response")

        return result

    def _extract_thinking_steps(self, content: str) -> tuple[list[str], str]:
        """
        Extract thinking/reasoning steps from response content.

        Ollama reasoning models (like Nemotron-3-nano) often wrap their thinking
        in special markers like <think>...</think> or similar patterns.

        Args:
            content: The full response content

        Returns:
            Tuple of (thinking_steps, cleaned_content)
            - thinking_steps: List of extracted thinking steps
            - cleaned_content: Content with thinking markers removed
        """
        import re

        thinking_steps = []
        cleaned_content = content

        # Pattern 1: <think>...</think> tags (Nemotron format shown in example)
        think_pattern = r"<think>(.*?)</think>"
        matches = re.findall(think_pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            logger.info(f"Found {len(matches)} <think> tag matches in response")
            for match in matches:
                # Split by newlines and filter empty lines
                steps = [step.strip() for step in match.strip().split("\n") if step.strip()]
                thinking_steps.extend(steps)
            # Remove <think> tags from cleaned content
            cleaned_content = re.sub(think_pattern, "", content, flags=re.DOTALL | re.IGNORECASE)

        # Pattern 2: "Thinking..." prefix (some models use this)
        thinking_prefix_pattern = r"^⠹?\s*Thinking\.\.\.?\s*\n(.*?)\n\.\.\.done thinking\.?\s*\n"
        matches = re.findall(
            thinking_prefix_pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        if matches:
            for match in matches:
                steps = [step.strip() for step in match.strip().split("\n") if step.strip()]
                thinking_steps.extend(steps)
            cleaned_content = re.sub(
                thinking_prefix_pattern, "", content, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
            )

        # Pattern 3: Explicit "Step N:" patterns in reasoning models
        step_pattern = r"(?:^|\n)(Step \d+:.*?)(?=\n(?:Step \d+:|$))"
        step_matches = re.findall(step_pattern, content, re.DOTALL | re.MULTILINE)
        if step_matches and not thinking_steps:  # Only if we haven't found thinking yet
            thinking_steps.extend([step.strip() for step in step_matches])
            # Don't remove step patterns from content as they might be part of the answer

        # Pattern 4: Reasoning blocks marked with specific headers
        reasoning_block_pattern = r"(?:^|\n)(?:Reasoning|Analysis|Thought Process):\s*\n(.*?)(?=\n\n|\n(?:[A-Z][a-z]+:)|$)"
        reasoning_matches = re.findall(reasoning_block_pattern, content, re.DOTALL | re.MULTILINE)
        if reasoning_matches and not thinking_steps:
            for match in reasoning_matches:
                steps = [step.strip() for step in match.strip().split("\n") if step.strip()]
                thinking_steps.extend(steps)

        # Clean up the content
        cleaned_content = cleaned_content.strip()

        # Remove any residual thinking markers
        cleaned_content = re.sub(
            r"^\s*\.\.\.done thinking\.?\s*\n?",
            "",
            cleaned_content,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        cleaned_content = re.sub(r"^\s*⠹\s*", "", cleaned_content, flags=re.MULTILINE)

        # Log extraction results
        if thinking_steps:
            logger.info(f"Extracted {len(thinking_steps)} thinking steps: {thinking_steps[:3]}...")
        else:
            logger.debug("No thinking steps extracted from response")

        return thinking_steps, cleaned_content

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
        cleaned_lines: list[str] = []
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

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a short human-readable summary for common tool results."""
        try:
            if not isinstance(result, dict):
                return ""

            # Handle scan_document results  (file upload analysis)
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

            # Handle search_web results
            if result.get("results") and isinstance(result["results"], list):
                results = result["results"][:3]  # Top 3 results
                summary_parts = ["Web search results:"]
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    snippet = r.get("snippet", "")[:150]
                    summary_parts.append(f"{idx}. {title}: {snippet}...")
                return "\n".join(summary_parts)

            # Handle failed tool calls with suggestions
            if not result.get("success"):
                message = result.get("message", "")
                suggestion = result.get("suggestion", "")
                if message:
                    summary = f"Note: {message}"
                    if suggestion == "search_web":
                        query = result.get("search_query", "")
                        summary += f" Suggested: search for '{query}'"
                    return summary
                return ""

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

    async def _handle_text_based_tool_extraction(
        self,
        response_text: str,
        messages: list[dict],
        temperature: float,
        top_p: float,
        tools: list[dict]
    ) -> tuple[str, list[str]]:
        """
        Extract and execute tool calls from plain text responses.
        
        This is crucial for models that don't support native tool calling.
        
        Args:
            response_text: Model's text response
            messages: Conversation messages
            temperature: Temperature setting
            top_p: Top-p setting
            tools: Available tools
            
        Returns:
            Tuple of (final_response, tools_used)
        """
        tools_used = []

        # Get list of available tool names
        available_tools = [tool["function"]["name"] for tool in tools]

        # Extract tool calls from text
        extracted_calls = ModelAdapter.extract_tool_calls_from_text(
            response_text,
            available_tools
        )

        if not extracted_calls:
            # No tool calls found, return original response
            return response_text, tools_used

        logger.info(f"🔍 Extracted {len(extracted_calls)} tool calls from text response")

        # Execute extracted tool calls
        tool_results = []
        for call in extracted_calls:
            try:
                logger.info(f"🔧 Executing extracted tool: {call.name}")
                result = self.tool_executor.execute(call.name, call.arguments)
                tool_results.append(result)
                tools_used.append(call.name)

                # Add tool result to messages
                summary = self._summarize_tool_result(result)
                if summary:
                    messages.append({
                        "role": "tool",
                        "content": summary
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result)[:2000]  # Truncate large results
                    })

            except Exception as e:
                logger.error(f"Failed to execute extracted tool {call.name}: {e}")
                continue

        if not tool_results:
            # No successful tool executions
            return response_text, tools_used

        # Get final response with tool results
        try:
            logger.info("🔄 Generating final response with tool results...")
            final_response = ollama.chat(
                model=self.settings.AI_MODEL,
                messages=messages,
                options={
                    "temperature": temperature,
                    "top_p": top_p,
                }
            )

            final_message = (
                final_response.get("message")
                if isinstance(final_response, dict)
                else getattr(final_response, "message", None)
            )

            if final_message and final_message.content:
                return final_message.content, tools_used
            else:
                # Fallback to summarizing tool results
                logger.warning("No final response from model, summarizing tool results")
                summaries = [self._summarize_tool_result(r) for r in tool_results if self._summarize_tool_result(r)]
                return "\n\n".join(summaries), tools_used

        except Exception as e:
            logger.error(f"Failed to get final response: {e}")
            # Return tool result summaries
            summaries = [self._summarize_tool_result(r) for r in tool_results if self._summarize_tool_result(r)]
            return "\n\n".join(summaries) if summaries else response_text, tools_used

