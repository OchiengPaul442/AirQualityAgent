"""
Gemini AI Provider Implementation.

Handles Gemini-specific setup and message processing with tool calling.
"""

import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types

from ..tool_definitions import gemini_tools
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
        Process a message with Gemini.

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
        if not self.client:
            return {
                "response": "Gemini client not initialized.",
                "tools_used": [],
            }

        # Convert history to Gemini format
        chat_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )

        # Get tools only for supported models
        tools = None
        if self.settings.AI_MODEL in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"]:
            tools = self.get_tool_definitions()

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
        if max_tokens is not None:
            config_params["max_output_tokens"] = max_tokens

        chat = self.client.chats.create(
            model=self.settings.AI_MODEL,
            config=types.GenerateContentConfig(**config_params),
            history=chat_history,
        )

        # Send message
        response = chat.send_message(message)
        tools_used: list[str] = []

        # Handle function calls
        if (
            tools
            and response.candidates
            and response.candidates[0].content.parts
        ):
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if part.function_call
            ]

            if function_calls:
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

                # Send results back to model
                function_responses = [
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=result["function_call"].name,
                            response={"result": result["result"]},
                        )
                    )
                    for result in function_results
                ]

                response = chat.send_message(types.Content(parts=function_responses))

        # Get final response
        final_response = response.text if response.text else ""

        # Check if response was truncated
        if response.candidates and response.candidates[0].finish_reason:
            finish_reason = response.candidates[0].finish_reason
            logger.info(f"Gemini response finish reason: {finish_reason}")
            
            if finish_reason == "MAX_TOKENS":
                logger.warning("Gemini response was truncated due to max tokens")
                final_response += "\n\n*Response was truncated due to length limits. Please ask for more specific information or break your question into smaller parts.*"

        if not final_response or not final_response.strip():
            logger.warning("Gemini returned empty response. Providing fallback.")
            final_response = (
                "I apologize, but I wasn't able to retrieve the requested information at this time. "
                "This could be due to data unavailability or connectivity issues. Please try:\n\n"
                "1. Asking about a different location\n"
                "2. Rephrasing your question\n"
                "3. Checking back in a few moments\n\n"
                "Is there anything else I can help you with?"
            )

        return {
            "response": final_response,
            "tools_used": tools_used,
        }

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
                    results.append({
                        "function_call": function_calls[i],
                        "result": {"error": f"Function execution failed: {str(result)}"},
                    })
                else:
                    results.append(result)  # type: ignore
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            results = [
                {"function_call": fc, "result": {"error": "Parallel execution failed"}}
                for fc in function_calls
            ]

        return results
