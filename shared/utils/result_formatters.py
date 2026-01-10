"""
Result Formatters for Tool Outputs

Centralized formatting utilities for different types of results.
Reduces duplication across query_analyzer.py and provider utilities.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ResultFormatter:
    """Centralized result formatting for consistent output across the agent."""

    @staticmethod
    def format_as_json(result: Any, indent: int = 2, max_length: int | None = None) -> str:
        """
        Format any result as readable JSON string.
        
        Args:
            result: Data to format (dict, list, or primitive)
            indent: JSON indentation level
            max_length: Maximum length (truncate if exceeded)
            
        Returns:
            Formatted JSON string
        """
        try:
            formatted = json.dumps(result, indent=indent, ensure_ascii=False)
            if max_length and len(formatted) > max_length:
                formatted = formatted[:max_length] + "..."
            return formatted
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to format result as JSON: {e}")
            result_str = str(result)
            if max_length and len(result_str) > max_length:
                result_str = result_str[:max_length] + "..."
            return result_str

    @staticmethod
    def _filter_internal_ids(obj: Any) -> Any:
        """
        Recursively filter out internal IDs from nested structures.
        
        Args:
            obj: Object to filter (dict, list, or primitive)
            
        Returns:
            Filtered copy without internal IDs
        """
        if isinstance(obj, dict):
            filtered = {}
            for key, value in obj.items():
                # Skip keys that contain internal ID patterns
                if re.search(
                    r"(?i)(site_id|device_id|station_id|sensor_id|location_id|monitor_id|node_id)",
                    key,
                ):
                    continue
                # Filter values that look like internal IDs (hex strings, UUIDs)
                if isinstance(value, str) and re.match(
                    r"^[a-f0-9]{24}$|^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
                    value,
                ):
                    continue
                # Recursively filter nested structures
                filtered[key] = ResultFormatter._filter_internal_ids(value)
            return filtered
        elif isinstance(obj, list):
            return [ResultFormatter._filter_internal_ids(item) for item in obj]
        else:
            return obj

    @staticmethod
    def format_air_quality(result: dict, max_length: int = 500) -> str:
        """
        Format air quality result for context injection.
        
        Args:
            result: Air quality data from any service
            max_length: Maximum output length
            
        Returns:
            Formatted string with key AQ metrics
        """
        try:
            # Filter internal IDs for cleaner output
            filtered_result = ResultFormatter._filter_internal_ids(result)

            if isinstance(filtered_result, dict):
                # AirQo format
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

                # OpenMeteo format
                elif filtered_result.get("data"):
                    data = filtered_result["data"]
                    formatted = f"AQI: {data.get('aqi', 'N/A')}\n"
                    formatted += f"PM2.5: {data.get('pm2_5', 'N/A')} µg/m³\n"
                    formatted += f"PM10: {data.get('pm10', 'N/A')} µg/m³\n"
                    return formatted

            # Fallback to truncated string
            result_str = str(filtered_result)
            return result_str[:max_length] + ("..." if len(result_str) > max_length else "")
        except Exception as e:
            logger.warning(f"Error formatting air quality result: {e}")
            return str(result)[:max_length]

    @staticmethod
    def format_search(result: dict, max_results: int = 3, max_length: int = 500) -> str:
        """
        Format search result for context injection.
        
        Args:
            result: Search results from SearchService
            max_results: Maximum number of results to include
            max_length: Maximum output length
            
        Returns:
            Formatted string with top search results
        """
        try:
            if isinstance(result, dict) and result.get("results"):
                formatted = ""
                for i, item in enumerate(result["results"][:max_results], 1):
                    formatted += f"{i}. {item.get('title', 'No title')}\n"
                    snippet = item.get('snippet', 'No snippet')
                    formatted += f"   {snippet[:200]}...\n"
                    formatted += f"   Source: {item.get('url', 'N/A')}\n\n"
                return formatted

            result_str = str(result)
            return result_str[:max_length] + ("..." if len(result_str) > max_length else "")
        except Exception as e:
            logger.warning(f"Error formatting search result: {e}")
            return str(result)[:max_length]

    @staticmethod
    def format_scrape(result: dict, max_length: int = 1000) -> str:
        """
        Format scrape result for context injection.
        
        Args:
            result: Scraped content from web scraper
            max_length: Maximum output length
            
        Returns:
            Formatted string with scraped content
        """
        try:
            if isinstance(result, dict):
                content = result.get("content", "")
                if len(content) > max_length:
                    return content[:max_length] + "..."
                return content

            result_str = str(result)
            return result_str[:max_length] + ("..." if len(result_str) > max_length else "")
        except Exception as e:
            logger.warning(f"Error formatting scrape result: {e}")
            return str(result)[:max_length]

    @staticmethod
    def format_forecast(result: dict, max_length: int = 1000) -> str:
        """
        Format forecast result for context injection.
        
        Args:
            result: Forecast data from any service
            max_length: Maximum output length
            
        Returns:
            Formatted string with forecast details
        """
        try:
            if isinstance(result, dict):
                if result.get("success") and result.get("forecast"):
                    forecast_data = result["forecast"]
                    formatted = ""

                    # Handle list format (daily forecasts)
                    if isinstance(forecast_data, list) and len(forecast_data) > 0:
                        tomorrow = forecast_data[0]
                        formatted += f"Date: {tomorrow.get('date', 'Unknown')}\n"
                        formatted += f"AQI: {tomorrow.get('aqi', 'N/A')}\n"
                        formatted += f"PM2.5: {tomorrow.get('pm25', 'N/A')} µg/m³\n"
                        formatted += f"PM10: {tomorrow.get('pm10', 'N/A')} µg/m³\n"
                        formatted += f"O3: {tomorrow.get('o3', 'N/A')} µg/m³\n"
                        formatted += f"NO2: {tomorrow.get('no2', 'N/A')} µg/m³\n"
                        formatted += f"SO2: {tomorrow.get('so2', 'N/A')} µg/m³\n"
                        formatted += f"CO: {tomorrow.get('co', 'N/A')} µg/m³\n"
                        return formatted

                    # Handle dict format
                    elif isinstance(forecast_data, dict):
                        formatted += f"AQI: {forecast_data.get('aqi', 'N/A')}\n"
                        formatted += f"PM2.5: {forecast_data.get('pm25', 'N/A')} µg/m³\n"
                        formatted += f"PM10: {forecast_data.get('pm10', 'N/A')} µg/m³\n"
                        return formatted

            result_str = str(result)
            return result_str[:max_length] + ("..." if len(result_str) > max_length else "")
        except Exception as e:
            logger.warning(f"Error formatting forecast result: {e}")
            return str(result)[:max_length]

    @staticmethod
    def format_weather(result: dict, max_length: int = 500) -> str:
        """
        Format weather result for context injection.
        
        Args:
            result: Weather data from WeatherService
            max_length: Maximum output length
            
        Returns:
            Formatted string with weather details
        """
        try:
            if isinstance(result, dict) and result.get("data"):
                data = result["data"]
                formatted = f"Temperature: {data.get('temperature', 'N/A')}°C\n"
                formatted += f"Humidity: {data.get('humidity', 'N/A')}%\n"
                formatted += f"Wind Speed: {data.get('wind_speed', 'N/A')} m/s\n"
                formatted += f"Conditions: {data.get('description', 'N/A')}\n"
                return formatted

            result_str = str(result)
            return result_str[:max_length] + ("..." if len(result_str) > max_length else "")
        except Exception as e:
            logger.warning(f"Error formatting weather result: {e}")
            return str(result)[:max_length]


# Convenience functions for backward compatibility
def format_tool_result_as_json(result: Any) -> str:
    """Legacy wrapper for ResultFormatter.format_as_json()"""
    return ResultFormatter.format_as_json(result)


def format_air_quality_result(result: dict) -> str:
    """Legacy wrapper for ResultFormatter.format_air_quality()"""
    return ResultFormatter.format_air_quality(result)


def format_search_result(result: dict) -> str:
    """Legacy wrapper for ResultFormatter.format_search()"""
    return ResultFormatter.format_search(result)


def format_scrape_result(result: dict) -> str:
    """Legacy wrapper for ResultFormatter.format_scrape()"""
    return ResultFormatter.format_scrape(result)


def format_forecast_result(result: dict) -> str:
    """Legacy wrapper for ResultFormatter.format_forecast()"""
    return ResultFormatter.format_forecast(result)
