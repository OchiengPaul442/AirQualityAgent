"""
Real-time Chain-of-Thought Streaming

This module implements transparent, real-time thought process streaming as recommended by
Anthropic's guide to building effective agents. It shows the agent's planning steps as
they happen, not after completion.

Key principles:
1. **Transparency First** - Users see how the agent thinks in real-time
2. **Simple & Direct** - No over-engineering, straightforward event emission
3. **Optimized for Low-Cost Models** - Works great with models that don't have native reasoning
4. **Resource Efficient** - Minimal overhead, suitable for production

The thought stream exposes:
- Query understanding and intent classification
- Tool selection and data source strategy  
- Data retrieval progress and results
- Response synthesis and quality checks
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThoughtType(Enum):
    """Types of thought events that can be emitted"""
    QUERY_ANALYSIS = "query_analysis"
    TOOL_SELECTION = "tool_selection"
    TOOL_EXECUTION = "tool_execution"
    DATA_RETRIEVAL = "data_retrieval"
    RESPONSE_SYNTHESIS = "response_synthesis"
    ERROR = "error"
    COMPLETE = "complete"


class ThoughtStream:
    """
    Manages real-time streaming of agent's thought process.
    
    This is a lightweight, async-friendly event emitter that allows
    various parts of the agent (orchestrator, tools, providers) to
    broadcast their reasoning steps as they work.
    
    Example usage:
        stream = ThoughtStream()
        
        # Start streaming thoughts
        async for event in stream.stream():
            print(f"Thought: {event['title']}")
            
        # In another coroutine, emit thoughts
        await stream.emit(
            thought_type=ThoughtType.QUERY_ANALYSIS,
            title="Understanding your question",
            details={"intent": "air_quality_data", "complexity": "simple"}
        )
    """

    def __init__(self):
        """Initialize the thought stream"""
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._enabled = False
        self._closed = False

    def enable(self):
        """Enable thought streaming"""
        self._enabled = True
        self._closed = False
        logger.info("🧠 Thought streaming ENABLED")

    def disable(self):
        """Disable thought streaming"""
        self._enabled = False
        logger.info("🧠 Thought streaming DISABLED")

    def is_enabled(self) -> bool:
        """Check if streaming is enabled"""
        return self._enabled

    async def emit(
        self,
        thought_type: ThoughtType,
        title: str,
        details: dict[str, Any],
        progress: float | None = None
    ):
        """
        Emit a thought event to the stream (real-time)
        
        Args:
            thought_type: Type of thought being emitted
            title: Human-readable title for this thought
            details: Detailed information about the thought process
            progress: Optional progress percentage (0.0 to 1.0)
        """
        if not self._enabled or self._closed:
            logger.debug(f"Skipping thought emission (enabled={self._enabled}, closed={self._closed}): {thought_type.value} - {title}")
            return

        event = {
            "type": thought_type.value,
            "title": title,
            "details": details,
            "timestamp": datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
            "progress": progress
        }

        try:
            await self._queue.put(event)
            logger.info(f"💭 Emitted thought: {thought_type.value} - {title}")
        except Exception as e:
            logger.error(f"Failed to emit thought: {e}")

    async def emit_query_analysis(
        self,
        query: str,
        intent: str,
        complexity: str,
        requires_data: bool
    ):
        """Emit query analysis thought"""
        await self.emit(
            thought_type=ThoughtType.QUERY_ANALYSIS,
            title="Understanding your question",
            details={
                "query_preview": query[:150],
                "detected_intent": intent,
                "complexity": complexity,
                "requires_external_data": requires_data,
                "reasoning": f"This is a {complexity} {intent} query"
            }
        )

    async def emit_tool_selection(
        self,
        query_type: str,
        selected_tools: list[str],
        confidence: float,
        rationale: str
    ):
        """Emit tool selection thought"""
        await self.emit(
            thought_type=ThoughtType.TOOL_SELECTION,
            title="Selecting data sources",
            details={
                "query_classification": query_type,
                "confidence_score": confidence,
                "selected_sources": selected_tools,
                "selection_rationale": rationale,
                "fallback_available": True
            }
        )

    async def emit_tool_execution(
        self,
        tool_name: str,
        status: str,
        result_summary: str | None = None,
        error: str | None = None
    ):
        """Emit tool execution progress"""
        await self.emit(
            thought_type=ThoughtType.TOOL_EXECUTION,
            title=f"Executing: {tool_name}",
            details={
                "tool": tool_name,
                "status": status,
                "result": result_summary,
                "error": error
            }
        )

    async def emit_data_retrieval(
        self,
        sources: list[str],
        data_size: int,
        quality: str,
        integration_method: str
    ):
        """Emit data retrieval completion"""
        await self.emit(
            thought_type=ThoughtType.DATA_RETRIEVAL,
            title="Retrieved and processed data",
            details={
                "sources_queried": sources,
                "data_size_chars": data_size,
                "quality_assessment": quality,
                "integration_method": integration_method
            }
        )

    async def emit_response_synthesis(
        self,
        approach: str,
        sources_used: list[str],
        token_usage: int | None = None
    ):
        """Emit response synthesis start"""
        await self.emit(
            thought_type=ThoughtType.RESPONSE_SYNTHESIS,
            title="Synthesizing response",
            details={
                "synthesis_approach": approach,
                "data_sources": sources_used,
                "estimated_tokens": token_usage
            }
        )

    async def emit_error(
        self,
        error_message: str,
        recoverable: bool = False,
        fallback_action: str | None = None
    ):
        """Emit error in thought process"""
        await self.emit(
            thought_type=ThoughtType.ERROR,
            title="Encountered an issue",
            details={
                "error": error_message,
                "recoverable": recoverable,
                "fallback": fallback_action
            }
        )

    async def complete(self, summary: dict[str, Any] | None = None):
        """
        Signal completion of thought stream
        
        Args:
            summary: Optional summary of the thinking process
        """
        if not self._enabled or self._closed:
            return

        await self.emit(
            thought_type=ThoughtType.COMPLETE,
            title="Response ready",
            details=summary or {"status": "completed"}
        )

        # Mark stream as closed
        self._closed = True
        logger.info("🧠 Thought stream COMPLETED")

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """
        Stream thought events in real-time
        
        Yields:
            Thought event dictionaries as they occur
        """
        timeout_count = 0
        max_timeouts = 300  # 30 seconds max wait (300 * 0.1s)

        while not self._closed:
            try:
                # Wait for next event with timeout
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                timeout_count = 0  # Reset timeout counter on successful event

                yield event

                # Check if this is the completion event
                if event.get("type") == ThoughtType.COMPLETE.value:
                    logger.debug("Received COMPLETE event, ending stream")
                    break

            except TimeoutError:
                # No events yet, continue waiting
                timeout_count += 1

                # If we've been waiting too long and stream is not enabled, break
                if timeout_count > max_timeouts:
                    logger.warning(f"Stream timeout after {max_timeouts * 0.1}s, ending stream")
                    break

                # If stream is closed, break immediately
                if self._closed:
                    break

                continue
            except Exception as e:
                logger.error(f"Error streaming thought: {e}")
                break

    def clear(self):
        """Clear all pending events (useful between requests)"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def close(self):
        """Close the thought stream and mark as complete"""
        self._closed = True
        self._enabled = False
        logger.debug("🧠 Thought stream CLOSED")


class ThoughtStreamContext:
    """
    Context manager for thought streaming
    
    Usage:
        async with ThoughtStreamContext() as stream:
            await stream.emit_query_analysis(...)
            # Do work
            async for thought in stream.stream():
                print(thought)
    """

    def __init__(self):
        self.stream = ThoughtStream()

    async def __aenter__(self):
        self.stream.enable()
        return self.stream

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.stream.emit_error(
                error_message=str(exc_val),
                recoverable=False
            )
        await self.stream.complete()
        return False
