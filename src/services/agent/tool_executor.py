"""
Tool execution module for AI agent.

Handles execution of various data source and utility tools.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools for the AI agent."""

    def __init__(
        self,
        waqi_service,
        airqo_service,
        openmeteo_service,
        carbon_intensity_service,
        defra_service,
        uba_service,
        weather_service,
        search_service,
        scraper,
        document_scanner,
    ):
        """
        Initialize tool executor with service instances.

        Args:
            waqi_service: WAQI air quality service
            airqo_service: AirQo air quality service
            openmeteo_service: OpenMeteo weather service
            carbon_intensity_service: UK carbon intensity service
            defra_service: UK DEFRA air quality service
            uba_service: German UBA air quality service
            weather_service: Weather service
            search_service: Web search service
            scraper: Web scraper
            document_scanner: Document scanner
        """
        self.waqi = waqi_service
        self.airqo = airqo_service
        self.openmeteo = openmeteo_service
        self.carbon_intensity = carbon_intensity_service
        self.defra = defra_service
        self.uba = uba_service
        self.weather = weather_service
        self.search = search_service
        self.scraper = scraper
        self.document_scanner = document_scanner

    def execute(self, function_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool synchronously.

        Args:
            function_name: Name of the tool/function to execute
            args: Arguments for the function

        Returns:
            Result dictionary from the tool execution
        """
        try:
            # WAQI tools
            if function_name == "get_city_air_quality":
                if self.waqi is None:
                    return {"success": False, "message": "WAQI service is not enabled."}
                return self.waqi.get_city_feed(args.get("city"))

            elif function_name == "search_waqi_stations":
                if self.waqi is None:
                    return {"success": False, "message": "WAQI service is not enabled."}
                return self.waqi.search_stations(args.get("keyword"))

            # AirQo tools
            elif function_name == "get_african_city_air_quality":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                city = args.get("city")
                site_id = args.get("site_id")
                try:
                    result = self.airqo.get_recent_measurements(city=city, site_id=site_id)
                    if result.get("success"):
                        return result
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
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                cities = args.get("cities", [])
                results = {}
                for city in cities:
                    try:
                        result = self.airqo.get_recent_measurements(city=city)
                        results[city] = result
                    except Exception as e:
                        logger.error(f"Error getting data for {city}: {e}")
                        results[city] = {
                            "success": False,
                            "message": f"Error retrieving data for {city}",
                            "error": str(e),
                        }
                return {"success": True, "data": results, "cities_count": len(cities)}

            elif function_name == "get_airqo_history":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                start_time_str = args.get("start_time")
                end_time_str = args.get("end_time")
                start_time = (
                    datetime.fromisoformat(start_time_str)
                    if isinstance(start_time_str, str)
                    else None
                )
                end_time = (
                    datetime.fromisoformat(end_time_str)
                    if isinstance(end_time_str, str)
                    else None
                )
                return self.airqo.get_historical_measurements(
                    site_id=args.get("site_id"),
                    device_id=args.get("device_id"),
                    start_time=start_time,
                    end_time=end_time,
                    frequency=args.get("frequency", "hourly"),
                )

            elif function_name == "get_airqo_forecast":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                return self.airqo.get_forecast(
                    site_id=args.get("site_id"),
                    device_id=args.get("device_id"),
                    city=args.get("city"),
                    frequency=args.get("frequency", "daily"),
                )

            elif function_name == "get_airqo_metadata":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                return self.airqo.get_metadata(entity_type=args.get("entity_type", "grids"))

            elif function_name == "get_air_quality_by_location":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                return self.airqo.get_air_quality_by_location(
                    latitude=args.get("latitude"), longitude=args.get("longitude")
                )

            # OpenMeteo tools
            elif function_name == "get_openmeteo_current_air_quality":
                if self.openmeteo is None:
                    return {"success": False, "message": "OpenMeteo service is not enabled."}
                return self.openmeteo.get_current_air_quality(
                    latitude=args.get("latitude"),
                    longitude=args.get("longitude"),
                    timezone=args.get("timezone", "auto"),
                )

            elif function_name == "get_openmeteo_forecast":
                if self.openmeteo is None:
                    return {"success": False, "message": "OpenMeteo service is not enabled."}
                return self.openmeteo.get_hourly_forecast(
                    latitude=args.get("latitude"),
                    longitude=args.get("longitude"),
                    forecast_days=args.get("forecast_days", 5),
                    timezone=args.get("timezone", "auto"),
                )

            elif function_name == "get_openmeteo_historical":
                if self.openmeteo is None:
                    return {"success": False, "message": "OpenMeteo service is not enabled."}
                start_date_str = args.get("start_date")
                end_date_str = args.get("end_date")
                return self.openmeteo.get_historical_data(
                    latitude=args.get("latitude"),
                    longitude=args.get("longitude"),
                    start_date=datetime.strptime(start_date_str, "%Y-%m-%d") if isinstance(start_date_str, str) else None,
                    end_date=datetime.strptime(end_date_str, "%Y-%m-%d") if isinstance(end_date_str, str) else None,
                    timezone=args.get("timezone", "auto"),
                )

            # Carbon Intensity tools
            elif function_name == "get_uk_carbon_intensity_current":
                if self.carbon_intensity is None:
                    return {"success": False, "message": "Carbon Intensity service is not enabled."}
                return self.carbon_intensity.get_current_intensity()

            elif function_name == "get_uk_carbon_intensity_today":
                if self.carbon_intensity is None:
                    return {"success": False, "message": "Carbon Intensity service is not enabled."}
                return self.carbon_intensity.get_intensity_today()

            elif function_name == "get_uk_carbon_intensity_regional":
                if self.carbon_intensity is None:
                    return {"success": False, "message": "Carbon Intensity service is not enabled."}
                return self.carbon_intensity.get_regional_intensity(args.get("region"))

            elif function_name == "get_uk_generation_mix":
                if self.carbon_intensity is None:
                    return {"success": False, "message": "Carbon Intensity service is not enabled."}
                return self.carbon_intensity.get_generation_mix()

            elif function_name == "get_uk_carbon_intensity_factors":
                if self.carbon_intensity is None:
                    return {"success": False, "message": "Carbon Intensity service is not enabled."}
                return self.carbon_intensity.get_intensity_factors()

            # DEFRA tools
            elif function_name == "get_defra_site_data":
                if self.defra is None:
                    return {"success": False, "message": "DEFRA service is not enabled."}
                return self.defra.get_site_data(args.get("site_code"))

            elif function_name == "get_defra_sites":
                if self.defra is None:
                    return {"success": False, "message": "DEFRA service is not enabled."}
                return self.defra.get_sites()

            elif function_name == "get_defra_species_codes":
                if self.defra is None:
                    return {"success": False, "message": "DEFRA service is not enabled."}
                return self.defra.get_species_codes()

            # UBA tools
            elif function_name == "get_uba_measures":
                if self.uba is None:
                    return {"success": False, "message": "UBA service is not enabled."}
                return self.uba.get_measures(
                    component=args.get("component"), scope=args.get("scope", "1h")
                )

            # Weather tools
            elif function_name == "get_city_weather":
                return self.weather.get_current_weather(args.get("city"))

            elif function_name == "get_weather_forecast":
                return self.weather.get_weather_forecast(
                    args.get("city"), args.get("days", 7)
                )

            # Search and scraping tools
            elif function_name == "search_web":
                return self.search.search(args.get("query"))

            elif function_name == "scrape_website":
                return self.scraper.scrape(args.get("url"))

            # Document tools
            elif function_name == "scan_document":
                file_path = args.get("file_path")
                if not file_path:
                    return {"error": "file_path parameter is required"}
                return self.document_scanner.scan_file(file_path)

            else:
                return {
                    "error": f"Unknown function {function_name}",
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches.",
                }

        except Exception as e:
            logger.error(f"Tool execution failed for {function_name}: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "function_name": function_name,
                "guidance": "This data source is currently unavailable or the requested location was not found. Please inform the user and suggest they try a different location or data source.",
            }

    async def execute_async(self, function_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool asynchronously.

        For now, this wraps the synchronous execution. Can be extended for
        truly async implementations in the future.

        Args:
            function_name: Name of the tool/function to execute
            args: Arguments for the function

        Returns:
            Result dictionary from the tool execution
        """
        import asyncio

        return await asyncio.to_thread(self.execute, function_name, args)
