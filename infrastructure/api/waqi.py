"""World Air Quality Index (WAQI) API Service.

Provides access to global air quality data from over 11,000 stations.

Docs:
- https://aqicn.org/api/
- https://aqicn.org/json-api/doc/

Important:
- WAQI returns AQI values (0-500), not raw concentrations.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from infrastructure.cache.cache_service import get_cache
from shared.utils.data_formatter import format_air_quality_data
from shared.utils.provider_errors import ProviderServiceError, provider_unavailable_message

logger = logging.getLogger(__name__)


class WAQIService:
    """Service for interacting with the World Air Quality Index API"""

    BASE_URL = "https://api.waqi.info"

    def __init__(self, api_token: str | None = None):
        """
        Initialize WAQI service

        Args:
            api_key: WAQI API token from https://aqicn.org/data-platform/token/
        """
        from shared.config.settings import get_settings

        settings = get_settings()
        self.api_key = api_token or settings.WAQI_API_KEY
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _sanitize_token(self, data: Any) -> Any:
        """Remove API tokens from response data to prevent leakage"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key == "token":
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, str) and self.api_key and self.api_key in value:
                    # Replace token in URLs and strings
                    sanitized[key] = value.replace(self.api_key, "[REDACTED]")
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_token(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_token(item) for item in data]
        elif isinstance(data, str) and self.api_key and self.api_key in data:
            return data.replace(self.api_key, "[REDACTED]")
        return data

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        Make request to WAQI API

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        # Build request params without mutating caller-owned dict
        request_params: dict[str, Any] = dict(params or {})
        request_params["token"] = self.api_key

        # Check Redis cache
        cached_data = self.cache_service.get_api_response("waqi", endpoint, request_params)
        if cached_data is not None:
            # Ensure cached data is also sanitized
            return self._sanitize_token(cached_data)

        try:
            response = self.session.get(url, params=request_params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                # Don't leak provider's reason to callers.
                raise ProviderServiceError(
                    provider="waqi",
                    public_message=provider_unavailable_message("WAQI"),
                    internal_message=f"WAQI status={data.get('status')} data={data.get('data')}",
                    http_status=response.status_code,
                )

            # Sanitize token from response before caching and returning
            sanitized_data = self._sanitize_token(data)

            # Cache the sanitized result in Redis
            self.cache_service.set_api_response(
                "waqi", endpoint, request_params, sanitized_data, self.cache_ttl
            )
            return sanitized_data

        except ProviderServiceError:
            raise
        except requests.exceptions.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            body = getattr(getattr(e, "response", None), "text", None)
            logger.warning("WAQI request failed", extra={"endpoint": endpoint, "status": status})
            raise ProviderServiceError(
                provider="waqi",
                public_message=provider_unavailable_message("WAQI"),
                internal_message=f"RequestException: {e}; status={status}; body={body}",
                http_status=status,
            ) from e

    def get_city_feed(self, city: str) -> dict[str, Any]:
        """
        Get real-time air quality data for a city

        IMPORTANT: WAQI API returns AQI values, NOT raw concentrations.
        - iaqi.pm25.v is the PM2.5 AQI (0-500 scale), NOT µg/m³
        - iaqi.pm10.v is the PM10 AQI (0-500 scale), NOT µg/m³
        - data.aqi is the overall AQI (maximum of all pollutant AQIs)

        The data formatter will convert these AQI values to estimated concentrations
        using EPA AQI breakpoint conversion formulas.

        Args:
            city: City name (e.g., "london", "beijing", "kampala")

        Returns:
            AQI data with pollutants, time, location info.
            Includes both AQI values and estimated concentrations in µg/m³.
        """
        # City can contain spaces or unicode; keep it safe in the URL path.
        # WAQI API format: /feed/{city}/ with token as query param
        safe_city = quote(city.strip(), safe="")
        data = self._make_request(f"feed/{safe_city}/")
        formatted = format_air_quality_data(data, source="waqi")

        # Add success flag based on WAQI API status
        if data.get("status") == "ok" and "data" in data:
            formatted["success"] = True
            
            # Extract key data and add to top level for easy AI access
            waqi_data = data.get("data", {})
            formatted["overall_aqi"] = waqi_data.get("aqi")
            formatted["city_name"] = waqi_data.get("city", {}).get("name", city)
            formatted["timestamp"] = waqi_data.get("time", {}).get("s")
            formatted["dominant_pollutant"] = waqi_data.get("dominentpol")
            
            # Extract PM2.5 and PM10 AQI values from iaqi and add to root for easy access
            iaqi = waqi_data.get("iaqi", {})
            
            # Initialize pollutants dict for easy access
            formatted["pollutants"] = {}
            
            if "pm25" in iaqi and isinstance(iaqi["pm25"], dict):
                pm25_aqi = iaqi["pm25"].get("v")
                if pm25_aqi is not None:
                    formatted["pm25_aqi"] = pm25_aqi
                    # Convert AQI to estimated concentration
                    from shared.utils.aqi_converter import aqi_to_concentration
                    pm25_conc = aqi_to_concentration(pm25_aqi, "pm25")
                    if pm25_conc is not None:
                        formatted["pm25_ugm3"] = round(pm25_conc, 1)
                        formatted["pollutants"]["pm25"] = {
                            "aqi": pm25_aqi,
                            "concentration_ugm3": round(pm25_conc, 1),
                            "unit": "µg/m³"
                        }
            
            if "pm10" in iaqi and isinstance(iaqi["pm10"], dict):
                pm10_aqi = iaqi["pm10"].get("v")
                if pm10_aqi is not None:
                    formatted["pm10_aqi"] = pm10_aqi
                    # Convert AQI to estimated concentration
                    from shared.utils.aqi_converter import aqi_to_concentration
                    pm10_conc = aqi_to_concentration(pm10_aqi, "pm10")
                    if pm10_conc is not None:
                        formatted["pm10_ugm3"] = round(pm10_conc, 1)
                        formatted["pollutants"]["pm10"] = {
                            "aqi": pm10_aqi,
                            "concentration_ugm3": round(pm10_conc, 1),
                            "unit": "µg/m³"
                        }
            
            # Extract other pollutants if available
            for pollutant in ["no2", "o3", "so2", "co"]:
                if pollutant in iaqi and isinstance(iaqi[pollutant], dict):
                    value = iaqi[pollutant].get("v")
                    if value is not None:
                        formatted["pollutants"][pollutant] = {
                            "aqi": value,
                            "note": "AQI value"
                        }
        else:
            formatted["success"] = False

        # Add explicit warning about data type
        if "data" in formatted:
            formatted["data"]["_important_note"] = (
                "WAQI provides AQI index values (0-500 scale), not raw pollutant concentrations. "
                "Concentrations in µg/m³ are estimated using EPA AQI breakpoint conversions. "
                "For exact concentration measurements, consider using AirQo or OpenMeteo data sources."
            )

        return formatted

    def get_station_feed(self, uid: int | str) -> dict[str, Any]:
        """Get station feed by WAQI station UID (aka @uid in WAQI URLs)."""

        data = self._make_request(f"feed/@{uid}/")
        formatted = format_air_quality_data(data, source="waqi")
        formatted["success"] = bool(data.get("status") == "ok" and "data" in data)
        return formatted

    def get_by_coordinates(self, lat: float, lon: float) -> dict[str, Any]:
        """Alias for get_station_by_coords"""
        return self.get_station_by_coords(lat, lon)

    def get_station_by_coords(self, lat: float, lon: float) -> dict[str, Any]:
        """
        Get nearest station data by coordinates

        IMPORTANT: WAQI API returns AQI values, NOT raw concentrations.
        See get_city_feed() documentation for details.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            AQI data for nearest station with both AQI and estimated concentrations
        """
        data = self._make_request(f"feed/geo:{lat};{lon}/")
        formatted = format_air_quality_data(data, source="waqi")

        # Add success flag based on WAQI API status
        if data.get("status") == "ok" and "data" in data:
            formatted["success"] = True
        else:
            formatted["success"] = False

        if "data" in formatted:
            formatted["data"]["_important_note"] = (
                "WAQI provides AQI index values (0-500 scale), not raw pollutant concentrations. "
                "Concentrations in µg/m³ are estimated using EPA AQI breakpoint conversions."
            )

        return formatted

    def get_station_by_ip(self) -> dict[str, Any]:
        """
        Get nearest station data by IP geolocation

        Returns:
            AQI data for nearest station to client IP
        """
        data = self._make_request("feed/here/")
        formatted = format_air_quality_data(data, source="waqi")
        formatted["success"] = bool(data.get("status") == "ok" and "data" in data)
        return formatted

    def search_stations(self, keyword: str) -> dict[str, Any]:
        """
        Search for stations by name/keyword

        Args:
            keyword: Search keyword (city, station name, etc.)

        Returns:
            List of matching stations
        """
        # WAQI v2 endpoint (matches official demo)
        return self._make_request("v2/search/", {"keyword": keyword})

    def get_map_bounds(self, lat1: float, lng1: float, lat2: float, lng2: float) -> dict[str, Any]:
        """
        Get all stations within map bounds

        Args:
            lat1: Southwest latitude
            lng1: Southwest longitude
            lat2: Northeast latitude
            lng2: Northeast longitude

        Returns:
            List of stations within bounds
        """
        # WAQI v2 endpoint expects `latlng` param (N,W,S,E style used by demos)
        latlng = f"{lat1},{lng1},{lat2},{lng2}"
        return self._make_request("v2/map/bounds/", {"latlng": latlng})

    def get_station_forecast(self, city: str) -> dict[str, Any]:
        """
        Get air quality forecast for a city (3-8 days)

        Args:
            city: City name

        Returns:
            Forecast data
        """
        # Forecast is included in the feed data
        feed_data = self.get_city_feed(city)
        return feed_data.get("data", {}).get("forecast", {})

    def get_multiple_cities(self, cities: list[str]) -> dict[str, dict[str, Any]]:
        """
        Get data for multiple cities

        Args:
            cities: List of city names

        Returns:
            Dictionary mapping city name to AQI data
        """
        results = {}
        for city in cities:
            try:
                results[city] = self.get_city_feed(city)
            except ProviderServiceError as e:
                # Non-leaky; keep service usable for agent even when one city fails.
                results[city] = {"success": False, "message": e.public_message}
            except Exception:
                results[city] = {
                    "success": False,
                    "message": provider_unavailable_message("WAQI"),
                }
        return results

    def interpret_aqi(self, aqi: int) -> dict[str, str]:
        """
        Interpret AQI value into health implications

        Args:
            aqi: Air Quality Index value

        Returns:
            Dictionary with level, color, and health implications
        """
        if aqi <= 50:
            return {
                "level": "Good",
                "color": "green",
                "health_implications": "Air quality is satisfactory, air pollution poses little or no risk.",
                "cautionary_statement": "None",
            }
        elif aqi <= 100:
            return {
                "level": "Moderate",
                "color": "yellow",
                "health_implications": "Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution.",
                "cautionary_statement": "Unusually sensitive people should consider limiting prolonged outdoor exertion.",
            }
        elif aqi <= 150:
            return {
                "level": "Unhealthy for Sensitive Groups",
                "color": "orange",
                "health_implications": "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
                "cautionary_statement": "Sensitive groups should limit prolonged outdoor exertion.",
            }
        elif aqi <= 200:
            return {
                "level": "Unhealthy",
                "color": "red",
                "health_implications": "Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects.",
                "cautionary_statement": "Everyone should limit prolonged outdoor exertion.",
            }
        elif aqi <= 300:
            return {
                "level": "Very Unhealthy",
                "color": "purple",
                "health_implications": "Health alert: The risk of health effects is increased for everyone.",
                "cautionary_statement": "Everyone should avoid prolonged outdoor exertion; sensitive groups should remain indoors.",
            }
        else:
            return {
                "level": "Hazardous",
                "color": "maroon",
                "health_implications": "Health warning of emergency conditions: everyone is more likely to be affected.",
                "cautionary_statement": "Everyone should avoid all outdoor exertion.",
            }
