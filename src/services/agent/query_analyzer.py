"""
Query Analyzer - Intelligent Pre-Processing for Tool Calling

This module analyzes user queries and proactively calls tools BEFORE sending to the AI.
This ensures that even models with weak tool-calling support get the data they need.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes queries and determines which tools need to be called proactively."""

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

        # Extract coordinates (lat/lon)
        coordinates = None
        coord_pattern = r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
        coord_match = re.search(coord_pattern, message)
        if coord_match:
            try:
                lat = float(coord_match.group(1))
                lon = float(coord_match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    coordinates = {"latitude": lat, "longitude": lon}
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
        Detect if the query requires web search.

        Returns:
            Dict with:
                - requires_search: bool
                - search_query: suggested search query string
        """
        message_lower = message.lower()

        # Search trigger keywords - EXPANDED LIST
        search_keywords = [
            "latest",
            "recent",
            "new",
            "current",
            "update",
            "up-to-date",
            "policy",
            "regulation",
            "legislation",
            "law",
            "government",
            "research",
            "study",
            "studies",
            "who",
            "epa",
            "guideline",
            "news",
            "development",
            "announcement",
            "breaking",
            "2024",
            "2025",
            "2026",
            "this year",
            "last year",
            "past",
            "statistics",
            "stats",
            "data",
            "chart",
            "graph",
            "visualize",
            "show me",
            "generate",
            "deaths",
            "mortality",
            "impact",
            "trends",
            "analysis",
            "report",
            "findings",
            "evidence",
            "global",
            "worldwide",
            "international",
            "epidemiology",
            "health effects",
            "risk assessment",
            "burden",
            "prevalence",
        ]

        # Data analysis keywords that definitely require search
        data_keywords = [
            "statistics",
            "stats",
            "data",
            "chart",
            "graph",
            "visualize",
            "show me",
            "generate",
            "deaths",
            "mortality",
            "trends",
            "analysis",
            "report",
            "findings",
            "evidence",
            "burden",
        ]

        # Check for data/statistics requests
        has_data_keywords = any(keyword in message_lower for keyword in data_keywords)

        # Check for temporal keywords (past years, recent, etc.)
        temporal_keywords = [
            "2023",
            "2024",
            "2025",
            "2026",
            "past",
            "last year",
            "recent",
            "latest",
        ]
        has_temporal = any(keyword in message_lower for keyword in temporal_keywords)

        # Check for research/health impact keywords
        research_keywords = ["deaths", "mortality", "impact", "burden", "epidemiology", "risk"]
        has_research = any(keyword in message_lower for keyword in research_keywords)

        # DEFINITE search triggers
        requires_search = (
            any(keyword in message_lower for keyword in search_keywords)
            or has_data_keywords
            or (has_temporal and has_research)
            or "pollution" in message_lower
            and (has_data_keywords or has_temporal)
        )

        # Generate search query
        if requires_search:
            # For data/statistics requests, create a focused search query
            if has_data_keywords:
                search_query = message + " WHO EPA statistics data"
            else:
                search_query = message
        else:
            search_query = None

        return {"requires_search": requires_search, "search_query": search_query}

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
        Analyze the query and proactively call necessary tools.

        Args:
            message: User's query
            tool_executor: ToolExecutor instance

        Returns:
            Dict with:
                - tool_results: Dict mapping tool names to results
                - tools_called: List of tool names called
                - context_injection: String to inject into AI context
        """
        tool_results = {}
        tools_called = []
        context_parts = []

        # Analyze query
        aq_analysis = QueryAnalyzer.detect_air_quality_query(message)
        forecast_analysis = QueryAnalyzer.detect_forecast_query(message)
        search_analysis = QueryAnalyzer.detect_search_query(message)
        data_analysis = QueryAnalyzer.detect_data_analysis_query(message)

        # Call air quality tools
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

            # Call for coordinates
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

        # Call search tool
        if search_analysis["requires_search"] and search_analysis["search_query"]:
            try:
                logger.info(
                    f"🔧 PROACTIVE CALL: search_web for '{search_analysis['search_query'][:50]}...'"
                )
                result = await tool_executor.execute_async(
                    "search_web", {"query": search_analysis["search_query"]}
                )
                tool_results["search_web"] = result
                tools_called.append("search_web")

                # Format result for context
                context_parts.append(
                    f"\n**LATEST INFORMATION from web search:**\n{format_search_result(result)}\n"
                )
            except Exception as e:
                logger.error(f"Proactive search call failed: {e}")

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

                # Note: Visualization tool not yet implemented in tool executor
                # For now, just provide search results that can be used for visualization

            except Exception as e:
                logger.error(f"Proactive data analysis call failed: {e}")

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
        }


