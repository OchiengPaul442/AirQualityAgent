"""
Open-Meteo Air Quality API Service

Provides access to global air quality data from CAMS (Copernicus Atmosphere Monitoring Service).
API Documentation: https://open-meteo.com/en/docs/air-quality-api

Features:
- No API key required (free for non-commercial use, up to 10,000 calls/day)
- Global coverage with 11km resolution (Europe) and 25km resolution (Global)
- Real-time and historical air quality data
- Forecasts up to 7 days
- European and US AQI indices
- Multiple pollutants: PM10, PM2.5, CO, NO2, SO2, O3, and more
"""

from datetime import datetime
from typing import Any

import requests

from infrastructure.cache.cache_service import get_cache
from shared.utils.data_formatter import format_air_quality_data


class OpenMeteoService:
    """Service for interacting with the Open-Meteo Air Quality API"""

    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self):
        """
        Initialize Open-Meteo service

        Note: No API key required for non-commercial use up to 10,000 calls/day
        """
        from shared.config.settings import get_settings

        settings = get_settings()
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _make_request(self, params: dict) -> dict[str, Any]:
        """
        Make request to Open-Meteo API

        Args:
            params: Query parameters

        Returns:
            JSON response data
        """
        # Check Redis cache
        cached_data = self.cache_service.get_api_response("openmeteo", "air-quality", params)
        if cached_data is not None:
            return cached_data

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if data.get("error"):
                raise Exception(f"Open-Meteo API error: {data.get('reason', 'Unknown error')}")

            # Cache the result in Redis
            self.cache_service.set_api_response(
                "openmeteo", "air-quality", params, data, self.cache_ttl
            )
            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"Open-Meteo API request failed: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f" Response: {e.response.text}"
            raise Exception(error_msg) from e

    def get_current_air_quality(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "auto",
        include_aqi: bool = True,
    ) -> dict[str, Any]:
        """
        Get current air quality data for a location

        Args:
            latitude: Location latitude
            longitude: Location longitude
            timezone: Timezone (auto, GMT, or IANA timezone like Europe/Berlin)
            include_aqi: Include both European and US AQI indices

        Returns:
            Current air quality measurements with AQI
        """
        # Define current parameters - all major pollutants plus AQI
        current_params = [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "dust",
            "uv_index",
            "aerosol_optical_depth",
        ]

        if include_aqi:
            current_params.extend(["european_aqi", "us_aqi"])

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(current_params),
            "timezone": timezone,
        }

        data = self._make_request(params)
        formatted = format_air_quality_data(data, source="openmeteo")

        # Add success flag based on presence of current data
        if "current" in data and not data.get("error"):
            formatted["success"] = True
        else:
            formatted["success"] = False
            formatted["error"] = data.get("reason", "Unknown error")

        return formatted

    def get_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 5,
        timezone: str = "auto",
        variables: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get hourly air quality forecast

        Args:
            latitude: Location latitude
            longitude: Location longitude
            forecast_days: Number of forecast days (0-7, default: 5)
            timezone: Timezone (auto, GMT, or IANA timezone)
            variables: List of variables to retrieve. If None, returns all major pollutants

        Returns:
            Hourly forecast data
        """
        if variables is None:
            # Default comprehensive set of variables
            variables = [
                "pm10",
                "pm2_5",
                "carbon_monoxide",
                "nitrogen_dioxide",
                "sulphur_dioxide",
                "ozone",
                "dust",
                "uv_index",
                "european_aqi",
                "us_aqi",
            ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(variables),
            "forecast_days": min(forecast_days, 7),  # Max 7 days
            "timezone": timezone,
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    def get_historical_data(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
        timezone: str = "auto",
        variables: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get historical air quality data

        Args:
            latitude: Location latitude
            longitude: Location longitude
            start_date: Start date for historical data
            end_date: End date for historical data
            timezone: Timezone (auto, GMT, or IANA timezone)
            variables: List of variables to retrieve

        Returns:
            Historical air quality data
        """
        if variables is None:
            variables = [
                "pm10",
                "pm2_5",
                "carbon_monoxide",
                "nitrogen_dioxide",
                "sulphur_dioxide",
                "ozone",
                "european_aqi",
                "us_aqi",
            ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(variables),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "timezone": timezone,
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    def get_comprehensive_data(
        self,
        latitude: float,
        longitude: float,
        past_days: int = 0,
        forecast_days: int = 5,
        timezone: str = "auto",
        domain: str = "auto",
    ) -> dict[str, Any]:
        """
        Get comprehensive air quality data (current + past + forecast)

        Args:
            latitude: Location latitude
            longitude: Location longitude
            past_days: Number of past days to include (0-92)
            forecast_days: Number of forecast days (0-7)
            timezone: Timezone (auto, GMT, or IANA timezone)
            domain: Data domain (auto, cams_europe, cams_global)

        Returns:
            Comprehensive air quality data with current conditions, history, and forecast
        """
        # All available pollutants and indices
        hourly_params = [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "dust",
            "uv_index",
            "aerosol_optical_depth",
            "european_aqi",
            "us_aqi",
        ]

        current_params = hourly_params.copy()

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(current_params),
            "hourly": ",".join(hourly_params),
            "past_days": min(past_days, 92),
            "forecast_days": min(forecast_days, 7),
            "timezone": timezone,
            "domains": domain,
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    def get_detailed_aqi(
        self, latitude: float, longitude: float, timezone: str = "auto"
    ) -> dict[str, Any]:
        """
        Get detailed AQI breakdown (both European and US standards)

        Args:
            latitude: Location latitude
            longitude: Location longitude
            timezone: Timezone

        Returns:
            Detailed AQI data with component-specific indices
        """
        # Get all AQI components for both European and US standards
        aqi_params = [
            "european_aqi",
            "european_aqi_pm2_5",
            "european_aqi_pm10",
            "european_aqi_nitrogen_dioxide",
            "european_aqi_ozone",
            "european_aqi_sulphur_dioxide",
            "us_aqi",
            "us_aqi_pm2_5",
            "us_aqi_pm10",
            "us_aqi_nitrogen_dioxide",
            "us_aqi_ozone",
            "us_aqi_sulphur_dioxide",
            "us_aqi_carbon_monoxide",
        ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(aqi_params),
            "hourly": ",".join(aqi_params),
            "forecast_days": 5,
            "timezone": timezone,
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    def get_pollutant_forecast(
        self,
        latitude: float,
        longitude: float,
        pollutant: str,
        forecast_days: int = 5,
        timezone: str = "auto",
    ) -> dict[str, Any]:
        """
        Get forecast for a specific pollutant

        Args:
            latitude: Location latitude
            longitude: Location longitude
            pollutant: Pollutant name (pm10, pm2_5, ozone, etc.)
            forecast_days: Number of forecast days
            timezone: Timezone

        Returns:
            Forecast data for the specific pollutant
        """
        valid_pollutants = [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "dust",
            "aerosol_optical_depth",
            "uv_index",
        ]

        if pollutant not in valid_pollutants:
            raise ValueError(
                f"Invalid pollutant: {pollutant}. Valid options: {', '.join(valid_pollutants)}"
            )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": pollutant,
            "hourly": pollutant,
            "forecast_days": min(forecast_days, 7),
            "timezone": timezone,
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    def get_european_data(
        self, latitude: float, longitude: float, include_pollen: bool = False
    ) -> dict[str, Any]:
        """
        Get European-specific air quality data (includes ammonia and optionally pollen)

        Args:
            latitude: Location latitude (must be in Europe)
            longitude: Location longitude (must be in Europe)
            include_pollen: Include pollen data (only available during pollen season)

        Returns:
            European air quality data with optional pollen information
        """
        params_list = [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "ammonia",  # Europe-only
            "european_aqi",
        ]

        if include_pollen:
            params_list.extend(
                [
                    "alder_pollen",
                    "birch_pollen",
                    "grass_pollen",
                    "mugwort_pollen",
                    "olive_pollen",
                    "ragweed_pollen",
                ]
            )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(params_list),
            "hourly": ",".join(params_list),
            "forecast_days": 4,  # Pollen forecast is 4 days
            "timezone": "auto",
            "domains": "cams_europe",  # Force European domain
        }

        data = self._make_request(params)
        return format_air_quality_data(data, source="openmeteo")

    @staticmethod
    def interpret_european_aqi(aqi_value: float) -> dict[str, str]:
        """
        Interpret European AQI value

        Args:
            aqi_value: European AQI value (0-100+)

        Returns:
            Dictionary with category and description
        """
        if aqi_value < 20:
            return {"category": "Good", "color": "green", "description": "Air quality is good"}
        elif aqi_value < 40:
            return {
                "category": "Fair",
                "color": "yellow",
                "description": "Air quality is fair",
            }
        elif aqi_value < 60:
            return {
                "category": "Moderate",
                "color": "orange",
                "description": "Air quality is moderate",
            }
        elif aqi_value < 80:
            return {
                "category": "Poor",
                "color": "red",
                "description": "Air quality is poor - sensitive groups should limit outdoor activity",
            }
        elif aqi_value < 100:
            return {
                "category": "Very Poor",
                "color": "purple",
                "description": "Air quality is very poor - everyone should limit outdoor activity",
            }
        else:
            return {
                "category": "Extremely Poor",
                "color": "maroon",
                "description": "Air quality is extremely poor - avoid outdoor activity",
            }

    @staticmethod
    def interpret_us_aqi(aqi_value: float) -> dict[str, str]:
        """
        Interpret US AQI value

        Args:
            aqi_value: US AQI value (0-500)

        Returns:
            Dictionary with category and description
        """
        if aqi_value <= 50:
            return {"category": "Good", "color": "green", "description": "Air quality is good"}
        elif aqi_value <= 100:
            return {
                "category": "Moderate",
                "color": "yellow",
                "description": "Air quality is acceptable",
            }
        elif aqi_value <= 150:
            return {
                "category": "Unhealthy for Sensitive Groups",
                "color": "orange",
                "description": "Sensitive groups should limit prolonged outdoor exertion",
            }
        elif aqi_value <= 200:
            return {
                "category": "Unhealthy",
                "color": "red",
                "description": "Everyone may experience health effects",
            }
        elif aqi_value <= 300:
            return {
                "category": "Very Unhealthy",
                "color": "purple",
                "description": "Health alert: everyone may experience serious health effects",
            }
        else:
            return {
                "category": "Hazardous",
                "color": "maroon",
                "description": "Health warning: emergency conditions",
            }
