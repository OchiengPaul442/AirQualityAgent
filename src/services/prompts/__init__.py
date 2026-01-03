"""Prompts and system instructions for the AI agent."""

from .system_instructions import (
    BASE_SYSTEM_INSTRUCTION,
    STYLE_PRESETS,
    get_response_parameters,
    get_system_instruction,
)

__all__ = [
    "BASE_SYSTEM_INSTRUCTION",
    "STYLE_PRESETS",
    "get_system_instruction",
    "get_response_parameters",
]
