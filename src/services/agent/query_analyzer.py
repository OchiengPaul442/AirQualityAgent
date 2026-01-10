"""
Query Analyzer - Intelligent Pre-Processing for Tool Calling

This module analyzes user queries and proactively calls tools BEFORE sending to the AI.
This ensures that even models with weak tool-calling support get the data they need.
"""

import logging
import re
from typing import Any

# Import centralized formatters to reduce code duplication
from ...utils.result_formatters import (
    format_air_quality_result,
    format_forecast_result,
    format_scrape_result,
    format_search_result,
)

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    Analyzes queries and determines which tools need to be called proactively.
    
    Implements intelligent tool selection to optimize for:
    - Low-quality AI models (proactive tool calling)
    - Speed (parallel tool execution)
    - Accuracy (smart query classification)
    """

    # City patterns for detection
    AFRICAN_CITIES = [
        "kampala",
        "gulu",
        "jinja",
        "mbale",
        "mbarara",
        "nakasero",
        "nairobi",
        "mombasa",
        "kisumu",
        "nakuru",
        "eldoret",
        "dar es salaam",
        "dodoma",
        "mwanza",
        "arusha",
        "mbeya",
        "kigali",
        "butare",
        "musanze",
        "ruhengeri",
        "gisenyi",
        "addis ababa",
        "accra",
        "lagos",
        "abuja",
        "cairo",
        "alexandria",
    ]

    GLOBAL_CITIES = [
        "london",
        "paris",
        "berlin",
        "munich",
        "rome",
        "madrid",
        "new york",
        "los angeles",
        "chicago",
        "houston",
        "phoenix",
        "tokyo",
        "osaka",
        "kyoto",
        "beijing",
        "shanghai",
        "guangzhou",
        "delhi",
        "mumbai",
        "bangalore",
        "chennai",
        "kolkata",
        "sydney",
        "melbourne",
        "brisbane",
        "perth",
        "auckland",
        "toronto",
        "vancouver",
        "montreal",
        "mexico city",
        "sao paulo",
    ]

    @staticmethod
    def classify_query_type(message: str) -> dict[str, Any]:
        """
        Intelligently classify query to determine optimal tool strategy.
        
        This reduces unnecessary tool calls and improves response speed.
        
        Returns:
            Dict with:
                - query_type: 'educational' | 'location_specific' | 'data_analysis' | 'research' | 'general_knowledge'
                - confidence: float (0-1)
                - recommended_tools: list of tool names
                - skip_ai_tools: bool (whether AI should call additional tools)
        """
        message_lower = message.lower()

        # CRITICAL: Check data_analysis and research FIRST (higher priority than educational)
        # Data analysis queries - Need web search + visualization
        data_indicators = [
            'statistics', 'stats', 'data', 'chart', 'graph', 'trend',
            'deaths', 'mortality', 'study', 'research', 'report',
        ]

        if any(indicator in message_lower for indicator in data_indicators):
            return {
                "query_type": "data_analysis",
                "confidence": 0.85,
                "recommended_tools": ["search_web", "generate_chart"],
                "skip_ai_tools": False,
            }

        # Research queries - Need web search only
        research_indicators = [
            'latest', 'recent', 'current', 'new', 'update',
            'policy', 'regulation', 'guideline', 'standard',
            '2024', '2025', '2026',
        ]

        if any(indicator in message_lower for indicator in research_indicators):
            return {
                "query_type": "research",
                "confidence": 0.8,
                "recommended_tools": ["search_web"],
                "skip_ai_tools": False,
            }

        # CRITICAL: General knowledge queries about air pollution/health effects - ALWAYS use web search
        # These need latest authoritative information from WHO, EPA, etc.
        general_knowledge_patterns = [
            r'\bhealth effects\b',
            r'\bhealth impacts?\b',
            r'\bhow does.*affect\b',
            r'\bwhat are.*effects\b',
            r'\bcauses?\b',
            r'\bsymptoms?\b',
            r'\brisks?\b',
            r'\bwho guidelines?\b',
            r'\bepa standards?\b',
            r'\bair pollution.*health\b',
        ]
        
        if any(re.search(pattern, message_lower) for pattern in general_knowledge_patterns):
            # Verify it's not location-specific
            if not any(city in message_lower for city in QueryAnalyzer.AFRICAN_CITIES + QueryAnalyzer.GLOBAL_CITIES):
                return {
                    "query_type": "general_knowledge",
                    "confidence": 0.9,
                    "recommended_tools": ["search_web"],
                    "skip_ai_tools": False,  # MUST use web search for latest info
                }

        # Educational queries - No tools needed, pure AI knowledge
        # CHECKED AFTER general_knowledge to avoid false positives
        educational_patterns = [
            r'\bwhat is\b',
            r'\bexplain\b',
            r'\bdefine\b',
            r'\bhow does\b',
            r'\bwhy does\b',
            r'\btell me about\b',
            r'\bdifference between\b',
            r'\bcompare.*and\b',  # "compare PM2.5 and PM10" (concepts, not cities)
        ]

        # Check if it's educational (no location mentions)
        if any(re.search(pattern, message_lower) for pattern in educational_patterns):
            # Verify it's not location-specific
            if not any(city in message_lower for city in QueryAnalyzer.AFRICAN_CITIES + QueryAnalyzer.GLOBAL_CITIES):
                return {
                    "query_type": "educational",
                    "confidence": 0.9,
                    "recommended_tools": [],
                    "skip_ai_tools": True,  # AI can answer without tools
                }

        # Location-specific queries - Need air quality tools
        location_indicators = [
            'in kampala', 'in london', 'in nairobi', 'in paris',
            'air quality', 'aqi', 'pollution level', 'pm2.5', 'pm10',
            'safe to', 'breathe', 'outdoor', 'exercise',
        ]

        has_location = any(city in message_lower for city in QueryAnalyzer.AFRICAN_CITIES + QueryAnalyzer.GLOBAL_CITIES)
        has_aq_keyword = any(indicator in message_lower for indicator in location_indicators)

        if has_location and has_aq_keyword:
            return {
                "query_type": "location_specific",
                "confidence": 0.95,
                "recommended_tools": ["get_city_air_quality", "get_african_city_air_quality"],
                "skip_ai_tools": False,  # Let proactive system handle it
            }

        # Default: Let proactive system decide
        return {
            "query_type": "general",
            "confidence": 0.5,
            "recommended_tools": [],
            "skip_ai_tools": False,
        }

    @staticmethod
    def detect_air_quality_query(message: str) -> dict[str, Any]:
        """
        Detect if the query is about air quality and extract cities.

        Returns:
            Dict with:
                - is_air_quality: bool
                - cities: list of detected cities
                - african_cities: list of African cities
                - global_cities: list of global cities
                - coordinates: dict with lat/lon if detected
        """
        message_lower = message.lower()

        # Check if it's an air quality query
        air_quality_keywords = [
            "air quality",
            "aqi",
            "pollution",
            "pm2.5",
            "pm10",
            "pollutant",
            "smog",
            "air",
            "breathe",
            "safe to exercise",
            "outdoor",
            "environment",
            "atmospheric",
        ]

        is_air_quality = any(keyword in message_lower for keyword in air_quality_keywords)

        # Extract coordinates (lat/lon) - handle multiple formats
        coordinates = None
        # Format 1: "latitude X, longitude Y" or "lat X, lon Y"
        coord_pattern_verbose = r'(?:latitude|lat)\s+(-?\d+\.?\d*)\s*,?\s*(?:longitude|lon)\s+(-?\d+\.?\d*)'
        # Format 2: Simple "X, Y"
        coord_pattern_simple = r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)'

        coord_match = re.search(coord_pattern_verbose, message, re.IGNORECASE)
        if not coord_match:
            coord_match = re.search(coord_pattern_simple, message)

        if coord_match:
            try:
                lat = float(coord_match.group(1))
                lon = float(coord_match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    coordinates = {"latitude": lat, "longitude": lon}
                    logger.info(f"📍 Extracted coordinates: lat={lat}, lon={lon}")
            except ValueError:
                pass

        # Extract cities
        african_cities = []
        global_cities = []

        for city in QueryAnalyzer.AFRICAN_CITIES:
            if city in message_lower:
                african_cities.append(city.title())

        for city in QueryAnalyzer.GLOBAL_CITIES:
            if city in message_lower:
                global_cities.append(city.title())

        # Remove duplicates
        african_cities = list(set(african_cities))
        global_cities = list(set(global_cities))

        return {
            "is_air_quality": is_air_quality,
            "cities": african_cities + global_cities,
            "african_cities": african_cities,
            "global_cities": global_cities,
            "coordinates": coordinates,
        }

    @staticmethod
    def detect_search_query(message: str) -> dict[str, Any]:
        """
        Detect if query requires web search to supplement response.
        Liberal by default - searches to provide current, comprehensive information.
        
        Returns:
            Dict with:
                - requires_search: bool
                - search_query: suggested search query string
        """
        message_lower = message.lower()

        # Educational/definition questions that DON'T need search
        educational_patterns = [
            r"what (is|are|does|do|means?)",
            r"how (does|do|is|are)",
            r"define",
            r"explain",
            r"tell me about",
            r"why (is|are|does|do)",
        ]

        # Check if it's a simple educational question without location/data requests
        is_educational = any(re.search(pattern, message_lower) for pattern in educational_patterns)
        is_short = len(message.split()) < 15  # Short questions are usually educational

        # Keywords that definitely need search
        temporal_keywords = ["latest", "recent", "new", "current", "update", "2024", "2025", "2026", "this year", "last year"]
        policy_keywords = ["policy", "regulation", "legislation", "law", "government", "standard", "standards"]
        research_keywords = ["research", "study", "studies", "report", "findings", "evidence", "published"]
        data_keywords = ["statistics", "stats", "data", "trends", "analysis", "deaths", "mortality", "how many", "list"]

        # If it's an educational question without search triggers, skip search
        if is_educational and is_short:
            has_search_trigger = any(k in message_lower for k in temporal_keywords + policy_keywords + research_keywords + data_keywords)
            if not has_search_trigger:
                logger.info(f"🎓 Educational question detected - no search needed: '{message[:50]}...'")
                return {
                    "requires_search": False,
                    "search_query": None
                }

        # Search if: temporal, policy, research, data keywords present
        has_search_keyword = any(k in message_lower for k in temporal_keywords + policy_keywords + research_keywords + data_keywords)

        # Log detection for debugging
        if has_search_keyword:
            matched_keywords = [k for k in temporal_keywords + policy_keywords + research_keywords + data_keywords if k in message_lower]
            logger.info(f"🔍 Search keywords detected: {matched_keywords}")

        requires_search = has_search_keyword

        # Generate focused search query
        search_query = message
        if any(k in message_lower for k in data_keywords):
            search_query += " WHO EPA statistics"

        logger.info(f"🔍 Search detection result: requires_search={requires_search}, query='{search_query[:50] if search_query else 'None'}...'")

        return {
            "requires_search": requires_search,
            "search_query": search_query if requires_search else None
        }

    @staticmethod
    def detect_data_analysis_query(message: str) -> dict[str, Any]:
        """
        Detect if the query is asking for data analysis, statistics, or visualizations.
        This is separate from location-based air quality queries.

        Returns:
            Dict with:
                - is_data_analysis: bool
                - requires_search: bool
                - requires_visualization: bool
                - topic: detected topic (deaths, trends, statistics, etc.)
                - time_period: detected time period if any
        """
        message_lower = message.lower()

        # Data analysis keywords
        data_keywords = [
            "statistics",
            "stats",
            "data",
            "chart",
            "graph",
            "plot",
            "visualize",
            "show me",
            "generate",
            "create",
            "display",
            "deaths",
            "mortality",
            "trends",
            "analysis",
            "report",
            "findings",
            "evidence",
            "burden",
            "prevalence",
            "epidemiology",
            "risk assessment",
            "impact",
            "global",
            "worldwide",
            "international",
            "numbers",
            "figures",
            "metrics",
        ]

        # Visualization keywords
        viz_keywords = [
            "chart",
            "graph",
            "plot",
            "visualize",
            "show me",
            "generate",
            "create",
            "display",
            "diagram",
            "map",
        ]

        # Time period keywords
        time_keywords = [
            "2023",
            "2024",
            "2025",
            "2026",
            "past",
            "last year",
            "recent",
            "latest",
            "current",
            "this year",
            "previous",
            "annual",
            "yearly",
        ]

        # Topic detection
        topic_keywords = {
            "deaths": ["deaths", "mortality", "fatalities", "died", "killed"],
            "health": ["health", "disease", "illness", "medical", "hospital"],
            "pollution": ["pollution", "air quality", "contamination", "emissions"],
            "trends": ["trends", "changes", "patterns", "evolution", "over time"],
            "statistics": ["statistics", "stats", "data", "numbers", "figures"],
        }

        # Check for data analysis intent
        has_data_keywords = any(keyword in message_lower for keyword in data_keywords)
        has_viz_keywords = any(keyword in message_lower for keyword in viz_keywords)
        has_time_keywords = any(keyword in message_lower for keyword in time_keywords)

        # Determine topic
        detected_topic = None
        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_topic = topic
                break

        # Determine time period
        time_period = None
        for time_kw in time_keywords:
            if time_kw in message_lower:
                time_period = time_kw
                break

        # This is data analysis if it has data keywords OR (visualization + time period)
        is_data_analysis = has_data_keywords or (has_viz_keywords and has_time_keywords)

        # Data analysis almost always requires search for current statistics
        requires_search = is_data_analysis

        # Requires visualization if asking for charts/graphs
        requires_visualization = has_viz_keywords

        return {
            "is_data_analysis": is_data_analysis,
            "requires_search": requires_search,
            "requires_visualization": requires_visualization,
            "topic": detected_topic,
            "time_period": time_period,
        }

    @staticmethod
    def detect_forecast_query(message: str) -> dict[str, Any]:
        """
        Detect if the query is asking for air quality forecasts using advanced NLP patterns.

        Handles various natural language patterns for forecasting:
        - Direct forecast requests: "forecast for tomorrow"
        - Future tense: "will the air quality be good tomorrow?"
        - Time references: "next week", "this weekend", "in 3 days"
        - Conditional forecasts: "should I go outside tomorrow?"
        - Comparative: "better tomorrow than today?"

        Returns:
            Dict with:
                - is_forecast: bool
                - cities: list of detected cities
                - days_ahead: number of days to forecast (1-7, default 1)
                - confidence: float (0.0-1.0) confidence score
                - time_references: list of detected time expressions
        """
        message_lower = message.lower()
        words = message_lower.split()

        # Advanced forecast detection patterns
        forecast_indicators = {
            # Direct forecast terms
            "forecast": 1.0,
            "prediction": 0.9,
            "outlook": 0.8,
            "projection": 0.8,
            # Future time references
            "tomorrow": 1.0,
            "next day": 1.0,
            "day after tomorrow": 0.9,
            "next week": 0.8,
            "this weekend": 0.9,
            "weekend": 0.7,
            "next month": 0.6,
            "coming days": 0.7,
            "upcoming": 0.6,
            # Future tense and modal verbs
            "will": 0.4,
            "going to": 0.5,
            "shall": 0.4,
            "expect": 0.6,
            "predict": 0.7,
            "anticipate": 0.6,
            "likely": 0.5,
            # Question patterns indicating future interest
            "should i": 0.3,
            "can i": 0.3,
            "is it safe": 0.4,
            "better tomorrow": 0.8,
            "worse tomorrow": 0.8,
        }

        # Time-specific patterns with day calculations
        time_patterns = {
            r"\btomorrow\b": (1, 1.0),
            r"\bnext day\b": (1, 1.0),
            r"\bday after\b": (2, 0.9),
            r"\bin 2 days\b": (2, 1.0),
            r"\bin 3 days\b": (3, 1.0),
            r"\bnext week\b": (7, 0.8),
            r"\bthis weekend\b": (3, 0.9),  # Assume current weekend
            r"\bweekend\b": (3, 0.7),  # Generic weekend reference
            r"\bmonday\b": (1, 0.6),  # Could be today or next Monday
            r"\btuesday\b": (1, 0.6),
            r"\bwednesday\b": (1, 0.6),
            r"\bthursday\b": (1, 0.6),
            r"\bfriday\b": (1, 0.6),
            r"\bsaturday\b": (2, 0.5),  # Often refers to upcoming weekend
            r"\bsunday\b": (2, 0.5),
        }

        # Calculate confidence score
        confidence = 0.0
        detected_indicators = []

        # Check for forecast indicators
        for indicator, weight in forecast_indicators.items():
            if indicator in message_lower:
                confidence += weight
                detected_indicators.append(indicator)

        # Check for time patterns
        days_ahead = 1  # Default
        time_references = []

        import re

        for pattern, (days, weight) in time_patterns.items():
            if re.search(pattern, message_lower):
                days_ahead = days
                confidence += weight
                time_references.append(pattern.strip(r"\\b"))

        # Boost confidence for air quality + time combinations
        air_quality_terms = ["air quality", "aqi", "pollution", "pm2.5", "pm10", "smog"]
        has_air_quality = any(term in message_lower for term in air_quality_terms)

        if has_air_quality and (detected_indicators or time_references):
            confidence += 0.3  # Boost for clear air quality + time combination

        # Context-aware adjustments
        # Questions about future activities often imply forecasts
        activity_questions = ["exercise", "run", "walk", "outdoor", "outside", "safe to"]
        if any(activity in message_lower for activity in activity_questions) and time_references:
            confidence += 0.2

        # Comparative language
        comparative_terms = ["better than", "worse than", "compared to", "versus"]
        if any(term in message_lower for term in comparative_terms) and time_references:
            confidence += 0.2

        # Determine if this is actually a forecast query
        is_forecast = confidence >= 0.5  # Threshold for forecast detection

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        # Extract cities with improved detection
        cities = []
        city_detection_boost = 0.0

        # Check all known cities
        all_cities = QueryAnalyzer.AFRICAN_CITIES + QueryAnalyzer.GLOBAL_CITIES
        for city in all_cities:
            if city in message_lower:
                cities.append(city.title())
                city_detection_boost += 0.1  # Small boost for city detection

        # If cities found, slightly boost confidence
        confidence = min(confidence + city_detection_boost, 1.0)

        # Special case: Very short messages with just city + time might be forecasts
        if len(words) <= 5 and cities and time_references:
            is_forecast = True
            confidence = max(confidence, 0.7)

        return {
            "is_forecast": is_forecast,
            "cities": cities,
            "days_ahead": days_ahead,
            "confidence": confidence,
            "time_references": time_references,
            "detected_indicators": detected_indicators,
        }

    @staticmethod
    async def proactively_call_tools(message: str, tool_executor: Any) -> dict[str, Any]:
        """
        Intelligently analyze query and proactively call relevant tools.
        
        Optimized for:
        - Low-quality AI models (bypasses weak tool calling)
        - Speed (parallel execution, skip unnecessary tools)
        - Accuracy (smart classification reduces errors)
        
        Args:
            message: User's query
            tool_executor: ToolExecutor instance

        Returns:
            Dict with:
                - tool_results: Dict mapping tool names to results
                - tools_called: List of tool names called
                - context_injection: String to inject into AI context
                - query_classification: Classification results
        """
        logger.info(f"🔍 Analyzing query: {message[:100]}...")

        # STEP 1: Classify query intelligently
        classification = QueryAnalyzer.classify_query_type(message)
        logger.info(f"📊 Query type: {classification['query_type']} (confidence: {classification['confidence']:.2f})")

        # STEP 2: Early return for educational queries (no tools needed)
        # But NOT for general_knowledge queries (they need web search)
        if classification["query_type"] == "educational" and classification["skip_ai_tools"]:
            logger.info("✅ Educational query - no tools needed")
            return {
                "tool_results": {},
                "tools_called": [],
                "context_injection": "",
                "query_classification": classification,
            }

        # STEP 3: Run analyses based on classification
        tool_results = {}
        tools_called = []
        context_parts = []

        # Analyze query intents in parallel
        aq_analysis = QueryAnalyzer.detect_air_quality_query(message)
        forecast_analysis = QueryAnalyzer.detect_forecast_query(message)
        search_analysis = QueryAnalyzer.detect_search_query(message)
        data_analysis = QueryAnalyzer.detect_data_analysis_query(message)

        # CRITICAL FIX: Detect composite queries with "AND" keyword
        # Example: "Gulu (coords: 2.7747, 32.2994) AND Kampala" → call 2+ tools
        has_and_keyword = " and " in message.lower()
        has_multiple_locations = (
            len(aq_analysis["cities"]) >= 2
            or (aq_analysis["coordinates"] and len(aq_analysis["cities"]) >= 1)
        )

        # Call air quality tools (optimized - only if location detected)
        if aq_analysis["is_air_quality"] and (aq_analysis["cities"] or aq_analysis["coordinates"]):
            # Call for African cities
            for city in aq_analysis["african_cities"]:
                try:
                    logger.info(f"🔧 PROACTIVE CALL: get_african_city_air_quality for {city}")
                    result = await tool_executor.execute_async(
                        "get_african_city_air_quality", {"city": city}
                    )
                    tool_results[f"get_african_city_air_quality_{city}"] = result
                    tools_called.append("get_african_city_air_quality")

                    # Format result for context
                    context_parts.append(
                        f"\n**REAL-TIME DATA from AirQo for {city}:**\n{format_air_quality_result(result)}\n"
                    )
                except Exception as e:
                    logger.error(f"Proactive tool call failed for {city}: {e}")

            # Call for global cities
            for city in aq_analysis["global_cities"]:
                try:
                    logger.info(f"🔧 PROACTIVE CALL: get_city_air_quality for {city}")
                    result = await tool_executor.execute_async(
                        "get_city_air_quality", {"city": city}
                    )
                    tool_results[f"get_city_air_quality_{city}"] = result
                    tools_called.append("get_city_air_quality")

                    # Format result for context
                    context_parts.append(
                        f"\n**REAL-TIME DATA from WAQI for {city}:**\n{format_air_quality_result(result)}\n"
                    )
                except Exception as e:
                    logger.error(f"Proactive tool call failed for {city}: {e}")

            # Call for coordinates (CRITICAL: Call this even if cities are present in composite queries)
            if aq_analysis["coordinates"]:
                try:
                    coords = aq_analysis["coordinates"]
                    logger.info(f"🔧 PROACTIVE CALL: get_openmeteo_air_quality for {coords}")
                    result = await tool_executor.execute_async(
                        "get_openmeteo_current_air_quality", coords
                    )
                    tool_results["get_openmeteo_air_quality"] = result
                    tools_called.append("get_openmeteo_current_air_quality")

                    # Format result for context
                    context_parts.append(
                        f"\n**REAL-TIME DATA from OpenMeteo for coordinates {coords['latitude']}, {coords['longitude']}:**\n{format_air_quality_result(result)}\n"
                    )
                except Exception as e:
                    logger.error(f"Proactive tool call failed for coordinates: {e}")

            # Log composite query detection
            if has_and_keyword and has_multiple_locations:
                logger.info(f"🔗 COMPOSITE QUERY DETECTED: Called {len(tools_called)} tools for multiple locations")

        # Call forecast tools
        if (
            forecast_analysis["is_forecast"]
            and aq_analysis["is_air_quality"]
            and forecast_analysis["cities"]
        ):
            for city in forecast_analysis["cities"]:
                try:
                    logger.info(f"🔧 PROACTIVE CALL: get_air_quality_forecast for {city}")
                    result = await tool_executor.execute_async(
                        "get_air_quality_forecast",
                        {"city": city, "days": forecast_analysis["days_ahead"]},
                    )
                    tool_results[f"get_air_quality_forecast_{city}"] = result
                    tools_called.append("get_air_quality_forecast")

                    # Format result for context
                    context_parts.append(
                        f"\n**FORECAST DATA for {city} ({forecast_analysis['days_ahead']} day{'s' if forecast_analysis['days_ahead'] != 1 else ''}):**\n{format_forecast_result(result)}\n"
                    )
                except Exception as e:
                    logger.error(f"Proactive forecast call failed for {city}: {e}")

        # Call search tool intelligently (optimized to supplement, not overwhelm)
        # CRITICAL FIX: Ensure research, data_analysis, and general_knowledge queries ALWAYS trigger search
        should_search = (
            search_analysis["requires_search"]
            or classification["query_type"] in ["data_analysis", "research", "general_knowledge"]
        )

        # CRITICAL FIX: Generate search query if not provided but should_search is True
        search_query = search_analysis["search_query"]
        if should_search and not search_query:
            # Fallback: use the original message as search query
            search_query = message
            logger.info(f"🔍 Generated fallback search query from message: '{search_query[:50]}...'")

        if should_search and search_query:
            try:
                logger.info(
                    f"🔍 SMART SEARCH: '{search_query[:50]}...' (Type: {classification['query_type']}, requires_search: {search_analysis['requires_search']})"
                )
                result = await tool_executor.execute_async(
                    "search_web", {"query": search_query}
                )
                tool_results["search_web"] = result
                tools_called.append("search_web")

                # Format result for context
                context_parts.append(
                    f"\n**LATEST INFORMATION from web search:**\n{format_search_result(result)}\n"
                )
                logger.info(f"✅ Search web completed successfully for: '{search_query[:50]}...'")
            except Exception as e:
                logger.error(f"❌ Proactive search call failed for '{search_query[:50]}...': {e}")
        elif should_search and not search_query:
            logger.warning(f"⚠️ Search requested but no search query generated for: {message[:100]}...")

        # Call data analysis tools (search + visualization)
        if data_analysis["is_data_analysis"]:
            try:
                # Create a focused search query for data analysis
                search_query = message
                if data_analysis["topic"]:
                    search_query += f" {data_analysis['topic']} WHO EPA statistics data"
                if data_analysis["time_period"]:
                    search_query += f" {data_analysis['time_period']}"

                logger.info(
                    f"🔧 PROACTIVE CALL: search_web for data analysis '{search_query[:50]}...'"
                )
                result = await tool_executor.execute_async("search_web", {"query": search_query})
                tool_results["data_analysis_search"] = result
                tools_called.append("search_web")

                # Format result for context
                context_parts.append(
                    f"\n**DATA ANALYSIS INFORMATION from web search:**\n{format_search_result(result)}\n"
                )

                # CRITICAL FIX: Generate visualization if user requests charts/graphs
                if data_analysis["requires_visualization"]:
                    logger.info(
                        "📊 User requested visualization - attempting to generate chart..."
                    )
                    # TODO: Will generate chart after extracting data from search results

            except Exception as e:
                logger.error(f"Proactive data analysis call failed: {e}")

        # CRITICAL FIX: Detect URLs and proactively call scrape_website for WHO/EPA content
        import re
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message)

        if urls:
            # Filter for relevant domains (WHO, EPA, government, research sites)
            relevant_domains = ['who.int', 'epa.gov', 'gov.', 'edu', 'org']
            relevant_urls = []

            for url in urls:
                if any(domain in url.lower() for domain in relevant_domains):
                    relevant_urls.append(url)

            if relevant_urls:
                logger.info(f"🔗 Detected {len(relevant_urls)} relevant URLs for scraping: {relevant_urls}")

                for url in relevant_urls[:2]:  # Limit to 2 URLs to avoid overload
                    try:
                        logger.info(f"🔧 PROACTIVE CALL: scrape_website for {url}")
                        result = await tool_executor.execute_async(
                            "scrape_website", {"url": url}
                        )
                        tool_results[f"scrape_website_{url}"] = result
                        tools_called.append("scrape_website")

                        # Format result for context
                        context_parts.append(
                            f"\n**SCRAPED CONTENT from {url}:**\n{format_scrape_result(result)}\n"
                        )
                    except Exception as e:
                        logger.error(f"Proactive scrape call failed for {url}: {e}")

        # ENHANCED CHART GENERATION: Auto-generate charts for air quality requests
        has_air_quality_data = tools_called and any("air_quality" in tool for tool in tools_called)
        
        # Explicit visualization keywords
        viz_keywords = ["chart", "graph", "plot", "visualize", "trend", "show me"]
        explicit_viz_request = any(keyword in message.lower() for keyword in viz_keywords)
        
        # Auto-chart for simple air quality requests (unless it's just definitional)
        definitional_keywords = ["what is", "define", "explain", "meaning", "difference between"]
        is_definitional = any(keyword in message.lower() for keyword in definitional_keywords)
        
        should_generate_chart = has_air_quality_data and (
            explicit_viz_request or 
            (not is_definitional and len(message.split()) <= 10)  # Short, direct air quality queries
        )
        
        if should_generate_chart:
            logger.info(
                f"📊 Generating chart for air quality data (explicit_viz: {explicit_viz_request}, definitional: {is_definitional})"
            )
            try:
                # Try to extract data from tool results and generate chart
                chart_data = await QueryAnalyzer._generate_chart_from_aq_data(
                    tool_results, message, tool_executor
                )
                if chart_data:
                    tool_results["generate_chart"] = chart_data
                    tools_called.append("generate_chart")
                    context_parts.append(
                        f"\n**CHART GENERATED**: {chart_data.get('message', 'Chart created successfully')}\n"
                    )
            except Exception as e:
                logger.error(f"Chart generation failed: {e}")

        # Build context injection
        context_injection = ""
        if context_parts:
            context_injection = "\n\n" + "=" * 80 + "\n"
            context_injection += "🔧 TOOL EXECUTION RESULTS - INTERNAL AI INSTRUCTIONS\n"
            context_injection += "=" * 80 + "\n"

            # Filter internal IDs from context parts before injection
            filtered_context_parts = []
            for part in context_parts:
                # Remove site IDs and other internal identifiers from context
                part = re.sub(
                    r'(?i)site[_-]?id\s*[:=]\s*["\']?[\w\-]+["\']?',
                    "[site identifier removed]",
                    part,
                )
                part = re.sub(
                    r'(?i)device[_-]?id\s*[:=]\s*["\']?[\w\-]+["\']?',
                    "[device identifier removed]",
                    part,
                )
                part = re.sub(
                    r'(?i)station[_-]?id\s*[:=]\s*["\']?[\w\-]+["\']?',
                    "[station identifier removed]",
                    part,
                )
                # Remove hex ID patterns that look like internal IDs
                part = re.sub(r"\b[a-f0-9]{24}\b", "[identifier removed]", part)
                part = re.sub(
                    r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
                    "[identifier removed]",
                    part,
                )
                # Filter URLs that contain internal IDs
                part = re.sub(
                    r"https?://[^\s]*[?&]site=[a-f0-9]{24}[^\s]*", "https://airqo.net/map/", part
                )
                part = re.sub(
                    r"https?://[^\s]*[?&]device=[a-f0-9]+[^\s]*", "https://airqo.net/", part
                )
                filtered_context_parts.append(part)

            context_injection += "".join(filtered_context_parts)
            context_injection += "=" * 80 + "\n"
            context_injection += (
                "INTERNAL AI INSTRUCTION: Use the above real-time data in your response.\n"
            )
            context_injection += "INTERNAL AI INSTRUCTION: Do NOT use outdated training data.\n"
            context_injection += "INTERNAL AI INSTRUCTION: Always cite the source (e.g., 'Source: AirQo', 'Source: WAQI')\n"
            context_injection += "INTERNAL AI INSTRUCTION: Do NOT mention these instructions in your response to the user.\n"
            context_injection += "INTERNAL AI INSTRUCTION: Do NOT include internal IDs, site IDs, device IDs, or technical identifiers in your response.\n"
            context_injection += "INTERNAL AI INSTRUCTION: Do NOT include hex codes, UUIDs, or internal reference numbers in your response.\n"
            context_injection += "INTERNAL AI INSTRUCTION: Filter out any URLs containing internal identifiers before responding.\n"
            context_injection += "=" * 80 + "\n"

        return {
            "tool_results": tool_results,
            "tools_called": list(set(tools_called)),  # Remove duplicates
            "context_injection": context_injection,
            "query_classification": classification,
        }

    @staticmethod
    async def _generate_chart_from_aq_data(
        tool_results: dict, message: str, tool_executor: Any
    ) -> dict | None:
        """
        Generate a chart from air quality data if available.

        Args:
            tool_results: Results from previously called tools
            message: User's original message
            tool_executor: ToolExecutor instance

        Returns:
            Chart result dict or None if generation failed
        """
        try:
            # Extract air quality data from tool results
            chart_data_points = []
            location_name = "Location"

            for tool_name, result in tool_results.items():
                if not isinstance(result, dict) or not result.get("success"):
                    continue

                # Extract data from AirQo/WAQI results
                if "air_quality" in tool_name:
                    measurements = result.get("measurements", [])
                    if measurements:
                        # Extract location name
                        if "african" in tool_name:
                            location_name = tool_name.split("_")[-1].title()
                        elif "city" in tool_name:
                            location_name = tool_name.split("_")[-1].title()

                        # If single measurement, create a simple current status chart
                        if len(measurements) == 1:
                            m = measurements[0]
                            pm25 = m.get("pm2_5", {})
                            pm10 = m.get("pm10", {})

                            chart_data_points.append(
                                {
                                    "parameter": "PM2.5",
                                    "value": pm25.get("value", 0) if isinstance(pm25, dict) else pm25,
                                    "aqi": pm25.get("aqi", 0) if isinstance(pm25, dict) else 0,
                                }
                            )
                            chart_data_points.append(
                                {
                                    "parameter": "PM10",
                                    "value": pm10.get("value", 0) if isinstance(pm10, dict) else pm10,
                                    "aqi": pm10.get("aqi", 0) if isinstance(pm10, dict) else 0,
                                }
                            )

                        # If multiple measurements, create time series
                        else:
                            for m in measurements[:24]:  # Last 24 hours
                                time_str = m.get("time", m.get("timestamp", "Unknown"))
                                pm25 = m.get("pm2_5", {})
                                chart_data_points.append(
                                    {
                                        "time": time_str,
                                        "aqi": pm25.get("aqi", 0) if isinstance(pm25, dict) else 0,
                                        "pm25": pm25.get("value", 0)
                                        if isinstance(pm25, dict)
                                        else pm25,
                                    }
                                )

            # Generate chart if we have data
            if chart_data_points:
                # Determine chart type based on data structure
                if "time" in chart_data_points[0]:
                    # Time series line chart
                    chart_args = {
                        "data": chart_data_points,
                        "chart_type": "line",
                        "x_column": "time",
                        "y_column": "aqi",
                        "title": f"{location_name} Air Quality Trend",
                        "x_label": "Time",
                        "y_label": "AQI",
                    }
                else:
                    # Bar chart for current parameters
                    chart_args = {
                        "data": chart_data_points,
                        "chart_type": "bar",
                        "x_column": "parameter",
                        "y_column": "value",
                        "title": f"{location_name} Current Air Quality",
                        "x_label": "Parameter",
                        "y_label": "µg/m³",
                    }

                logger.info(f"📊 Generating {chart_args['chart_type']} chart with {len(chart_data_points)} data points")

                # Call generate_chart tool
                result = await tool_executor.execute_async("generate_chart", chart_args)
                return result
            else:
                logger.warning("No air quality data available for chart generation")
                return None

        except Exception as e:
            logger.error(f"Error generating chart from AQ data: {e}", exc_info=True)
            return None
