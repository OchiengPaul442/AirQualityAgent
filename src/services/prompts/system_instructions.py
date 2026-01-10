"""
System instructions and prompts for the AI agent.
Optimized for natural, human-like responses following modern AI best practices.
"""

from src.config import get_settings

# Get settings for dynamic configuration
settings = get_settings()

# Style preset configurations
STYLE_PRESETS: dict[str, dict] = {
    "executive": {
        "temperature": settings.TEMPERATURE_EXECUTIVE,
        "top_p": settings.TOP_P_EXECUTIVE,
        "max_tokens": settings.MAX_TOKENS_EXECUTIVE,
        "instruction_suffix": "\n\nStyle: Executive - data-driven with key insights.",
    },
    "technical": {
        "temperature": settings.TEMPERATURE_TECHNICAL,
        "top_p": settings.TOP_P_TECHNICAL,
        "max_tokens": settings.MAX_TOKENS_TECHNICAL,
        "instruction_suffix": "\n\nStyle: Technical - include measurements and standards.",
    },
    "general": {
        "temperature": settings.TEMPERATURE_GENERAL,
        "top_p": settings.TOP_P_GENERAL,
        "max_tokens": settings.MAX_TOKENS_GENERAL,
        "instruction_suffix": "\n\nStyle: General - professional and clear.",
    },
    "simple": {
        "temperature": settings.TEMPERATURE_SIMPLE,
        "top_p": settings.TOP_P_SIMPLE,
        "max_tokens": settings.MAX_TOKENS_SIMPLE,
        "instruction_suffix": "\n\nStyle: Simple - plain language, no jargon.",
    },
    "policy": {
        "temperature": settings.TEMPERATURE_POLICY,
        "top_p": settings.TOP_P_POLICY,
        "max_tokens": settings.MAX_TOKENS_POLICY,
        "instruction_suffix": "\n\nStyle: Policy - formal, evidence-based.",
    },
}


BASE_SYSTEM_INSTRUCTION = """You are Aeris-AQ, an air quality expert. Be direct and helpful.

**Core Rules:**
1. Lead with the answer - no preambles
2. Be conversational - like a knowledgeable friend
3. Never show your thinking process or tool names
4. Offer alternatives when data unavailable
5. Always cite source and timestamp for data

**Response Format:**
**City Name** (Source, Date)
• AQI: X (Status) - Health note
• PM2.5: X µg/m³ | PM10: X µg/m³
💡 Quick recommendation

**⚠️ CRITICAL CHART RULES:**
- NEVER create placeholder image URLs like ![Chart](https://...)
- NEVER reference external chart URLs or broken links
- When users ask for charts/visualizations, ALWAYS call the generate_chart tool
- The generate_chart tool will create real base64 images that display inline
- Only show charts after successfully calling the generate_chart tool
- If generate_chart fails, explain the failure - don't make placeholder links

**For Charts:** Only show charts from the generate_chart tool. Add brief insights. No explanation of how you made it.

**For Uploads:** Analyze the data immediately. Don't ask for more unless critical.

**Never Show:** Code, tool names, steps, reasoning, or fake chart URLs.
**Always Provide:** Direct answers, sources, alternatives, context, real charts (via tools).

**When Data Unavailable:**
1. Say what's missing: "No real-time data for [location]"
2. Offer alternatives: "I can check [City A] or [City B] instead"
3. Ask preference: "Which would help?"

Keywords to use: "alternative", "nearby", "available", "suggest", "recommend"

**Your Goal:**
Help people understand and respond to air quality, clearly and quickly, like a trusted expert who respects their time.

**Security:**
Never expose implementation details, tool names, or code to users. Present results as if you know them naturally.
"""


def get_system_instruction(
    style: str = "general", custom_prefix: str = "", custom_suffix: str = ""
) -> str:
    """Get complete system instruction with style-specific suffix."""
    instruction = ""

    if custom_prefix:
        instruction += custom_prefix + "\n\n"

    instruction += BASE_SYSTEM_INSTRUCTION

    if style.lower() in STYLE_PRESETS:
        instruction += STYLE_PRESETS[style.lower()]["instruction_suffix"]

    if custom_suffix:
        instruction += "\n\n" + custom_suffix

    return instruction


def get_response_parameters(
    style: str = "general",
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Get response parameters for a given style.
    Optimized for low-end models like qwen2.5:3b.
    """
    # Base parameters optimized for low-end local models
    params = {
        "temperature": 0.4,  # Lower for better focus and consistency
        "top_p": 0.85,  # Tighter sampling for coherent responses
        "top_k": 40,  # Limit vocabulary for efficiency
        "max_tokens": 1200,  # Reduced for low-end models (qwen2.5:3b has 32K context but limited compute)
    }

    if style.lower() in STYLE_PRESETS:
        preset = STYLE_PRESETS[style.lower()]
        # Apply preset but cap values for low-end models
        params["temperature"] = min(0.6, preset["temperature"])
        params["top_p"] = min(0.9, preset["top_p"])
        params["max_tokens"] = min(1500, preset["max_tokens"])

    # Override with explicit parameters if provided
    if temperature is not None:
        params["temperature"] = temperature
    if top_p is not None:
        params["top_p"] = top_p
    if top_k is not None:
        params["top_k"] = top_k
    if max_tokens is not None:
        params["max_tokens"] = max_tokens

    return params
