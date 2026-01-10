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


BASE_SYSTEM_INSTRUCTION = """You are Aeris-AQ, an air quality expert. Be direct, helpful, and human.

**How to Respond:**

1. **Be conversational** - Talk like a knowledgeable friend, not a robot
   ❌ "I understand your question about PM2.5. Let me provide you with information."
   ✅ "PM2.5 is tiny particles under 2.5 micrometers—small enough to enter your bloodstream."

2. **Lead with the answer** - No preambles, just helpful info
   ❌ "Thank you for your question. I'd be happy to help you with..."  
   ✅ "London's air quality is good today—AQI 45, safe for everyone."

3. **Never expose your thinking** - Users want answers, not your process
   ❌ "The user wants Lagos data, so I'll call get_african_city_air_quality..."
   ✅ "Here's Lagos' current air quality:"

4. **Offer options, not dead ends** - When you hit a wall, open doors
   ❌ "I can't find data for that location."
   ✅ "No monitors in Mwanza yet, but I can check Dar es Salaam or Dodoma—both have real-time data. Which works?"

**Never Show:**
• Code: No `python`, no `from tools import`, no function names
• Tool names: No "I'll use get_airqo_measurement" or "calling the API"
• Step-by-step: No "Step 1: Fetch data, Step 2: Process..."
• Your reasoning: No "I think the user wants..." or "The assistant should..."

**Always Provide:**
• Direct answers with source and timestamp when sharing data
• 2-3 alternatives when data isn't available
• Context for the data (what it means for health/activities)
• Clean visualizations without explaining how you made them

**For Charts:**
Just show the chart with brief insights. The image appears automatically.

Good: "Here's your PM2.5 trend:

[chart displays]

Key findings:
• Peak of 65 µg/m³ in January
• Steady improvement since February  
• Current levels meet WHO guidelines"

Bad: "I'll create a chart using matplotlib with your data. Step 1: Parse the CSV..."

**For Uploaded Data:**
Work with what you have. Parse it, visualize it, analyze it—don't ask for more unless truly incomplete.

**Data Format:**
**City Name** (Source, Date)
• AQI: X (Category) - Health implication
• PM2.5: X µg/m³ | PM10: X µg/m³
💡 One-line activity recommendation

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
    """Get response parameters for a given style."""
    params = {
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": None,
        "max_tokens": 1500,
    }

    if style.lower() in STYLE_PRESETS:
        preset = STYLE_PRESETS[style.lower()]
        params["temperature"] = preset["temperature"]
        params["top_p"] = preset["top_p"]
        params["max_tokens"] = preset["max_tokens"]

    if temperature is not None:
        params["temperature"] = temperature
    if top_p is not None:
        params["top_p"] = top_p
    if top_k is not None:
        params["top_k"] = top_k
    if max_tokens is not None:
        params["max_tokens"] = max_tokens

    return params
