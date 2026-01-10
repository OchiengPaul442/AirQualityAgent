"""
Advanced Tool Orchestration Layer for Low-End Models

This module implements intelligent orchestration patterns inspired by LangChain/LangGraph
but optimized for lightweight deployment and low-end models. It provides:

1. **Multi-Step Reasoning**: Chain tool calls with dependency resolution
2. **Intelligent Retry Logic**: Exponential backoff with context-aware retries
3. **Fallback Chains**: Automatic fallback to alternative tools
4. **Response Validation**: Quality checks for malformed responses
5. **Context Management**: Smart token management for long conversations

Key Design Principles:
- Zero external framework dependencies (pure Python)
- Optimized for models with weak or no tool-calling support
- Production-ready error handling and circuit breakers
- Memory-efficient operation for resource-constrained environments
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolExecutionStatus(Enum):
    """Status of tool execution in the orchestration flow."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class ToolCall:
    """Represents a single tool call in the orchestration chain."""
    name: str
    args: dict[str, Any]
    priority: int = 0  # Higher priority tools execute first
    dependencies: list[str] = field(default_factory=list)  # Tool names this depends on
    status: ToolExecutionStatus = ToolExecutionStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0


@dataclass
class OrchestrationResult:
    """Result of an orchestration execution."""
    success: bool
    tools_executed: list[str]
    results: dict[str, Any]
    errors: dict[str, str]
    total_execution_time: float
    context_injection: str


