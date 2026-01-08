"""
Enhanced Reasoning Engine for AI Agent - Human-Like Communication

Provides natural, conversational transparency into the agent's thinking process,
similar to ChatGPT's reasoning display. Uses professional yet approachable language.
"""

import logging
from datetime import datetime
from typing import Any
import time

logger = logging.getLogger(__name__)


class ReasoningStep:
    """Represents a single reasoning step with natural human-like phrasing."""
    
    def __init__(self, content: str, step_type: str = "thinking", duration_ms: int = 0):
        """
        Initialize a reasoning step with conversational language.
        
        Args:
            content: Natural language description of what the agent is thinking/doing
            step_type: Type of step (thinking, searching, analyzing, processing)
            duration_ms: Time taken for this step in milliseconds
        """
        self.content = content
        self.step_type = step_type
        self.timestamp = datetime.now()
        self.duration_ms = duration_ms
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "content": self.content,
            "type": self.step_type,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms
        }
    
    def to_markdown(self) -> str:
        """Convert to markdown format with natural language."""
        return self.content


class ReasoningEngine:
    """
    Manages human-like reasoning and thinking process for the AI agent.
    
    Provides natural, conversational transparency similar to ChatGPT's reasoning display.
    Professional yet approachable communication style.
    """
    
    def __init__(self, human_like: bool = True, verbose: bool = False):
        """Initialize reasoning engine.
        
        Args:
            human_like: Use natural, conversational language (like ChatGPT)
            verbose: Show detailed steps or keep it concise
        """
        self.steps: list[ReasoningStep] = []
        self.enabled = True
        self.human_like = human_like
        self.verbose = verbose
        self.total_thinking_time_ms = 0
        self.start_time = None
    
    def start_thinking(self) -> None:
        """Start tracking thinking time."""
        self.start_time = time.time()
    
    def add_step(self, content: str, step_type: str = "thinking", duration_ms: int = 0) -> None:
        """
        Add a reasoning step with natural language.
        
        Args:
            content: Natural description in conversational tone
            step_type: Type of step (thinking, searching, analyzing, processing)
            duration_ms: Processing time in milliseconds
        """
        if not self.enabled:
            return
        
        step = ReasoningStep(content, step_type, duration_ms)
        self.steps.append(step)
        self.total_thinking_time_ms += duration_ms
        
        if self.verbose:
            logger.debug(f"[Reasoning] {content} ({duration_ms}ms)")
    
    def think(self, content: str) -> None:
        """Add a thinking step - initial analysis."""
        self.add_step(f"Let me think about this... {content}", "thinking")
    
    def search(self, content: str) -> None:
        """Add a searching step - gathering information."""
        self.add_step(f"I'll need to look up {content}", "searching")
    
    def analyze(self, content: str) -> None:
        """Add an analyzing step - processing data."""
        self.add_step(f"Looking at {content}", "analyzing")
    
    def process(self, content: str) -> None:
        """Add a processing step - working on the task."""
        self.add_step(f"Now I'm {content}", "processing")
    
    def conclude(self, content: str) -> None:
        """Add a concluding step - wrapping up."""
        self.add_step(f"Based on what I found, {content}", "concluding")
    
    def clear(self) -> None:
        """Clear all reasoning steps."""
        self.steps = []
        self.total_thinking_time_ms = 0
    
    def get_all_steps(self) -> list[ReasoningStep]:
        """Get all reasoning steps."""
        return self.steps
    
    def to_markdown(self, include_in_response: bool = False) -> str:
        """
        Convert reasoning steps to natural markdown format.
        
        Args:
            include_in_response: Include reasoning in the main response
        
        Returns:
            Markdown formatted string
        """
        if not self.steps:
            return ""
        
        if not include_in_response:
            return ""  # Reasoning is separate from response
        
        parts = []
        
        # Natural introduction
        parts.append("*Thinking through your question...*\n")
        
        # Add each step naturally
        for step in self.steps:
            parts.append(step.to_markdown())
        
        parts.append("\n---\n")
        
        return "\n".join(parts)
    
    def to_compact_markdown(self) -> str:
        """
        Convert reasoning steps to collapsible markdown format.
        
        Returns:
            Compact markdown with collapsible details
        """
        if not self.steps:
            return ""
        
        parts = [
            "<details>",
            "<summary>💭 See how I thought through this</summary>\n"
        ]
        
        for step in self.steps:
            parts.append(f"• {step.content}")
        
        parts.append("\n</details>\n")
        
        return "\n".join(parts)
    
    def to_json(self) -> dict[str, Any]:
        """
        Convert reasoning to JSON format for API responses.
        
        Returns:
            Dictionary with reasoning data
        """
        return {
            "enabled": self.enabled,
            "steps": [step.to_dict() for step in self.steps],
            "total_steps": len(self.steps),
            "total_thinking_time_ms": self.total_thinking_time_ms
        }
    
    def get_summary(self) -> str:
        """Get a brief summary of the reasoning process."""
        if not self.steps:
            return "No reasoning steps recorded"
        
        return f"Completed {len(self.steps)} thinking steps in {self.total_thinking_time_ms}ms"


def create_human_reasoning_engine() -> ReasoningEngine:
    """
    Factory function to create a human-like reasoning engine.
    
    Returns:
        ReasoningEngine configured for natural communication
    """
    return ReasoningEngine(human_like=True, verbose=False)
