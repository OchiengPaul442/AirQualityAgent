"""
OpenAI-compatible Provider Implementation.

Handles OpenAI, DeepSeek, Kimi, and OpenRouter provider setup and message processing.
"""

import asyncio
import json
import logging
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
        
        for attempt in range(max_retries):
            try:
                # Create completion
                # Use higher max_tokens when tools are available (responses tend to be longer)
                effective_max_tokens = max_tokens if max_tokens is not None else (self.settings.AI_MAX_TOKENS * 2 if self.get_tool_definitions() else self.settings.AI_MAX_TOKENS)
                
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
                logger.error(f"Rate limit exceeded: {e}")
                return {
                    "response": "The AI service is currently experiencing high demand. Please wait a moment and try again.",
                    "tools_used": [],
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
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_result["tool_call"].id),
                        "content": json.dumps({"result": tool_result["result"]}),
                    }
                )

            # Get final response with retry logic
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

        # Handle empty responses
        if not response_text or not response_text.strip():
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
