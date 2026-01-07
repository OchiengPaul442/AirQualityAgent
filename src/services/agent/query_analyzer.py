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
        'kampala', 'gulu', 'jinja', 'mbale', 'mbarara', 'nakasero',
        'nairobi', 'mombasa', 'kisumu', 'nakuru', 'eldoret',
        'dar es salaam', 'dodoma', 'mwanza', 'arusha', 'mbeya',
        'kigali', 'butare', 'musanze', 'ruhengeri', 'gisenyi',
        'addis ababa', 'accra', 'lagos', 'abuja', 'cairo', 'alexandria'
    ]

    GLOBAL_CITIES = [
        'london', 'paris', 'berlin', 'munich', 'rome', 'madrid',
        'new york', 'los angeles', 'chicago', 'houston', 'phoenix',
        'tokyo', 'osaka', 'kyoto', 'beijing', 'shanghai', 'guangzhou',
        'delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata',
        'sydney', 'melbourne', 'brisbane', 'perth', 'auckland',
        'toronto', 'vancouver', 'montreal', 'mexico city', 'sao paulo'
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
            'air quality', 'aqi', 'pollution', 'pm2.5', 'pm10', 
            'pollutant', 'smog', 'air', 'breathe', 'safe to exercise',
            'outdoor', 'environment', 'atmospheric'
        ]
        
        is_air_quality = any(keyword in message_lower for keyword in air_quality_keywords)
        
        # Extract coordinates (lat/lon)
        coordinates = None
        coord_pattern = r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)'
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
            "coordinates": coordinates
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
        
        # Search trigger keywords
        search_keywords = [
            'latest', 'recent', 'new', 'current', 'update', 'up-to-date',
            'policy', 'regulation', 'legislation', 'law', 'government',
            'research', 'study', 'studies', 'who', 'epa', 'guideline',
            'news', 'development', 'announcement', 'breaking',
            '2024', '2025', '2026', 'this year', 'last year'
        ]
        
        requires_search = any(keyword in message_lower for keyword in search_keywords)
        
        # Generate search query
        search_query = message if requires_search else None
        
        return {
            "requires_search": requires_search,
            "search_query": search_query
        }

    @staticmethod
    def detect_scraping_query(message: str) -> dict[str, Any]:
        """
        Detect if the query requires web scraping.
        
        Returns:
            Dict with:
                - requires_scraping: bool
                - url: URL to scrape if detected
        """
        # Extract URLs
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message)
        
        scraping_keywords = ['scrape', 'check this', 'analyze this', 'what does this say']
        requires_scraping = len(urls) > 0 or any(keyword in message.lower() for keyword in scraping_keywords)
        
        return {
            "requires_scraping": requires_scraping and len(urls) > 0,
            "url": urls[0] if urls else None
        }

    @staticmethod
    async def proactively_call_tools(
        message: str,
        tool_executor: Any
    ) -> dict[str, Any]:
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
        search_analysis = QueryAnalyzer.detect_search_query(message)
        scrape_analysis = QueryAnalyzer.detect_scraping_query(message)
        
        # Call air quality tools
        if aq_analysis["is_air_quality"] and (aq_analysis["cities"] or aq_analysis["coordinates"]):
            # Call for African cities
            for city in aq_analysis["african_cities"]:
                try:
                    logger.info(f"🔧 PROACTIVE CALL: get_african_city_air_quality for {city}")
                    result = await tool_executor.execute_async("get_african_city_air_quality", {"city": city})
                    tool_results[f"get_african_city_air_quality_{city}"] = result
                    tools_called.append("get_african_city_air_quality")
                    
                    # Format result for context
                    context_parts.append(f"\n**REAL-TIME DATA from AirQo for {city}:**\n{format_air_quality_result(result)}\n")
                except Exception as e:
                    logger.error(f"Proactive tool call failed for {city}: {e}")
            
            # Call for global cities
            for city in aq_analysis["global_cities"]:
                try:
                    logger.info(f"🔧 PROACTIVE CALL: get_city_air_quality for {city}")
                    result = await tool_executor.execute_async("get_city_air_quality", {"city": city})
                    tool_results[f"get_city_air_quality_{city}"] = result
                    tools_called.append("get_city_air_quality")
                    
                    # Format result for context
                    context_parts.append(f"\n**REAL-TIME DATA from WAQI for {city}:**\n{format_air_quality_result(result)}\n")
                except Exception as e:
                    logger.error(f"Proactive tool call failed for {city}: {e}")
            
            # Call for coordinates
            if aq_analysis["coordinates"]:
                try:
                    coords = aq_analysis["coordinates"]
                    logger.info(f"🔧 PROACTIVE CALL: get_openmeteo_air_quality for {coords}")
                    result = await tool_executor.execute_async("get_openmeteo_current_air_quality", coords)
                    tool_results["get_openmeteo_air_quality"] = result
                    tools_called.append("get_openmeteo_current_air_quality")
                    
                    # Format result for context
                    context_parts.append(f"\n**REAL-TIME DATA from OpenMeteo for coordinates {coords['latitude']}, {coords['longitude']}:**\n{format_air_quality_result(result)}\n")
                except Exception as e:
                    logger.error(f"Proactive tool call failed for coordinates: {e}")
        
        # Call search tool
        if search_analysis["requires_search"] and search_analysis["search_query"]:
            try:
                logger.info(f"🔧 PROACTIVE CALL: search_web for '{search_analysis['search_query'][:50]}...'")
                result = await tool_executor.execute_async("search_web", {"query": search_analysis["search_query"]})
                tool_results["search_web"] = result
                tools_called.append("search_web")
                
                # Format result for context
                context_parts.append(f"\n**LATEST INFORMATION from web search:**\n{format_search_result(result)}\n")
            except Exception as e:
                logger.error(f"Proactive search call failed: {e}")
        
        # Call scraping tool
        if scrape_analysis["requires_scraping"] and scrape_analysis["url"]:
            try:
                logger.info(f"🔧 PROACTIVE CALL: scrape_website for {scrape_analysis['url']}")
                result = await tool_executor.execute_async("scrape_website", {"url": scrape_analysis["url"]})
                tool_results["scrape_website"] = result
                tools_called.append("scrape_website")
                
                # Format result for context
                context_parts.append(f"\n**CONTENT from {scrape_analysis['url']}:**\n{format_scrape_result(result)}\n")
            except Exception as e:
                logger.error(f"Proactive scrape call failed: {e}")
        
        # Build context injection
        context_injection = ""
        if context_parts:
            context_injection = "\n\n" + "="*80 + "\n"
            context_injection += "🔧 TOOL EXECUTION RESULTS (MANDATORY - USE THIS DATA IN YOUR RESPONSE)\n"
            context_injection += "="*80 + "\n"
            context_injection += "".join(context_parts)
            context_injection += "="*80 + "\n"
            context_injection += "⚠️ YOU MUST use the above real-time data in your response. DO NOT use training data.\n"
            context_injection += "⚠️ ALWAYS cite the source (e.g., 'Source: AirQo', 'Source: WAQI', 'Source: Web Search')\n"
            context_injection += "="*80 + "\n"
        
        return {
            "tool_results": tool_results,
            "tools_called": list(set(tools_called)),  # Remove duplicates
            "context_injection": context_injection
        }


def format_air_quality_result(result: dict) -> str:
    """Format air quality result for context injection."""
    try:
        if isinstance(result, dict):
            if result.get("success") and result.get("measurements"):
                m = result["measurements"][0]
                pm25 = m.get("pm2_5", {})
                pm10 = m.get("pm10", {})
                site = m.get("siteDetails", {})
                
                formatted = f"AQI: {pm25.get('aqi', 'N/A')}\n"
                formatted += f"PM2.5: {pm25.get('value', 'N/A')} µg/m³\n"
                formatted += f"PM10: {pm10.get('value', 'N/A')} µg/m³\n"
                formatted += f"Location: {site.get('name', 'Unknown')}\n"
                formatted += f"Time: {m.get('time', 'Unknown')}\n"
                return formatted
            elif result.get("data"):
                # OpenMeteo format
                data = result["data"]
                formatted = f"AQI: {data.get('aqi', 'N/A')}\n"
                formatted += f"PM2.5: {data.get('pm2_5', 'N/A')} µg/m³\n"
                formatted += f"PM10: {data.get('pm10', 'N/A')} µg/m³\n"
                return formatted
        return str(result)[:500]  # Truncate if too long
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
