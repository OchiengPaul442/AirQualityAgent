"""
Agent Service - Streamlined Orchestrator

Refactored to use modular architecture:
- Cost tracking via CostTracker
- Tool execution via ToolExecutor
- Provider abstraction (Gemini, OpenAI, Ollama)
- System instructions from prompts module
"""

import hashlib
import inspect
import json
import logging
from typing import Any, Awaitable

from src.config import get_settings
from src.mcp.client import MCPClient
from src.services.agent.cost_tracker import CostTracker
from src.services.agent.tool_executor import ToolExecutor
from src.services.airqo_service import AirQoService
from src.services.cache import get_cache
from src.services.carbon_intensity_service import CarbonIntensityService
from src.services.defra_service import DefraService
from src.services.geocoding_service import GeocodingService
from src.services.nsw_service import NSWService
from src.services.openmeteo_service import OpenMeteoService
from src.services.prompts.system_instructions import get_response_parameters, get_system_instruction
from src.services.providers.base_provider import BaseAIProvider
from src.services.providers.gemini_provider import GeminiProvider
from src.services.providers.ollama_provider import OllamaProvider
from src.services.providers.openai_provider import OpenAIProvider
from src.services.search_service import SearchService
from src.services.uba_service import UbaService
from src.services.waqi_service import WAQIService
from src.services.weather_service import WeatherService
from src.tools.document_scanner import DocumentScanner
from src.tools.robust_scraper import RobustScraper

logger = logging.getLogger(__name__)


