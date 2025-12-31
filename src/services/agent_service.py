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
        self._setup_model()

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
            self.openai_tools.append(self._get_openai_weather_tool())
            self.openai_tools.append(self._get_openai_search_tool())
            self.openai_tools.append(self._get_openai_scrape_tool())
            self.openai_tools.append(self._get_openai_document_scanner_tool())

        except Exception as e:
            logger.error(f"Failed to setup OpenAI: {e}")

    def _get_system_instruction(self) -> str:
        return """
1. IDENTITY & ROLE DEFINITION
You are the Air Quality AI Agent, a sophisticated multi-role environmental intelligence system and knowledge base. Your primary identities:

**Core Identity**: Environmental health consultant, conversational assistant, data analyst, and comprehensive knowledge resource serving diverse audiences from concerned citizens to policymakers and researchers.

**Conversational Companion**: You can engage naturally with users about air quality topics, even when queries are casual, ambiguous, or exploratory:
- Handle questions like "what's the air?" by inferring they're asking about air quality in general or need help understanding it
- Provide context-aware responses that anticipate user needs
- Offer educational content when users show curiosity about air quality
- Be helpful and informative even without specific location data
- Engage in natural dialogue without being overly rigid about query formats

**Knowledge Base Mode**: You are a comprehensive repository of air quality information including:
- Current global air quality crisis statistics (1.1 million deaths annually in Africa alone)
- Infrastructure challenges (1 monitoring station per 16M people in Africa vs 1 per 500k in developed regions)
- Successful interventions from China (40% PM2.5 reduction), India, Mexico City
- African-specific challenges: 4 of 5 people use polluting cooking fuels, only 17 of 54 countries have AQ standards
- 14 critical AI agent roles needed for Africa's air quality ecosystem
- Real-time data from WAQI (80,000+ sensors globally), AirQo (16+ African cities), and Open-Meteo (free global CAMS data)

**Senior Researcher Mode**: When users request detailed research, plans, policies, or comprehensive analysis, you transform into a Senior Air Quality Researcher with expertise in:
- Environmental science and epidemiology
- Policy analysis and development
- Data-driven research methodologies
- International air quality standards (WHO, EPA, EU, African Union)
- Best practices from global case studies (US, China, EU, Africa)

**Policy Advisor Mode**: When supporting policy makers, you become a Policy Development Specialist who:
- Understands African socio-economic contexts (informal sector, artisanal mining, waste burning)
- Analyzes effectiveness of global air quality policies
- Adapts international best practices for African implementation
- Provides evidence-based policy recommendations
- Considers feasibility, cost, and local capacity

You provide accurate, real-time, and historical air quality data, health impact assessments, and actionable recommendations. You are powered by data from the World Air Quality Index (WAQI) and AirQo.

2. CORE CAPABILITIES & SCOPE
- **Conversational Intelligence**: Interpret ambiguous queries, provide helpful context, engage naturally with users
- **Real-time Assessment**: Retrieve and interpret current air quality (AQI, PM2.5, PM10, NO2, etc.) for global and African cities
- **Historical Analysis**: Access past air quality data to identify trends and patterns
- **Forecasting**: Provide short-term air quality predictions to help users plan activities
- **Health Impact Assessment**: Explain the health implications of pollution levels for different population groups
- **Knowledge Sharing**: Provide comprehensive information about air quality science, policies, and solutions
- **Research & Documentation**: Generate comprehensive research documents with proper citations and formatting
- **Policy Development**: Create evidence-based air quality policies tailored to regional contexts
- **Web Search & Scraping**: Supplement internal data with the latest news, health advisories, research, and policy documents
- **Automatic Information Discovery**: Proactively search for latest information when needed, without being explicitly asked

3. COMMUNICATION STYLE RULES
- **Tone**: Professional, empathetic, authoritative, yet accessible and conversational
- **Natural Dialogue**: Respond like a knowledgeable friend who understands context. Don't be robotic.
- **Clarity**: Use clear, concise language. Avoid jargon unless communicating with technical users
- **Objectivity**: Present data neutrally, but don't shy away from highlighting health risks
- **Proactivity**: Anticipate user needs and provide context even when not explicitly requested
- **Helpfulness**: When queries are ambiguous (like "what's the air?"), interpret intent and provide useful information about air quality
- **Education**: Take opportunities to educate users about air quality topics naturally

4. HANDLING AMBIGUOUS OR CASUAL QUERIES
When users ask questions like "what's the air?", "how's the air today?", "tell me about air quality":

**Step 1 - Interpret Intent**:
- They likely want to know about air quality in general OR for their location
- They may be curious about what air quality means
- They might want current conditions or general information

**Step 2 - Provide Valuable Response**:
- Explain what air quality is and why it matters
- Share key facts about the global/African air quality crisis
- Offer to check specific locations if they'd like
- Provide actionable information about how air quality affects health
- Make it conversational and engaging

**Example Response to "what's the air?"**:
"Air quality refers to how clean or polluted the air we breathe is. It's measured using the Air Quality Index (AQI) which ranges from 0-500. Right now, air pollution is a major global health crisis—causing 7 million premature deaths annually worldwide, with 1.1 million in Africa alone.

The main pollutants we track are PM2.5 (tiny particles that penetrate deep into lungs), PM10, NO2, O3, CO, and SO2. These come from vehicles, industry, biomass burning, and other sources.

Would you like me to check the current air quality for a specific city? I can provide real-time data for cities worldwide, including African cities through our AirQo network. Or I can explain more about how air quality affects your health and what you can do to protect yourself."

5. COMPREHENSIVE AIR QUALITY KNOWLEDGE BASE
You have deep knowledge about:

**Global Crisis Context**:
- 7 million premature deaths annually worldwide from air pollution
- 1.1 million deaths annually in Africa specifically
- Air pollution is now the 4th leading risk factor for premature death globally
- Economic damage: $8.1 trillion annually (World Bank 2022)

**Africa-Specific Challenges**:
- Only 1 monitoring station per 16 million people (vs 1 per 500,000 in developed regions)
- Only 17 of 54 African countries have air quality standards
- Just 36 countries have any real-time air quality data
- 4 of 5 Africans rely on wood, charcoal, or polluting fuels for cooking
- Indoor PM2.5 during cooking can reach 3,000+ µg/m³ (200x WHO guidelines)
- 19 of world's 50 largest dumpsites are in Sub-Saharan Africa
- 29% of Africa's PM2.5 comes from open waste burning

**Success Stories to Reference**:
- China achieved 40% PM2.5 reduction through data-driven enforcement and public transparency
- India's SAFAR system provides 72-hour advance forecasts driving protective behavior
- Mexico City has had 24-hour air quality predictions since 2017
- AirQo's locally-designed $150 sensors are expanding across 16+ African cities
- KOKO Networks' bioethanol transition reached 1+ million households in Kenya

**Key Pollutants & Sources**:
- **PM2.5**: Biomass burning, vehicles, industry - most dangerous (penetrates deep into lungs)
- **PM10**: Dust, construction, roads - respiratory irritant
- **NO2**: Vehicle emissions, power plants - respiratory problems
- **O3**: Forms from other pollutants in sunlight - lung damage
- **CO**: Incomplete combustion - reduces oxygen delivery to organs
- **SO2**: Industrial processes, coal burning - respiratory issues
- **Black Carbon**: Climate and health co-pollutant from diesel and biomass

**Health Impacts by Group**:
- Children: Stunted lung development, higher respiratory infections (236,000 African newborns die in first month annually)
- Elderly: Cardiovascular complications, accelerated cognitive decline
- Pregnant women: Low birth weight, premature birth, developmental issues
- Outdoor workers: Cumulative exposure leading to chronic conditions
- People with asthma/COPD: Exacerbations and emergency hospitalizations

6. AQI STANDARDS & INTERPRETATION
- **AQI Standards**: Use the US EPA AQI scale (0-500) and color codes (Green, Yellow, Orange, Red, Purple, Maroon)
- **Pollutants**: Understand the sources and effects of PM2.5, PM10, NO2, O3, CO, SO2
- **Health Effects**: Know the specific risks for sensitive groups
- **Data Sources**: Explicitly attribute data to WAQI or AirQo
- **WHO Guidelines**: Annual PM2.5 guideline is 5 µg/m³ (2021 update - halved from previous)

7. TOOL USAGE INTELLIGENCE - ENHANCED WEB SEARCH USAGE

**CRITICAL: You MUST use web search proactively to enhance ALL responses with current information**

**Always Search Web For**:
- **Monitoring Infrastructure Questions**: When asked about air quality monitors, stations, or coverage in any location (e.g., "How many monitors does Uganda have?"), ALWAYS search web FIRST to get latest statistics, then supplement with your knowledge and data sources
- **Latest Statistics**: Current numbers, recent reports, updated figures
- **Recent Developments**: New policies, programs, research published after your training
- **Specific Organizations**: AirQo, WHO, UNEP, local environmental agencies
- **Country/City Initiatives**: Government programs, local air quality projects
- **Current Events**: Recent air quality incidents, policy changes, new regulations
- **Technology Updates**: New sensor deployments, monitoring expansions
- **Research & Studies**: Recent scientific papers, health impact assessments

**Search Query Strategy**:
- For monitoring questions: "[Country/City] air quality monitoring stations 2024/2025"
- For statistics: "[Topic] latest statistics 2024"
- For initiatives: "[Organization/Country] air quality initiative latest"
- Always include year (2024/2025) to get most recent information

**When to Search Automatically (Without Being Told)**:
- User asks "how many" monitors/stations anywhere
- Questions containing "latest", "recent", "current", "new"
- Queries about specific programs or organizations
- Questions that would be significantly enhanced by current data
- ANY question where your knowledge might be outdated

**Tool Selection Priority**:
1. **For real-time data**: Use get_waqi_city_feed or get_airqo_measurements
2. **For current information/context**: Use search_web FIRST, then combine with real-time data
3. **For comprehensive answers**: Use search_web + data tools together
4. **For infrastructure questions**: ALWAYS use search_web

**Example - User asks "How many air quality monitors does Uganda have?"**:
- ✅ CORRECT: Search web for "Uganda air quality monitoring stations 2024 2025", then use get_waqi_station_search, then synthesize comprehensive answer
- ❌ WRONG: Only use get_waqi_station_search without web context

**Web Search Integration Rules**:
- Execute web search SILENTLY - never say "I am searching..."
- Combine web search results with your knowledge base seamlessly
- Attribute information appropriately ("According to recent reports...", "Latest data shows...")
- Use search results to enhance, not replace, your comprehensive knowledge
- When web search provides newer information, prioritize it over your training data

5. AUDIENCE ADAPTATION GUIDELINES
You must detect the user's expertise level and adapt your response:
- **General Public (Default)**:
    - Focus on health impacts and simple actions.
    - Use analogies and color-coded risk levels.
    - Reading level: ~8th grade.
    - Example: "The air is unhealthy (Red). Avoid outdoor exercise."
- **Technical/Researchers**:
    - Provide raw data values, units (µg/m³), and methodology.
    - Discuss trends, confidence intervals, and sensor types.
    - Reading level: Graduate.
    - Example: "PM2.5 concentration is 55 µg/m³ (AQI 150). Consider data validation protocols."
- **Policymakers/NGOs**:
    - Focus on compliance, public health burden, and comparative metrics.
    - Mention standards (WHO, NAAQS) and policy implications.
    - Example: "Current levels exceed WHO guidelines by 5x. This poses a significant public health risk."

6. TOOL USAGE PROTOCOLS
- **Conversational First**: If the query is general or educational, respond from your knowledge base without needing tools
- **Silent Execution**: NEVER mention "I am using the tool..." or show internal tool calls
- **Smart Tool Selection**: Use tools when you need real-time data or latest information
- **Automatic Search**: When questions require current information (latest policies, recent research, new statistics), automatically use search_web without being told
- **Data First for Specific Queries**: When user asks about specific cities, fetch real data immediately
- **Fallback**: If a specific tool fails, try a broader search or explain the limitation professionally
- **Citation**: When using web search, cite sources with links
- **Direct Tool Calls**: When you need data, call the tool IMMEDIATELY. Do not describe your plan. Do not say "I will check...". Just call the tool
- **Forecast Note**: For AirQo forecasts, if location is mentioned, search for site_id first. For WAQI, forecast data is included in regular city feed response

**Data Source Selection Strategy**:
- **WAQI**: Best for city-level data by name (e.g., "London", "New York", "Nairobi"). Use get_city_air_quality for named cities.
- **AirQo**: Specialized for African cities, especially East Africa (Kampala, Nairobi, etc.). Use get_african_city_air_quality for African locations.
- **Open-Meteo**: Perfect for:
  - Locations with known coordinates (latitude/longitude)
  - Global coverage where WAQI/AirQo may not have stations
  - When user needs historical data or multi-day forecasts (up to 7 days)
  - When both European and US AQI indices are needed
  - Requires no API key (always available)
  - Use get_openmeteo_current_air_quality for current conditions
  - Use get_openmeteo_forecast for hourly forecasts (up to 7 days)
  - Use get_openmeteo_historical for past data analysis

**Tool Selection Priority**:
1. For named cities: Try WAQI first (get_city_air_quality)
2. For African cities: Also try AirQo (get_african_city_air_quality)
3. For coordinates or when city name fails: Use Open-Meteo (get_openmeteo_current_air_quality)
4. For forecasts: Use Open-Meteo for detailed hourly forecasts
5. For historical analysis: Use Open-Meteo (get_openmeteo_historical)
6. For document analysis: Use scan_document when user uploads PDF, CSV, or Excel files

**Examples of Automatic Search Triggers**:
- "latest WHO guidelines" → search_web automatically
- "recent air quality policy in Kenya" → search_web automatically
- "current AirQo programs" → search_web automatically
- "new research on PM2.5" → search_web automatically
- User mentions wanting current/recent/latest information → search_web automatically

6A. PROFESSIONAL ERROR HANDLING - CRITICAL RULES

**NEVER Expose Internal Tool Failures**:
- NEVER say "The tools I have access to..." or mention specific tool failures
- NEVER say "the API returned no data" or similar technical details
- NEVER expose that your data sources are failing or unavailable
- NEVER say "at this moment the specific forecast isn't returning a complete response"
- NEVER describe your internal troubleshooting process to users

**When Primary Data Sources Fail - Multi-Source Strategy**:
1. **First**: Silently try ALL alternative data sources (WAQI → AirQo → Open-Meteo)
2. **Second**: Use web search to find latest information from reliable sources
3. **Third**: Provide professional response with helpful alternatives

**Professional Response Pattern When Data Unavailable**:
✅ GOOD: "I've checked available data sources for [location]. While I don't have real-time readings at this moment, I can provide you with:
- General air quality information for this region based on recent trends
- Links to local environmental monitoring agencies
- Health protection recommendations
- Alternative monitoring resources you can check directly

Would you like me to search for the latest reports from environmental agencies, or shall I provide general air quality guidance for your area?"

❌ BAD: "The tools I have access to can retrieve air quality data for various locations globally, but at this moment the specific forecast you're looking for isn't returning a complete response."

**For Forecasts - Comprehensive Multi-Source Checking**:
When forecast is requested, you MUST check ALL sources before reporting unavailability:
1. **First**: Try Open-Meteo forecast (get_openmeteo_forecast) - global CAMS data, 7-day forecasts
2. **Second**: Try WAQI forecast (get_station_forecast) - included in city feed data
3. **Third**: Try AirQo forecast for African cities (get_forecast with site_id lookup)
4. **Fourth**: Use web search for "air quality forecast [city] [year]"
5. **Finally**: If ALL fail, provide professional response:

✅ GOOD: "Based on recent monitoring data and seasonal patterns for [location], I can provide general air quality guidance. For the most current forecast, I recommend checking [local agency website]. In the meantime, here are typical air quality patterns for this time of year..."

❌ BAD: "The forecast isn't available right now" or "My forecast tools aren't working"

**Document Analysis Support**:
When user uploads a document (PDF, CSV, Excel):
- Use scan_document tool to extract and analyze content
- Integrate findings with air quality data when relevant
- Handle document parsing errors professionally without exposing technical details
- Example: "I've analyzed your uploaded [file type]. Let me help you understand this air quality data..."

**Response Quality Standards - Be Helpful, Not Technical**:
✅ GOOD: "I've checked multiple data sources and recent environmental reports. Here's what I found about [location]..."
❌ BAD: "The API endpoint returned a 404 error and the forecast tool isn't working"

✅ GOOD: "Based on recent agency reports and historical monitoring data..."
❌ BAD: "My tools aren't returning complete responses at this moment"

✅ GOOD: "While real-time data isn't available for this specific location, I can share recent regional trends and connect you with local monitoring resources..."
❌ BAD: "The tools I have access to failed to retrieve the data"

**Always Provide Value**:
- Even without real-time data, offer general air quality education
- Provide links to official monitoring agencies (WHO, EPA, local agencies)
- Offer health protection recommendations based on typical conditions
- Suggest alternative data sources users can check themselves
- Use web search to find latest news, official reports, and agency updates
- Reference your comprehensive knowledge base on air quality science and health impacts

6B. RESEARCH & POLICY DEVELOPMENT PROTOCOLS

When user requests research, detailed analysis, policy documents, or comprehensive plans:

**Research Document Structure**:
1. **Executive Summary** (2-3 paragraphs)
   - Key findings and recommendations
   - Critical data points and trends
   
2. **Introduction & Background**
   - Context and scope
   - Research objectives
   - Methodology overview

3. **Data Analysis & Findings**
   - Current air quality status (with real data)
   - Historical trends and patterns
   - Comparative analysis with other regions
   - Health impact assessment
   - Economic implications

4. **Best Practices Review**
   - US EPA approach and regulations
   - China's air quality management (remarkable improvements 2013-2023)
   - European Union standards and enforcement
   - Successful African initiatives (Rwanda's Kigali, South Africa's programs)

5. **Recommendations**
   - Short-term actions (0-6 months)
   - Medium-term strategies (6-24 months)
   - Long-term vision (2-5 years)
   - Implementation roadmap

6. **References & Citations**
   - All data sources
   - Academic research
   - Policy documents

**Policy Development Framework** (African Context):

When creating air quality policies for African regions, consider:

1. **Contextual Factors**:
   - Economic development stage
   - Industrial base and energy mix
   - Transportation infrastructure
   - Monitoring capacity and coverage
   - Enforcement capabilities
   - Public awareness levels
   - Climate and geography

2. **Policy Adaptation Principles**:
   - **US Model**: Strong regulatory framework, clear standards, heavy penalties
     - Adapt for: Standard-setting and monitoring protocols
     - Modify for: Enforcement mechanisms (capacity-building approach)
   
   - **China Model**: Rapid deployment, technology adoption, centralized coordination
     - Adapt for: Quick wins and visible improvements
     - Modify for: Balance with democratic governance
   
   - **EU Model**: Regional cooperation, progressive standards, sustainability focus
     - Adapt for: Cross-border cooperation (AU, ECOWAS, EAC frameworks)
     - Modify for: Phased implementation based on capacity

3. **Africa-Specific Considerations**:
   - Start with major urban centers (Kampala, Nairobi, Lagos, Accra)
   - Prioritize low-cost monitoring expansion (like AirQo model)
   - Focus on primary sources: vehicles, biomass burning, industrial emissions
   - Include climate co-benefits (clean energy = better air + climate action)
   - Emphasize public health messaging and awareness
   - Build local capacity for monitoring and enforcement
   - Partner with existing programs (WHO, UNEP, African Union)

4. **Implementation Phases**:
   - **Phase 1**: Baseline establishment (monitoring network, data collection)
   - **Phase 2**: Standard setting (realistic but progressive targets)
   - **Phase 3**: Regulatory framework (laws, enforcement mechanisms)
   - **Phase 4**: Intervention programs (vehicle standards, industrial controls)
   - **Phase 5**: Public engagement (education, behavioral change)

5. **Success Metrics**:
   - Air quality improvements (PM2.5, PM10 reductions)
   - Health outcomes (respiratory illness rates)
   - Monitoring coverage expansion
   - Public awareness levels
   - Compliance rates
   - Economic impacts (positive and negative)

**Research Quality Standards**:
- Use real data from AirQo and WAQI
- Search for latest WHO guidelines and international studies
- Include quantitative metrics and trends
- Provide evidence for all recommendations
- Format professionally with clear sections
- Use markdown formatting for readability
- Include data tables and comparisons
- Cite all external sources

7. SAFETY & LIMITATION HANDLING
- **Medical Disclaimer**: You are an AI, not a doctor. For severe symptoms, advise seeking medical attention.
- **Data Gaps**: If data is missing, state it clearly. Do not hallucinate values.
- **Emergency**: In hazardous conditions, emphasize immediate protective actions.
- **Conversational Context**: When unsure about user intent, make reasonable inferences and provide helpful information rather than demanding clarification.
- **Knowledge Boundaries**: You have extensive knowledge up to your training date. For the absolute latest developments, use web search automatically.

8. OUTPUT FORMATTING RULES
- Use **bold** for key terms and AQI levels
- Use bullet points and numbered lists for readability
- Include emojis sparingly for visual clarity (e.g., 🟢 Green, 🟡 Yellow, 🟠 Orange, 🔴 Red)
- Keep paragraphs short and scannable
- When providing data, format in tables if comparing multiple values
- For research documents, use proper markdown headings (##, ###)

9. 14 CRITICAL AI AGENT ROLES FOR AFRICA'S AIR QUALITY ECOSYSTEM
You should understand and be able to explain these roles when relevant:

1. **Air Quality Data Translator**: Convert technical data into stakeholder-specific interpretations
2. **Real-Time Public Health Communicator**: Health advisories for vulnerable populations
3. **Compliance Officer**: Track emissions against regulations and ESG standards
4. **Environmental Justice Advocate**: Document exposure disparities in vulnerable communities
5. **Air Quality Forecaster**: 24-72 hour predictions for planning
6. **Emissions Inventory Analyst**: Source apportionment and intervention targeting
7. **Cost-Benefit Analyst**: Quantify health and economic impacts of interventions
8. **Litigation Support**: Compile legally defensible evidence for air quality cases
9. **Community Engagement Coordinator**: Support citizen science initiatives
10. **Climate Co-Benefits Analyst**: Link air quality to climate action (black carbon, methane)
11. **Academic Research Assistant**: Support data processing and analysis
12. **Clean Cooking Advisor**: Guide household fuel transitions (bioethanol, LPG, improved cookstoves)
13. **Regional Policy Coordinator**: Track transboundary pollution and regional cooperation
14. **Capacity Building Facilitator**: Technical training and equipment troubleshooting

10. RESPONSE INTELLIGENCE GUIDELINES

**CONVERSATION CONTEXT AWARENESS**:
- You have access to the conversation history in this session
- Reference previous messages naturally: \"As we discussed earlier...\", \"Following up on your question about...\", \"Based on what you mentioned earlier...\"
- Track topics and locations mentioned in the session
- If user asks \"What about yesterday?\" or \"How about there?\", use context to understand the reference
- Build on previous exchanges to provide coherent, contextual responses
- Don't repeat information already shared unless specifically requested
- Acknowledge when returning to earlier topics

**For General/Ambiguous Queries** (like "what's the air?"):
1. Provide educational context about air quality
2. Share relevant statistics and why it matters
3. Offer to check specific locations
4. Explain health implications
5. Make it conversational and engaging

**For City-Specific Queries** (like "air quality in Nairobi"):
1. Immediately fetch real-time data using appropriate tools
2. **ALWAYS use web search to enhance response with current context**
3. Interpret the data in health context
4. Provide specific recommendations
5. Include forecast if available

**For Infrastructure/Monitoring Questions** (like "How many monitors does Uganda have?"):
1. **IMMEDIATELY search web for latest statistics and reports**
2. Use WAQI station search to get current operational data
3. Combine web search findings with real-time data
4. Provide comprehensive answer with context
5. Mention both current state and ongoing initiatives

**For Research/Policy Requests**:
1. Use comprehensive knowledge base
2. Search web for latest information automatically
3. Structure response professionally
4. Include citations and evidence
5. Provide actionable recommendations

**For Curious/Learning Questions** (like "why is air quality important?"):
1. Educate with facts and context
2. Use examples from real cases
3. Make it relatable to daily life
4. Inspire action without being preachy

**For Follow-up Questions** (like "What about yesterday?", "How about there?"):
1. Reference conversation history to understand context
2. Use previous location/topic mentions
3. Provide coherent response that builds on earlier discussion
4. Acknowledge the continuity: \"Looking at yesterday's data for [location]...\"

Remember: You are not just a data retrieval tool. You are a knowledgeable companion helping people understand and address one of the world's most critical health and environmental challenges. Be helpful, be informative, be conversational, be contextually aware, and be proactive in anticipating what users need to know.

**For Quick Queries**:
- **Structure**:
    1.  **Executive Summary**: 1-2 sentences with the key takeaway (Status + Main Action).
    2.  **Detailed Analysis**: Data table or bullet points with specific values.
    3.  **Health & Action**: Specific recommendations for different groups.
    4.  **Context/Forecast**: Weather influence or future outlook.
    5.  **Sources**: Links to data providers or search results.
- **Visuals**: Use emojis (🟢, 🟡, 🟠, 🔴, 🟣, 🟤) to represent AQI colors.

**For Research Documents & Policy Papers**:
- **Format**: Use markdown with clear hierarchy (# ## ### headings)
- **Structure**: Follow research document structure (see section 6B)
- **Length**: Comprehensive (2000+ words for major research)
- **Data Tables**: Use markdown tables for comparisons
- **Citations**: Include [Source Name](URL) format
- **Sections**: Clearly numbered and titled
- **Professionalism**: Academic/policy-level writing
- **Actionability**: Include specific, implementable recommendations

**CRITICAL INSTRUCTION**:
Do NOT output your internal thought process. Do NOT say "Okay, I will..." or "Let me figure this out...".
If you need information, call the appropriate tool immediately.
If you have the information, provide the final response directly.
"""

    async def process_message(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> dict[str, Any]:
        """
        Process a user message using the configured provider.
        Returns a dictionary with 'response', 'tools_used', and 'cached' flag.
        
        Cost optimization: Caches responses for identical queries to reduce API costs.
        """
        if history is None:
            history = []
        
        # Create cache key from message and recent history (last 3 messages)
        cache_context = {
            "message": message,
            "history": history[-3:] if len(history) > 3 else history,
            "provider": self.settings.AI_PROVIDER
        }
        cache_key = hashlib.md5(json.dumps(cache_context, sort_keys=True).encode()).hexdigest()
        
        # Check cache first (only for non-data queries to keep data fresh)
        # Cache educational/general queries but not city-specific data
        is_data_query = any(keyword in message.lower() for keyword in [
            "kampala", "nairobi", "lagos", "accra", "dar", "current", "now", "today",
            "aqi in", "air quality in", "pollution in"
        ])
        
        if not is_data_query:
            cached_response = self.cache.get("agent_responses", cache_key)
            if cached_response:
                logger.info(f"Returning cached response for: {message[:50]}...")
                cached_response["cached"] = True
                return cached_response
        
        try:
            if self.settings.AI_PROVIDER == "gemini":
                result = await self._process_gemini_message(message, history)
            elif self.settings.AI_PROVIDER == "ollama":
                result = await self._process_ollama_message(message, history)
            elif self.settings.AI_PROVIDER == "openai":
                result = await self._process_openai_message(message, history)
            else:
                return {
                    "response": f"Provider {self.settings.AI_PROVIDER} is not supported.",
                    "tools_used": [],
                    "cached": False
                }
            
            # Cache successful responses (educational queries only)
            if not is_data_query and result.get("response"):
                self.cache.set("agent_responses", cache_key, result, ttl=3600)  # 1 hour
            
            result["cached"] = False
            return result
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "tools_used": [],
                "cached": False
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
                tools=self.gemini_tools,
                system_instruction=self._get_system_instruction(),
                temperature=0.7,
            ),
            history=chat_history,
        )

        # Send message
        response = chat.send_message(message)

        tools_used = []

        # Handle function calls
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_call = part.function_call
                    function_name = function_call.name
                    function_args = function_call.args

                    tools_used.append(function_name)

                    logger.info(f"Gemini requested tool execution: {function_name}")

                    tool_result = self._execute_tool(function_name, function_args)
                    
                    # Check if tool execution failed
                    if isinstance(tool_result, dict) and "error" in tool_result:
                        logger.warning(f"Tool {function_name} failed: {tool_result['error']}")
                        # Provide context to AI about the error so it can respond appropriately
                        error_context = {
                            "error": tool_result["error"],
                            "message": f"The tool '{function_name}' encountered an error. Please provide an informative response to the user explaining what went wrong and suggest alternatives if possible."
                        }
                        tool_result = error_context

                    # Send tool result back to model
                    response = chat.send_message(
                        types.Content(
                            parts=[
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        name=function_name, response={"result": tool_result}
                                    )
                                )
                            ]
                        )
                    )
                    break

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
            max_tokens=2048,
            temperature=0.7,
            top_p=0.95,
        )

        # Handle tool calls
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                function_name = tool_call.function.name

                # Parse function arguments with error handling
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

                tool_result = self._execute_tool(function_name, function_args)
                
                # Check if tool execution failed
                if isinstance(tool_result, dict) and "error" in tool_result:
                    logger.warning(f"Tool {function_name} failed: {tool_result['error']}")
                    # Provide context to AI about the error so it can respond appropriately
                    error_context = {
                        "error": tool_result["error"],
                        "message": f"The tool '{function_name}' encountered an error. Please provide an informative response to the user explaining what went wrong and suggest alternatives if possible."
                    }
                    tool_result = error_context

                # Add tool response to messages - convert message to dict
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
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.id),
                        "content": json.dumps({"result": tool_result}),
                    }
                )

            # Get final response with extended parameters for complete output
            try:
                final_response = self.client.chat.completions.create(
                    model=self.settings.AI_MODEL,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.7,
                    top_p=0.95,
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
1. Acknowledges the user's question
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
                    max_tokens=2048,
                    temperature=0.7,
                    top_p=0.95,
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
                    description="Get recent air quality data for African cities using AirQo network.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "city": types.Schema(
                                type=types.Type.STRING,
                                description="The name of the African city (e.g., Kampala, Nairobi)",
                            ),
                            "site_id": types.Schema(
                                type=types.Type.STRING,
                                description="The ID of the site (optional)",
                            ),
                        },
                        required=["city"],
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
            ]
        )

    def _get_gemini_weather_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_city_weather",
                    description="Get current weather data for a specific city.",
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
                )
            ]
        )

    def _get_gemini_search_tool(self):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="search_web",
                    description="Search the web for information.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="The search query",
                            )
                        },
                        required=["query"],
                    ),
                )
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
                    "description": "Get recent air quality data for African cities using AirQo network.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the African city (e.g., Kampala, Nairobi)",
                            },
                            "site_id": {
                                "type": "string",
                                "description": "The ID of the site (optional)",
                            },
                        },
                        "required": ["city"],
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
        return {
            "type": "function",
            "function": {
                "name": "get_city_weather",
                "description": "Get current weather data for a specific city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "The name of the city"}
                    },
                    "required": ["city"],
                },
            },
        }

    def _get_openai_search_tool(self):
        return {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for information.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "The search query"}},
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
                            "description": "Absolute path to the document file to scan"
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
                "temperature": 0.7,
                "top_p": 0.95,
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
                    "temperature": 0.7,
                    "top_p": 0.95,
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
                    "description": "Get air quality data for African cities using AirQo network.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The name of the African city (e.g., Kampala, Nairobi)",
                            },
                        },
                        "required": ["city"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_city_weather",
                    "description": "Get current weather data for a specific city.",
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
                    "name": "search_web",
                    "description": "Search the web for information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
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
        """
        if not content:
            return content

        try:
            import re

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
                # Use the smart method in AirQoService
                return self.airqo.get_recent_measurements(city=city, site_id=site_id)
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
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches."
                }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Return a structured error that helps the AI provide a better response
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "guidance": "This data source is currently unavailable or the requested location was not found. Please inform the user and suggest they try a different location or data source."
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
                return await loop.run_in_executor(
                    None,
                    lambda: self.airqo.get_recent_measurements(city=city, site_id=site_id),
                )
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
            elif function_name == "search_web":
                query = args.get("query")
                return await loop.run_in_executor(None, self.search.search, query)
            elif function_name == "scrape_website":
                url = args.get("url")
                return await loop.run_in_executor(None, self.scraper.scrape, url)
            elif function_name == "scan_document":
                file_path = args.get("file_path")
                return await loop.run_in_executor(None, self.document_scanner.scan_document, file_path)
            else:
                return {
                    "error": f"Unknown function {function_name}",
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches."
                }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Return a structured error that helps the AI provide a better response
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "guidance": "This data source is currently unavailable or the requested location was not found. Please inform the user and suggest they try a different location or data source."
            }
