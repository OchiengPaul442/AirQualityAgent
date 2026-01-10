"""
Model Adapter Layer - Normalize Tool Calling Across Models

This module provides a unified interface for tool calling across different
model capabilities, especially for models with weak or no native tool support.

Strategy:
1. **Pattern Detection**: Identify tool requests in plain text responses
2. **Template Matching**: Use regex patterns to extract tool calls
3. **JSON Parsing**: Parse semi-structured tool requests
4. **Prompt Engineering**: Craft prompts that guide models to request tools correctly
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedToolCall:
    """Represents a tool call extracted from model output."""
    name: str
    arguments: dict[str, Any]
    confidence: float  # 0.0 to 1.0
    raw_text: str


class ModelAdapter:
    """
    Adapts different model capabilities to a unified tool calling interface.
    
    Handles:
    - Models with native tool calling (GPT-4, Gemini, Claude)
    - Models with weak tool calling (smaller models)
    - Models with no tool calling (pure text models)
    """

    # Patterns for detecting tool requests in plain text
    TOOL_PATTERNS = [
        # Pattern 1: JSON-like format
        r'\{[\s\n]*"tool"[\s\n]*:[\s\n]*"([^"]+)"[\s\n]*,[\s\n]*"args"[\s\n]*:[\s\n]*(\{[^\}]+\})[\s\n]*\}',

        # Pattern 2: Function call style
        r'(?:TOOL_CALL|USE_TOOL|CALL)[\s\n]*:?[\s\n]*([a-z_]+)\(([^\)]+)\)',

        # Pattern 3: Natural language request
        r'(?:I need to|Let me|Should|Will) (?:call|use|invoke|execute) (?:the )?([a-z_]+)(?: tool)?(?: with| using)? ([^.]+)',

        # Pattern 4: Markdown code block with tool call
        r'```(?:json|tool)?\s*\n\s*\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^\}]+\})\s*\}\s*```',
    ]

    # Known tools and their argument patterns
    TOOL_SIGNATURES = {
        "get_african_city_air_quality": {"city": str},
        "get_city_air_quality": {"city": str},
        "get_openmeteo_current_air_quality": {
            "latitude": float,
            "longitude": float,
            "timezone": str
        },
        "get_air_quality_forecast": {"city": str, "days": int},
        "get_weather_forecast": {"location": str, "days": int},
        "search_web": {"query": str, "max_results": int},
        "scrape_website": {"url": str},
        "generate_chart": {"data": dict, "chart_type": str, "title": str},
    }

    @classmethod
    def extract_tool_calls_from_text(
        cls,
        text: str,
        available_tools: list[str]
    ) -> list[ExtractedToolCall]:
        """
        Extract tool call requests from plain text responses.
        
        This is crucial for models that don't support native tool calling.
        
        Args:
            text: Model's text response
            available_tools: List of available tool names
            
        Returns:
            List of extracted tool calls
        """
        extracted_calls = []

        # Try each pattern
        for pattern_idx, pattern in enumerate(cls.TOOL_PATTERNS):
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                try:
                    tool_name = match.group(1).strip()
                    args_text = match.group(2).strip() if len(match.groups()) > 1 else "{}"

                    # Validate tool name
                    if tool_name not in available_tools:
                        # Try fuzzy matching
                        tool_name = cls._fuzzy_match_tool(tool_name, available_tools)
                        if not tool_name:
                            continue

                    # Parse arguments
                    arguments = cls._parse_arguments(args_text, tool_name)

                    confidence = 0.9 - (pattern_idx * 0.1)  # Earlier patterns = higher confidence

                    extracted_calls.append(ExtractedToolCall(
                        name=tool_name,
                        arguments=arguments,
                        confidence=confidence,
                        raw_text=match.group(0)
                    ))

                    logger.info(f"✅ Extracted tool call: {tool_name} (confidence: {confidence:.2f})")

                except Exception as e:
                    logger.warning(f"Failed to parse tool call match: {e}")
                    continue

        # Deduplicate
        unique_calls = cls._deduplicate_tool_calls(extracted_calls)

        return unique_calls

    @classmethod
    def _fuzzy_match_tool(cls, candidate: str, available_tools: list[str]) -> Optional[str]:
        """
        Fuzzy match a tool name candidate to available tools.
        
        Args:
            candidate: Candidate tool name
            available_tools: List of available tool names
            
        Returns:
            Matched tool name or None
        """
        candidate_lower = candidate.lower().replace("-", "_").replace(" ", "_")

        for tool in available_tools:
            tool_lower = tool.lower()

            # Exact match
            if candidate_lower == tool_lower:
                return tool

            # Partial match
            if candidate_lower in tool_lower or tool_lower in candidate_lower:
                # Check if it's a reasonable match (> 60% overlap)
                overlap = len(set(candidate_lower) & set(tool_lower))
                if overlap / max(len(candidate_lower), len(tool_lower)) > 0.6:
                    logger.info(f"Fuzzy matched '{candidate}' to '{tool}'")
                    return tool

        return None

    @classmethod
    def _parse_arguments(cls, args_text: str, tool_name: str) -> dict[str, Any]:
        """
        Parse tool arguments from various formats.
        
        Args:
            args_text: Arguments as text
            tool_name: Tool name for signature validation
            
        Returns:
            Parsed arguments dictionary
        """
        # Try JSON parsing first
        try:
            args = json.loads(args_text)
            if isinstance(args, dict):
                return cls._validate_arguments(args, tool_name)
        except json.JSONDecodeError:
            pass

        # Try key=value parsing
        try:
            args = {}
            # Parse patterns like: city="London", days=3
            pairs = re.findall(r'(\w+)\s*[=:]\s*["\']?([^,"\']+)["\']?', args_text)
            for key, value in pairs:
                # Try to infer type
                args[key] = cls._infer_value_type(value, key, tool_name)

            if args:
                return cls._validate_arguments(args, tool_name)
        except Exception as e:
            logger.warning(f"Failed to parse key=value arguments: {e}")

        # Fallback: return raw text as single argument
        return {"query": args_text} if args_text else {}

    @classmethod
    def _infer_value_type(cls, value: str, key: str, tool_name: str) -> Any:
        """Infer the correct type for an argument value."""
        value = value.strip().strip('"\'')

        # Get expected type from signature
        if tool_name in cls.TOOL_SIGNATURES:
            expected_type = cls.TOOL_SIGNATURES[tool_name].get(key)

            if expected_type == int:
                try:
                    return int(value)
                except ValueError:
                    pass
            elif expected_type == float:
                try:
                    return float(value)
                except ValueError:
                    pass

        # Try int
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Try boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Default to string
        return value

    @classmethod
    def _validate_arguments(cls, args: dict[str, Any], tool_name: str) -> dict[str, Any]:
        """
        Validate and fix argument types based on tool signature.
        
        Args:
            args: Arguments to validate
            tool_name: Tool name
            
        Returns:
            Validated arguments
        """
        if tool_name not in cls.TOOL_SIGNATURES:
            return args

        signature = cls.TOOL_SIGNATURES[tool_name]
        validated = {}

        for key, expected_type in signature.items():
            if key in args:
                value = args[key]

                # Convert to expected type
                try:
                    if expected_type == int and not isinstance(value, int):
                        validated[key] = int(value)
                    elif expected_type == float and not isinstance(value, float):
                        validated[key] = float(value)
                    elif expected_type == str and not isinstance(value, str):
                        validated[key] = str(value)
                    else:
                        validated[key] = value
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {key}={value} to {expected_type}")
                    validated[key] = value
            else:
                # Add default value if missing
                if key == "days":
                    validated[key] = 3
                elif key == "max_results":
                    validated[key] = 5
                elif key == "timezone":
                    validated[key] = "auto"

        # Preserve extra arguments
        for key, value in args.items():
            if key not in validated:
                validated[key] = value

        return validated

    @classmethod
    def _deduplicate_tool_calls(cls, calls: list[ExtractedToolCall]) -> list[ExtractedToolCall]:
        """Remove duplicate tool calls, keeping highest confidence."""
        if not calls:
            return []

        # Group by tool name
        by_name = {}
        for call in calls:
            key = (call.name, json.dumps(call.arguments, sort_keys=True))
            if key not in by_name or call.confidence > by_name[key].confidence:
                by_name[key] = call

        return list(by_name.values())

    @classmethod
    def create_tool_prompt_template(cls, available_tools: list[str]) -> str:
        """
        Create a prompt template that helps models request tools correctly.
        
        Args:
            available_tools: List of available tool names
            
        Returns:
            Prompt template string
        """
        tool_docs = []
        for tool in available_tools:
            if tool in cls.TOOL_SIGNATURES:
                args = cls.TOOL_SIGNATURES[tool]
                args_str = ", ".join([f"{k}: {v.__name__}" for k, v in args.items()])
                tool_docs.append(f"- {tool}({args_str})")

        template = f"""
