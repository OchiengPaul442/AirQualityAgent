"""
UK Carbon Intensity API Service

Provides access to carbon intensity data for Great Britain from National Grid ESO.
API Documentation: https://carbon-intensity.github.io/api-definitions/

Features:
- No API key required (free access)
- Carbon intensity data for electricity generation in GB
- Real-time, forecast, and historical data
- Regional breakdown (England, Scotland, Wales)
- Generation mix data
- Carbon intensity factors for different fuel types

Note: Carbon intensity is measured in gCO2/kWh and indicates the amount of CO2
emitted per unit of electricity generated. This data is related to air quality
as CO2 emissions contribute to climate change and air pollution.
"""

from typing import Any

import requests

from .cache import get_cache


class CarbonIntensityService:
    """Service for interacting with the UK Carbon Intensity API"""

    BASE_URL = "https://api.carbonintensity.org.uk"

    def __init__(self):
        """
        Initialize Carbon Intensity service

        Note: No API key required for access
        """
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        from ..config import get_settings

        settings = get_settings()
        self.session = requests.Session()

        # Configure retries
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        Make request to Carbon Intensity API

        Args:
            endpoint: API endpoint (e.g., '/intensity')
            params: Optional query parameters

        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Check Redis cache
        cache_key = f"carbon_intensity{endpoint}"
        cached_data = self.cache_service.get_api_response(
            "carbon_intensity", endpoint, params or {}
        )
        if cached_data is not None:
            return cached_data

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "error" in data:
                raise Exception(
                    f"Carbon Intensity API error: {data['error'].get('message', 'Unknown error')}"
                )

            # Cache the result in Redis
            self.cache_service.set_api_response(
                "carbon_intensity", endpoint, params or {}, data, self.cache_ttl
            )
            return data

        except requests.exceptions.RequestException as e:
            error_msg = f"Carbon Intensity API request failed: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f" Response: {e.response.text}"
            raise Exception(error_msg) from e

    def get_current_intensity(self) -> dict[str, Any]:
        """
        Get current carbon intensity for GB

        Returns:
            Current carbon intensity data with forecast, actual, and index
        """
        return self._make_request("/intensity")

    def get_intensity_for_date(self, date: str) -> dict[str, Any]:
        """
        Get carbon intensity data for a specific date

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Carbon intensity data for the specified date
        """
        return self._make_request(f"/intensity/date/{date}")

    def get_intensity_today(self) -> dict[str, Any]:
        """
        Get carbon intensity data for today

        Returns:
            Carbon intensity data for today
        """
        return self._make_request("/intensity/date")

    def get_intensity_range(self, from_datetime: str, to_datetime: str) -> dict[str, Any]:
        """
        Get carbon intensity data for a date range

        Args:
            from_datetime: Start datetime in ISO8601 format (YYYY-MM-DDTHH:mmZ)
            to_datetime: End datetime in ISO8601 format (YYYY-MM-DDTHH:mmZ)

        Returns:
            Carbon intensity data for the specified range
        """
        return self._make_request(f"/intensity/{from_datetime}/{to_datetime}")

    def get_regional_intensity(self, region: str | None = None) -> dict[str, Any]:
        """
        Get regional carbon intensity data

        Args:
            region: Optional region ('england', 'scotland', 'wales')

        Returns:
            Regional carbon intensity data
        """
        if region:
            return self._make_request(f"/regional/{region}")
        return self._make_request("/regional")

    def get_generation_mix(self) -> dict[str, Any]:
        """
        Get current generation mix (fuel types and percentages)

        Returns:
            Current generation mix data
        """
        return self._make_request("/generation")

    def get_intensity_factors(self) -> dict[str, Any]:
        """
        Get carbon intensity factors for different fuel types

        Returns:
            Carbon intensity factors in gCO2/kWh for each fuel type
        """
        return self._make_request("/intensity/factors")

    def get_intensity_statistics(self, from_datetime: str, to_datetime: str) -> dict[str, Any]:
        """
        Get carbon intensity statistics for a date range

        Args:
            from_datetime: Start datetime in ISO8601 format
            to_datetime: End datetime in ISO8601 format

        Returns:
            Statistics including max, average, min carbon intensity
        """
        return self._make_request(f"/intensity/stats/{from_datetime}/{to_datetime}")

    def format_carbon_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Format carbon intensity data for display

        Args:
            data: Raw API response data

        Returns:
            Formatted data with human-readable information
        """
        if not data.get("data"):
            return {"error": "No data available"}

        formatted_data: dict[str, Any] = {
            "source": "UK Carbon Intensity API",
            "description": "Carbon intensity of electricity generation in Great Britain (gCO2/kWh)",
            "data": [],
        }

        for item in data["data"]:
            entry = {
                "period": {"from": item.get("from"), "to": item.get("to")},
                "intensity": {
                    "forecast": item.get("intensity", {}).get("forecast"),
                    "actual": item.get("intensity", {}).get("actual"),
                    "index": item.get("intensity", {}).get("index"),
                },
            }

            # Add generation mix if available
            if "generationmix" in item:
                entry["generation_mix"] = item["generationmix"]

            formatted_data["data"].append(entry)

        return formatted_data
