"""
New South Wales Air Quality API Service

Provides access to NSW air quality monitoring data from over 300 stations.
API Documentation: https://www.airquality.nsw.gov.au/air-quality-data-services/air-quality-api
Data License: Creative Commons Attribution 4.0 International (CC BY 4.0)
"""

from datetime import datetime, timedelta
from typing import Any

import requests

from ..utils.data_formatter import format_air_quality_data
from .cache import get_cache


class NSWService:
    """Service for interacting with the NSW Air Quality API"""

    BASE_URL = "https://data.airquality.nsw.gov.au"

    def __init__(self):
        """
        Initialize NSW air quality service

        No API key required - data is openly accessible
        """
        from ..config import get_settings

        settings = get_settings()
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """
        Make request to NSW Air Quality API

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET or POST)
            params: Query parameters for GET requests
            data: JSON data for POST requests

        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}/{endpoint}"

        # Check Redis cache for GET requests
        if method == "GET":
            cached_data = self.cache_service.get_api_response("nsw", endpoint, params or {})
            if cached_data is not None:
                return cached_data

        try:
            if method == "POST":
                response = self.session.post(url, json=data, timeout=30)
            else:
                response = self.session.get(url, params=params, timeout=30)

            response.raise_for_status()
            data_response = response.json()

            # NSW API doesn't have a standard status field, but we can check for error responses
            if isinstance(data_response, dict) and "error" in data_response:
                raise Exception(f"NSW API error: {data_response['error']}")

            # Cache GET responses
            if method == "GET":
                self.cache_service.set_api_response(
                    "nsw", endpoint, params or {}, data_response, self.cache_ttl
                )

            return data_response

        except requests.exceptions.RequestException as e:
            raise Exception(f"NSW API request failed: {str(e)}") from e

    def get_air_quality(self, region: str | None = None) -> dict[str, Any]:
        """
        Get current air quality observations.

        Args:
            region: Optional region name to filter by (not currently used but kept for interface consistency)

        Returns:
            Observation data
        """
        # Default to getting all observations for today
        today = datetime.now().strftime("%Y-%m-%d")
        request_data = {
            "StartDate": today,
            "EndDate": today,
            "Categories": ["Good", "Fair", "Poor", "Very Poor", "Extremely Poor"],
        }
        return self.get_observations(request_data)

    def get_site_details(self) -> list[dict[str, Any]]:
        """
        Get details of all air quality monitoring sites in NSW

        Returns:
            List of site details including site name, location, region, etc.
        """
        data = self._make_request("api/Data/get_SiteDetails")
        return data if isinstance(data, list) else []

    def get_parameter_details(self) -> list[dict[str, Any]]:
        """
        Get details of all air quality parameters measured

        Returns:
            List of parameter details including parameter name, units, averaging periods, etc.
        """
        data = self._make_request("api/Data/get_ParameterDetails")
        return data if isinstance(data, list) else []

    def get_observations(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get air quality observation data

        IMPORTANT: NSW API returns raw pollutant concentrations in µg/m³, NOT AQI values.
        They use Air Quality Categories (AQC): Good, Fair, Poor, Very Poor, Extremely Poor.

        Args:
            request_data: Request parameters including:
                - Parameters: List of parameter codes (e.g., ["PM2.5", "PM10", "O3"])
                - Sites: List of site codes (optional, gets all sites if not specified)
                - StartDate: Start date in YYYY-MM-DD format
                - EndDate: End date in YYYY-MM-DD format
                - Categories: List of AQCs to filter by (optional)
                - StartTimeLocal: Start time in HH:MM format (optional)
                - EndTimeLocal: End time in HH:MM format (optional)

        Returns:
            Observation data with concentrations and air quality categories
        """
        try:
            data = self._make_request("api/Data/get_Observations", method="POST", data=request_data)

            # NSW API returns different formats - handle both
            if isinstance(data, list):
                # Convert list to expected dict format
                formatted_data = {"Values": data}
            else:
                formatted_data = data

            # Format the data using our standard formatter
            formatted = format_air_quality_data(formatted_data, source="nsw")

            # Add important notes about NSW data
            if "data" in formatted:
                formatted["data"]["_important_note"] = (
                    "NSW provides raw pollutant concentrations in µg/m³ and Air Quality Categories (AQC). "
                    "AQCs are: Good, Fair, Poor, Very Poor, Extremely Poor. "
                    "Data is quality-assured and updated hourly."
                )

            return formatted

        except Exception as e:
            # Return a structured error response
            return {
                "success": False,
                "error": f"NSW API unavailable: {str(e)}",
                "message": "NSW air quality data is currently unavailable via API. Data is openly available at https://www.airquality.nsw.gov.au/",
                "source": "nsw",
                "data": {
                    "_important_note": "NSW air quality monitoring data is openly available under Creative Commons Attribution 4.0 International license. Visit https://www.airquality.nsw.gov.au/ for current data."
                },
            }

    def get_current_air_quality(self, location: str | None = None) -> dict[str, Any]:
        """
        Get current air quality data for NSW

        Args:
            location: Optional location filter (site name or region)

        Returns:
            Current air quality data with concentrations and AQCs
        """
        try:
            from datetime import datetime, timedelta

            # Get data for the last hour
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=1)

            request_data = {
                "Parameters": ["PM2.5", "PM10", "O3", "NO2", "SO2", "CO"],
                "StartDate": start_date.strftime("%Y-%m-%d"),
                "EndDate": end_date.strftime("%Y-%m-%d"),
                "StartTimeLocal": start_date.strftime("%H:%M"),
                "EndTimeLocal": end_date.strftime("%H:%M"),
            }

            # If location is specified, try to find matching sites
            if location:
                sites = self.get_site_details()
                matching_sites = []
                location_lower = location.lower()

                for site in sites:
                    site_name = site.get("SiteName", "").lower()
                    region = site.get("Region", "").lower()

                    if location_lower in site_name or location_lower in region:
                        matching_sites.append(site.get("Site_Id"))

                if matching_sites:
                    request_data["Sites"] = matching_sites[:5]  # Limit to 5 sites

            return self.get_observations(request_data)
        except Exception as e:
            return {
                "success": False,
                "error": f"Unable to retrieve current NSW data: {str(e)}",
                "message": "NSW air quality data is openly available at https://www.airquality.nsw.gov.au/",
                "source": "nsw",
            }

    def get_sites_by_region(self, region: str) -> list[dict[str, Any]]:
        """
        Get all sites in a specific region

        Args:
            region: Region name (e.g., "Sydney", "Newcastle", "Central Tablelands")

        Returns:
            List of sites in the specified region
        """
        sites = self.get_site_details()
        region_lower = region.lower()

        matching_sites = []
        for site in sites:
            site_region = site.get("Region", "").lower()
            if region_lower in site_region:
                matching_sites.append(site)

        return matching_sites

    def get_pollutant_data(self, pollutant: str, hours: int = 24) -> dict[str, Any]:
        """
        Get recent data for a specific pollutant across all NSW sites

        Args:
            pollutant: Pollutant code (e.g., "PM2.5", "PM10", "O3", "NO2", "SO2", "CO")
            hours: Number of hours of data to retrieve (default: 24)

        Returns:
            Pollutant data across all sites
        """
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)

        request_data = {
            "Parameters": [pollutant],
            "StartDate": start_date.strftime("%Y-%m-%d"),
            "EndDate": end_date.strftime("%Y-%m-%d"),
        }

        return self.get_observations(request_data)