class ToolOrchestrator:
    """
    Advanced orchestration layer for multi-tool workflows.
    
    Implements intelligent patterns for low-end models:
    - Proactive tool execution before AI inference
    - Dependency-aware tool chaining
    - Automatic retries with exponential backoff
    - Fallback chains when primary tools fail
    - Result validation and quality checks
    """

    def __init__(
        self,
        tool_executor: Any,
        max_retries: int = 1,  # Reduced to 1 for speed
        retry_delay: float = 0.3,  # Reduced to 0.3 for speed
        enable_fallbacks: bool = True,
        timeout_per_tool: float = 10.0  # Reduced to 10 for speed
    ):
        """
        Initialize the orchestrator.
        
        Args:
            tool_executor: ToolExecutor instance
            max_retries: Maximum retry attempts per tool
            retry_delay: Initial delay between retries (exponential backoff)
            enable_fallbacks: Enable automatic fallback to alternative tools
            timeout_per_tool: Timeout for each tool execution
        """
        self.tool_executor = tool_executor
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_fallbacks = enable_fallbacks
        self.timeout_per_tool = timeout_per_tool

        # Circuit breaker state
        self.circuit_breaker = {}  # {tool_name: {"failures": 0, "last_failure": timestamp}}
        self.circuit_threshold = 5
        self.circuit_timeout = 300  # 5 minutes

        # Fallback chains for tools
        self.fallback_chains = {
            "get_african_city_air_quality": [
                "get_city_air_quality",  # WAQI as fallback
                "get_openmeteo_current_air_quality"  # OpenMeteo as last resort
            ],
            "get_city_air_quality": [
                "get_openmeteo_current_air_quality"  # OpenMeteo as fallback
            ],
            "search_web": [
                "scrape_website"  # If search fails, try scraping known URLs
            ]
        }

    def _is_circuit_open(self, tool_name: str) -> bool:
        """Check if circuit breaker is open for a tool."""
        if tool_name not in self.circuit_breaker:
            return False

        breaker = self.circuit_breaker[tool_name]
        if breaker["failures"] >= self.circuit_threshold:
            time_since_failure = time.time() - breaker["last_failure"]
            if time_since_failure < self.circuit_timeout:
                logger.warning(f"Circuit breaker OPEN for {tool_name}")
                return True
            else:
                # Reset circuit
                logger.info(f"Circuit breaker RESET for {tool_name}")
                self.circuit_breaker[tool_name] = {"failures": 0, "last_failure": 0}
                return False
        return False

    def _record_failure(self, tool_name: str):
        """Record a tool failure for circuit breaker."""
        if tool_name not in self.circuit_breaker:
            self.circuit_breaker[tool_name] = {"failures": 0, "last_failure": 0}

        self.circuit_breaker[tool_name]["failures"] += 1
        self.circuit_breaker[tool_name]["last_failure"] = time.time()
        logger.info(f"Tool {tool_name} failure count: {self.circuit_breaker[tool_name]['failures']}")

    def _record_success(self, tool_name: str):
        """Record a tool success (resets circuit breaker)."""
        if tool_name in self.circuit_breaker:
            self.circuit_breaker[tool_name] = {"failures": 0, "last_failure": 0}

    async def _execute_single_tool_with_retry(
        self,
        tool_call: ToolCall
    ) -> ToolCall:
        """
        Execute a single tool with retry logic and timeout protection.
        
        Args:
            tool_call: ToolCall to execute
            
        Returns:
            Updated ToolCall with result or error
        """
        tool_name = tool_call.name

        # Check circuit breaker
        if self._is_circuit_open(tool_name):
            tool_call.status = ToolExecutionStatus.FAILED
            tool_call.error = "Circuit breaker open - too many recent failures"
            return tool_call

        start_time = time.time()
        tool_call.status = ToolExecutionStatus.RUNNING

        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔧 Executing {tool_name} (attempt {attempt + 1}/{self.max_retries})")

                # Execute with timeout
                task = asyncio.create_task(
                    self.tool_executor.execute_async(tool_name, tool_call.args)
                )
                result = await asyncio.wait_for(task, timeout=self.timeout_per_tool)

                # Validate result
                if self._is_valid_result(result):
                    tool_call.status = ToolExecutionStatus.SUCCESS
                    tool_call.result = result
                    tool_call.execution_time = time.time() - start_time
                    self._record_success(tool_name)
                    logger.info(f"✅ {tool_name} succeeded in {tool_call.execution_time:.2f}s")
                    return tool_call
                else:
                    logger.warning(f"⚠️ {tool_name} returned invalid result: {result}")
                    if attempt < self.max_retries - 1:
                        tool_call.status = ToolExecutionStatus.RETRYING
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    else:
                        tool_call.status = ToolExecutionStatus.FAILED
                        tool_call.error = "Invalid result after all retries"

            except asyncio.TimeoutError:
                logger.error(f"⏱️ {tool_name} timed out after {self.timeout_per_tool}s")
                if attempt < self.max_retries - 1:
                    tool_call.status = ToolExecutionStatus.RETRYING
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    tool_call.status = ToolExecutionStatus.FAILED
                    tool_call.error = f"Timeout after {self.timeout_per_tool}s"
                    self._record_failure(tool_name)

            except Exception as e:
                logger.error(f"❌ {tool_name} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    tool_call.status = ToolExecutionStatus.RETRYING
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    tool_call.status = ToolExecutionStatus.FAILED
                    tool_call.error = str(e)
                    self._record_failure(tool_name)

        tool_call.execution_time = time.time() - start_time
        return tool_call

    async def _execute_with_fallback(
        self,
        tool_call: ToolCall
    ) -> ToolCall:
        """
        Execute a tool with automatic fallback to alternatives if it fails.
        
        Args:
            tool_call: Primary tool to execute
            
        Returns:
            ToolCall with result from primary or fallback tool
        """
        # Try primary tool
        result = await self._execute_single_tool_with_retry(tool_call)

        if result.status == ToolExecutionStatus.SUCCESS:
            return result

        # Try fallback chain if enabled
        if not self.enable_fallbacks or tool_call.name not in self.fallback_chains:
            return result

        logger.info(f"🔄 Primary tool {tool_call.name} failed, trying fallbacks...")

        for fallback_name in self.fallback_chains[tool_call.name]:
            logger.info(f"🔄 Attempting fallback: {fallback_name}")

            # Create fallback tool call
            fallback_call = ToolCall(
                name=fallback_name,
                args=self._adapt_args_for_fallback(tool_call.name, fallback_name, tool_call.args),
                priority=tool_call.priority
            )

            fallback_result = await self._execute_single_tool_with_retry(fallback_call)

            if fallback_result.status == ToolExecutionStatus.SUCCESS:
                logger.info(f"✅ Fallback {fallback_name} succeeded!")
                # Update original tool call with fallback result
                tool_call.result = fallback_result.result
                tool_call.status = ToolExecutionStatus.SUCCESS
                tool_call.execution_time = fallback_result.execution_time
                return tool_call

        logger.warning(f"❌ All fallbacks exhausted for {tool_call.name}")
        return result

    def _adapt_args_for_fallback(
        self,
        primary_tool: str,
        fallback_tool: str,
        args: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Adapt arguments when switching to a fallback tool.
        
        Args:
            primary_tool: Name of the primary tool
            fallback_tool: Name of the fallback tool
            args: Arguments from primary tool
            
        Returns:
            Adapted arguments for fallback tool
        """
        # Example: Convert city name to coordinates for OpenMeteo fallback
        adapted_args = args.copy()

        # Add adaptation logic here based on tool compatibility
        # For now, pass through as-is since most tools have compatible interfaces

        return adapted_args

    def _is_valid_result(self, result: Any) -> bool:
        """
        Validate tool result to ensure it's usable.
        
        Args:
            result: Tool execution result
            
        Returns:
            True if result is valid, False otherwise
        """
        if result is None:
            return False

        # Check for error indicators
        if isinstance(result, dict):
            if result.get("error") and not result.get("success"):
                return False
            if result.get("success") is False:
                return False

        return True

    def _resolve_dependencies(self, tool_calls: list[ToolCall]) -> list[list[ToolCall]]:
        """
        Resolve tool dependencies and create execution batches.
        
        Tools with no dependencies run in parallel in the first batch.
        Tools that depend on others run in subsequent batches.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of batches, where each batch can be executed in parallel
        """
        # Create dependency graph
        remaining = tool_calls.copy()
        batches = []
        executed = set()

        while remaining:
            # Find tools with satisfied dependencies
            batch = []
            for tool_call in remaining:
                deps_satisfied = all(dep in executed for dep in tool_call.dependencies)
                if deps_satisfied:
                    batch.append(tool_call)

            if not batch:
                # Circular dependency or invalid dependency - execute remaining in order
                logger.warning("⚠️ Circular dependency detected, executing remaining tools in order")
                batches.append(remaining)
                break

            # Sort by priority (higher priority first)
            batch.sort(key=lambda x: x.priority, reverse=True)
            batches.append(batch)

            # Update executed set and remaining list
            for tool_call in batch:
                executed.add(tool_call.name)
                remaining.remove(tool_call)

        return batches

    async def orchestrate(
        self,
        tool_calls: list[ToolCall],
        parallel_execution: bool = True
    ) -> OrchestrationResult:
        """
        Orchestrate execution of multiple tools with dependencies.
        
        Args:
            tool_calls: List of tools to execute
            parallel_execution: Execute independent tools in parallel
            
        Returns:
            OrchestrationResult with execution details
        """
        start_time = time.time()
        logger.info(f"🎯 Orchestrating {len(tool_calls)} tool calls...")

        # Resolve dependencies
        batches = self._resolve_dependencies(tool_calls)
        logger.info(f"📊 Resolved {len(batches)} execution batches")

        all_results = {}
        all_errors = {}
        tools_executed = []

        # Execute batches
        for batch_idx, batch in enumerate(batches):
            logger.info(f"🔄 Executing batch {batch_idx + 1}/{len(batches)} ({len(batch)} tools)")

            if parallel_execution and len(batch) > 1:
                # Execute batch in parallel
                tasks = [self._execute_with_fallback(tool_call) for tool_call in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for tool_call, result in zip(batch, results):
                    if isinstance(result, Exception):
                        tool_call.status = ToolExecutionStatus.FAILED
                        tool_call.error = str(result)
                        all_errors[tool_call.name] = str(result)
                    elif isinstance(result, ToolCall):  # Success case
                        if result.status == ToolExecutionStatus.SUCCESS:
                            all_results[result.name] = result.result
                            tools_executed.append(result.name)
                        else:
                            all_errors[result.name] = result.error or "Unknown error"
                    else:
                        logger.warning(f"Unexpected result type: {type(result)}")
            else:
                # Execute sequentially
                for tool_call in batch:
                    result = await self._execute_with_fallback(tool_call)
                    if result.status == ToolExecutionStatus.SUCCESS:
                        all_results[result.name] = result.result
                        tools_executed.append(result.name)
                    else:
                        all_errors[result.name] = result.error or "Unknown error"

        # Generate context injection
        context_injection = self._format_results_for_context(all_results)

        total_time = time.time() - start_time
        success = len(all_results) > 0

        logger.info(f"✅ Orchestration complete: {len(tools_executed)} succeeded, {len(all_errors)} failed in {total_time:.2f}s")

        return OrchestrationResult(
            success=success,
            tools_executed=tools_executed,
            results=all_results,
            errors=all_errors,
            total_execution_time=total_time,
            context_injection=context_injection
        )

    def _format_results_for_context(self, results: dict[str, Any]) -> str:
        """
        Format tool results for injection into AI context.
        
        Args:
            results: Dictionary of tool results
            
        Returns:
            Formatted string for context injection
        """
        if not results:
            return ""

        context_parts = [
            "\n" + "=" * 80,
            "📊 RETRIEVED DATA (Use this information to answer the user's question):",
            "=" * 80
        ]

        for tool_name, result in results.items():
            context_parts.append(f"\n🔧 {tool_name}:")
            context_parts.append(self._format_single_result(result))

        context_parts.append("=" * 80 + "\n")

        return "\n".join(context_parts)

    def _format_single_result(self, result: Any) -> str:
        """Format a single tool result for human readability."""
        import json

        if isinstance(result, dict):
            try:
                return json.dumps(result, indent=2, ensure_ascii=False)
            except:
                return str(result)
        return str(result)


class ResponseValidator:
    """
    Validates and enhances AI responses for quality and consistency.
    
    Handles common issues with low-end models:
    - Malformed JSON in responses
    - Incomplete responses
    - Leaked internal function names
    - Inconsistent formatting
    """

    @staticmethod
    def validate_response(
        response: str,
        tools_used: list[str],
        min_length: int = 50
    ) -> tuple[bool, Optional[str]]:
        """
        Validate an AI response for quality issues.
        
        Args:
            response: AI-generated response text
            tools_used: List of tools that were called
            min_length: Minimum acceptable response length
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not response:
            return False, "Empty response"

        if len(response.strip()) < min_length:
            return False, f"Response too short (< {min_length} chars)"

        # Check for common error patterns
        error_patterns = [
            "error",
            "failed",
            "unable to",
            "could not",
            "cannot",
        ]

        response_lower = response.lower()
        if all(pattern in response_lower for pattern in ["error", "failed"]):
            return False, "Response indicates error"

        # Check for leaked function names (should be cleaned by provider)
        leaked_patterns = [
            "get_african_city_air_quality",
            "get_city_air_quality",
            "execute_tool",
            "function_call"
        ]

        for pattern in leaked_patterns:
            if pattern in response:
                return False, f"Leaked internal function: {pattern}"

        return True, None

    @staticmethod
    def enhance_response(
        response: str,
        tools_used: list[str],
        tool_results: dict[str, Any]
    ) -> str:
        """
        Enhance a response with additional context or formatting.
        
        Args:
            response: Original AI response
            tools_used: List of tools called
            tool_results: Results from tool execution
            
        Returns:
            Enhanced response
        """
        # If response is very short but we have good data, enhance it
        if len(response.strip()) < 100 and tool_results:
            logger.info("🔧 Enhancing short response with tool data")
            # Add a note about data sources
            sources = ResponseValidator._extract_sources(tools_used)
            if sources:
                response += f"\n\n*Data sources: {', '.join(sources)}*"

        return response

    @staticmethod
    def _extract_sources(tools_used: list[str]) -> list[str]:
        """Extract human-readable source names from tool names."""
        source_map = {
            "get_african_city_air_quality": "AirQo",
            "get_city_air_quality": "WAQI",
            "get_openmeteo_current_air_quality": "Open-Meteo",
            "search_web": "Web Search",
            "get_weather_forecast": "Weather Forecast"
        }

        sources = []
        for tool in tools_used:
            if tool in source_map:
                sources.append(source_map[tool])

        return list(set(sources))
