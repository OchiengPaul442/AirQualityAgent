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
        self._configure_response_params()

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
                "instruction_suffix": "\\n\\nIMPORTANT: Provide concise, data-driven responses. Lead with key insights and actionable recommendations. Use bullet points. Avoid repetition and unnecessary elaboration."
            },
            "technical": {
                "temperature": 0.4,
                "top_p": 0.88,
                "instruction_suffix": "\\n\\nIMPORTANT: Use precise technical terminology. Include specific measurements, standards, and methodologies. Provide detailed explanations with scientific accuracy."
            },
            "general": {
                "temperature": 0.45,
                "top_p": 0.9,
                "instruction_suffix": "\\n\\nIMPORTANT: Adapt to your audience automatically. Be professional yet clear. Match detail level to query complexity. Never repeat phrases. Be concise."
            },
            "simple": {
                "temperature": 0.6,
                "top_p": 0.92,
                "instruction_suffix": "\\n\\nIMPORTANT: Use simple, everyday language. Explain concepts clearly as if speaking to someone without technical background. Use analogies and examples from daily life."
            },
            "policy": {
                "temperature": 0.35,
                "top_p": 0.87,
                "instruction_suffix": "\\n\\nIMPORTANT: Maintain formal, evidence-based tone suitable for government officials and policy makers. Include citations, comparative analysis, and specific policy recommendations."
            }
        }
        
        # Get style preset or use custom values
        style = self.settings.AI_RESPONSE_STYLE.lower()
        if style in style_presets:
            preset = style_presets[style]
            self.response_temperature = preset["temperature"]
            self.response_top_p = preset["top_p"]
            self.style_instruction = preset["instruction_suffix"]
            logger.info(f"Applied '{style}' response style preset (temp={self.response_temperature}, top_p={self.response_top_p})")
        else:
            # Use custom values from config
            self.response_temperature = self.settings.AI_RESPONSE_TEMPERATURE
            self.response_top_p = self.settings.AI_RESPONSE_TOP_P
            self.style_instruction = "\\n\\nIMPORTANT: Provide clear, professional responses suitable for all audiences. Avoid repetition."
            logger.info(f"Using custom response parameters (temp={self.response_temperature}, top_p={self.response_top_p})")

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
        base_instruction = """You are an Air Quality AI Assistant. Your role: fetch real-time air quality data and provide health recommendations.

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
❌ BAD: "Kampala PM2.5 is 177" (ambiguous!)
✅ GOOD: "Kampala has a PM2.5 AQI of 177 (Unhealthy), approximately 110 µg/m³"
✅ GOOD: "Kampala PM2.5 concentration is 83.6 µg/m³ (AQI: 165, Unhealthy)"

## CRITICAL: Always Use Tools First

When user mentions a location, IMMEDIATELY call the appropriate tool:
- City name (e.g., "Gulu", "New York") → get_waqi_city_feed OR get_airqo_measurements
- "tomorrow", "next week", "forecast" → get_openmeteo_forecast  
- Coordinates → get_openmeteo_current_air_quality

NEVER respond with "I don't have access" before trying ALL available tools.

## Location Memory

Extract and remember locations from conversation:
- User says "Gulu University" → remember "Gulu"
- User asks "tomorrow there" → use "Gulu" from memory
- NEVER ask for location if already mentioned

## Response Guidelines

Keep responses SHORT (under 150 words):
1. State the data CLEARLY: "PM2.5 AQI: [value]" or "PM2.5 concentration: [X] µg/m³"
2. Give health category and ONE recommendation
3. No lengthy explanations unless asked

BAD: "At this moment I don't have access to live data for New York..."
GOOD: [calls get_waqi_city_feed] → "New York PM2.5 AQI: 45 (Good), approximately 10 µg/m³. Air quality is safe for all activities."

## Tool Priority

Current data: get_waqi_city_feed → get_airqo_measurements → get_openmeteo_current_air_quality → search_web
Forecast: get_openmeteo_forecast → search_web
If ALL tools fail: suggest user check local environmental agency (one sentence)

## When Tools Fail

DON'T: Write 300-word apology about "tools not returning data"
DO: Try alternative source, or give brief explanation with helpful link

Example: "I couldn't retrieve live data for [location]. Check airnow.gov or aqicn.org for current readings."

## Health Recommendations by AQI:

- **0-50 (Good)**: Air quality is satisfactory. Normal activities.
- **51-100 (Moderate)**: Acceptable. Sensitive individuals may want to limit prolonged outdoor exertion.
- **101-150 (Unhealthy for Sensitive Groups)**: Sensitive groups should limit prolonged outdoor exertion.
- **151-200 (Unhealthy)**: Everyone should limit prolonged outdoor exertion. Sensitive groups avoid it.
- **201-300 (Very Unhealthy)**: Everyone avoid prolonged exertion. Sensitive groups stay indoors.
- **301+ (Hazardous)**: Everyone avoid all outdoor exertion. Stay indoors with air purification.
"""
        # Append style-specific instructions
        return base_instruction + self.style_instruction

    async def process_message(
        self, message: str, history: list[dict[str, str]] | None = None, document_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Process a user message using the configured provider.
        Returns a dictionary with 'response', 'tools_used', and 'cached' flag.
        
        Args:
            message: User's message/query
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
            max_doc_length = 15000  # characters
            if len(doc_content) > max_doc_length:
                doc_content = doc_content[:max_doc_length] + "\\n[... content truncated due to length ...]"
            
            # Create enhanced message with document context
            enhanced_message = f'''User Question: {message}

Document uploaded: {doc_filename}
Document type: {doc_metadata.get('file_type', 'unknown')}

Document Content:
---
{doc_content}
---

Please analyze the document above and answer the user's question based on its contents.'''
        
        # Create cache key from message and recent history (last 3 messages)
        # Don't cache when document is uploaded (always process fresh)
        cache_context = {
            "message": message,
            "history": history[-3:] if len(history) > 3 else history,
            "provider": self.settings.AI_PROVIDER,
            "has_document": document_data is not None
        }
        cache_key = hashlib.md5(json.dumps(cache_context, sort_keys=True).encode()).hexdigest()
        
        # Check cache first (only for non-data queries and no document uploads)
        # Cache educational/general queries but not city-specific data or document analysis
        is_data_query = any(keyword in message.lower() for keyword in [
            "kampala", "nairobi", "lagos", "accra", "dar", "current", "now", "today",
            "aqi in", "air quality in", "pollution in"
        ])
        
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
                    "cached": False
                }
            
            # Cache successful responses (educational queries only, not document uploads)
            if not is_data_query and not document_data and result.get("response"):
                self.cache.set("agent_responses", cache_key, result, ttl=3600)  # 1 hour
            
            result["cached"] = False
            return result
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}", exc_info=True)
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
                temperature=self.response_temperature,
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
            temperature=self.response_temperature,
            top_p=self.response_top_p,
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