You have access to the following tools:

{chr(10).join(tool_docs)}

To use a tool, respond with a JSON object in this format:
```json
{{
  "tool": "tool_name",
  "args": {{
    "arg1": "value1",
    "arg2": "value2"
  }}
}}
```

After using a tool, you'll receive the results and can then provide your answer.
"""
        return template


class PromptEnhancer:
    """
    Enhance prompts to improve tool usage for low-end models.
    
    Techniques:
    - Few-shot examples of correct tool usage
    - Explicit instructions for when to use tools
    - Structured output formatting
    """

    @staticmethod
    def enhance_system_prompt(
        original_prompt: str,
        available_tools: list[str],
        add_examples: bool = True
    ) -> str:
        """
        Enhance system prompt for better tool usage.
        
        Args:
            original_prompt: Original system prompt
            available_tools: List of available tools
            add_examples: Whether to add few-shot examples
            
        Returns:
            Enhanced prompt
        """
        tool_template = ModelAdapter.create_tool_prompt_template(available_tools)

        enhanced = original_prompt

        # Add tool instructions
        enhanced += "\n\n" + tool_template

        # Add few-shot examples if requested
        if add_examples:
            enhanced += "\n\n" + PromptEnhancer._get_few_shot_examples()

        return enhanced

    @staticmethod
    def _get_few_shot_examples() -> str:
        """Get few-shot examples of correct tool usage."""
        return """