class AgentService:
    """
    Main orchestrator for the Air Quality AI Agent.

    Responsibilities:
    - Initialize all service dependencies
    - Create and configure AI provider
    - Handle message processing requests
    - Manage cost tracking and caching
    - Connect to MCP servers
    """

    def __init__(self):
        """Initialize agent with all required services and providers."""
        self.settings = get_settings()
        self.cache = get_cache()
        self.mcp_clients: dict[str, MCPClient] = {}

        # Parse enabled data sources
        enabled_sources = set(src.strip().lower() for src in self.settings.ENABLED_DATA_SOURCES.split(',') if src.strip())

        # Initialize services based on enabled sources
        self.waqi = WAQIService() if 'waqi' in enabled_sources else None
        self.airqo = AirQoService() if 'airqo' in enabled_sources else None
        self.openmeteo = OpenMeteoService() if 'openmeteo' in enabled_sources else None
        self.carbon_intensity = CarbonIntensityService() if 'carbon_intensity' in enabled_sources else None
        self.defra = DefraService() if 'defra' in enabled_sources else None
        self.uba = UbaService() if 'uba' in enabled_sources else None
        self.nsw = NSWService() if 'nsw' in enabled_sources else None
        self.weather = WeatherService()  # Always enabled as it's used by other services
        self.scraper = RobustScraper()  # Always enabled for web scraping
        self.search = SearchService()  # Always enabled for web search
        self.document_scanner = DocumentScanner()  # Always enabled for document processing
        self.geocoding = GeocodingService()  # Always enabled for location services

        # Initialize tool executor with available services
        self.tool_executor = ToolExecutor(
            self.waqi,
            self.airqo,
            self.openmeteo,
            self.carbon_intensity,
            self.defra,
            self.uba,
            self.nsw,
            self.weather,
            self.search,
            self.scraper,
            self.document_scanner,
            self.geocoding,
        )

        # Initialize cost tracker
        self.cost_tracker = CostTracker()

        # Create and setup AI provider (support sync or async setup)
        self.provider = self._create_provider()
        try:
            setup_result = self.provider.setup()
            if inspect.isawaitable(setup_result):
                # schedule or run loop-aware await if running in async context
                # we do not await here to avoid requiring async __init__, but
                # callers that need full setup should call provider.setup() themselves
                pass
        except Exception:
            # swallow provider setup errors here; provider will raise on use
            logger.exception("Provider setup failed during AgentService init")

        logger.info(
            f"AgentService initialized with provider: {self.settings.AI_PROVIDER}"
        )

    def _create_provider(self) -> BaseAIProvider:
        """
        Factory method to create the appropriate AI provider.

        Returns:
            BaseAIProvider: Configured provider instance
        """
        provider_map: dict[str, type[BaseAIProvider]] = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "ollama": OllamaProvider,
        }

        provider_class = provider_map.get(self.settings.AI_PROVIDER.lower())
        if not provider_class:
            raise ValueError(
                f"Unsupported AI_PROVIDER: {self.settings.AI_PROVIDER}. "
                f"Supported: {', '.join(provider_map.keys())}"
            )

        return provider_class(self.settings, self.tool_executor)

    def _has_location_consent(self, history: list[dict[str, Any]]) -> bool:
        """
        Check if the user has already consented to location sharing in the conversation history.

        Args:
            history: Conversation history

        Returns:
            bool: True if user has consented to location sharing
        """
        consent_keywords = [
            "yes", "sure", "okay", "proceed", "go ahead", "allow", "consent", "please",
            "yes please", "of course", "absolutely", "fine", "ok", "alright", "sure thing"
        ]
        
        location_related_phrases = [
            "location", "current location", "my location", "where i am", "local", "here",
            "air quality", "pollution", "aqi", "gps", "coordinates"
        ]
        
        has_location_question = False
        has_consent = False
        
        for message in history:
            content = message.get("content", "").lower().strip()
            role = message.get("role", "")
            
            # Check assistant messages for location questions
            if role == "assistant":
                if any(phrase in content for phrase in location_related_phrases):
                    has_location_question = True
            
            # Check user messages for consent
            elif role == "user":
                if any(keyword in content for keyword in consent_keywords):
                    has_consent = True
        
        # Only consider consent valid if there was a location-related question before
        return has_location_question and has_consent
        """
        Check if a message is a simple appreciation/acknowledgment.

        Args:
            message: User message to check

        Returns:
            bool: True if message is appreciation-only
        """
        message_lower = message.lower().strip()
        words = message_lower.split()

        # Very short messages (1-2 words) - check exact matches or abbreviations
        if len(words) <= 2:
            # Exact matches for short appreciation messages
            exact_matches = ["thanks", "thank", "thx", "ty", "cheers", "ok", "okay", "awesome", "helpful"]
            if message_lower in exact_matches:
                return True
            # Check for appreciation phrases
            appreciation_phrases = [
                "thank you", "thank you very much", "thanks a lot", "thank you so much",
                "appreciate it", "much appreciated", "good job", "well done", "nice work", "great job"
            ]
            if message_lower in appreciation_phrases:
                return True
            return False

        # Short messages (3-5 words) that contain appreciation keywords as whole words
        if len(words) <= 5:
            appreciation_words = ["thank", "thanks", "appreciate", "great", "awesome", "perfect", "nice", "helpful", "cheers", "appreciated"]
            # Check if any appreciation word is in the message as a whole word
            for word in words:
                if word in appreciation_words:
                    return True
            # Check for specific phrases
            specific_phrases = ["thanks a lot", "thank you very much", "thanks on that"]
            if message_lower in specific_phrases:
                return True
            return False

        # Longer messages that are direct thanks (6-8 words)
        if len(words) <= 8:
            if any(phrase in message_lower for phrase in ["thank you", "thanks", "thank"]):
                return True

        return False

    def _generate_cache_key(
        self,
        message: str,
        history: list[dict[str, Any]],
        document_data: list[dict[str, Any]] | None = None,
        style: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> str:
        """
        Generate a unique cache key for the request.

        Args:
            message: User message
            history: Conversation history
            document_data: Optional document context
            style: Response style
            temperature: Temperature parameter
            top_p: Top-p parameter

        Returns:
            str: MD5 hash cache key
        """
        # Custom JSON encoder to handle datetime and other non-serializable objects
        def json_serializer(obj):
            """Convert non-serializable objects to strings"""
            from datetime import date, datetime
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return str(obj)
        
        # Create a hashable representation
        try:
            doc_str = json.dumps(document_data, sort_keys=True, default=json_serializer) if document_data else ""
        except Exception as e:
            logger.warning(f"Failed to serialize document_data for cache key, using fallback: {e}")
            # Fallback: use string representation
            doc_str = str(document_data) if document_data else ""
        
        cache_parts = [
            self.settings.AI_PROVIDER,
            self.settings.AI_MODEL,
            message,
            json.dumps(history[-5:] if len(history) > 5 else history, sort_keys=True, default=json_serializer),
            doc_str,
            style or "",
            str(temperature) if temperature is not None else "",
            str(top_p) if top_p is not None else "",
        ]

        cache_string = "|".join(cache_parts)
        return hashlib.md5(cache_string.encode()).hexdigest()

    async def process_message(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        document_data: list[dict[str, Any]] | None = None,
        style: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        client_ip: str | None = None,
        location_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and generate a response.

        This is the main entry point for message processing. It:
        1. Checks for appreciation messages (simple acknowledgment)
        2. Verifies cost limits haven't been exceeded
        3. Checks cache for previous identical responses
        4. Delegates to provider for actual processing
        5. Tracks costs and caches results

        Args:
            message: User's message
            history: Conversation history (default: [])
            document_data: Optional uploaded document context
            style: Response style preset (default: "general")
            temperature: Temperature override (default: from style)
            top_p: Top-p override (default: from style)
            client_ip: Client IP address for location services (fallback)
            location_data: GPS or IP location data with format:
                {"source": "gps", "latitude": float, "longitude": float} or
                {"source": "ip", "ip_address": str}

        Returns:
            Dict containing:
                - response: AI's response text
                - tokens_used: Token count (if available)
                - cost_estimate: Estimated cost in USD
                - cached: Whether response was from cache
        """
        history = history or []

        # Check for GPS-based location queries
        if location_data and location_data.get("source") == "gps":
            location_keywords = ['my location', 'current location', 'here', 'this location', 'where i am', 'my area', 'local']
            if any(keyword in message.lower() for keyword in location_keywords):
                logger.info(f"GPS location query detected, providing direct air quality data for coordinates: {location_data['latitude']}, {location_data['longitude']}")
                
                # Get air quality data directly
                from src.services.openmeteo_service import OpenMeteoService
                openmeteo = OpenMeteoService()
                air_quality_result = openmeteo.get_current_air_quality(
                    latitude=location_data["latitude"],
                    longitude=location_data["longitude"],
                    timezone="auto"
                )
                
                # Get location name
                from src.services.geocoding_service import GeocodingService
                geocoding = GeocodingService()
                reverse_result = geocoding.reverse_geocode(location_data["latitude"], location_data["longitude"])
                location_name = "your current location"
                if reverse_result.get("success"):
                    city = reverse_result.get("address", {}).get("city", "")
                    if city:
                        location_name = city
                
                # Format response
                if "current" in air_quality_result and air_quality_result["current"]:
                    response_text = f"# Air Quality at {location_name}\n\n"
                    response_text += f"**Location**: {location_data['latitude']:.4f}, {location_data['longitude']:.4f} (precise GPS)\n\n"
                    
                    # Add air quality data
                    current = air_quality_result["current"]
                    response_text += "## Current Air Quality\n\n"
                    response_text += "| Parameter | Value | Status |\n"
                    response_text += "|-----------|-------|--------|\n"
                    
                    if "us_aqi" in current:
                        us_aqi = current["us_aqi"]
                        status = "Good" if us_aqi <= 50 else "Moderate" if us_aqi <= 100 else "Unhealthy"
                        response_text += f"| US AQI | {us_aqi} | {status} |\n"
                    
                    if "pm2_5" in current:
                        pm25 = current["pm2_5"]
                        response_text += f"| PM2.5 | {pm25} µg/m³ | |\n"
                    
                    if "pm10" in current:
                        pm10 = current["pm10"]
                        response_text += f"| PM10 | {pm10} µg/m³ | |\n"
                    
                    response_text += "\n*Data provided with precise GPS coordinates for accurate local air quality information.*"
                else:
                    response_text = f"I couldn't retrieve air quality data for your current location ({location_data['latitude']:.4f}, {location_data['longitude']:.4f}). Please try again or specify a different location."
                
                return {
                    "response": response_text,
                    "tokens_used": 0,
                    "cost_estimate": 0.0,
                    "cached": False,
                }

        # Check for location consent in history and modify message if needed
        original_message = message
        has_consent = self._has_location_consent(history)
        is_location_query = any(keyword in message.lower() for keyword in ['my location', 'current location', 'here', 'this location', 'where i am', 'my area', 'local', 'air quality in my location'])
        is_consent_response = any(keyword in message.lower() for keyword in ['yes', 'sure', 'okay', 'proceed', 'go ahead', 'allow', 'consent', 'please'])
        
        if has_consent and is_location_query:
            message = f"User has already consented to location sharing. Get air quality data for my current location using the get_location_from_ip tool."
            logger.info(f"Detected location consent in history and location query, modified message: '{original_message}' -> '{message}'")
        elif is_consent_response and not is_location_query:
            # User is responding to consent request with just "yes" - treat as location query
            message = f"User has consented to location sharing. Get air quality data for my current location using the get_location_from_ip tool."
            logger.info(f"Detected consent response without explicit location query, treating as location request: '{original_message}' -> '{message}'")

        # Check cost limits
        within_limits, error_msg = self.cost_tracker.check_limits()
        if not within_limits:
            logger.warning(f"Cost limits exceeded: {error_msg}")
            return {
                "response": (
                    f"I've reached my daily usage limit. {error_msg}. "
                    "Please try again tomorrow or contact support to increase limits."
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "error": "cost_limit_exceeded",
            }

        # Check cache
        cache_key = self._generate_cache_key(
            message, history, document_data, style, temperature, top_p
        )

        # cache.get expects (namespace, key)
        cached_response = self.cache.get("agent", cache_key)
        if cached_response is not None:
            logger.info(f"Cache hit for key: {cache_key[:16]}...")
            cached_response["cached"] = True
            return cached_response

        # Get response parameters for the style
        response_params = get_response_parameters(style or "general", temperature, top_p)

        # Get system instruction with document context (pass history for new doc detection)
        location_context = ""
        if location_data and location_data.get("source") == "gps":
            location_context = f"\n\n**GPS LOCATION AVAILABLE**: The user has provided precise GPS coordinates ({location_data['latitude']:.4f}, {location_data['longitude']:.4f}). When they ask about air quality in their location, use the get_location_from_ip tool directly without asking for consent."

        system_instruction = get_system_instruction(
            style=style or "general",
            custom_suffix=self._build_document_context(document_data, history) + location_context,
        )
        
        # Log if document context was added
        if document_data:
            doc_context_length = len(self._build_document_context(document_data, history))
            has_previous = any("UPLOADED DOCUMENTS" in msg.get("content", "") for msg in (history or []))
            if has_previous:
                logger.info(f"NEW document uploaded in existing session - replacing previous document(s)")
            logger.info(f"Document context added to system instruction: {doc_context_length} chars for {len(document_data)} document(s)")

        # Set location data for geocoding services (GPS takes precedence over IP)
        if location_data:
            if location_data.get("source") == "gps":
                self.tool_executor.client_location = {
                    "source": "gps",
                    "latitude": location_data["latitude"],
                    "longitude": location_data["longitude"]
                }
                logger.info(f"Set GPS location for tool executor: {location_data['latitude']}, {location_data['longitude']}")
            elif location_data.get("source") == "ip":
                self.tool_executor.client_ip = location_data["ip_address"]
                self.tool_executor.client_location = None  # Clear GPS if IP is used
                logger.info(f"Set IP location for tool executor: {location_data['ip_address']}")
        elif client_ip:
            # Fallback to IP if no location_data provided
            self.tool_executor.client_ip = client_ip
            self.tool_executor.client_location = None
            logger.info(f"Set IP location for tool executor (fallback): {client_ip}")

        # Process with provider
        try:
            response_data = await self.provider.process_message(
                message=message,
                history=history,
                system_instruction=system_instruction,
                temperature=response_params.get("temperature"),
                top_p=response_params.get("top_p"),
                top_k=response_params.get("top_k"),
                max_tokens=response_params.get("max_output_tokens"),
            )

            # Track costs
            tokens_used = response_data.get("tokens_used", 0)
            cost_estimate = response_data.get("cost_estimate", 0.0)

            if tokens_used > 0:
                self.cost_tracker.track_usage(tokens_used, cost_estimate)

            # Cache the response
            response_data["cached"] = False
            # cache.set expects (namespace, key, value, ttl)
            self.cache.set("agent", cache_key, response_data, ttl=3600)  # 1 hour TTL

            logger.info(
                f"Message processed successfully. Tokens: {tokens_used}, "
                f"Cost: ${cost_estimate:.4f}"
            )

            return response_data

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "response": (
                    "I apologize, but I encountered an error processing your request. "
                    "Please try again or rephrase your question."
                ),
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "error": str(e),
            }

    def _build_document_context(
        self, document_data: list[dict[str, Any]] | None, history: list[dict[str, str]] | None = None
    ) -> str:
        """
        Build document context string for system instruction.

        Args:
            document_data: List of document metadata and content
            history: Conversation history to check for previous document uploads

        Returns:
            str: Formatted document context or empty string
        """
        if not document_data:
            return ""

        # Ensure document_data is a list
        if not isinstance(document_data, list):
            logger.warning(f"document_data should be a list, got {type(document_data)}")
            return ""
        
        # Check if there was a previous document upload in this session
        has_previous_document = False
        if history:
            for msg in history:
                content = msg.get("content", "")
                if "UPLOADED DOCUMENTS" in content or "Document:" in content or "📄 Document" in content:
                    has_previous_document = True
                    break

        context_parts = [
            "\n\n=== UPLOADED DOCUMENTS ===",
        ]
        
        # Add explicit replacement notice if this is a new document in existing session
        if has_previous_document:
            context_parts.append(
                "\n🔄 NEW DOCUMENT UPLOADED - IMPORTANT NOTICE:"
            )
            context_parts.append(
                "The user has uploaded a NEW document that REPLACES any previous documents."
            )
            context_parts.append(
                "⚠️ DISREGARD all previous document references from earlier in this conversation."
            )
            context_parts.append(
                "⚠️ ONLY analyze and reference the document(s) shown below."
            )
            context_parts.append(
                "⚠️ DO NOT mention, compare, or reference any previously uploaded files.\n"
            )
        else:
            context_parts.append(
                "\n⚠️ IMPORTANT: The document data below is ALREADY PROVIDED to you. DO NOT use the scan_document tool."
            )
            context_parts.append(
                "You have direct access to this data - analyze it immediately without requesting file access.\n"
            )

        for idx, doc in enumerate(document_data, 1):
            # Skip if not a dictionary
            if not isinstance(doc, dict):
                logger.warning(f"Skipping non-dict document: {type(doc)}")
                continue
            
            filename = doc.get("filename", "Unknown")
            content = doc.get("content", "")
            file_type = doc.get("file_type", "unknown")
            truncated = doc.get("truncated", False)
            full_length = doc.get("full_length", len(content))
            
            # Build document header
            context_parts.append(f"\n📄 Document {idx}: {filename}")
            context_parts.append(f"File Type: {file_type.upper()}")
            context_parts.append(f"Status: ✅ Scanned and Ready")
            
            # Add metadata if available
            metadata = doc.get("metadata", {})
            if metadata:
                metadata_str = ", ".join([f"{k}: {v}" for k, v in metadata.items() if k not in ['characters']])
                if metadata_str:
                    context_parts.append(f"Details: {metadata_str}")
            
            # Show truncation info
            if truncated:
                context_parts.append(f"Size: {full_length} characters total (preview showing first 1,000)")
            
            # Add content with clear delimiter
            context_parts.append(f"\n--- DATA START ---\n{content[:1000]}")
            if truncated:
                context_parts.append("\n--- DATA TRUNCATED (use above preview) ---")
            else:
                context_parts.append("\n--- DATA END ---")
        
        context_parts.append("\n\n✅ All document data above is ready for your analysis. Proceed with answering the user's question using this data.")
        context_parts.append("=== END DOCUMENTS ===\n")

        return "\n".join(context_parts)

    async def connect_mcp_server(
        self, server_name: str, command: str, args: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Connect to an MCP (Model Context Protocol) server.

        Args:
            server_name: Name/identifier for the server
            command: Command to execute
            args: Command arguments

        Returns:
            Dict with connection status and details
        """
        try:
            if server_name in self.mcp_clients:
                logger.info(f"MCP client '{server_name}' already connected")
                return {
                    "status": "already_connected",
                    "message": f"Already connected to {server_name}",
                }

            # Create and initialize MCP client
            mcp_client = MCPClient(command, args or [])
            async with mcp_client.connect():
                # Connection successful, store the client
                self.mcp_clients[server_name] = mcp_client

            logger.info(f"Successfully connected to MCP server: {server_name}")
            return {
                "status": "success",
                "message": f"Connected to {server_name}",
                "server_name": server_name,
            }

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect: {str(e)}",
                "error": str(e),
            }

    def get_cost_status(self) -> dict[str, Any]:
        """
        Get current cost tracking status.

        Returns:
            Dict with cost and usage statistics
        """
        return self.cost_tracker.get_status()

    async def cleanup(self):
        """Clean up resources (MCP clients, provider connections)."""
        # Disconnect all MCP clients
        for server_name, client in self.mcp_clients.items():
            try:
                # Some MCPClient implementations may provide sync or async disconnect
                disconnect_fn = getattr(client, "disconnect", None)
                if disconnect_fn is not None:
                    res = disconnect_fn()
                    if inspect.isawaitable(res):
                        await res
                logger.info(f"Disconnected MCP client: {server_name}")
            except Exception as e:
                logger.error(f"Error disconnecting MCP client {server_name}: {e}")

        # Cleanup provider
        if hasattr(self.provider, "cleanup"):
            try:
                cleanup_fn = getattr(self.provider, "cleanup")
                res = cleanup_fn()
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(f"Error cleaning up provider: {e}")

        logger.info("AgentService cleanup completed")
