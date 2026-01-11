"""
MCP Server Implementation

This module exposes the agent's capabilities (AirQo, Scraping, etc.) as an MCP server.
"""

import asyncio
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from core.tools.robust_scraper import RobustScraper
from infrastructure.api.airqo import AirQoService
from shared.config.settings import get_settings
from shared.utils.provider_errors import ProviderServiceError, provider_unavailable_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize services
airqo_service = AirQoService()
scraper_service = RobustScraper()

# Create MCP Server
mcp = FastMCP("Agent2 MCP Server")


@mcp.tool()
async def get_air_quality(city: str, site_id: str | None = None) -> dict[str, Any]:
    """
    Get recent air quality measurements for a city or specific site.

    Args:
        city: Name of the city (e.g., "Kampala")
        site_id: Optional specific AirQo site ID
    """
    try:
        return airqo_service.get_recent_measurements(city=city, site_id=site_id)
    except ProviderServiceError as e:
        logger.warning("AirQo tool failure", extra={"city": city})
        return {"error": e.public_message}
    except Exception:
        logger.exception("AirQo tool failure", extra={"city": city})
        return {"error": provider_unavailable_message("AirQo")}


@mcp.tool()
async def get_multiple_cities_air_quality(cities: list[str]) -> dict[str, Any]:
    """
    Get recent air quality measurements for multiple cities simultaneously.

    Args:
        cities: List of city names (e.g., ["Kampala", "Gulu"])
    """
    try:
        return airqo_service.get_multiple_cities_air_quality(cities)
    except ProviderServiceError as e:
        logger.warning("AirQo multi-city tool failure")
        return {"error": e.public_message}
    except Exception:
        logger.exception("AirQo multi-city tool failure")
        return {"error": provider_unavailable_message("AirQo")}


@mcp.tool()
async def get_air_quality_forecast(site_id: str, frequency: str = "daily") -> dict[str, Any]:
    """
    Get air quality forecast for a specific site.

    Args:
        site_id: AirQo site ID
        frequency: Forecast frequency ("daily" or "hourly")
    """
    try:
        return airqo_service.get_forecast(site_id=site_id, frequency=frequency)
    except ProviderServiceError as e:
        logger.warning("AirQo forecast tool failure", extra={"site_id": site_id})
        return {"error": e.public_message}
    except Exception:
        logger.exception("AirQo forecast tool failure", extra={"site_id": site_id})
        return {"error": provider_unavailable_message("AirQo")}


@mcp.tool()
async def get_air_quality_history(
    site_id: str, start_time: str, end_time: str, frequency: str = "hourly"
) -> dict[str, Any]:
    """
    Get historical air quality measurements.

    Args:
        site_id: AirQo site ID
        start_time: Start time in ISO format (e.g., "2023-01-01T00:00:00Z")
        end_time: End time in ISO format
        frequency: Data frequency ("hourly", "daily", "raw")
    """
    from datetime import datetime

    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        return airqo_service.get_historical_measurements(
            site_id=site_id, start_time=start, end_time=end, frequency=frequency
        )
    except ProviderServiceError as e:
        logger.warning("AirQo history tool failure", extra={"site_id": site_id})
        return {"error": e.public_message}
    except Exception:
        logger.exception("AirQo history tool failure", extra={"site_id": site_id})
        return {"error": provider_unavailable_message("AirQo")}


@mcp.tool()
async def scrape_webpage(url: str) -> dict[str, Any]:
    """
    Scrape a webpage and return its content.

    Args:
        url: The URL to scrape
    """
    try:
        # Run synchronous scraper in a thread pool
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, scraper_service.scrape, url)
    except Exception:
        logger.exception("Scraper tool failure", extra={"url": url})
        return {"error": provider_unavailable_message("Web Scraper")}


@mcp.tool()
async def search_web(query: str) -> dict[str, Any]:
    """
    MANDATORY TOOL: Use this for ANY question requiring research, current information, health data, policy information, solutions, safety guidelines, or general knowledge. ALWAYS use this instead of saying 'data not available' or giving generic advice. Search for specific, accurate information from reliable sources.

    Args:
        query: The search query for any topic
    """
    try:
        # Import here to avoid circular imports
        from domain.services.search_service import SearchService

        search_service = SearchService()
        results = search_service.search(query)
        return {"results": results}
    except Exception:
        logger.exception("Web search tool failure")
        return {"error": provider_unavailable_message("Web Search")}


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