def format_air_quality_result(result: dict) -> str:
    """Format air quality result for context injection."""
    try:
        import re

        # Filter out internal identifiers from the result data
        def filter_internal_ids(obj):
            """Recursively filter out internal IDs from nested dict/list structures."""
            if isinstance(obj, dict):
                filtered = {}
                for key, value in obj.items():
                    # Skip keys that contain internal ID patterns
                    if re.search(
                        r"(?i)(site_id|device_id|station_id|sensor_id|location_id|monitor_id|node_id)",
                        key,
                    ):
                        continue
                    # Filter values that look like internal IDs (hex strings, long alphanumeric)
                    if isinstance(value, str) and re.match(
                        r"^[a-f0-9]{24}$|^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
                        value,
                    ):
                        continue
                    # Recursively filter nested structures
                    filtered[key] = filter_internal_ids(value)
                return filtered
            elif isinstance(obj, list):
                return [filter_internal_ids(item) for item in obj]
            else:
                return obj

        # Filter the result to remove internal IDs
        filtered_result = filter_internal_ids(result)

        if isinstance(filtered_result, dict):
            if filtered_result.get("success") and filtered_result.get("measurements"):
                m = filtered_result["measurements"][0]
                pm25 = m.get("pm2_5", {})
                pm10 = m.get("pm10", {})
                site = m.get("siteDetails", {})

                formatted = f"AQI: {pm25.get('aqi', 'N/A')}\n"
                formatted += f"PM2.5: {pm25.get('value', 'N/A')} µg/m³\n"
                formatted += f"PM10: {pm10.get('value', 'N/A')} µg/m³\n"
                formatted += f"Location: {site.get('name', 'Unknown')}\n"
                formatted += f"Time: {m.get('time', 'Unknown')}\n"
                return formatted
            elif filtered_result.get("data"):
                # OpenMeteo format
                data = filtered_result["data"]
                formatted = f"AQI: {data.get('aqi', 'N/A')}\n"
                formatted += f"PM2.5: {data.get('pm2_5', 'N/A')} µg/m³\n"
                formatted += f"PM10: {data.get('pm10', 'N/A')} µg/m³\n"
                return formatted
        return str(filtered_result)[:500]  # Truncate if too long
    except Exception:
        return str(result)[:500]


def format_search_result(result: dict) -> str:
    """Format search result for context injection."""
    try:
        if isinstance(result, dict) and result.get("results"):
            formatted = ""
            for i, item in enumerate(result["results"][:3], 1):  # Top 3 results
                formatted += f"{i}. {item.get('title', 'No title')}\n"
                formatted += f"   {item.get('snippet', 'No snippet')[:200]}...\n"
                formatted += f"   Source: {item.get('url', 'N/A')}\n\n"
            return formatted
        return str(result)[:500]
    except Exception:
        return str(result)[:500]


def format_scrape_result(result: dict) -> str:
    """Format scrape result for context injection."""
    try:
        if isinstance(result, dict):
            content = result.get("content", "")
            return content[:1000] + "..." if len(content) > 1000 else content
        return str(result)[:500]
    except Exception:
        return str(result)[:500]


def format_forecast_result(result: dict) -> str:
    """Format forecast result for context injection."""
    try:
        if isinstance(result, dict):
            if result.get("success") and result.get("forecast"):
                forecast_data = result["forecast"]
                formatted = ""

                # Handle different forecast formats
                if isinstance(forecast_data, list) and len(forecast_data) > 0:
                    # Take the first forecast entry (tomorrow)
                    tomorrow = forecast_data[0]
                    formatted += f"Date: {tomorrow.get('date', 'Unknown')}\n"
                    formatted += f"AQI: {tomorrow.get('aqi', 'N/A')}\n"
                    formatted += f"PM2.5: {tomorrow.get('pm25', 'N/A')} µg/m³\n"
                    formatted += f"PM10: {tomorrow.get('pm10', 'N/A')} µg/m³\n"
                    formatted += f"O3: {tomorrow.get('o3', 'N/A')} µg/m³\n"
                    formatted += f"NO2: {tomorrow.get('no2', 'N/A')} µg/m³\n"
                    formatted += f"SO2: {tomorrow.get('so2', 'N/A')} µg/m³\n"
                    formatted += f"CO: {tomorrow.get('co', 'N/A')} µg/m³\n"
                elif isinstance(forecast_data, dict):
                    # Single forecast entry
                    formatted += f"Date: {forecast_data.get('date', 'Unknown')}\n"
                    formatted += f"AQI: {forecast_data.get('aqi', 'N/A')}\n"
                    formatted += f"PM2.5: {forecast_data.get('pm25', 'N/A')} µg/m³\n"
                    formatted += f"PM10: {forecast_data.get('pm10', 'N/A')} µg/m³\n"

                # Add source information
                if result.get("data_source"):
                    formatted += f"Source: {result['data_source']}\n"

                return formatted
        return str(result)[:500]  # Truncate if too long
    except Exception:
        return str(result)[:500]