**Examples of correct tool usage:**

User: "What's the air quality in Kampala?"
Assistant: I'll check the air quality for you.
```json
{
  "tool": "get_african_city_air_quality",
  "args": {"city": "Kampala"}
}
```

User: "Compare London and Paris air quality"
Assistant: I'll retrieve air quality data for both cities.
```json
{
  "tool": "get_city_air_quality",
  "args": {"city": "London"}
}
```
```json
{
  "tool": "get_city_air_quality",
  "args": {"city": "Paris"}
}
```

User: "Search for air pollution studies in 2025"
Assistant: I'll search for recent studies.
```json
{
  "tool": "search_web",
  "args": {"query": "air pollution studies 2025", "max_results": 5}
}
```
"""


class ResponsePostProcessor:
    """
    Post-process model responses to clean up and enhance quality.
    
    Handles:
    - Removing leaked internal details
    - Fixing markdown formatting
    - Cleaning up redundant information
    """

    @staticmethod
    def clean_response(response: str) -> str:
        """
        Clean up a model response.
        
        Args:
            response: Raw model response
            
        Returns:
            Cleaned response
        """
        if not response:
            return response

        # Remove tool call artifacts
        response = re.sub(
            r'```(?:json|tool)?\s*\n\s*\{[^\}]+\}\s*```',
            '',
            response,
            flags=re.MULTILINE
        )

        # Remove duplicate newlines
        response = re.sub(r'\n{3,}', '\n\n', response)

        # Remove leaked function names
        leaked_patterns = [
            r'\bget_african_city_air_quality\b',
            r'\bget_city_air_quality\b',
            r'\bexecute_tool\b',
            r'\bfunction_call\b',
            r'\btool_executor\b',
        ]

        for pattern in leaked_patterns:
            response = re.sub(pattern, '', response, flags=re.IGNORECASE)

        # Clean up whitespace
        response = response.strip()

        return response

    @staticmethod
    def enhance_markdown_formatting(response: str) -> str:
        """
        Enhance markdown formatting in response.
        
        Args:
            response: Response text
            
        Returns:
            Response with improved formatting
        """
        # Ensure proper spacing around headers
        response = re.sub(r'(#+\s+[^\n]+)\n([^\n])', r'\1\n\n\2', response)

        # Ensure proper list formatting
        response = re.sub(r'(\n\s*[-*]\s+[^\n]+)\n([^\n\s-*])', r'\1\n\n\2', response)

        return response
