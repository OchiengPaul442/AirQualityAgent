"""
Tool execution module for AI agent.

Handles execution of various data source and utility tools with intelligent fallbacks and retry logic.
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from shared.utils.provider_errors import ProviderServiceError, aeris_unavailable_message


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
        self.documents_provided = (
            False  # Will be set by agent service when documents are in context
        )
        self.uploaded_documents = (
            {}
        )  # Store uploaded documents temporarily for fallback access: {filename: content_dict}
        self.session_id = None  # Will be set by agent service for chart organization

        # Lazy-load visualization service
        self._visualization_service = None

        # Circuit breaker for failing services
        self.service_failures = {}  # Track failures per service
        self.circuit_breaker_threshold = 5  # Failures before circuit opens
        self.circuit_breaker_timeout = 300  # 5 minutes before retry

    @property
    def visualization_service(self):
        """Lazy-load visualization service."""
        if self._visualization_service is None:
            from infrastructure.api.visualization import get_visualization_service

            self._visualization_service = get_visualization_service()
        return self._visualization_service

    def _is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service."""
        if service_name not in self.service_failures:
            return False

        failure_data = self.service_failures[service_name]
        if failure_data["count"] >= self.circuit_breaker_threshold:
            # Check if timeout has passed
            if time.time() - failure_data["last_failure"] < self.circuit_breaker_timeout:
                logger.warning(f"Circuit breaker OPEN for {service_name}")
                return True
            else:
                # Reset circuit breaker
                self.service_failures[service_name] = {"count": 0, "last_failure": 0}
                logger.info(f"Circuit breaker RESET for {service_name}")
                return False
        return False

    def _record_failure(self, service_name: str):
        """Record a service failure."""
        if service_name not in self.service_failures:
            self.service_failures[service_name] = {"count": 0, "last_failure": 0}

        self.service_failures[service_name]["count"] += 1
        self.service_failures[service_name]["last_failure"] = time.time()
        logger.warning(
            f"Service failure recorded for {service_name}: {self.service_failures[service_name]['count']} failures"
        )

    def _record_success(self, service_name: str):
        """Record a successful service call."""
        if service_name in self.service_failures:
            # Reset failure count on success
            self.service_failures[service_name] = {"count": 0, "last_failure": 0}

    def _get_city_air_quality_with_fallback(self, city: str) -> dict[str, Any]:
        """
        Get city air quality with comprehensive fallback strategy.

        Tries ALL available data sources in intelligent order:
        1. AirQo FIRST (if African city - better coverage for Africa)
        2. WAQI (global coverage, 13k+ stations)
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

        # Detect if this is likely an African city
        african_indicators = [
            "kampala", "nairobi", "lagos", "accra", "kigali", "dar es salaam", "addis ababa",
            "cairo", "johannesburg", "cape town", "kinshasa", "luanda", "abidjan", "dakar",
            "casablanca", "algiers", "tunis", "khartoum", "mogadishu", "harare", "lusaka",
            "maputo", "windhoek", "gaborone", "lilongwe", "blantyre", "bujumbura", "bamako",
            "ouagadougou", "niamey", "ndjamena", "bangui", "libreville", "brazzaville",
            "yaoundé", "douala", "malabo", "monrovia", "freetown", "conakry", "bissau",
            "praia", "banjul", "nouakchott", "kampala", "jinja", "mbarara", "gulu"
        ]
        is_african_city = any(indicator in city.lower() for indicator in african_indicators)

        # 1. Try AirQo FIRST if African city (better African coverage)
        if is_african_city and self.airqo and not self._is_circuit_open("airqo"):
            try:
                logger.info(f"🌍 Trying AirQo FIRST for African city: {city}")
                tried_services.append("AirQo")
                result = self.airqo.get_recent_measurements(city=city)
                if result.get("success"):
                    self._record_success("airqo")
                    result["data_source"] = "AirQo"
                    return result
                # Log internally but don't expose error to user
                logger.info(f"AirQo returned no data for {city}")
                self._record_failure("airqo")
            except Exception as e:
                # Log exception internally but don't expose to user
                logger.error(f"AirQo error for {city}: {str(e)[:200]}")
                self._record_failure("airqo")

        # 2. Try WAQI (global coverage)
        if self.waqi and not self._is_circuit_open("waqi"):
            try:
                logger.info(f"Trying WAQI for {city}")
                tried_services.append("WAQI")
                result = self.waqi.get_city_feed(city)
                if result.get("success"):
                    self._record_success("waqi")
                    result["data_source"] = "WAQI"
                    return result
                # Log internally but don't expose error to user
                logger.info(f"WAQI returned no data for {city}")
                self._record_failure("waqi")
            except Exception as e:
                # Log exception internally but don't expose to user
                logger.error(f"WAQI error for {city}: {str(e)[:200]}")
                self._record_failure("waqi")

        # 3. Try AirQo if not tried yet (for non-African cities, try as fallback)
        if not is_african_city and self.airqo and not self._is_circuit_open("airqo"):
            try:
                logger.info(f"Trying AirQo as fallback for {city}")
                tried_services.append("AirQo")
                result = self.airqo.get_recent_measurements(city=city)
                if result.get("success"):
                    self._record_success("airqo")
                    result["data_source"] = "AirQo"
                    return result
                logger.info(f"AirQo returned no data for {city}")
                self._record_failure("airqo")
            except Exception as e:
                logger.error(f"AirQo error for {city}: {e}")
                self._record_failure("airqo")

        # 4. Try Geocode + OpenMeteo (works anywhere with coordinates)
        if self.geocoding and self.openmeteo and not self._is_circuit_open("openmeteo"):
            try:
                logger.info(f"Trying Geocoding + OpenMeteo for {city}")
                tried_services.append("OpenMeteo")
                geocode_result = self.geocoding.geocode_address(city, limit=1)
                if geocode_result.get("success") and geocode_result.get("results"):
                    location = geocode_result["results"][0]
                    lat = location.get("latitude")
                    lon = location.get("longitude")
                    if lat and lon:
                        aq_result = self.openmeteo.get_current_air_quality(lat, lon)
                        if aq_result.get("success"):
                            self._record_success("openmeteo")
                            # Enhance result to indicate fallback was used
                            aq_result["data_source"] = "meteorological services"
                            aq_result["location_name"] = city
                            aq_result["note"] = f"Data retrieved using coordinates for {city}"
                            return aq_result
                logger.info(f"Geocoding + OpenMeteo failed for {city}")
                self._record_failure("openmeteo")
            except Exception as e:
                logger.error(f"Geocoding + OpenMeteo error for {city}: {e}")
                self._record_failure("openmeteo")

        # 5. Try DEFRA (UK cities)
        if self.defra and not self._is_circuit_open("defra"):
            try:
                logger.info(f"Trying DEFRA for {city}")
                tried_services.append("DEFRA")
                result = self.defra.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success("defra")
                    result["data_source"] = "DEFRA UK environmental monitoring"
                    return result
                logger.info(f"DEFRA returned no data for {city}")
                self._record_failure("defra")
            except Exception as e:
                logger.error(f"DEFRA error for {city}: {e}")
                self._record_failure("defra")

        # 6. Try UBA (German cities)
        if self.uba and not self._is_circuit_open("uba"):
            try:
                logger.info(f"Trying UBA for {city}")
                tried_services.append("UBA")
                result = self.uba.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success("uba")
                    result["data_source"] = "UBA Germany environmental monitoring"
                    return result
                logger.info(f"UBA returned no data for {city}")
                self._record_failure("uba")
            except Exception as e:
                logger.error(f"UBA error for {city}: {e}")
                self._record_failure("uba")

        # 7. Try NSW (Australian cities)
        if self.nsw and not self._is_circuit_open("nsw"):
            try:
                logger.info(f"Trying NSW for {city}")
                tried_services.append("NSW")
                result = self.nsw.get_city_air_quality(city)
                if result.get("success"):
                    self._record_success("nsw")
                    result["data_source"] = "NSW Australia environmental monitoring"
                    return result
                logger.info(f"NSW returned no data for {city}")
                self._record_failure("nsw")
            except Exception as e:
                logger.error(f"NSW error for {city}: {e}")
                self._record_failure("nsw")

        # 8. Try Carbon Intensity (UK only, but worth a try)
        if self.carbon_intensity and not self._is_circuit_open("carbon_intensity"):
            try:
                logger.info(f"Trying Carbon Intensity for {city}")
                tried_services.append("Carbon Intensity")
                # This is UK-specific, so only try if city might be in UK
                uk_cities = [
                    "london",
                    "manchester",
                    "birmingham",
                    "leeds",
                    "glasgow",
                    "sheffield",
                    "bradford",
                    "liverpool",
                    "edinburgh",
                    "leicester",
                ]
                if any(uk_city in city.lower() for uk_city in uk_cities):
                    result = self.carbon_intensity.get_current_intensity()
                    if result.get("success"):
                        self._record_success("carbon_intensity")
                        result["data_source"] = "UK Carbon Intensity monitoring"
                        result["note"] = "UK carbon intensity data (not specific air quality)"
                        return result
                logger.info(f"Carbon Intensity not applicable for {city}")
                self._record_failure("carbon_intensity")
            except Exception as e:
                logger.error(f"Carbon Intensity error for {city}: {e}")
                self._record_failure("carbon_intensity")

        # Last resort: web search with comprehensive query
        logger.info(f"All services failed for {city}. Tried: {', '.join(tried_services)}")
        return {
            "success": False,
            "message": f"Unable to retrieve air quality data for {city} from any available monitoring networks. Tried {len(tried_services)} different services: {', '.join(tried_services)}.",
            "tried_services": tried_services,
            "suggestion": "search_web",
            "search_query": f"current air quality {city} site:epa.gov OR site:airnow.gov OR site:who.int",
            "fallback_advice": f"No monitoring station data found for {city} from {len(tried_services)} services. Try searching official environmental agency websites or nearby major cities.",
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
        if self.airqo and not self._is_circuit_open("airqo"):
            try:
                logger.info(f"Trying AirQo for {city}")
                result = self.airqo.get_recent_measurements(city=city, site_id=site_id)
                if result.get("success"):
                    self._record_success("airqo")
                    return result
                logger.info(f"AirQo returned no data for {city}")
                self._record_failure("airqo")
            except Exception as e:
                logger.error(f"AirQo error for {city}: {e}")
                self._record_failure("airqo")

        # Fallback to WAQI
        if self.waqi and not self._is_circuit_open("waqi"):
            try:
                logger.info(f"Trying WAQI fallback for {city}")
                result = self.waqi.get_city_feed(city)
                if result.get("success"):
                    self._record_success("waqi")
                    result["data_source"] = "World Air Quality Index monitoring network"
                    result["note"] = f"AirQo data unavailable. Using WAQI station data for {city}"
                    return result
                self._record_failure("waqi")
            except Exception as e:
                logger.error(f"WAQI fallback error for {city}: {e}")
                self._record_failure("waqi")

        # Fallback to Geocode + OpenMeteo
        if self.geocoding and self.openmeteo and not self._is_circuit_open("openmeteo"):
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
                            self._record_success("openmeteo")
                            aq_result["data_source"] = "meteorological services"
                            aq_result["location_name"] = city
                            aq_result["note"] = (
                                f"Local monitoring data unavailable. Using modeled data for {city}"
                            )
                            return aq_result
                self._record_failure("openmeteo")
            except Exception as e:
                logger.error(f"Geocoding + OpenMeteo fallback error for {city}: {e}")
                self._record_failure("openmeteo")

        return {
            "success": False,
            "message": f"Unable to retrieve air quality data for {city}. This location may not have active monitoring coverage.",
            "suggestion": "search_web",
            "search_query": f"air quality {city} Africa",
            "fallback_advice": "Consider checking local environmental agencies or nearby cities with monitoring stations.",
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
                    return {"success": False, "message": aeris_unavailable_message()}
                if self._is_circuit_open("waqi"):
                    return {
                        "success": False,
                        "message": aeris_unavailable_message(),
                    }
                try:
                    result = self.waqi.search_stations(args.get("keyword"))
                    self._record_success("waqi")
                    return result
                except ProviderServiceError as e:
                    self._record_failure("waqi")
                    return {"success": False, "message": e.public_message}
                except Exception as e:
                    self._record_failure("waqi")
                    logger.error(f"WAQI search stations error: {str(e)[:200]}")
                    return {"success": False, "message": aeris_unavailable_message()}

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
                    return {"success": False, "message": aeris_unavailable_message()}
                try:
                    start_time_str = args.get("start_time")
                    end_time_str = args.get("end_time")
                    start_time = (
                        datetime.fromisoformat(start_time_str)
                        if isinstance(start_time_str, str)
                        else None
                    )
                    end_time = (
                        datetime.fromisoformat(end_time_str) if isinstance(end_time_str, str) else None
                    )
                    return self.airqo.get_historical_measurements(
                        site_id=args.get("site_id"),
                        device_id=args.get("device_id"),
                        start_time=start_time,
                        end_time=end_time,
                        frequency=args.get("frequency", "hourly"),
                    )
                except ProviderServiceError as e:
                    return {"success": False, "message": e.public_message}
                except Exception as e:
                    logger.error(f"AirQo history error: {str(e)[:200]}")
                    return {"success": False, "message": aeris_unavailable_message()}

            elif function_name == "get_airqo_metadata":
                if self.airqo is None:
                    return {"success": False, "message": aeris_unavailable_message()}
                try:
                    return self.airqo.get_metadata(entity_type=args.get("entity_type", "grids"))
                except ProviderServiceError as e:
                    return {"success": False, "message": e.public_message}
                except Exception as e:
                    logger.error(f"AirQo metadata error: {str(e)[:200]}")
                    return {"success": False, "message": aeris_unavailable_message()}

            elif function_name == "get_air_quality_forecast":
                # Intelligent routing: Use AirQo for African cities, WAQI for others
                city = args.get("city", "").lower()
                days = args.get("days", 3)

                # List of African countries/cities that should use AirQo
                african_indicators = [
                    "africa",
                    "kenya",
                    "uganda",
                    "tanzania",
                    "rwanda",
                    "ghana",
                    "nigeria",
                    "ethiopia",
                    "south africa",
                    "egypt",
                    "morocco",
                    "algeria",
                    "tunisia",
                    "nairobi",
                    "kampala",
                    "dar es salaam",
                    "kigali",
                    "accra",
                    "lagos",
                    "addis ababa",
                    "cape town",
                    "cairo",
                    "casablanca",
                    "algiers",
                    "tunis",
                ]

                is_african = any(indicator in city for indicator in african_indicators)

                if is_african and self.airqo is not None:
                    # Use AirQo for African cities
                    try:
                        result = self.airqo.get_forecast(city=city, frequency="daily")
                        # Add explicit source attribution
                        if isinstance(result, dict) and result.get("success"):
                            result["data_source"] = "AirQo monitoring network"
                            result["source_type"] = "airqo"
                        return result
                    except Exception as e:
                        logger.warning(
                            f"AirQo forecast failed for {city}, falling back to WAQI: {e}"
                        )
                        # Fall back to WAQI if AirQo fails

                # Use WAQI for non-African cities or as fallback
                if self.waqi is not None:
                    try:
                        result = self.waqi.get_station_forecast(city)
                        # Add explicit source attribution
                        if isinstance(result, dict) and result.get("success"):
                            result["data_source"] = "World Air Quality Index (WAQI) network"
                            result["source_type"] = "waqi"
                        return result
                    except Exception as e:
                        logger.error(f"WAQI forecast failed for {city}: {e}")
                        return {
                            "success": False,
                            "message": f"Unable to get forecast for {city}. No monitoring stations found or service unavailable.",
                        }
                else:
                    return {
                        "success": False,
                        "message": "Air quality forecast services are not available.",
                    }

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
                    location=args.get("location"), limit=args.get("limit", 50)
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
                    start_date=(
                        datetime.strptime(start_date_str, "%Y-%m-%d")
                        if isinstance(start_date_str, str)
                        else None
                    ),
                    end_date=(
                        datetime.strptime(end_date_str, "%Y-%m-%d")
                        if isinstance(end_date_str, str)
                        else None
                    ),
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
                return self.nsw.get_pollutant_data(args.get("pollutant"), args.get("hours", 24))

            # Weather tools
            elif function_name == "get_city_weather":
                return self.weather.get_current_weather(args.get("city"))

            elif function_name == "get_weather_forecast":
                return self.weather.get_weather_forecast(args.get("city"), args.get("days", 7))

            # Search and scraping tools
            elif function_name == "search_web":
                query = args.get("query")
                if not query:
                    return {"success": False, "error": "No query provided"}
                try:
                    results = self.search.search(query)
                    return {
                        "success": True,
                        "results": results,
                        "count": len(results),
                        "query": query
                    }
                except Exception as e:
                    logger.error(f"Web search error: {e}", exc_info=True)
                    return {"success": False, "error": aeris_unavailable_message()}

            elif function_name == "scrape_website":
                url = args.get("url")
                if not url:
                    return {"success": False, "error": "No URL provided"}
                try:
                    result = self.scraper.scrape(url)
                    # If scraper returns error dict, wrap it properly
                    if "error" in result:
                        return {"success": False, "error": result["error"], "url": url}
                    return {"success": True, **result}
                except Exception as e:
                    logger.error(f"Web scraping error: {e}", exc_info=True)
                    return {"success": False, "error": aeris_unavailable_message(), "url": url}

            # Document tools
            elif function_name == "scan_document":
                file_path = args.get("file_path")
                if not file_path:
                    return {"error": "file_path parameter is required", "success": False}

                # FALLBACK: Check if this is an uploaded document we have in memory
                # Extract filename from path (user might pass just filename or full path)
                import os

                filename = os.path.basename(file_path)

                # Check uploaded documents cache first (FALLBACK for when AI can't see context)
                if filename in self.uploaded_documents:
                    logger.info(f"\u2713 scan_document: Found uploaded document in cache: {filename}")
                    doc_data = self.uploaded_documents[filename]
                    return {
                        "success": True,
                        "filename": filename,
                        "file_type": doc_data.get("file_type", "unknown"),
                        "content": doc_data.get("content", ""),
                        "metadata": doc_data.get("metadata", {}),
                        "truncated": doc_data.get("truncated", False),
                        "full_length": doc_data.get("full_length", 0),
                        "source": "uploaded_cache",
                        "note": "Document was uploaded with your message and retrieved from memory"
                    }

                # Check if file path exists (for disk-based files)
                if not os.path.exists(file_path):
                    # Maybe it's in uploaded docs but with different casing?
                    for uploaded_filename in self.uploaded_documents.keys():
                        if uploaded_filename.lower() == filename.lower():
                            logger.info(f"\u2713 scan_document: Found document with case mismatch: {uploaded_filename}")
                            doc_data = self.uploaded_documents[uploaded_filename]
                            return {
                                "success": True,
                                "filename": uploaded_filename,
                                "file_type": doc_data.get("file_type", "unknown"),
                                "content": doc_data.get("content", ""),
                                "metadata": doc_data.get("metadata", {}),
                                "truncated": doc_data.get("truncated", False),
                                "full_length": doc_data.get("full_length", 0),
                                "source": "uploaded_cache"
                            }
                    
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}. If you uploaded a document, it should already be in the conversation context.",
                        "available_documents": list(self.uploaded_documents.keys())
                    }

                # Otherwise try to scan from disk
                logger.info(f"\u2139 scan_document: Attempting to scan from disk: {file_path}")
                result = self.document_scanner.scan_file(file_path)
                if not result.get("success"):
                    result["available_documents"] = list(self.uploaded_documents.keys())
                return result

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
                        latitude=latitude, longitude=longitude, timezone="auto"
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
                            "accuracy": "precise",
                        },
                        "air_quality": air_quality_result,
                    }
                    return combined_result
                else:
                    # Fall back to IP geolocation
                    location_result = self.geocoding.get_location_from_ip(self.client_ip)
                    # If location retrieval succeeds, automatically get air quality for those coordinates
                    if (
                        location_result.get("success")
                        and location_result.get("latitude")
                        and location_result.get("longitude")
                    ):
                        logger.info(
                            f"Location retrieved from IP: {location_result.get('latitude')}, {location_result.get('longitude')}"
                        )
                        # Automatically call air quality API with the coordinates
                        air_quality_result = self.openmeteo.get_current_air_quality(
                            latitude=location_result["latitude"],
                            longitude=location_result["longitude"],
                            timezone="auto",
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
                                "accuracy": "approximate",
                            },
                            "air_quality": air_quality_result,
                        }
                        return combined_result
                    else:
                        # Location retrieval failed, return the error
                        return location_result

            elif function_name == "generate_chart":
                """
                Generate a chart/graph from data.

                Expected args:
                    - data: List of dictionaries with data points
                    - chart_type: Type of chart (line, bar, scatter, etc.)
                    - x_column: Column name for x-axis
                    - y_column: Column name(s) for y-axis
                    - title: Chart title
                    - x_label: X-axis label (optional)
                    - y_label: Y-axis label (optional)
                """
                try:
                    logger.info(
                        f"Generating {args.get('chart_type', 'line')} chart: {args.get('title', 'Chart')}"
                    )

                    # Validate required fields
                    if "data" not in args:
                        return {
                            "success": False,
                            "error": "Missing 'data' parameter. Please provide data as a list of dictionaries.",
                        }

                    if not args["data"]:
                        return {
                            "success": False,
                            "error": "Empty data provided. Cannot generate chart without data.",
                        }

                    # Use visualization service to generate chart
                    result = self.visualization_service.generate_chart(
                        data=args["data"],
                        chart_type=args.get("chart_type", "line"),
                        x_column=args.get("x_column"),
                        y_column=args.get("y_column"),
                        title=args.get("title"),
                        x_label=args.get("x_label"),
                        y_label=args.get("y_label"),
                        color_column=args.get("color_column"),
                        output_format=args.get("output_format", "file"),  # Default to file instead of base64
                        interactive=args.get("interactive", False),
                        session_id=getattr(self, "session_id", None),  # Pass session_id for organization
                    )

                    if result.get("success"):
                        logger.info(
                            f"Chart generated successfully: {result.get('chart_type')} with {result.get('data_rows')} rows"
                        )

                    return result

                except Exception as e:
                    logger.error(f"Chart generation error: {e}", exc_info=True)
                    return {
                        "success": False,
                        "error": "Failed to generate chart.",
                        "message": aeris_unavailable_message(),
                    }

            else:
                return {
                    "error": f"Unknown function {function_name}",
                    "guidance": "This tool is not available. Please inform the user and suggest alternative approaches.",
                }

        except Exception as e:
            logger.error(f"Tool execution failed for {function_name}: {e}", exc_info=True)
            return {
                "error": aeris_unavailable_message(),
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

    async def execute_parallel(
        self, tool_calls: list[tuple[str, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """
        Execute multiple tools in parallel using asyncio.gather().

        This implements Anthropic's parallelization pattern for independent tool calls,
        significantly reducing latency when multiple tools are needed simultaneously.

        Pattern: Sectioning - breaking independent subtasks to run in parallel.

        Args:
            tool_calls: List of (function_name, args) tuples to execute

        Returns:
            List of result dictionaries, one per tool call (maintains order)

        Example:
            results = await executor.execute_parallel([
                ("get_african_city_air_quality", {"city": "Kampala"}),
                ("get_city_air_quality", {"city": "London"}),
                ("get_openmeteo_current_air_quality", {"latitude": 0.3, "longitude": 32.5})
            ])
        """
        import asyncio

        if not tool_calls:
            return []

        logger.info(
            f"Executing {len(tool_calls)} tools in parallel: "
            f"{[name for name, _ in tool_calls]}"
        )

        start_time = time.time()

        # Create tasks for all tool calls
        tasks = [
            self.execute_async(function_name, args) for function_name, args in tool_calls
        ]

        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dictionaries
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                function_name = tool_calls[i][0]
                logger.error(f"Parallel execution failed for {function_name}: {result}")
                processed_results.append(
                    {
                        "error": str(result),
                        "error_type": type(result).__name__,
                        "function_name": function_name,
                        "guidance": "This tool failed during parallel execution. Please try again or use an alternative.",
                    }
                )
            else:
                processed_results.append(result)

        elapsed = time.time() - start_time
        logger.info(
            f"Parallel execution completed: {len(tool_calls)} tools in {elapsed:.2f}s "
            f"(vs ~{elapsed * len(tool_calls):.2f}s sequential)"
        )

        return processed_results
