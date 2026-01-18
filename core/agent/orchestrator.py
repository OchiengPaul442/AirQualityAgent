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
from typing import Any

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
    result: Any | None = None
    error: str | None = None
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
        timeout_per_tool: float = 20.0  # Increased to 20 for reliability
    ):
        """
        Initialize the orchestrator.
        
        Args:
            tool_executor: ToolExecutor instance
            max_retries: Maximum retry attempts per tool
            retry_delay: Initial delay between retries (exponential backoff)
            enable_fallbacks: Enable automatic fallback to alternative tools
            timeout_per_tool: Timeout for each tool execution (20s for web searches)
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

        # Fallback chains for tools (Audit Requirement: 5-level cascade)
        self.fallback_chains = {
            "get_african_city_air_quality": [
                "get_city_air_quality",  # Level 2: WAQI as fallback
                "get_openmeteo_current_air_quality",  # Level 3: OpenMeteo
                "search_web",  # Level 4: Web search for city data
                "get_seasonal_context"  # Level 5: Seasonal estimates (Africa intelligence)
            ],
            "get_city_air_quality": [
                "get_openmeteo_current_air_quality",  # Level 2: OpenMeteo as fallback
                "search_web",  # Level 3: Web search
                "get_seasonal_context"  # Level 4: Seasonal estimates
            ],
            "search_web": [
                "scrape_website"  # If search fails, try scraping known URLs
            ]
        }

        # Tool relevance scoring (Audit Requirement: Confidence scoring 0-1)
        self.tool_capabilities = {
            "get_african_city_air_quality": {
                "regions": ["africa"],
                "metrics": ["pm2.5", "pm10", "aqi"],
                "cities": ["nairobi", "kampala", "lagos", "accra", "addis ababa", "dar es salaam", "kigali"],
                "realtime": True,
                "historical": False,
                "confidence": 0.95  # AirQo is primary source for Africa
            },
            "get_city_air_quality": {
                "regions": ["global"],
                "metrics": ["pm2.5", "pm10", "o3", "no2", "so2", "co", "aqi"],
                "cities": ["*"],  # Worldwide
                "realtime": True,
                "historical": False,
                "confidence": 0.85  # WAQI is reliable globally
            },
            "get_openmeteo_current_air_quality": {
                "regions": ["global"],
                "metrics": ["pm2.5", "pm10", "o3", "no2", "so2", "aqi"],
                "cities": ["*"],
                "realtime": True,
                "historical": False,
                "confidence": 0.75  # Open-Meteo is modeled data
            },
            "get_weather_forecast": {
                "regions": ["global"],
                "metrics": ["temperature", "humidity", "wind", "precipitation"],
                "cities": ["*"],
                "realtime": True,
                "historical": False,
                "confidence": 0.90  # Weather is reliable
            },
            "search_web": {
                "regions": ["global"],
                "metrics": ["*"],  # Can search for anything
                "cities": ["*"],
                "realtime": False,
                "historical": True,
                "confidence": 0.60  # Search is unpredictable
            }
        }

    def evaluate_query_requirements(self, query: str) -> dict[str, Any]:
        """
        Intelligent query parsing to determine tool requirements.
        
        Per audit requirement: "Parse: locations (count), time ranges, data types, comparison intent"
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with parsed requirements:
            - locations: List of city names detected
            - location_count: Number of locations
            - time_range: "current", "forecast", "historical", or "comparison"
            - metrics: List of metrics requested (aqi, pm2.5, etc.)
            - comparison_intent: Boolean indicating if comparing multiple locations
            - is_african_city: Boolean for each location
            - complexity: "simple", "moderate", "complex"
        """
        query_lower = query.lower()

        # Known African cities
        african_cities = [
            "nairobi", "kampala", "lagos", "accra", "addis ababa", "dar es salaam",
            "kigali", "johannesburg", "cape town", "cairo", "casablanca", "tunis"
        ]

        # Detect locations
        locations = []
        is_african = []
        for city in african_cities:
            if city in query_lower:
                locations.append(city.title())
                is_african.append(True)

        # Generic location detection (vs, versus, compared to, etc.)
        if " vs " in query_lower or " versus " in query_lower or " compared to " in query_lower:
            comparison_intent = True
        else:
            comparison_intent = len(locations) > 1

        # Detect time range
        time_range = "current"  # Default
        if any(word in query_lower for word in ["forecast", "tomorrow", "next week", "upcoming"]):
            time_range = "forecast"
        elif any(word in query_lower for word in ["yesterday", "last week", "trend", "history", "past"]):
            time_range = "historical"
        elif any(word in query_lower for word in ["weekend", "week", "daily", "hourly"]):
            time_range = "comparison"

        # Detect metrics
        metrics = []
        metric_keywords = {
            "aqi": ["aqi", "air quality index", "quality"],
            "pm2.5": ["pm2.5", "pm 2.5", "fine particles", "particulate"],
            "pm10": ["pm10", "pm 10", "coarse particles"],
            "o3": ["ozone", "o3"],
            "no2": ["nitrogen dioxide", "no2"],
            "so2": ["sulfur dioxide", "so2"],
            "co": ["carbon monoxide", "co"],
        }
        for metric, keywords in metric_keywords.items():
            if any(kw in query_lower for kw in keywords):
                metrics.append(metric)

        # If no specific metrics, default to AQI
        if not metrics:
            metrics.append("aqi")

        # Determine complexity
        complexity = "simple"
        if len(locations) > 2 or (comparison_intent and time_range == "historical"):
            complexity = "complex"
        elif len(locations) == 2 or time_range in ["forecast", "comparison"]:
            complexity = "moderate"

        return {
            "locations": locations,
            "location_count": len(locations),
            "time_range": time_range,
            "metrics": metrics,
            "comparison_intent": comparison_intent,
            "is_african_city": is_african,
            "complexity": complexity,
            "raw_query": query
        }

    def score_tool_relevance(self, tool_name: str, requirements: dict[str, Any]) -> float:
        """
        Score tool relevance (0-1) based on query requirements.
        
        Per audit requirement: "Score: Tool relevance 0-1 for EACH requirement"
        
        Args:
            tool_name: Name of the tool to score
            requirements: Parsed query requirements from evaluate_query_requirements()
            
        Returns:
            Relevance score 0.0-1.0 (higher = more relevant)
        """
        if tool_name not in self.tool_capabilities:
            return 0.5  # Unknown tool, neutral score

        capabilities = self.tool_capabilities[tool_name]
        score = capabilities["confidence"]  # Start with base confidence

        # Boost for African cities if tool specializes in Africa
        if "africa" in capabilities["regions"] and any(requirements.get("is_african_city", [])):
            score *= 1.2  # 20% boost for specialized tool

        # Boost for realtime if query is current
        if requirements.get("time_range") == "current" and capabilities.get("realtime"):
            score *= 1.1  # 10% boost for realtime capability

        # Penalty for historical if tool doesn't support it
        if requirements.get("time_range") == "historical" and not capabilities.get("historical"):
            score *= 0.7  # 30% penalty

        # Cap at 1.0
        return min(score, 1.0)

    def build_execution_plan(self, requirements: dict[str, Any]) -> list[ToolCall]:
        """
        Build intelligent execution plan with dependencies and priorities.
        
        Per audit requirement: "Graph: Execution dependencies (parallel vs sequential)"
        
        Args:
            requirements: Parsed query requirements
            
        Returns:
            List of ToolCall objects with priorities and dependencies
        """
        plan = []

        # Determine primary tools based on requirements
        locations = requirements.get("locations", [])
        is_african = requirements.get("is_african_city", [])
        comparison_intent = requirements.get("comparison_intent", False)

        if locations:
            for idx, location in enumerate(locations):
                # Choose tool based on location
                if idx < len(is_african) and is_african[idx]:
                    tool_name = "get_african_city_air_quality"
                    priority = 100  # Highest priority for African cities
                else:
                    tool_name = "get_city_air_quality"
                    priority = 90  # High priority for global cities

                # Score relevance
                relevance = self.score_tool_relevance(tool_name, requirements)

                # Create tool call
                tool_call = ToolCall(
                    name=tool_name,
                    args={"city": location},
                    priority=int(priority * relevance),
                    dependencies=[]  # Parallel execution for multiple cities
                )
                plan.append(tool_call)

        # Add weather if forecast requested
        if requirements.get("time_range") == "forecast":
            for location in locations:
                tool_call = ToolCall(
                    name="get_weather_forecast",
                    args={"city": location, "days": 3},
                    priority=80,
                    dependencies=[]  # Can run in parallel
                )
                plan.append(tool_call)

        # Add search for historical or if no locations detected
        if requirements.get("time_range") == "historical" or not locations:
            tool_call = ToolCall(
                name="search_web",
                args={"query": requirements.get("raw_query", "")},
                priority=60,
                dependencies=[]  # Can run in parallel
            )
            plan.append(tool_call)

        return plan

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

            except TimeoutError:
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

                for tool_call, result in zip(batch, results, strict=False):
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
    ) -> tuple[bool, str | None]:
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

        # Always add detailed sources section when search_web was used
        if "search_web" in tools_used and "search_web" in tool_results:
            search_result = tool_results["search_web"]
            if search_result.get("success") and search_result.get("results"):
                results = search_result["results"][:5]  # Top 5 results

                # Note: Source formatting is handled by MarkdownFormatter.format_response()
                # which properly consolidates all sources into a single "Sources & References" section.
                # We no longer add sources here to prevent duplication.

                # The LLM is instructed to use "Source: Title (URL)" inline format,
                # and MarkdownFormatter will extract and consolidate these automatically.

                logger.info(f"✓ Search returned {len(results)} results for context enrichment")
            else:
                logger.debug(f"Search result: success={search_result.get('success')}, has_results={bool(search_result.get('results'))}")

        # If response is very short but we have good data, enhance it
        elif len(response.strip()) < 100 and tool_results:
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
