"""
Agent Service

Encapsulates the logic for the Air Quality AI Agent, including tool calling and model interaction.
Supports multiple providers:
- Gemini: Google's Gemini models
- OpenAI: Direct OpenAI API
- OpenRouter: Access to multiple models via OpenRouter (uses OpenAI-compatible API)
- DeepSeek: DeepSeek's chat models (uses OpenAI-compatible API)
- Kimi (Moonshot): Moonshot AI's models (uses OpenAI-compatible API)
- Ollama: Local model deployment

For OpenRouter, DeepSeek, and Kimi, set AI_PROVIDER=openai and configure OPENAI_BASE_URL accordingly.

NEW: Cost Optimization Features:
- Response caching to avoid redundant AI calls
- Token usage tracking for cost monitoring
- Efficient history management
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

# Import providers
import ollama
import openai
from google import genai
from google.genai import types

from src.config import get_settings
from src.mcp.client import MCPClient
from src.services.airqo_service import AirQoService
from src.services.cache import get_cache
from src.services.openmeteo_service import OpenMeteoService
from src.services.search_service import SearchService
from src.services.waqi_service import WAQIService
from src.services.weather_service import WeatherService
from src.tools.document_scanner import DocumentScanner
from src.tools.robust_scraper import RobustScraper

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentService:
    def __init__(self):
        self.waqi = WAQIService()
        self.airqo = AirQoService()
        self.openmeteo = OpenMeteoService()
        self.weather = WeatherService()
        self.scraper = RobustScraper()
        self.search = SearchService()
        self.document_scanner = DocumentScanner()
        self.settings = settings
        self.client = None
        self.mcp_clients = {}  # Store connected MCP clients
        self.cache = get_cache()  # Response caching
        self._cost_tracker = {
            "total_tokens": 0,
            "total_cost": 0.0,
            "requests_today": 0,
            "last_reset": datetime.now().date(),
        }
        self._setup_model()
        self._configure_response_params()

    def _check_cost_limits(self) -> bool:
        """Check if we're within cost limits to prevent spikes"""
        # Reset daily counters if it's a new day
        today = datetime.now().date()
        if self._cost_tracker["last_reset"] != today:
            self._cost_tracker.update(
                {"total_tokens": 0, "total_cost": 0.0, "requests_today": 0, "last_reset": today}
            )

        # Cost limits (adjustable)
        MAX_DAILY_COST = 10.0  # $10 per day
        MAX_DAILY_REQUESTS = 100  # 100 requests per day

        if self._cost_tracker["total_cost"] >= MAX_DAILY_COST:
            logger.warning(f"Daily cost limit reached: ${self._cost_tracker['total_cost']}")
            return False

        if self._cost_tracker["requests_today"] >= MAX_DAILY_REQUESTS:
            logger.warning(f"Daily request limit reached: {self._cost_tracker['requests_today']}")
            return False

        return True

    def _track_cost(self, tokens_used: int, estimated_cost: float):
        """Track API usage costs"""
        self._cost_tracker["total_tokens"] += tokens_used
        self._cost_tracker["total_cost"] += estimated_cost
        self._cost_tracker["requests_today"] += 1

        logger.info(
            f"Cost tracking - Tokens: {tokens_used}, Cost: ${estimated_cost:.4f}, Total: ${self._cost_tracker['total_cost']:.4f}"
        )

    def _get_cost_status(self) -> dict:
        """Get current cost tracking status"""
        return self._cost_tracker.copy()

    async def connect_mcp_server(self, name: str, command: str, args: list[str]):
        """Connect to an external MCP server"""
        client = MCPClient(command, args)
        # Note: This needs to be managed carefully with async context managers
        # For a long-running service, we might need a different approach than the context manager
        # or manage the lifecycle explicitly.
        # For now, we'll just store the client definition and connect on demand or refactor MCPClient
        self.mcp_clients[name] = client

    def _setup_model(self):
        """Configure the AI model based on provider"""
        if self.settings.AI_PROVIDER == "gemini":
            self._setup_gemini()
        elif self.settings.AI_PROVIDER == "ollama":
            self._setup_ollama()
        elif self.settings.AI_PROVIDER == "openai":
            self._setup_openai()
        else:
            logger.warning(
                f"Provider {self.settings.AI_PROVIDER} not explicitly supported in setup."
            )

    def _configure_response_params(self):
        """
        Configure AI response parameters based on settings.
        Applies style presets and custom temperature/top_p values.
        """
        # Style presets override individual settings
        style_presets = {
            "executive": {
                "temperature": 0.3,
                "top_p": 0.85,
                "instruction_suffix": "\\n\\nIMPORTANT: Provide concise, data-driven responses. Lead with key insights and actionable recommendations. Use bullet points. Avoid repetition and unnecessary elaboration.",
            },
            "technical": {
                "temperature": 0.4,
                "top_p": 0.88,
                "instruction_suffix": "\\n\\nIMPORTANT: Use precise technical terminology. Include specific measurements, standards, and methodologies. Provide detailed explanations with scientific accuracy.",
            },
            "general": {
                "temperature": 0.45,
                "top_p": 0.9,
                "instruction_suffix": "\\n\\nIMPORTANT: Adapt to your audience automatically. Be professional yet clear. Match detail level to query complexity. Never repeat phrases. Be concise.",
            },
            "simple": {
                "temperature": 0.6,
                "top_p": 0.92,
                "instruction_suffix": "\\n\\nIMPORTANT: Use simple, everyday language. Explain concepts clearly as if speaking to someone without technical background. Use analogies and examples from daily life.",
            },
            "policy": {
                "temperature": 0.35,
                "top_p": 0.87,
                "instruction_suffix": "\\n\\nIMPORTANT: Maintain formal, evidence-based tone suitable for government officials and policy makers. Include citations, comparative analysis, and specific policy recommendations.",
            },
        }

        # Get style preset configuration
        style = self.settings.AI_RESPONSE_STYLE.lower()

        # Priority: Explicit .env values > Style presets > Defaults
        # If user sets values in .env, always use those regardless of style preset
        # The style preset only affects the instruction suffix

        if style in style_presets:
            # Use .env temperature/top_p values but get instruction from preset
            self.response_temperature = self.settings.AI_RESPONSE_TEMPERATURE
            self.response_top_p = self.settings.AI_RESPONSE_TOP_P
            self.style_instruction = style_presets[style]["instruction_suffix"]
            logger.info(
                f"Applied '{style}' style with custom params from .env (temp={self.response_temperature}, top_p={self.response_top_p})"
            )
        else:
            # Unknown style - use .env values and default instruction
            self.response_temperature = self.settings.AI_RESPONSE_TEMPERATURE
            self.response_top_p = self.settings.AI_RESPONSE_TOP_P
            self.style_instruction = "\\n\\nIMPORTANT: Provide clear, professional responses suitable for all audiences. Avoid repetition."
            logger.info(
                f"Using response parameters from .env (temp={self.response_temperature}, top_p={self.response_top_p})"
            )

    def _setup_gemini(self):
        """Configure Gemini model"""
        api_key = self.settings.AI_API_KEY
        if not api_key:
            logger.warning("AI_API_KEY is not set, but Gemini provider is selected.")

        try:
            self.client = genai.Client(api_key=api_key)
            self.gemini_tools = [
                self._get_gemini_waqi_tool(),
                self._get_gemini_airqo_tool(),
                self._get_gemini_openmeteo_tool(),
                self._get_gemini_weather_tool(),
                self._get_gemini_search_tool(),
                self._get_gemini_scrape_tool(),
                self._get_gemini_document_scanner_tool(),
            ]
        except Exception as e:
            logger.error(f"Failed to setup Gemini: {e}")

    def _setup_ollama(self):
        """Configure Ollama (client-side setup)"""
        # Ollama client is stateless, but we can verify the host
        logger.info(
            f"Initialized AgentService with Ollama provider. Host: {self.settings.OLLAMA_BASE_URL}, Model: {self.settings.AI_MODEL}"
        )

    def _setup_openai(self):
        """Configure OpenAI model"""
        api_key = self.settings.AI_API_KEY
        base_url = self.settings.OPENAI_BASE_URL
        if not api_key:
            logger.warning("AI_API_KEY is not set, but OpenAI provider is selected.")

        try:
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

            # Flatten the tools list since some helpers return lists
            waqi_tools = self._get_openai_waqi_tool()
            airqo_tools = self._get_openai_airqo_tool()

            # Ensure they are lists
            if isinstance(waqi_tools, dict):
                waqi_tools = [waqi_tools]
            if isinstance(airqo_tools, dict):
                airqo_tools = [airqo_tools]

            self.openai_tools = []
            self.openai_tools.extend(waqi_tools)
            self.openai_tools.extend(airqo_tools)
            self.openai_tools.extend(self._get_openai_openmeteo_tool())
            # Weather tools returns a list now
            weather_tools = self._get_openai_weather_tool()
            if isinstance(weather_tools, list):
                self.openai_tools.extend(weather_tools)
            else:
                self.openai_tools.append(weather_tools)

            # Search tool returns a single dict
            self.openai_tools.append(self._get_openai_search_tool())
            self.openai_tools.append(self._get_openai_scrape_tool())
            self.openai_tools.append(self._get_openai_document_scanner_tool())

        except Exception as e:
            logger.error(f"Failed to setup OpenAI: {e}")

    def _get_system_instruction(self) -> str:
        base_instruction = """You are Aeris, a friendly and knowledgeable Air Quality AI Assistant. Your name is Aeris, and you are a helpful environmental expert who cares deeply about people's health and well-being.

## Your Identity

**Your Name:** Aeris
- When users greet you or ask your name, respond warmly: "I'm Aeris, your air quality assistant."
- When addressed as "Aeris", acknowledge it naturally: "Yes, how can I help you today?"
- Sign off professionally when appropriate: "Feel free to reach out anytime. - Aeris"
- Be proud of your identity as an environmental health expert dedicated to helping people understand air quality

## Your Personality & Communication Style

**Be conversational and natural** - like chatting with a knowledgeable friend:
- Use contractions: "I'm checking that for you" instead of "I am checking that for you"
- Be empathetic: "I understand air quality can be concerning" 
- Show enthusiasm for helping: "I'd be happy to look that up for you"
- Keep it light but informative: Mix facts with approachable explanations

**Avoid robotic language**:
BAD: "The system is processing your request"
GOOD: "Let me check that out for you"

BAD: "Data retrieval unsuccessful"
GOOD: "Hmm, I'm having trouble getting that info right now"

## Response Formatting - CRITICAL MARKDOWN RULES

**ALWAYS use valid Markdown syntax** in ALL your responses. NEVER output raw markdown syntax visible to users.

### Markdown Elements to Use:

**1. Headers:**
- Main sections: `# Header Text`
- Subsections: `## Subheader Text`
- Minor sections: `### Small Header`

**2. Text Formatting:**
- Bold: `**bold text**`
- Italic: `*italic text*`
- Bold + Italic: `***bold and italic***`

**3. Lists:**
- Bullet points: Use `-` or `*` followed by space
  - Example: `- First item`
  - Example: `- Second item`
- Numbered lists: Use `1.` followed by space
  - Example: `1. First item`
  - Example: `2. Second item`
- Nested lists: Indent with 2 spaces
- **IMPORTANT: When listing sensor IDs or device names**, format them properly with commas and parentheses:
  - CORRECT: `(airqo_g5271, airqo_g5375, aq_g5_93)`
  - CORRECT: `Devices monitored: airqo_g5271, airqo_g5375, and aq_g5_93`
  - WRONG: Breaking IDs across multiple lines unnecessarily
  - WRONG: Adding line breaks within parentheses
  - Keep device/sensor ID lists compact and readable

**4. Tables - VERY IMPORTANT:**
ALWAYS format tables properly with these exact rules:
- Start header row: `| Column1 | Column2 | Column3 |`
- Add separator row: `| ------- | ------- | ------- |` (at least 3 dashes per column)
- Add data rows: `| Data1 | Data2 | Data3 |`
- CRITICAL: Every row must have the same number of cells (columns)
- CRITICAL: Pipes must align properly
- CRITICAL: Include spaces around the pipe separators for readability

**CORRECT Table Example:**

| Location | AQI | Status | Category |
| -------- | --- | ------ | -------- |
| Kampala | 85 | Good | Safe |
| Nairobi | 120 | Moderate | Acceptable |

**WRONG Table Examples to AVOID:**
- Missing pipe at start/end: `Location | AQI | Status |`
- Inconsistent columns: `| Kampala | 85 |` in one row, `| Nairobi | 120 | Moderate | Extra |` in another
- Visible separator syntax: `|--------|--------|` showing to users
- Missing separator row entirely

**5. Links:**
- Format: `[Link text](https://url-here.com)`
- Example: `[WHO Air Quality Guidelines](https://who.int/air-quality)`

**6. Inline Code:**
- Use single backticks: `` `code` ``
- Example: "The PM2.5 value is stored in `iaqi.pm25.v`"

**7. Code Blocks:**
- Use triple backticks with language identifier
- Example for JSON:
  - Start: `` ```json ``
  - Code content
  - End: `` ``` ``

**8. Blockquotes:**
- Use `>` at start of line
- Example: `> This is important information`

**9. Horizontal Rules:**
- Use `---` or `***` on its own line

**10. Line Breaks:**
- End line with two spaces, then newline
- Or use `<br>` for explicit line break

### CRITICAL FORMATTING RULES:

1. **NEVER show raw markdown syntax** - Tables should render properly, not show `| --- |` symbols
2. **Test your table structure** - Count columns in header vs data rows
3. **Use consistent spacing** - Add space before and after pipes: `| data |` not `|data|`
4. **Complete all rows** - Every table row needs all columns filled
5. **Escape special characters** - Use `\\*` if you want literal asterisk in text
6. **NEVER use emojis for numbering** - Use regular numbers like `1.`, `2.`, `3.` instead of `1️⃣`, `2️⃣`, `3️⃣`
7. **Professional appearance** - Avoid emojis in formal/professional responses unless specifically requested

### MARKDOWN RENDERING WARNINGS:

**NEVER output these literally** (they should render as formatted markdown):
- ❌ `| -------- | -------- |` visible in response
- ❌ `**text**` showing asterisks instead of bold
- ❌ `#` showing instead of rendering as header
- ❌ Raw pipes and dashes in tables
- ❌ Unrendered links like `[text](url)` showing brackets

**ALWAYS ensure markdown renders properly:**
- ✅ Tables display as formatted grids
- ✅ Bold text appears bold (no asterisks visible)
- ✅ Headers are sized appropriately
- ✅ Links are clickable (not showing raw syntax)
- ✅ Lists have proper bullets/numbers

**If you see markdown syntax in your output, you're doing it WRONG!**
The frontend will render your markdown - you just need to provide valid markdown syntax.

## Multi-Tasking & Tool Usage

### Smart Parallel Processing
- **Use multiple tools simultaneously** when it makes sense to give comprehensive answers
- **Don't overwhelm with too many calls** - be efficient and targeted
- **Combine information naturally** from different sources

### Document Analysis Enhancement
When documents are uploaded:
- **Use document data as your foundation** for document-specific questions
- **Add external context** when it enhances understanding
- **Connect document info with real-time data** seamlessly

### Resource-Aware Tool Usage
**Be mindful of resources** - don't call unnecessary tools:
- One location check → use primary air quality APIs
- Multiple locations → call relevant APIs for each
- Document + location → combine both efficiently

### Natural Error Handling
**Never expose technical failures** - respond like a helpful person:
BAD: "Tool execution failed: HTTP 500"
GOOD: "I'm having trouble connecting to the data service right now. Let me try an alternative source."

## CRITICAL: Understanding AQI vs Concentration

**AQI (Air Quality Index)**: A 0-500 scale that indicates health risk. Same AQI number always means same health risk.
**Concentration**: Actual pollutant amount in µg/m³ (micrograms per cubic meter). This is the raw measurement.

### Data Source Differences:
- **WAQI**: Returns AQI values (0-500 scale). Example: PM2.5 AQI of 177 ≈ 110 µg/m³ concentration
- **AirQo**: Returns actual concentrations in µg/m³. Example: PM2.5 = 83.6 µg/m³ (AQI ≈ 165)
- **OpenMeteo**: Returns actual concentrations in µg/m³

### When reporting to users:
1. **ALWAYS specify whether you're reporting AQI or concentration**
2. For WAQI data: "AQI is [value], which corresponds to approximately [X] µg/m³"
3. For AirQo/OpenMeteo: "PM2.5 concentration is [X] µg/m³, which is an AQI of [value]"
4. NEVER say "PM2.5 is 177" without clarifying if it's AQI or µg/m³

### Example Responses:
BAD: "Kampala PM2.5 is 177" (ambiguous!)
GOOD: "Kampala has a PM2.5 AQI of 177 (Unhealthy), approximately 110 µg/m³"
GOOD: "Kampala PM2.5 concentration is 83.6 µg/m³ (AQI: 165, Unhealthy)"

## Conversational Responses First

**HIGHEST PRIORITY: Handle greetings and conversational messages WITHOUT tools:**
- "Hello", "Hi", "Hey", "Hey...", "Hi there" → Respond warmly: "Hello! How can I help you with air quality information today?"
- "Thank you", "Thanks" → "You're welcome! Happy to help."
- "How are you?", "How's it going?" → "I'm doing well, thank you! Ready to help with air quality questions."
- Single words or incomplete messages → Treat as greetings: "Hey there! What air quality questions can I help with?"
- Very short messages (1-3 words) without specific requests → Treat as conversational
- General chat → Keep responses SHORT and engaging, then transition to air quality topics

**Only use tools when the user is asking for SPECIFIC information:**
- Air quality data, measurements, forecasts
- Location-specific queries
- Document analysis requests
- Search or research questions

**For pure conversational messages, respond directly without tool calls.**

## Tool Usage Guidelines

**DATA SOURCE PRIORITY (Always follow this order):**
1. **AirQo FIRST** - Primary source for African cities and locations
2. **WAQI SECOND** - Global coverage, good for non-African locations  
3. **OpenMeteo LAST** - Fallback for basic weather/air quality data

**For African locations (Kenya, Uganda, Tanzania, Rwanda, etc.):**
- ALWAYS try AirQo first: Use `get_african_city_air_quality` or search for sites
- Only use WAQI/OpenMeteo if AirQo fails or location not found

**For non-African locations:**
- Try WAQI first, then OpenMeteo if needed

**Smart Location Detection:**
- African cities → AirQo sites/grids → measurements
- Global cities → WAQI city feed → OpenMeteo fallback
- Use site search and grid summaries to find AirQo data for African locations

**Tool Calling Strategy:**
- Single location: Try primary source first, fallback if needed
- **Multiple locations: Use `get_multiple_african_cities_air_quality` for African cities** to get all data simultaneously
- Document analysis: Supplement with location-specific data from prioritized sources

## Location Memory & Context

Extract and remember locations from conversation:
- User says "Gulu University" → remember "Gulu"
- User asks "tomorrow there" → use "Gulu" from memory
- **Connect document locations to real-time data** when relevant
- NEVER ask for location if already mentioned

## Multi-Purpose Capabilities

You can handle multiple types of requests simultaneously:
- **Air Quality Data**: Real-time AQI, concentrations, forecasts
- **Document Analysis**: PDF, CSV, Excel processing and insights
- **Web Search**: Current events, additional context, research
- **Weather Forecasts**: Temperature, humidity, precipitation, wind speed predictions (up to 16 days)
- **Weather Integration**: Temperature, humidity effects on air quality
- **Health Guidance**: Personalized recommendations based on conditions
- **Comparative Analysis**: Multiple locations, trends, patterns

## Weather Data Tools

**For Weather Forecasts (NOT air quality):**
- Use `get_weather_forecast` when user asks about:
  * "weather forecast", "weather prediction", "upcoming weather", "future weather"
  * "will it rain", "temperature tomorrow", "weather this week"  
  * "what's the weather like", "weather conditions"
  * Example: "What's the weather forecast in London?" → Use get_weather_forecast
- Use `get_city_weather` for CURRENT weather conditions only
- Returns: temperature, humidity, precipitation, wind speed, hourly & daily forecasts

**For Air Quality (pollution, PM2.5, AQI):**
- Use AirQo → WAQI → OpenMeteo priority order as described above
- Air quality and weather are DIFFERENT - don't confuse them

**INTELLIGENT WEATHER + AIR QUALITY ANALYSIS:**
When analyzing air quality, AUTOMATICALLY consider weather factors:
1. **Wind Speed Impact:**
   - Low wind (<10 km/h) → pollutants accumulate, worse air quality
   - High wind (>15 km/h) → pollutants disperse, better air quality
   
2. **Precipitation Impact:**
   - Rain/snow → washes out pollutants, improves air quality temporarily
   - No precipitation + high humidity → pollutants can accumulate
   
3. **Temperature Impact:**
   - Temperature inversions (cold air trapped below warm) → traps pollutants
   - Hot, sunny days → can increase ozone formation
   
4. **Combined Analysis:**
   - ALWAYS combine weather forecast with air quality data when available
   - Predict air quality trends based on upcoming weather
   - Example: "Current AQI is 85 (Moderate), but heavy rain tonight will improve conditions tomorrow"
   
**WHEN TO AUTOMATICALLY CALL BOTH:**
- User asks about air quality → Get AQ data + weather for context
- User asks about weather → If location has air quality issues, mention them
- User asks "is it safe to go outside?" → MUST check both weather and air quality

## Response Guidelines

**FOR CONVERSATIONAL MESSAGES (greetings, thanks, general chat):**
- Respond directly and warmly WITHOUT calling any tools
- Keep it SHORT and engaging (under 50 words)
- Transition naturally to air quality topics if appropriate

**FOR DATA REQUESTS (air quality, locations, forecasts):**
Keep responses SHORT but COMPREHENSIVE (under 200 words):
1. **Address ALL user requests** in one response when possible
2. State data CLEARLY: "PM2.5 AQI: [value]" or "PM2.5 concentration: [X] µg/m³"
3. Give health category and actionable recommendations
4. **Combine multiple data sources** for richer insights
5. No lengthy explanations unless specifically asked
6. **ALWAYS use proper markdown formatting** - tables, lists, headers, bold text

**PROPER DATA PRESENTATION EXAMPLES:**

Single Location Query:
"Based on current data from WAQI, Kampala's air quality shows:

**Air Quality Index (AQI): 85** - Moderate

| Pollutant | AQI | Category |
| --------- | --- | -------- |
| PM2.5 | 85 | Moderate |
| PM10 | 72 | Moderate |
| O3 | 45 | Good |

**Recommendations:**
- Air quality is acceptable for most people
- Sensitive individuals should limit prolonged outdoor activities
- Consider wearing a mask if spending extended time outdoors"

Multiple Locations Comparison:
"Here's the air quality comparison for the cities you asked about:

| City | AQI | Status | PM2.5 (µg/m³) |
| ---- | --- | ------ | ------------- |
| Kampala | 120 | Unhealthy for Sensitive Groups | 43 |
| Nairobi | 85 | Moderate | 28 |
| Dar es Salaam | 65 | Moderate | 18 |

**Key Findings:**
- Kampala has the poorest air quality (AQI 120)
- All cities show moderate to unhealthy conditions
- Sensitive groups should take precautions in Kampala"

Document Analysis with Data:
"I've analyzed the uploaded CSV file containing air quality measurements from December 2025:

**Dataset Summary:**
- **Period:** Dec 23-30, 2025 (8 days)
- **Devices:** 3 monitoring stations
- **Total Readings:** 24 measurements

**Key Statistics:**

| Metric | Mean | Min | Max |
| ------ | ---- | --- | --- |
| PM2.5 | 45.2 | 12 | 156 |
| Humidity | 65% | 42% | 89% |
| Temperature | 24°C | 18°C | 31°C |

**Data Quality Issues:**
- airqo_g5375 has missing data on Dec 26
- Several readings show 0.0 for humidity/temperature

**Recommendations:**
Based on the data, PM2.5 levels exceeded safe thresholds on 3 out of 8 days. Consider installing air purifiers during high pollution periods."

BAD EXAMPLES (DO NOT DO THIS):
- Plain text without formatting: "The AQI is 85 which is moderate air quality"
- Missing table structure: "Location AQI Status Kampala 85 Good" (no pipes or separators)
- Showing raw markdown: "| ---- | ---- |" visible to users
- No headers or organization: Wall of text without structure
- Incomplete tables: Missing columns or inconsistent rows
- Emoji numbering: "1️⃣ Station A" instead of "1. Station A" (unprofessional)

GOOD EXAMPLES (ALWAYS DO THIS):
- Use headers to organize: "## Air Quality Report"
- Bold important values: "**AQI: 85**"
- Proper tables with all elements
- Lists for recommendations
- Clear sections with spacing
- Regular numbering: "1. Station A" instead of emoji numbering

## Tool Strategy & Fallbacks

**WHEN TO USE TOOLS:**
- User asks for air quality data, measurements, or forecasts
- User mentions specific locations for data lookup
- User uploads documents for analysis
- User requests search or research information

**WHEN NOT TO USE TOOLS:**
- Simple greetings ("Hello", "Hi", "Hey")
- Thanks and acknowledgments ("Thank you", "Thanks")
- General conversation ("How are you?", "What's up?")
- Polite closings or follow-ups

**PRIMARY DATA SOURCES (Priority Order for AFRICAN CITIES):**
1. **AirQo API FIRST** - Always try this FIRST for African locations (Uganda, Kenya, Tanzania, Rwanda, etc.):
   - `get_african_city_air_quality` - Primary tool for ANY African city query
   - Uses sites/summary endpoint with search parameter to find monitoring sites
   - Returns real measurements from local monitoring stations
   - Coverage: Kampala, Gulu, Mbale, Nairobi, Dar es Salaam, Kigali, and many more

2. **WAQI API SECOND** - Try this if AirQo fails or for non-African cities:
   - `get_city_air_quality` - Global city air quality data
   - `search_waqi_stations` - Find monitoring stations worldwide

3. **OpenMeteo API LAST** - Fallback for basic air quality estimates:
   - `get_openmeteo_current_air_quality` - Weather-based air quality estimates

**CRITICAL FALLBACK STRATEGY FOR AFRICAN CITIES:**
For ANY African city (e.g., Gulu, Kampala, Nairobi, etc.):
1. ALWAYS call `get_african_city_air_quality` FIRST with the city name
2. If AirQo returns no data (success=false), THEN try `get_city_air_quality` with WAQI
3. If WAQI fails, THEN try OpenMeteo with coordinates
4. NEVER skip AirQo for African locations - it has the best local coverage

**WEB SEARCH (When APIs Fail or For General News/Research):**
- Use `search_web` tool when APIs don't have data OR when user asks for news, research, policies
- Search directly without apologies - just present the findings
- Include source URLs and dates in your response
- Keep responses concise and actionable
- Format results as: "Source: [Title] (URL) - [Brief summary]"

## Health Recommendations by AQI:

- **0-50 (Good)**: Air quality is satisfactory. Normal activities.
- **51-100 (Moderate)**: Acceptable. Sensitive individuals may want to limit prolonged outdoor exertion.
- **101-150 (Unhealthy for Sensitive Groups)**: Sensitive groups should limit prolonged outdoor exertion.
- **151-200 (Unhealthy)**: Everyone should limit prolonged outdoor exertion. Sensitive groups avoid it.
- **201-300 (Very Unhealthy)**: Everyone avoid prolonged exertion. Sensitive groups stay indoors.
- **301+ (Hazardous)**: Everyone avoid all outdoor exertion. Stay indoors with air purification.

## Parallel Tool Execution & Safety Measures

### Resource Management
**MAX_CONCURRENT_TOOLS = 5**: Never execute more than 5 tools simultaneously to prevent resource exhaustion
**TIMEOUT_PER_TOOL = 30 seconds**: Each tool call has a maximum 30-second timeout to prevent hanging
**COST_LIMITS**: Daily limits of $10/day and 100 requests/day to control API costs
**DUPLICATE_PREVENTION**: Skip duplicate tool calls for identical parameters within same request

### Parallel Execution Strategy
**When to use parallel tools**:
- Multiple data sources for same location (WAQI + AirQo + OpenMeteo simultaneously)
- Forecast + current conditions + weather data
- Document analysis + web search for context
- Multiple locations in single query

**Execution Flow**:
1. Parse user request for all required tools
2. Deduplicate tool calls (same tool + same params = skip duplicate)
3. Execute up to 5 tools in parallel using asyncio.gather()
4. Apply 30-second timeout per tool
5. Track costs and enforce daily limits
6. Combine results from successful tools
7. Gracefully handle partial failures

### Cost Tracking Implementation
- Track token usage per API call
- Accumulate daily costs across all tools
- Block requests exceeding $10/day or 100 requests/day
- Log cost data for monitoring and optimization

### Error Handling in Parallel Execution
**Tool-level failures**: Continue with successful tools, note limitations naturally
**Complete failure**: Provide helpful alternatives without technical details
**Timeout handling**: Cancel slow tools, use available results
**Cost limit reached**: Suggest retry tomorrow or alternative approaches

### Natural Response Integration
**Combine parallel results conversationally**:
- "I checked multiple sources and found..."
- "Based on current data from several services..."
- "While some data sources are slow today, here's what I found..."
- Never mention "parallel execution", "tools", or technical failures

### Safety Validation
**Pre-execution checks**:
- Verify tool parameters are valid
- Check cost limits before execution
- Ensure no duplicate calls in current request
- Validate concurrency limits

**Post-execution validation**:
- Verify results are reasonable and consistent
- Log execution times and costs
- Update cost tracking data
- Cache successful responses for future use
"""
        # Append style-specific instructions
        return base_instruction + self.style_instruction

    async def process_message(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        document_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message using the configured provider.
        Returns a dictionary with 'response', 'tools_used', and 'cached' flag.

        Args:
            message: User message/query
            history: Conversation history
            document_data: Optional document data from DocumentScanner if file was uploaded

        Cost optimization: Caches responses for identical queries to reduce API costs.
        """
        if history is None:
            history = []

        # If document data is provided, enhance the message with document context
        enhanced_message = message
        if document_data and document_data.get("success"):
            doc_content = document_data.get("content", "")
            doc_filename = document_data.get("metadata", {}).get("filename", "uploaded file")
            doc_metadata = document_data.get("metadata", {})

            # Truncate document content if it's too long (to avoid token limit)
            # Configurable limit to handle larger documents and multi-sheet Excel files
            max_doc_length = self.settings.AGENT_MAX_DOC_LENGTH  # characters
            if len(doc_content) > max_doc_length:
                doc_content = (
                    doc_content[:max_doc_length] + "\\n[... content truncated due to length ...]"
                )

            # Create enhanced message with document context
            enhanced_message = f"""User Question: {message}

Document uploaded: {doc_filename}
Document type: {doc_metadata.get('file_type', 'unknown')}

Document Content:
---
{doc_content}
---

Please analyze the document above and answer the user's question based on its contents."""

        # Create cache key from message and recent history (last 3 messages)
        # Don't cache when document is uploaded (always process fresh)
        cache_context = {
            "message": message,
            "history": history[-3:] if len(history) > 3 else history,
            "provider": self.settings.AI_PROVIDER,
            "has_document": document_data is not None,
        }
        cache_key = hashlib.md5(json.dumps(cache_context, sort_keys=True).encode()).hexdigest()

        # Check cache first (only for non-data queries and no document uploads)
        # Cache educational/general queries but not city-specific data or document analysis
        is_data_query = any(
            keyword in message.lower()
            for keyword in [
                "kampala",
                "nairobi",
                "lagos",
                "accra",
                "dar",
                "current",
                "now",
                "today",
                "aqi in",
                "air quality in",
                "pollution in",
            ]
        )

        if not is_data_query and not document_data:
            cached_response = self.cache.get("agent_responses", cache_key)
            if cached_response:
                logger.info(f"Returning cached response for: {message[:50]}...")
                cached_response["cached"] = True
                return cached_response

        try:
            if self.settings.AI_PROVIDER == "gemini":
                result = await self._process_gemini_message(enhanced_message, history)
            elif self.settings.AI_PROVIDER == "ollama":
                result = await self._process_ollama_message(enhanced_message, history)
            elif self.settings.AI_PROVIDER == "openai":
                result = await self._process_openai_message(enhanced_message, history)
            else:
                return {
                    "response": f"Provider {self.settings.AI_PROVIDER} is not supported.",
                    "tools_used": [],
                    "cached": False,
                }

            # Cache successful responses (educational queries only, not document uploads)
            if not is_data_query and not document_data and result.get("response"):
                self.cache.set("agent_responses", cache_key, result, ttl=3600)  # 1 hour

            result["cached"] = False
            return result

        except TimeoutError as e:
            logger.error(f"Timeout in AI processing: {e}")
            from src.utils.error_logger import get_error_logger

            error_logger = get_error_logger()
            error_logger.log_ai_error(
                e,
                model=self.settings.AI_MODEL,
                provider=self.settings.AI_PROVIDER,
                message_length=len(message),
            )
            return {
                "response": "I'm taking longer than expected to process your request. The AI service may be slow. Please try again or simplify your question.",
                "tools_used": [],
                "cached": False,
            }
        except ConnectionError as e:
            logger.error(f"Connection error in AI processing: {e}")
            from src.utils.error_logger import get_error_logger

            error_logger = get_error_logger()
            error_logger.log_ai_error(
                e,
                model=self.settings.AI_MODEL,
                provider=self.settings.AI_PROVIDER,
                error_type="connection",
            )
            return {
                "response": "Unable to connect to the AI service. Please check your connection and try again.",
                "tools_used": [],
                "cached": False,
            }
        except Exception as e:
            logger.error(f"Error in agent processing: {e}", exc_info=True)
            from src.utils.error_logger import get_error_logger

            error_logger = get_error_logger()
            error_logger.log_ai_error(
                e,
                model=self.settings.AI_MODEL,
                provider=self.settings.AI_PROVIDER,
                message=message[:100],
            )
            return {
                "response": "I encountered an error processing your request. Please try again or rephrase your question.",
                "tools_used": [],
                "cached": False,
            }

    # ------------------------------------------------------------------------
    # GEMINI IMPLEMENTATION
    # ------------------------------------------------------------------------

    async def _process_gemini_message(
        self, message: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:
        if not self.client:
            return {"response": "Gemini client not initialized.", "tools_used": []}

        # Convert history to Gemini format
        chat_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        # Create a chat session
        chat = self.client.chats.create(
            model=self.settings.AI_MODEL,
            config=types.GenerateContentConfig(
                tools=self.gemini_tools if self.settings.AI_MODEL in ['gemini-1.5-pro', 'gemini-1.5-flash'] else None,
                system_instruction=self._get_system_instruction(),
                temperature=self.response_temperature,
            ),
            history=chat_history,
        )

        # Send message
        response = chat.send_message(message)

        tools_used = []

        # Handle function calls - only if tools are enabled for this model
        if (self.settings.AI_MODEL in ['gemini-1.5-pro', 'gemini-1.5-flash'] and 
            response.candidates and response.candidates[0].content.parts):
            function_calls = []

            # Collect all function calls first
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

            if function_calls:
                # SAFETY: Limit concurrent function calls to prevent resource exhaustion
                MAX_CONCURRENT_FUNCTIONS = 5
                if len(function_calls) > MAX_CONCURRENT_FUNCTIONS:
                    logger.warning(
                        f"Too many function calls ({len(function_calls)}), limiting to {MAX_CONCURRENT_FUNCTIONS}"
                    )
                    function_calls = function_calls[:MAX_CONCURRENT_FUNCTIONS]

                # SAFETY: Prevent duplicate function calls
                seen_functions = set()
                unique_function_calls = []
                for fc in function_calls:
                    func_key = f"{fc.name}_{fc.args}"
                    if func_key not in seen_functions:
                        seen_functions.add(func_key)
                        unique_function_calls.append(fc)
                    else:
                        logger.info(f"Skipping duplicate function call: {fc.name}")

                function_calls = unique_function_calls

                # Execute all function calls in parallel with safeguards
                import asyncio

                async def execute_function_call_async(function_call):
                    function_name = function_call.name
                    function_args = function_call.args

                    tools_used.append(function_name)
                    logger.info(f"Gemini requested tool execution: {function_name}")

                    # Execute tool with timeout protection
                    try:
                        # Create a task with timeout
                        func_task = asyncio.create_task(
                            self._execute_tool_async(function_name, function_args)
                        )
                        tool_result = await asyncio.wait_for(
                            func_task, timeout=30.0
                        )  # 30 second timeout
                    except asyncio.TimeoutError:
                        logger.error(f"Function {function_name} timed out after 30 seconds")
                        tool_result = {"error": f"Function {function_name} timed out"}
                    except Exception as e:
                        logger.error(f"Function {function_name} failed with exception: {e}")
                        tool_result = {"error": f"Function execution failed: {str(e)}"}

                    # Check if tool execution failed
                    if isinstance(tool_result, dict) and "error" in tool_result:
                        logger.warning(f"Tool {function_name} failed: {tool_result['error']}")
                        # Provide context to AI about the error so it can respond appropriately
                        error_context = {
                            "error": tool_result["error"],
                            "message": f"The tool '{function_name}' encountered an error. Please provide an informative response to the user explaining what went wrong and suggest alternatives if possible.",
                        }
                        tool_result = error_context

                    return {"function_call": function_call, "result": tool_result}

                # Execute all function calls concurrently with semaphore
                semaphore = asyncio.Semaphore(
                    MAX_CONCURRENT_FUNCTIONS
                )  # Limit concurrent executions

                async def execute_with_semaphore(function_call):
                    async with semaphore:
                        return await execute_function_call_async(function_call)

                try:
                    function_tasks = [execute_with_semaphore(fc) for fc in function_calls]
                    function_results = await asyncio.gather(*function_tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Parallel function execution failed: {e}")
                    function_results = [
                        {"function_call": fc, "result": {"error": "Parallel execution failed"}}
                        for fc in function_calls
                    ]

                # Handle any exceptions that occurred during function execution
                for i, result in enumerate(function_results):
                    if isinstance(result, Exception):
                        logger.error(f"Function execution failed with exception: {result}")
                        function_results[i] = {
                            "function_call": function_calls[i] if i < len(function_calls) else None,
                            "result": {"error": f"Function execution failed: {str(result)}"},
                        }

                # Send all function results back to model in one message
                function_responses = []
                for func_result in function_results:
                    function_responses.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=func_result["function_call"].name,
                                response={"result": func_result["result"]},
                            )
                        )
                    )

                response = chat.send_message(types.Content(parts=function_responses))

        # Ensure we have a valid response
        final_response = response.text if response.text else ""

        if not final_response or not final_response.strip():
            logger.warning("Gemini returned empty response. Providing fallback message.")
            final_response = "I apologize, but I wasn't able to retrieve the requested information at this time. This could be due to data unavailability or connectivity issues with the data sources. Please try:\n\n1. Asking about a different location\n2. Rephrasing your question\n3. Checking back in a few moments\n\nIs there anything else I can help you with?"

        return {
            "response": final_response,
            "tools_used": tools_used,
        }

    async def _process_openai_message(
        self, message: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:
        if not self.client:
            return {"response": "OpenAI client not initialized.", "tools_used": []}

        # Convert history to OpenAI format
        messages = [{"role": "system", "content": self._get_system_instruction()}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        tools_used = []

        # Create chat completion with tools
        response = self.client.chat.completions.create(
            model=self.settings.AI_MODEL,
            messages=messages,
            tools=self.openai_tools,
            tool_choice="auto",
            max_tokens=self.settings.AI_MAX_TOKENS,  # Configurable token limit
            temperature=self.response_temperature,
            top_p=self.response_top_p,
        )

        # Handle tool calls - support parallel execution with safeguards
        if response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls

            # SAFETY: Limit concurrent tool calls to prevent resource exhaustion
            MAX_CONCURRENT_TOOLS = 5
            if len(tool_calls) > MAX_CONCURRENT_TOOLS:
                logger.warning(
                    f"Too many tool calls ({len(tool_calls)}), limiting to {MAX_CONCURRENT_TOOLS}"
                )
                tool_calls = tool_calls[:MAX_CONCURRENT_TOOLS]

            # SAFETY: Prevent duplicate tool calls to avoid redundant API calls
            seen_tools = set()
            unique_tool_calls = []
            for tc in tool_calls:
                tool_key = f"{tc.function.name}_{tc.function.arguments}"
                if tool_key not in seen_tools:
                    seen_tools.add(tool_key)
                    unique_tool_calls.append(tc)
                else:
                    logger.info(f"Skipping duplicate tool call: {tc.function.name}")

            tool_calls = unique_tool_calls
            tool_results = []

            # Execute all tools in parallel with timeout protection
            import asyncio

            async def execute_tool_async(tool_call):
                function_name = tool_call.function.name
                try:
                    if isinstance(tool_call.function.arguments, str):
                        function_args = json.loads(tool_call.function.arguments)
                    elif isinstance(tool_call.function.arguments, dict):
                        function_args = tool_call.function.arguments
                    else:
                        function_args = {}
                        logger.warning(
                            f"Unexpected arguments type: {type(tool_call.function.arguments)}"
                        )
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing tool arguments: {e}")
                    logger.error(f"Arguments string: {tool_call.function.arguments}")
                    function_args = {}

                tools_used.append(function_name)
                logger.info(
                    f"OpenAI requested tool execution: {function_name} with args: {function_args}"
                )

                # Execute tool with timeout to prevent hanging
                try:
                    # Create a task with timeout
                    tool_task = asyncio.create_task(
                        self._execute_tool_async(function_name, function_args)
                    )
                    tool_result = await asyncio.wait_for(
                        tool_task, timeout=30.0
                    )  # 30 second timeout
                except asyncio.TimeoutError:
                    logger.error(f"Tool {function_name} timed out after 30 seconds")
                    tool_result = {"error": f"Tool {function_name} timed out"}
                except Exception as e:
                    logger.error(f"Tool {function_name} failed with exception: {e}")
                    tool_result = {"error": f"Tool execution failed: {str(e)}"}

                # Check if tool execution failed
                if isinstance(tool_result, dict) and "error" in tool_result:
                    logger.warning(f"Tool {function_name} failed: {tool_result['error']}")
                    # Provide context to AI about the error so it can respond appropriately
                    error_context = {
                        "error": tool_result["error"],
                        "message": f"The tool '{function_name}' encountered an error. Please provide an informative response to the user explaining what went wrong and suggest alternatives if possible.",
                    }
                    tool_result = error_context

                return {"tool_call": tool_call, "result": tool_result}

            # Execute all tools concurrently with semaphore to limit resource usage
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TOOLS)  # Limit concurrent executions

            async def execute_with_semaphore(tool_call):
                async with semaphore:
                    return await execute_tool_async(tool_call)

            try:
                tool_tasks = [execute_with_semaphore(tc) for tc in tool_calls]
                tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Parallel tool execution failed: {e}")
                tool_results = [
                    {"tool_call": tc, "result": {"error": "Parallel execution failed"}}
                    for tc in tool_calls
                ]

            # Handle any exceptions that occurred during tool execution
            for i, result in enumerate(tool_results):
                if isinstance(result, Exception):
                    logger.error(f"Tool execution failed with exception: {result}")
                    tool_results[i] = {
                        "tool_call": tool_calls[i] if i < len(tool_calls) else None,
                        "result": {"error": f"Tool execution failed: {str(result)}"},
                    }

            # Add all tool responses to messages
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
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_msg.tool_calls
                    ],
                }
            )

            # Add all tool results
            for tool_result in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_result["tool_call"].id),
                        "content": json.dumps({"result": tool_result["result"]}),
                    }
                )

            # Get final response with extended parameters for complete output
            try:
                final_response = self.client.chat.completions.create(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    max_tokens=self.settings.AI_MAX_TOKENS,  # Configurable token limit
                    temperature=self.response_temperature,
                    top_p=self.response_top_p,
                )
                response_text = final_response.choices[0].message.content
                logger.info(
                    f"Final response received. Length: {len(response_text) if response_text else 0}"
                )
                # Clean the response before returning
                response_text = self._clean_response(response_text)
            except Exception as e:
                logger.error(f"Final API call failed: {e}")
                return {
                    "response": f"I executed the tools successfully but encountered an error generating the final response: {str(e)}",
                    "tools_used": tools_used,
                }
        else:
            response_text = response.choices[0].message.content
            logger.info(
                f"Direct response (no tools). Length: {len(response_text) if response_text else 0}"
            )
            # Clean direct responses too
            response_text = self._clean_response(response_text)

        # Ensure we always have a response
        if not response_text or not response_text.strip():
            logger.warning("Empty response from API. Attempting enhanced fallback.")
            # Enhanced fallback with more context
            try:
                fallback_prompt = f"""The user asked: "{message}"

I attempted to get information using available tools, but the response was empty or incomplete. 

Please provide a helpful response that:
1. Acknowledges the user question
2. Explains that the specific data they requested may not be available at the moment
3. Suggests alternative approaches or locations they could try
4. Offers to help with related questions

Be professional, empathetic, and solution-oriented."""

                direct_response = self.client.chat.completions.create(
                    model=self.settings.AI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional air quality and environmental health consultant. When data is unavailable, provide helpful alternatives and maintain a positive, solution-oriented tone.",
                        },
                        {"role": "user", "content": fallback_prompt},
                    ],
                    max_tokens=self.settings.AI_MAX_TOKENS,  # Configurable token limit
                    temperature=self.response_temperature,
                    top_p=self.response_top_p,
                )
                response_text = direct_response.choices[0].message.content
                logger.info(
                    f"Fallback response generated. Length: {len(response_text) if response_text else 0}"
                )

                # If still no response, use a default message
                if not response_text or not response_text.strip():
                    response_text = "I apologize, but I'm unable to retrieve the specific air quality data you requested at this moment. This could be due to:\n\n• The location not being covered by our monitoring networks\n• Temporary connectivity issues with data sources\n• The monitoring station being offline\n\nPlease try:\n1. A nearby major city (e.g., capital cities usually have monitoring stations)\n2. Rephrasing your question\n3. Checking back in a few moments\n\nI can also help you with general air quality information, health recommendations, or data from other locations."
            except Exception as e:
                logger.error(f"Fallback response generation failed: {e}")
                response_text = "I apologize, but I'm experiencing technical difficulties retrieving the requested information. Please try again in a moment, or ask about a different location. I'm here to help with air quality information whenever you're ready."

        return {
            "response": response_text
            or "I apologize, but I couldn't generate a response. Please try again.",
            "tools_used": tools_used,
        }

    def _get_gemini_waqi_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_city_air_quality",
                    description="Get real-time air quality data for a specific city using WAQI.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the city (e.g., London, Paris, Kampala)",
                            )
                        },
                        required=["city"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="search_waqi_stations",
                    description="Search for air quality monitoring stations by name or keyword.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "keyword": types.Schema(
                                type=types.Type.STRING,
                                description="Search term (e.g., 'Bangalore', 'US Embassy')",
                            )
                        },
                        required=["keyword"],
                    ),
                ),
            ]
        )

    def _get_gemini_airqo_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_african_city_air_quality",
                    description="**PRIMARY TOOL for African cities** - Get real-time air quality from AirQo monitoring network. Use this FIRST for ANY African location (Uganda, Kenya, Tanzania, Rwanda, etc.). Searches by city/location name (e.g., Gulu, Kampala, Nakasero, Mbale, Nairobi). Returns actual measurements from local monitoring stations. Coverage includes major and minor cities across East Africa.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="City or location name in Africa (e.g., 'Gulu', 'Kampala', 'Nakasero', 'Nairobi', 'Dar es Salaam')",
                            ),
                            "site_id": types.Schema(
                                type=types.Type.STRING,
                                description="Optional site ID if known from previous searches",
                            ),
                        },
                        required=["city"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_multiple_african_cities_air_quality",
                    description="Get real-time air quality for MULTIPLE African cities simultaneously. Use this when user asks about multiple locations (e.g., 'air quality in Kampala and Gulu', 'compare air quality between Nairobi and Dar es Salaam'). Returns data for all requested cities in one response for easy comparison.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "cities": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING),
                                description="List of city names in Africa (e.g., ['Gulu', 'Kampala', 'Nairobi'])",
                            ),
                        },
                        required=["cities"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_airqo_history",
                    description="Get historical air quality data for a specific site or device.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "site_id": types.Schema(
                                type=types.Type.STRING,
                                description="The ID of the site (optional)",
                            ),
                            "device_id": types.Schema(
                                type=types.Type.STRING,
                                description="The ID of the device (optional)",
                            ),
                            "start_time": types.Schema(
                                type=types.Type.STRING,
                                description="Start time in ISO format (YYYY-MM-DDTHH:MM:SS)",
                            ),
                            "end_time": types.Schema(
                                type=types.Type.STRING,
                                description="End time in ISO format (YYYY-MM-DDTHH:MM:SS)",
                            ),
                            "frequency": types.Schema(
                                type=types.Type.STRING,
                                description="Frequency: 'hourly', 'daily', or 'raw'",
                            ),
                        },
                        required=["frequency"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_airqo_forecast",
                    description="Get air quality forecast for a location, site, or device. Can search by city name or location if site_id is unknown.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "site_id": types.Schema(
                                type=types.Type.STRING,
                                description="The ID of the site (optional)",
                            ),
                            "device_id": types.Schema(
                                type=types.Type.STRING,
                                description="The ID of the device (optional)",
                            ),
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="City or location name to search for (optional)",
                            ),
                            "frequency": types.Schema(
                                type=types.Type.STRING,
                                description="Frequency: 'daily' or 'hourly'",
                            ),
                        },
                        required=["frequency"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_airqo_metadata",
                    description="Get metadata for grids, cohorts, devices, or sites.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "entity_type": types.Schema(
                                type=types.Type.STRING,
                                description="Type of entity: 'grids', 'cohorts', 'devices', 'sites'",
                            )
                        },
                        required=["entity_type"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_air_quality_by_location",
                    description="Get air quality data for any location using AirQo's enhanced site-based approach. PRIORITY for African locations.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "location": types.Schema(
                                type=types.Type.STRING,
                                description="Location name (city, town, or specific site name)",
                            ),
                            "country": types.Schema(
                                type=types.Type.STRING,
                                description="Country code (default 'UG' for Uganda)",
                            ),
                        },
                        required=["location"],
                    ),
                ),
            ]
        )

    def _get_gemini_weather_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_city_weather",
                    description="Get current weather conditions for any city. Returns temperature, humidity, wind, precipitation, and weather conditions.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the city",
                            )
                        },
                        required=["city"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_weather_forecast",
                    description="**Get detailed weather FORECAST for any city** - Use this when user asks for weather forecast, future weather, upcoming weather, or weather predictions. Returns hourly and daily forecasts up to 16 days including temperature, precipitation, humidity, wind, sunrise/sunset.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the city (e.g., 'London', 'New York', 'Tokyo')",
                            ),
                            "days": types.Schema(
                                type=types.Type.INTEGER,
                                description="Number of forecast days (1-16, default: 7)",
                            ),
                        },
                        required=["city"],
                    ),
                ),
            ]
        )

    def _get_gemini_search_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="search_web",
                    description="Search the web for any air quality information, news, research, policies, or general questions. Use this when APIs don't have data OR when user asks about news, policies, research, organizations, or general air quality topics. Returns recent web results with URLs. Format responses with sources: 'Source: [Title] (URL) - [Summary]'",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="Topic or location to search news for (e.g., 'Beijing air quality', 'WHO pollution standards', 'carbon emissions policy')",
                            )
                        },
                        required=["topic"],
                    ),
                ),
            ]
        )

    def _get_gemini_scrape_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="scrape_website",
                    description="Scrape content from a specific URL.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "url": types.Schema(
                                type=types.Type.STRING,
                                description="The URL to scrape",
                            )
                        },
                        required=["url"],
                    ),
                )
            ]
        )

    def _get_openai_waqi_tool(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_city_air_quality",
                    "description": "Get real-time air quality data for a specific city using WAQI.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the city (e.g., London, Paris, Kampala)",
                            }
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_waqi_stations",
                    "description": "Search for air quality monitoring stations by name or keyword.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "Search term (e.g., 'Bangalore', 'US Embassy')",
                            }
                        },
                        "required": ["keyword"],
                    },
                },
            },
        ]

    def _get_openai_airqo_tool(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_african_city_air_quality",
                    "description": "**PRIMARY TOOL for African cities** - Get real-time air quality from AirQo monitoring network. Use this FIRST for ANY African location (Uganda, Kenya, Tanzania, Rwanda, etc.). Searches by city/location name (e.g., Gulu, Kampala, Nakasero, Mbale, Nairobi). Returns actual measurements from local monitoring stations. Coverage includes major and minor cities across East Africa.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City or location name in Africa (e.g., 'Gulu', 'Kampala', 'Nakasero', 'Nairobi', 'Dar es Salaam')",
                            },
                            "site_id": {
                                "type": "string",
                                "description": "Optional site ID if known from previous searches",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_multiple_african_cities_air_quality",
                    "description": "Get real-time air quality for MULTIPLE African cities simultaneously. Use this when user asks about multiple locations (e.g., 'air quality in Kampala and Gulu', 'compare air quality between Nairobi and Dar es Salaam'). Returns data for all requested cities in one response for easy comparison.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of city names in Africa (e.g., ['Gulu', 'Kampala', 'Nairobi'])",
                            },
                        },
                        "required": ["cities"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_airqo_history",
                    "description": "Get historical air quality data for a specific site or device.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {
                                "type": "string",
                                "description": "The ID of the site (optional)",
                            },
                            "device_id": {
                                "type": "string",
                                "description": "The ID of the device (optional)",
                            },
                            "start_time": {
                                "type": "string",
                                "description": "Start time in ISO format",
                            },
                            "end_time": {"type": "string", "description": "End time in ISO format"},
                            "frequency": {
                                "type": "string",
                                "description": "Frequency: 'hourly', 'daily', or 'raw'",
                            },
                        },
                        "required": ["frequency"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_airqo_forecast",
                    "description": "Get air quality forecast for a site or device.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {
                                "type": "string",
                                "description": "The ID of the site (optional)",
                            },
                            "device_id": {
                                "type": "string",
                                "description": "The ID of the device (optional)",
                            },
                            "frequency": {
                                "type": "string",
                                "description": "Frequency: 'daily' or 'hourly'",
                            },
                        },
                        "required": ["frequency"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_airqo_metadata",
                    "description": "Get metadata for grids, cohorts, devices, or sites.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_type": {
                                "type": "string",
                                "description": "Type of entity: 'grids', 'cohorts', 'devices', 'sites'",
                            }
                        },
                        "required": ["entity_type"],
                    },
                },
            },
        ]

    def _get_gemini_openmeteo_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_openmeteo_current_air_quality",
                    description="Get current air quality data for any global location using Open-Meteo (CAMS). Provides comprehensive pollutant data and both European & US AQI indices. No API key needed, covers worldwide.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "latitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Latitude of the location",
                            ),
                            "longitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Longitude of the location",
                            ),
                            "timezone": types.Schema(
                                type=types.Type.STRING,
                                description="Timezone (auto, GMT, or IANA timezone like Europe/Berlin)",
                            ),
                        },
                        required=["latitude", "longitude"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_openmeteo_forecast",
                    description="Get hourly air quality forecast up to 7 days for any global location. Includes all major pollutants and AQI indices.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "latitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Latitude of the location",
                            ),
                            "longitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Longitude of the location",
                            ),
                            "forecast_days": types.Schema(
                                type=types.Type.INTEGER,
                                description="Number of forecast days (1-7)",
                            ),
                            "timezone": types.Schema(
                                type=types.Type.STRING,
                                description="Timezone (auto, GMT, or IANA timezone)",
                            ),
                        },
                        required=["latitude", "longitude"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_openmeteo_historical",
                    description="Get historical air quality data for any date range. Useful for trend analysis and long-term studies.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "latitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Latitude of the location",
                            ),
                            "longitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Longitude of the location",
                            ),
                            "start_date": types.Schema(
                                type=types.Type.STRING,
                                description="Start date in YYYY-MM-DD format",
                            ),
                            "end_date": types.Schema(
                                type=types.Type.STRING,
                                description="End date in YYYY-MM-DD format",
                            ),
                            "timezone": types.Schema(
                                type=types.Type.STRING,
                                description="Timezone (auto, GMT, or IANA timezone)",
                            ),
                        },
                        required=["latitude", "longitude", "start_date", "end_date"],
                    ),
                ),
            ]
        )

    def _get_openai_openmeteo_tool(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_openmeteo_current_air_quality",
                    "description": "Get current air quality data for any global location using Open-Meteo (CAMS). Provides comprehensive pollutant data and both European & US AQI indices. No API key needed, covers worldwide.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {
                                "type": "number",
                                "description": "Latitude of the location",
                            },
                            "longitude": {
                                "type": "number",
                                "description": "Longitude of the location",
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Timezone (auto, GMT, or IANA timezone like Europe/Berlin)",
                            },
                        },
                        "required": ["latitude", "longitude"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_openmeteo_forecast",
                    "description": "Get hourly air quality forecast up to 7 days for any global location. Includes all major pollutants and AQI indices.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {
                                "type": "number",
                                "description": "Latitude of the location",
                            },
                            "longitude": {
                                "type": "number",
                                "description": "Longitude of the location",
                            },
                            "forecast_days": {
                                "type": "integer",
                                "description": "Number of forecast days (1-7)",
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Timezone (auto, GMT, or IANA timezone)",
                            },
                        },
                        "required": ["latitude", "longitude"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_openmeteo_historical",
                    "description": "Get historical air quality data for any date range. Useful for trend analysis and long-term studies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {
                                "type": "number",
                                "description": "Latitude of the location",
                            },
                            "longitude": {
                                "type": "number",
                                "description": "Longitude of the location",
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format",
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Timezone (auto, GMT, or IANA timezone)",
                            },
                        },
                        "required": ["latitude", "longitude", "start_date", "end_date"],
                    },
                },
            },
        ]

    def _get_openai_weather_tool(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_city_weather",
                    "description": "Get current weather conditions for any city. Returns temperature, humidity, wind, precipitation, and weather conditions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "The name of the city"}
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather_forecast",
                    "description": "**Get detailed weather FORECAST for any city** - Use this when user asks for weather forecast, future weather, upcoming weather, or weather predictions. Returns hourly and daily forecasts up to 16 days including temperature, precipitation, humidity, wind, sunrise/sunset.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the city (e.g., 'London', 'New York', 'Tokyo')",
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of forecast days (1-16, default: 7)",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
        ]

    def _get_openai_search_tool(self):
        return {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for any air quality information, news, research, policies, or general questions. Use this when APIs don't have data OR when user asks about news, policies, research, organizations, or general air quality topics. Returns recent web results with URLs. Format responses with sources: 'Source: [Title] (URL) - [Summary]'",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Web search query"}},
                    "required": ["query"],
                },
            },
        }

    def _get_openai_scrape_tool(self):
        return {
            "type": "function",
            "function": {
                "name": "scrape_website",
                "description": "Scrape content from a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "The URL to scrape"}},
                    "required": ["url"],
                },
            },
        }

    def _get_gemini_document_scanner_tool(self):
        """Tool definition for Gemini to scan documents"""
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="scan_document",
                    description="Scan and extract text/data from uploaded documents. Supports PDF, CSV, and Excel (.xlsx, .xls) files. Use this when user uploads a document for analysis.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "file_path": types.Schema(
                                type=types.Type.STRING,
                                description="Absolute path to the document file to scan",
                            )
                        },
                        required=["file_path"],
                    ),
                )
            ]
        )

    def _get_openai_document_scanner_tool(self):
        """Tool definition for OpenAI to scan documents"""
        return {
            "type": "function",
            "function": {
                "name": "scan_document",
                "description": "Scan and extract text/data from uploaded documents. Supports PDF, CSV, and Excel (.xlsx, .xls) files. Use this when user uploads a document for analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the document file to scan",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        }

    # ------------------------------------------------------------------------
    # OLLAMA IMPLEMENTATION
    # ------------------------------------------------------------------------

    async def _process_ollama_message(
        self, message: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:

        client = ollama.AsyncClient(host=self.settings.OLLAMA_BASE_URL)

        # Convert history to Ollama format
        messages = [{"role": "system", "content": self._get_system_instruction()}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        # First call: check if model wants to use a tool
        response = await client.chat(
            model=self.settings.AI_MODEL,
            messages=messages,
            tools=self._get_ollama_tools(),
            options={
                "temperature": self.response_temperature,
                "top_p": self.response_top_p,
                "num_predict": 2048,
            },
        )

        tools_used = []

        # Check if the model decided to use the provided function
        tool_calls = response.get("message", {}).get("tool_calls", [])

        # Also check for tool calls embedded in content (for DeepSeek models)
        content = response.get("message", {}).get("content", "")
        if not tool_calls and content:
            try:
                # Try to parse JSON tool call from content
                import json

                # Look for JSON-like structure in content
                content_lower = content.lower()
                if "{" in content and "name" in content_lower and "arguments" in content_lower:
                    # Extract JSON from content
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        json_str = content[start:end]
                        tool_data = json.loads(json_str)
                        if "name" in tool_data and "arguments" in tool_data:
                            tool_calls = [{"function": tool_data}]
            except (json.JSONDecodeError, KeyError):
                pass

        if tool_calls:
            # Add the model's response (which includes the tool call) to history
            messages.append(response["message"])

            for tool in tool_calls:
                if "function" in tool:
                    function_name = tool["function"]["name"]
                    function_args = tool["function"]["arguments"]
                else:
                    # Handle DeepSeek format
                    function_name = tool["name"]
                    function_args = tool["arguments"]

                tools_used.append(function_name)

                logger.info(f"Ollama requested tool execution: {function_name}")

                tool_result = await self._execute_tool_async(function_name, function_args)

                # Add tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "content": str(tool_result),
                    }
                )

            # Second call: get final response with tool outputs
            final_response = await client.chat(
                model=self.settings.AI_MODEL,
                messages=messages,
                options={
                    "temperature": self.response_temperature,
                    "top_p": self.response_top_p,
                    "num_predict": 2048,
                },
            )
            return {
                "response": self._clean_response(final_response["message"]["content"]),
                "tools_used": tools_used,
            }

        return {
            "response": self._clean_response(response["message"]["content"]),
            "tools_used": tools_used,
        }

    def _get_ollama_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_city_air_quality",
                    "description": "Get real-time air quality data for a specific city using WAQI.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the city (e.g., London, Paris, Kampala)",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_african_city_air_quality",
                    "description": "**PRIMARY TOOL for African cities** - Get real-time air quality from AirQo monitoring network. Use this FIRST for ANY African location (Uganda, Kenya, Tanzania, Rwanda, etc.). Searches by city/location name (e.g., Gulu, Kampala, Nakasero, Mbale, Nairobi). Returns actual measurements from local monitoring stations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City or location name in Africa (e.g., 'Gulu', 'Kampala', 'Nakasero', 'Nairobi')",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_multiple_african_cities_air_quality",
                    "description": "Get real-time air quality for MULTIPLE African cities simultaneously. Use this when user asks about multiple locations (e.g., 'air quality in Kampala and Gulu', 'compare air quality between Nairobi and Dar es Salaam'). Returns data for all requested cities in one response for easy comparison.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of city names in Africa (e.g., ['Gulu', 'Kampala', 'Nairobi'])",
                            },
                        },
                        "required": ["cities"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_city_weather",
                    "description": "Get current weather conditions for any city. Returns temperature, humidity, wind, precipitation, and weather conditions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the city",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather_forecast",
                    "description": "**Get detailed weather FORECAST for any city** - Use this when user asks for weather forecast, future weather, upcoming weather, or weather predictions. Returns hourly and daily forecasts up to 16 days including temperature, precipitation, humidity, wind, sunrise/sunset.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the city (e.g., 'London', 'New York', 'Tokyo')",
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of forecast days (1-16, default: 7)",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for any air quality information, news, research, policies, or general questions. Use this when APIs don't have data OR when user asks about news, policies, research, organizations, or general air quality topics. Returns recent web results with URLs. Format responses with sources: 'Source: [Title] (URL) - [Summary]'",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Web search query",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "scrape_website",
                    "description": "Scrape content from a specific URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to scrape",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "scan_document",
                    "description": "Read and extract text from a document file (PDF or Text).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "The absolute path to the file to scan",
                            },
                        },
                        "required": ["file_path"],
                    },
                },
            },
        ]

    def _clean_response(self, content: str) -> str:
        """
        Clean the model response by removing thinking content, tool calls, and formatting for natural presentation.
        Now includes professional markdown formatting.
        """
        if not content:
            return content

        try:
            import re

            from src.utils.markdown_formatter import format_markdown

            # Remove XML-like tool calling syntax
            content = re.sub(r"<tool_call>.*?</tool_call>", "", content, flags=re.DOTALL)
            content = re.sub(r"<function=.*?>", "", content)
            content = re.sub(r"</function>", "", content)
            content = re.sub(r"<parameter=.*?>", "", content)
            content = re.sub(r"</parameter>", "", content)

            # Remove <think> blocks
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
            content = content.replace("<think>", "").replace("</think>", "")

            # Remove conversational thinking patterns at the start
            # Matches lines like "Okay, let me...", "I will now...", "Let's figure out..."
            lines = content.split("\n")
            cleaned_lines = []
            skip_mode = True

            thinking_patterns = (
                "let me",
                "i will",
                "i need to",
                "okay, so",
                "alright,",
                "first, i",
                "to answer this",
                "i'll start",
                "let's break",
                "i am going to",
                "based on the",
                "i have retrieved",
                "searching for",
            )

            for line in lines:
                line_lower = line.strip().lower()
                # If we are in skip mode (start of message) and line looks like thinking
                if skip_mode and (
                    any(p in line_lower for p in thinking_patterns)
                    or len(line.strip()) < 3
                    or line.strip().endswith("...")
                ):
                    continue

                # Once we hit a real line (like a heading or substantial text), stop skipping
                skip_mode = False
                cleaned_lines.append(line)

            content = "\n".join(cleaned_lines)

            # Clean up excessive newlines and whitespace
            content = re.sub(r"\n{3,}", "\n\n", content)
            content = content.strip()

            # Apply professional markdown formatting
            # This ensures lists, tables, headers are properly formatted
            try:
                content = format_markdown(content)
            except Exception as fmt_error:
                logger.warning(f"Markdown formatting failed, continuing with basic cleanup: {fmt_error}")

            # Return content or empty string (let fallback handle empty)
            return content

        except Exception as e:
            logger.error(f"Error cleaning response: {e}")
            return content  # Return original if cleaning fails

    # ------------------------------------------------------------------------
    # SHARED HELPERS
    # ------------------------------------------------------------------------

    def _execute_tool(self, function_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the requested tool synchronously (for Gemini and OpenAI)"""
        try:
            if function_name == "get_city_air_quality":
                city = args.get("city")
                return self.waqi.get_city_feed(city)
            elif function_name == "search_waqi_stations":
                keyword = args.get("keyword")
                return self.waqi.search_stations(keyword)
            elif function_name == "get_african_city_air_quality":
                city = args.get("city")
                site_id = args.get("site_id")
                # Try AirQo first with smart search
                try:
                    result = self.airqo.get_recent_measurements(city=city, site_id=site_id)
                    if result.get("success"):
                        return result
                    # If AirQo returns success=False, log but don't fallback here
                    # Let the AI decide to try WAQI based on the response
                    logger.info(f"AirQo returned no data for {city}: {result.get('message')}")
                    return result
                except Exception as e:
                    logger.error(f"AirQo API error for {city}: {e}")
                    return {
                        "success": False,
                        "message": f"Could not retrieve AirQo data for {city}. The location may not have AirQo monitoring coverage.",
                        "error": str(e),
                    }
            elif function_name == "get_airqo_history":
                from datetime import datetime

                start_time = (
                    datetime.fromisoformat(args.get("start_time"))
                    if args.get("start_time")
                    else None
                )
                end_time = (
                    datetime.fromisoformat(args.get("end_time")) if args.get("end_time") else None
                )
                return self.airqo.get_historical_measurements(
                    site_id=args.get("site_id"),
                    device_id=args.get("device_id"),
                    start_time=start_time,
                    end_time=end_time,
                    frequency=args.get("frequency", "hourly"),
                )
            elif function_name == "get_airqo_forecast":
                return self.airqo.get_forecast(
                    site_id=args.get("site_id"),
                    device_id=args.get("device_id"),
                    city=args.get("city"),
                    frequency=args.get("frequency", "daily"),
                )
            elif function_name == "get_airqo_metadata":
                return self.airqo.get_metadata(entity_type=args.get("entity_type", "grids"))
            elif function_name == "get_air_quality_by_location":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                return self.airqo.get_air_quality_by_location(
                    latitude=latitude, longitude=longitude
                )
            elif function_name == "get_openmeteo_current_air_quality":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                timezone = args.get("timezone", "auto")
                return self.openmeteo.get_current_air_quality(
                    latitude=latitude, longitude=longitude, timezone=timezone
                )
            elif function_name == "get_openmeteo_forecast":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                forecast_days = args.get("forecast_days", 5)
                timezone = args.get("timezone", "auto")
                return self.openmeteo.get_hourly_forecast(
                    latitude=latitude,
                    longitude=longitude,
                    forecast_days=forecast_days,
                    timezone=timezone,
                )
            elif function_name == "get_openmeteo_historical":
                from datetime import datetime

                latitude = args.get("latitude")
                longitude = args.get("longitude")
                start_date = datetime.strptime(args.get("start_date"), "%Y-%m-%d")
                end_date = datetime.strptime(args.get("end_date"), "%Y-%m-%d")
                timezone = args.get("timezone", "auto")
                return self.openmeteo.get_historical_data(
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                    timezone=timezone,
                )
            elif function_name == "get_city_weather":
                city = args.get("city")
                return self.weather.get_current_weather(city)
            elif function_name == "get_weather_forecast":
                city = args.get("city")
                days = args.get("days", 7)
                return self.weather.get_weather_forecast(city, days)
            elif function_name == "search_web":
                query = args.get("query")
                return self.search.search(query)
            elif function_name == "scrape_website":
                url = args.get("url")
                return self.scraper.scrape(url)
            elif function_name == "scan_document":
                file_path = args.get("file_path")
                return self.document_scanner.scan_document(file_path)
            else:
                return {
                    "error": f"Unknown function {function_name}",
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches.",
                }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Return a structured error that helps the AI provide a better response
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "guidance": "This data source is currently unavailable or the requested location was not found. Please inform the user and suggest they try a different location or data source.",
            }

    async def _execute_tool_async(self, function_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the requested tool asynchronously"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            if function_name == "get_city_air_quality":
                city = args.get("city")
                return await loop.run_in_executor(None, self.waqi.get_city_feed, city)
            elif function_name == "search_waqi_stations":
                keyword = args.get("keyword")
                return await loop.run_in_executor(None, self.waqi.search_stations, keyword)
            elif function_name == "get_african_city_air_quality":
                city = args.get("city")
                site_id = args.get("site_id")
                # Try AirQo first with smart search
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self.airqo.get_recent_measurements(city=city, site_id=site_id),
                    )
                    if result.get("success"):
                        return result
                    # If AirQo returns success=False, log but don't fallback here
                    logger.info(f"AirQo returned no data for {city}: {result.get('message')}")
                    return result
                except Exception as e:
                    logger.error(f"AirQo API error for {city}: {e}")
                    return {
                        "success": False,
                        "message": f"Could not retrieve AirQo data for {city}. The location may not have AirQo monitoring coverage.",
                        "error": str(e),
                    }
            elif function_name == "get_multiple_african_cities_air_quality":
                cities = args.get("cities", [])
                if not cities:
                    return {"error": "No cities provided"}
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self.airqo.get_multiple_cities_air_quality(cities),
                    )
                    return result
                except Exception as e:
                    logger.error(f"Error getting multiple cities air quality: {e}")
                    return {
                        "success": False,
                        "message": f"Could not retrieve air quality data for multiple cities: {str(e)}",
                        "error": str(e),
                    }
            elif function_name == "get_airqo_history":
                from datetime import datetime

                start_time = (
                    datetime.fromisoformat(args.get("start_time"))
                    if args.get("start_time")
                    else None
                )
                end_time = (
                    datetime.fromisoformat(args.get("end_time")) if args.get("end_time") else None
                )
                return await loop.run_in_executor(
                    None,
                    lambda: self.airqo.get_historical_measurements(
                        site_id=args.get("site_id"),
                        device_id=args.get("device_id"),
                        start_time=start_time,
                        end_time=end_time,
                        frequency=args.get("frequency", "hourly"),
                    ),
                )
            elif function_name == "get_airqo_forecast":
                return await loop.run_in_executor(
                    None,
                    lambda: self.airqo.get_forecast(
                        site_id=args.get("site_id"),
                        device_id=args.get("device_id"),
                        city=args.get("city"),
                        frequency=args.get("frequency", "daily"),
                    ),
                )
            elif function_name == "get_airqo_metadata":
                return await loop.run_in_executor(
                    None,
                    lambda: self.airqo.get_metadata(entity_type=args.get("entity_type", "grids")),
                )
            elif function_name == "get_air_quality_by_location":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                return await loop.run_in_executor(
                    None,
                    lambda: self.airqo.get_air_quality_by_location(
                        latitude=latitude, longitude=longitude
                    ),
                )
            elif function_name == "get_openmeteo_current_air_quality":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                timezone = args.get("timezone", "auto")
                return await loop.run_in_executor(
                    None,
                    lambda: self.openmeteo.get_current_air_quality(
                        latitude=latitude, longitude=longitude, timezone=timezone
                    ),
                )
            elif function_name == "get_openmeteo_forecast":
                latitude = args.get("latitude")
                longitude = args.get("longitude")
                forecast_days = args.get("forecast_days", 5)
                timezone = args.get("timezone", "auto")
                return await loop.run_in_executor(
                    None,
                    lambda: self.openmeteo.get_hourly_forecast(
                        latitude=latitude,
                        longitude=longitude,
                        forecast_days=forecast_days,
                        timezone=timezone,
                    ),
                )
            elif function_name == "get_openmeteo_historical":
                from datetime import datetime

                latitude = args.get("latitude")
                longitude = args.get("longitude")
                start_date = datetime.strptime(args.get("start_date"), "%Y-%m-%d")
                end_date = datetime.strptime(args.get("end_date"), "%Y-%m-%d")
                timezone = args.get("timezone", "auto")
                return await loop.run_in_executor(
                    None,
                    lambda: self.openmeteo.get_historical_data(
                        latitude=latitude,
                        longitude=longitude,
                        start_date=start_date,
                        end_date=end_date,
                        timezone=timezone,
                    ),
                )
            elif function_name == "get_city_weather":
                city = args.get("city")
                return await loop.run_in_executor(None, self.weather.get_current_weather, city)
            elif function_name == "get_weather_forecast":
                city = args.get("city")
                days = args.get("days", 7)
                return await loop.run_in_executor(
                    None, lambda: self.weather.get_weather_forecast(city, days)
                )
            elif function_name == "search_web":
                query = args.get("query")
                return await loop.run_in_executor(None, self.search.search, query)
            elif function_name == "scrape_website":
                url = args.get("url")
                return await loop.run_in_executor(None, self.scraper.scrape, url)
            elif function_name == "scan_document":
                file_path = args.get("file_path")
                return await loop.run_in_executor(
                    None, self.document_scanner.scan_document, file_path
                )
            else:
                return {
                    "error": f"Unknown function {function_name}",
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches.",
                }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Return a structured error that helps the AI provide a better response
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "guidance": "This data source is currently unavailable or the requested location was not found. Please inform the user and suggest they try a different location or data source.",
            }
