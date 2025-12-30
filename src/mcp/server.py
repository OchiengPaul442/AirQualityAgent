"""
MCP Server Implementation

This module exposes the agent's capabilities (AirQo, Scraping, etc.) as an MCP server.
"""

import asyncio
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from src.config import get_settings
from src.services.airqo_service import AirQoService
from src.tools.robust_scraper import RobustScraper

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
async def get_air_quality(city: str, site_id: Optional[str] = None) -> dict[str, Any]:
    """
    Get recent air quality measurements for a city or specific site.

    Args:
        city: Name of the city (e.g., "Kampala")
        site_id: Optional specific AirQo site ID
    """
    try:
        return airqo_service.get_recent_measurements(city=city, site_id=site_id)
    except Exception as e:
        return {"error": str(e)}


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
    except Exception as e:
        return {"error": str(e)}


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
    except Exception as e:
        return {"error": str(e)}


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
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def search_airqo_sites(query: str) -> dict[str, Any]:
    """
    Search for AirQo sites by name or description.

    Args:
        query: Search query (e.g., "Makerere")
    """
    try:
        # This is a helper to expose the site search capability
        # We might need to add a specific search method to AirQoService if get_metadata isn't enough
        # For now, we can use get_site_id_by_name logic but return more info
        # Or just expose get_metadata("sites") and let the client filter

        # Let's implement a simple filter here for utility
        response = airqo_service.get_metadata("sites")
        sites = response.get("sites", [])
        query_lower = query.lower()

        matches = [
            {
                "id": s.get("_id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "country": s.get("country"),
                "city": s.get("city"),
            }
            for s in sites
            if query_lower in s.get("name", "").lower()
            or query_lower in s.get("description", "").lower()
        ]
        return {"matches": matches[:10]}  # Limit to 10 results
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
