"""
Tool execution module for AI agent.

Handles execution of various data source and utility tools with intelligent fallbacks and retry logic.
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools for the AI agent with intelligent fallbacks and error handling."""

    def __init__(
        self,
        waqi_service,
        airqo_service,
        openmeteo_service,
        carbon_intensity_service,
        defra_service,
        uba_service,
        nsw_service,
        weather_service,
        search_service,
        scraper,
        document_scanner,
        geocoding_service,
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
            nsw_service: NSW air quality service
            weather_service: Weather service
            search_service: Web search service
            scraper: Web scraper
            document_scanner: Document scanner
            geocoding_service: Geocoding service
        """
        self.waqi = waqi_service
        self.airqo = airqo_service
        self.openmeteo = openmeteo_service
        self.carbon_intensity = carbon_intensity_service
        self.defra = defra_service
        self.uba = uba_service
        self.nsw = nsw_service
        self.weather = weather_service
        self.search = search_service
        self.scraper = scraper
        self.document_scanner = document_scanner
        self.geocoding = geocoding_service
        self.client_ip = None  # Will be set by agent service
        self.client_location = None  # Will be set by agent service (GPS data)
        
        # Circuit breaker for failing services
        self.service_failures = {}  # Track failures per service
        self.circuit_breaker_threshold = 5  # Failures before circuit opens
        self.circuit_breaker_timeout = 300  # 5 minutes before retry

    def _is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service."""
        if service_name not in self.service_failures:
            return False
        
        failure_data = self.service_failures[service_name]
        if failure_data['count'] >= self.circuit_breaker_threshold:
            # Check if timeout has passed
            if time.time() - failure_data['last_failure'] < self.circuit_breaker_timeout:
                logger.warning(f"Circuit breaker OPEN for {service_name}")
                return True
            else:
                # Reset circuit breaker
                self.service_failures[service_name] = {'count': 0, 'last_failure': 0}
                logger.info(f"Circuit breaker RESET for {service_name}")
                return False
        return False

    def _record_failure(self, service_name: str):
        """Record a service failure."""
        if service_name not in self.service_failures:
            self.service_failures[service_name] = {'count': 0, 'last_failure': 0}
        
        self.service_failures[service_name]['count'] += 1
        self.service_failures[service_name]['last_failure'] = time.time()
        logger.warning(f"Service failure recorded for {service_name}: {self.service_failures[service_name]['count']} failures")

    def _record_success(self, service_name: str):
        """Record a successful service call."""
        if service_name in self.service_failures:
            # Reset failure count on success
            self.service_failures[service_name] = {'count': 0, 'last_failure': 0}

    def _get_city_air_quality_with_fallback(self, city: str) -> dict[str, Any]:
        """
        Get city air quality with comprehensive fallback strategy.
        
        Tries ALL available data sources in intelligent order:
        1. WAQI (global coverage, 13k+ stations)
        2. AirQo (if African city)
        3. Geocode + OpenMeteo (works anywhere with coordinates)
        4. DEFRA (UK cities)
        5. UBA (German cities) 
        6. NSW (Australian cities)
        7. Carbon Intensity (UK only)
        8. Web search (last resort)
        
        Args:
            city: City name
            
        Returns:
            Result dictionary with success flag and data/message
        """
        tried_services = []
        
        # 1. Try WAQI first (global coverage)
        if self.waqi and not self._is_circuit_open('waqi'):
            try:
                logger.info(f"Trying WAQI for {city}")
                tried_services.append('WAQI')
                result = self.waqi.get_city_feed(city)
                if result.get("success"):
                    self._record_success('waqi')
                    result["data_source"] = "WAQI"
                    return result
                logger.info(f"WAQI returned no data for {city}")
                self._record_failure('waqi')
            except Exception as e:
                logger.error(f"WAQI error for {city}: {e}")
                self._record_failure('waqi')
        
        # 2. Try AirQo (good for African cities, but also try globally)
        if self.airqo and not self._is_circuit_open('airqo'):
            try:
                logger.info(f"Trying AirQo for {city}")
                tried_services.append('AirQo')
                result = self.airqo.get_recent_measurements(city=city)
                if result.get("success"):
                    self._record_success('airqo')
                    result["data_source"] = "AirQo"
                    return result
                logger.info(f"AirQo returned no data for {city}")
                self._record_failure('airqo')
            except Exception as e:
                logger.error(f"AirQo error for {city}: {e}")
                self._record_failure('airqo')
        
        # 3. Try Geocode + OpenMeteo (works anywhere with coordinates)
        if self.geocoding and self.openmeteo and not self._is_circuit_open('openmeteo'):
            try:
                logger.info(f"Trying Geocoding + OpenMeteo for {city}")
                tried_services.append('OpenMeteo')
                geocode_result = self.geocoding.geocode_address(city, limit=1)
                if geocode_result.get("success") and geocode_result.get("results"):
                    location = geocode_result["results"][0]
                    lat = location.get("latitude")
                    lon = location.get("longitude")
                    if lat and lon:
                        aq_result = self.openmeteo.get_current_air_quality(lat, lon)
                        if aq_result.get("success"):
                            self._record_success('openmeteo')
                            # Enhance result to indicate fallback was used
                            aq_result["data_source"] = "OpenMeteo (via geocoding)"
                            aq_result["location_name"] = city
                            aq_result["note"] = f"Data retrieved using coordinates for {city}"
                            return aq_result
                logger.info(f"Geocoding + OpenMeteo failed for {city}")
                self._record_failure('openmeteo')
            except Exception as e:
                logger.error(f"Geocoding + OpenMeteo error for {city}: {e}")
                self._record_failure('openmeteo')
        
        # 4. Try DEFRA (UK cities)
        if self.defra and not self._is_circuit_open('defra'):
            try:
                logger.info(f"Trying DEFRA for {city}")
                tried_services.append('DEFRA')
                result = self.defra.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success('defra')
                    result["data_source"] = "DEFRA (UK)"
                    return result
                logger.info(f"DEFRA returned no data for {city}")
                self._record_failure('defra')
            except Exception as e:
                logger.error(f"DEFRA error for {city}: {e}")
                self._record_failure('defra')
        
        # 5. Try UBA (German cities)
        if self.uba and not self._is_circuit_open('uba'):
            try:
                logger.info(f"Trying UBA for {city}")
                tried_services.append('UBA')
                result = self.uba.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success('uba')
                    result["data_source"] = "UBA (Germany)"
                    return result
                logger.info(f"UBA returned no data for {city}")
                self._record_failure('uba')
            except Exception as e:
                logger.error(f"UBA error for {city}: {e}")
                self._record_failure('uba')
        
        # 6. Try NSW (Australian cities)
        if self.nsw and not self._is_circuit_open('nsw'):
            try:
                logger.info(f"Trying NSW for {city}")
                tried_services.append('NSW')
                result = self.nsw.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success('nsw')
                    result["data_source"] = "NSW (Australia)"
                    return result
                logger.info(f"NSW returned no data for {city}")
                self._record_failure('nsw')
            except Exception as e:
                logger.error(f"NSW error for {city}: {e}")
                self._record_failure('nsw')
        
        # 7. Try Carbon Intensity (UK only, but worth a try)
        if self.carbon_intensity and not self._is_circuit_open('carbon_intensity'):
            try:
                logger.info(f"Trying Carbon Intensity for {city}")
                tried_services.append('Carbon Intensity')
                # This is UK-specific, so only try if city might be in UK
                uk_cities = ['london', 'manchester', 'birmingham', 'leeds', 'glasgow', 'sheffield', 'bradford', 'liverpool', 'edinburgh', 'leicester']
                if any(uk_city in city.lower() for uk_city in uk_cities):
                    result = self.carbon_intensity.get_current_intensity()
                    if result.get("success"):
                        self._record_success('carbon_intensity')
                        result["data_source"] = "Carbon Intensity (UK)"
                        result["note"] = "UK carbon intensity data (not specific air quality)"
                        return result
                logger.info(f"Carbon Intensity not applicable for {city}")
                self._record_failure('carbon_intensity')
            except Exception as e:
                logger.error(f"Carbon Intensity error for {city}: {e}")
                self._record_failure('carbon_intensity')
        
        # Last resort: web search with comprehensive query
        logger.info(f"All services failed for {city}. Tried: {', '.join(tried_services)}")
        return {
            "success": False,
            "message": f"Unable to retrieve air quality data for {city} from any available monitoring networks. Tried {len(tried_services)} different services: {', '.join(tried_services)}.",
            "tried_services": tried_services,
            "suggestion": "search_web",
            "search_query": f"current air quality {city} site:epa.gov OR site:airnow.gov OR site:who.int",
            "fallback_advice": f"No monitoring station data found for {city} from {len(tried_services)} services. Try searching official environmental agency websites or nearby major cities."
        }

    def _get_african_city_with_fallback(self, city: str, site_id: str = None) -> dict[str, Any]:
        """
        Get African city air quality with fallback to WAQI and OpenMeteo.
        
        Args:
            city: City name
            site_id: Optional AirQo site ID
            
        Returns:
            Result dictionary
        """
        # Try AirQo first (primary for Africa)
        if self.airqo and not self._is_circuit_open('airqo'):
            try:
                logger.info(f"Trying AirQo for {city}")
                result = self.airqo.get_recent_measurements(city=city, site_id=site_id)
                if result.get("success"):
                    self._record_success('airqo')
                    return result
                logger.info(f"AirQo returned no data for {city}")
                self._record_failure('airqo')
            except Exception as e:
                logger.error(f"AirQo error for {city}: {e}")
                self._record_failure('airqo')
        
        # Fallback to WAQI
        if self.waqi and not self._is_circuit_open('waqi'):
            try:
                logger.info(f"Trying WAQI fallback for {city}")
                result = self.waqi.get_city_feed(city)
                if result.get("success"):
                    self._record_success('waqi')
                    result["data_source"] = "WAQI (fallback from AirQo)"
                    result["note"] = f"AirQo data unavailable. Using WAQI station data for {city}"
                    return result
                self._record_failure('waqi')
            except Exception as e:
                logger.error(f"WAQI fallback error for {city}: {e}")
                self._record_failure('waqi')
        
        # Fallback to Geocode + OpenMeteo
        if self.geocoding and self.openmeteo and not self._is_circuit_open('openmeteo'):
            try:
                logger.info(f"Trying Geocoding + OpenMeteo fallback for {city}")
                geocode_result = self.geocoding.geocode_address(city, limit=1)
                if geocode_result.get("success") and geocode_result.get("results"):
                    location = geocode_result["results"][0]
                    lat = location.get("latitude")
                    lon = location.get("longitude")
                    if lat and lon:
                        aq_result = self.openmeteo.get_current_air_quality(lat, lon)
                        if aq_result.get("success"):
                            self._record_success('openmeteo')
                            aq_result["data_source"] = "OpenMeteo (fallback)"
                            aq_result["location_name"] = city
                            aq_result["note"] = f"Local monitoring data unavailable. Using modeled data for {city}"
                            return aq_result
                self._record_failure('openmeteo')
            except Exception as e:
                logger.error(f"Geocoding + OpenMeteo fallback error for {city}: {e}")
                self._record_failure('openmeteo')
        
        return {
            "success": False,
            "message": f"Unable to retrieve air quality data for {city}. This location may not have active monitoring coverage.",
            "suggestion": "search_web",
            "search_query": f"air quality {city} Africa",
            "fallback_advice": f"Consider checking local environmental agencies or nearby cities with monitoring stations."
        }

    def execute(self, function_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool synchronously with intelligent fallback handling.

        Args:
            function_name: Name of the tool/function to execute
            args: Arguments for the function

        Returns:
            Result dictionary from the tool execution
        """
        try:
            # WAQI tools - with intelligent fallback
            if function_name == "get_city_air_quality":
                if self.waqi is None and self.openmeteo is None:
                    return {"success": False, "message": "Air quality services are not enabled."}
                return self._get_city_air_quality_with_fallback(args.get("city"))

            elif function_name == "search_waqi_stations":
                if self.waqi is None:
                    return {"success": False, "message": "WAQI service is not enabled."}
                if self._is_circuit_open('waqi'):
                    return {"success": False, "message": "WAQI service temporarily unavailable. Try again later."}
                try:
                    result = self.waqi.search_stations(args.get("keyword"))
                    self._record_success('waqi')
                    return result
                except Exception as e:
                    self._record_failure('waqi')
                    raise

            # AirQo tools - with intelligent fallback
            elif function_name == "get_african_city_air_quality":
                if self.airqo is None and self.waqi is None and self.openmeteo is None:
                    return {"success": False, "message": "Air quality services are not enabled."}
                city = args.get("city")
                site_id = args.get("site_id")
                return self._get_african_city_with_fallback(city, site_id)

            elif function_name == "get_multiple_african_cities_air_quality":
                if self.airqo is None and self.waqi is None and self.openmeteo is None:
                    return {"success": False, "message": "Air quality services are not enabled."}
                cities = args.get("cities", [])
                results = {}
                for city in cities:
                    results[city] = self._get_african_city_with_fallback(city)
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

            elif function_name == "search_airqo_sites":
                if self.airqo is None:
                    return {"success": False, "message": "AirQo service is not enabled."}
                return self.airqo.search_sites_by_location(
                    location=args.get("location"),
                    limit=args.get("limit", 50)
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

            # NSW tools
            elif function_name == "get_nsw_air_quality":
                if self.nsw is None:
                    return {"success": False, "message": "NSW service is not enabled."}
                return self.nsw.get_current_air_quality(args.get("location"))

            elif function_name == "get_nsw_sites":
                if self.nsw is None:
                    return {"success": False, "message": "NSW service is not enabled."}
                sites = self.nsw.get_site_details()
                return {"success": True, "data": sites, "count": len(sites)}

            elif function_name == "get_nsw_pollutant_data":
                if self.nsw is None:
                    return {"success": False, "message": "NSW service is not enabled."}
                return self.nsw.get_pollutant_data(
                    args.get("pollutant"), args.get("hours", 24)
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

            # Geocoding tools
            elif function_name == "geocode_address":
                return self.geocoding.geocode_address(args.get("address"), args.get("limit", 1))

            elif function_name == "reverse_geocode":
                return self.geocoding.reverse_geocode(args.get("latitude"), args.get("longitude"))

            elif function_name == "get_location_from_ip":
                # Check if we have GPS coordinates first (preferred over IP)
                if self.client_location and self.client_location.get("source") == "gps":
                    # Use GPS coordinates directly
                    latitude = self.client_location["latitude"]
                    longitude = self.client_location["longitude"]
                    
                    # Get location name using reverse geocoding
                    reverse_result = self.geocoding.reverse_geocode(latitude, longitude)
                    if reverse_result.get("success"):
                        location_name = reverse_result.get("display_name", "Unknown location")
                        city = reverse_result.get("address", {}).get("city", "Unknown city")
                    else:
                        location_name = f"{latitude:.4f}, {longitude:.4f}"
                        city = "Unknown city"
                    
                    # Automatically call air quality API with GPS coordinates
                    air_quality_result = self.openmeteo.get_current_air_quality(
                        latitude=latitude,
                        longitude=longitude,
                        timezone="auto"
                    )
                    
                    combined_result = {
                        "success": True,
                        "message": "Location determined from GPS coordinates (precise)",
                        "location": {
                            "latitude": latitude,
                            "longitude": longitude,
                            "city": city,
                            "display_name": location_name,
                            "source": "gps",
                            "accuracy": "precise"
                        },
                        "air_quality": air_quality_result
                    }
                    return combined_result
                else:
                    # Fall back to IP geolocation
                    location_result = self.geocoding.get_location_from_ip(self.client_ip)
                    # If location retrieval succeeds, automatically get air quality for those coordinates
                    if location_result.get("success") and location_result.get("latitude") and location_result.get("longitude"):
                        logger.info(f"Location retrieved from IP: {location_result.get('latitude')}, {location_result.get('longitude')}")
                        # Automatically call air quality API with the coordinates
                        air_quality_result = self.openmeteo.get_current_air_quality(
                            latitude=location_result["latitude"],
                            longitude=location_result["longitude"],
                            timezone="auto"
                        )
                        # Combine the results
                        combined_result = {
                            "success": True,
                            "message": "Location and air quality data retrieved from IP address (approximate)",
                            "location": {
                                "latitude": location_result["latitude"],
                                "longitude": location_result["longitude"],
                                "country": location_result.get("country_name"),
                                "city": location_result.get("city"),
                                "region": location_result.get("region"),
                                "source": "ip",
                                "accuracy": "approximate"
                            },
                            "air_quality": air_quality_result
                        }
                        return combined_result
                    else:
                        # Location retrieval failed, return the error
                        return location_result

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
