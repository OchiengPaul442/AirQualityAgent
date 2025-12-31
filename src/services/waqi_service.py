"""
World Air Quality Index (WAQI) API Service

Provides access to global air quality data from over 11,000 stations.
API Documentation: https://aqicn.org/json-api/doc/
"""

from typing import Any

import requests

from ..utils.data_formatter import format_air_quality_data
from .cache import get_cache


class WAQIService:
    """Service for interacting with the World Air Quality Index API"""

    BASE_URL = "https://api.waqi.info"

    def __init__(self, api_token: str | None = None):
        """
        Initialize WAQI service

        Args:
            api_key: WAQI API token from https://aqicn.org/data-platform/token/
        """
        from ..config import get_settings

        settings = get_settings()
        self.api_key = api_token or settings.WAQI_API_KEY
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        Make request to WAQI API

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}/{endpoint}"

        # Add API key to params
        if params is None:
            params = {}
        params["token"] = self.api_key

        # Check Redis cache
        cached_data = self.cache_service.get_api_response("waqi", endpoint, params)
        if cached_data is not None:
            return cached_data

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"WAQI API error: {data.get('data', 'Unknown error')}")

            # Cache the result in Redis
            self.cache_service.set_api_response("waqi", endpoint, params, data, self.cache_ttl)
            return data

        except requests.exceptions.RequestException as e:
            raise Exception(f"WAQI API request failed: {str(e)}") from e

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
        data = self._make_request(f"feed/{city}/")
        formatted = format_air_quality_data(data, source="waqi")
        
        # Add explicit warning about data type
        if "data" in formatted:
            formatted["data"]["_important_note"] = (
                "WAQI provides AQI index values (0-500 scale), not raw pollutant concentrations. "
                "Concentrations in µg/m³ are estimated using EPA AQI breakpoint conversions. "
                "For exact concentration measurements, consider using AirQo or OpenMeteo data sources."
            )
        
        return formatted

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
        return self._make_request("feed/here/")

    def search_stations(self, keyword: str) -> dict[str, Any]:
        """
        Search for stations by name/keyword

        Args:
            keyword: Search keyword (city, station name, etc.)

        Returns:
            List of matching stations
        """
        return self._make_request("search/", {"keyword": keyword})

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
        bounds = f"{lat1},{lng1},{lat2},{lng2}"
        return self._make_request("map/bounds/", {"bounds": bounds})

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
            except Exception as e:
                results[city] = {"error": str(e)}
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
