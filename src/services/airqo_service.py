"""
AirQo API Service

Provides access to AirQo air quality monitoring network data.
API Documentation: https://docs.airqo.net/airqo-rest-api-documentation/
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import requests

from ..utils.data_formatter import format_air_quality_data
from .cache import get_cache

logger = logging.getLogger(__name__)


class AirQoService:
    """Service for interacting with the AirQo Analytics API"""

    BASE_URL = "https://api.airqo.net/api/v2"

    def __init__(self, api_token: str | None = None):
        """
        Initialize AirQo service

        Args:
            api_token: AirQo API token from https://analytics.airqo.net
        """
        from ..config import get_settings

        settings = get_settings()
        self.api_token = api_token or settings.AIRQO_API_TOKEN
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _get_headers(self) -> dict[str, str]:
        """Get request headers"""
        return {"Content-Type": "application/json"}

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        Make authenticated request to AirQo API

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data
        """

        url = f"{self.BASE_URL}/{endpoint}"

        # Add authentication token to params
        request_params = params.copy() if params else {}
        if self.api_token:
            request_params["token"] = self.api_token

        # Check Redis cache
        cached_data = self.cache_service.get_api_response("airqo", endpoint, request_params)
        if cached_data is not None:
            return cached_data

        try:
            response = self.session.get(
                url, headers=self._get_headers(), params=request_params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Cache the result in Redis
            self.cache_service.set_api_response(
                "airqo", endpoint, request_params, data, self.cache_ttl
            )
            return data

        except requests.exceptions.RequestException as e:
            # Log the full error for debugging
            error_msg = f"AirQo API request failed: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f" Response: {e.response.text}"
            raise Exception(error_msg) from e

    def get_measurements(
        self,
        site_id: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        frequency: str = "hourly",
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get air quality measurements (General endpoint)

        Args:
            site_id: Specific site/location ID
            device_id: Specific device ID
            start_time: Start of time range
            end_time: End of time range
            frequency: Data frequency (hourly, daily, raw)
            limit: Maximum number of records

        Returns:
            Measurements data with PM2.5, PM10, etc.
        """
        params = {"frequency": frequency, "limit": limit}

        if site_id:
            params["site_id"] = site_id
        if device_id:
            params["device_id"] = device_id
        if start_time:
            params["startTime"] = start_time.isoformat()
        if end_time:
            params["endTime"] = end_time.isoformat()

        data = self._make_request("devices/measurements", params)
        return format_air_quality_data(data, source="airqo")

    def get_historical_measurements(
        self,
        site_id: Optional[str] = None,
        device_id: Optional[str] = None,
        grid_id: Optional[str] = None,
        cohort_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        frequency: str = "hourly",
    ) -> dict[str, Any]:
        """
        Get historical measurements by Site, Device, Grid, or Cohort ID.
        """
        params = {"frequency": frequency}
        if start_time:
            params["startTime"] = start_time.isoformat()
        if end_time:
            params["endTime"] = end_time.isoformat()

        if site_id:
            return self._make_request(f"devices/measurements/sites/{site_id}/historical", params)
        elif device_id:
            return self._make_request(
                f"devices/measurements/devices/{device_id}/historical", params
            )
        elif grid_id:
            return self._make_request(f"devices/measurements/grids/{grid_id}/historical", params)
        elif cohort_id:
            return self._make_request(
                f"devices/measurements/cohorts/{cohort_id}/historical", params
            )
        else:
            raise ValueError("One of site_id, device_id, grid_id, or cohort_id must be provided.")

    def get_forecast(
        self,
        site_id: Optional[str] = None,
        device_id: Optional[str] = None,
        city: Optional[str] = None,
        search: Optional[str] = None,
        frequency: str = "daily",
    ) -> dict[str, Any]:
        """
        Get air quality forecast.
        If site_id or device_id is not provided, will try to find site by city or search.

        Args:
            site_id: The ID of the site
            device_id: The ID of the device
            city: City name to search for
            search: Search query for site
            frequency: 'daily' or 'hourly'
        """
        if frequency not in ["daily", "hourly"]:
            raise ValueError("Frequency must be 'daily' or 'hourly'")

        endpoint_type = "daily-forecast" if frequency == "daily" else "hourly-forecast"
        params = {}

        # Try direct IDs first
        if site_id:
            params["site_id"] = site_id
        elif device_id:
            params["device_id"] = device_id
        else:
            # Try to find site_id using search or city
            search_query = search or city
            if search_query:
                found_site_id = self.get_site_id_by_name(search_query)
                if found_site_id:
                    # Handle both single ID and list of IDs
                    if isinstance(found_site_id, list):
                        params["site_id"] = found_site_id[0]
                    else:
                        params["site_id"] = found_site_id
                else:
                    return {
                        "success": False,
                        "message": f"No monitoring sites found for '{search_query}' to generate forecast."
                    }
            else:
                raise ValueError("Either site_id, device_id, city, or search must be provided for forecast.")

        data = self._make_request(f"predict/{endpoint_type}", params)
        return format_air_quality_data(data, source="airqo")

    def get_metadata(self, entity_type: str = "grids", search: str | None = None) -> dict[str, Any]:
        """
        Get metadata for grids, cohorts, devices, or sites.

        Args:
            entity_type: 'grids', 'cohorts', 'devices', or 'sites'
            search: Optional search query parameter
        """
        valid_types = ["grids", "cohorts", "devices", "sites"]
        if entity_type not in valid_types:
            raise ValueError(f"Invalid entity_type. Must be one of {valid_types}")

        params = {}
        if search:
            params["search"] = search

        return self._make_request(f"devices/metadata/{entity_type}", params)

    def get_sites_summary(self, search: str | None = None, limit: int = 30) -> dict[str, Any]:
        """
        Get sites summary - returns detailed site information including online status.
        This is more comprehensive than metadata/sites.

        Args:
            search: Optional search query to filter sites
            limit: Maximum number of results (default 30)

        Returns:
            Dictionary with sites array containing detailed site information
        """
        params = {"limit": limit}
        if search:
            params["search"] = search

        return self._make_request("devices/sites/summary", params)

    def get_grids_summary(self, search: str | None = None, limit: int = 30) -> dict[str, Any]:
        """
        Get grids summary - returns grids with their associated sites.
        Each grid contains a list of sites with their details.

        Args:
            search: Optional search query to filter grids
            limit: Maximum number of results (default 30)

        Returns:
            Dictionary with grids array, each containing sites
        """
        params = {"limit": limit}
        if search:
            params["search"] = search

        return self._make_request("devices/grids/summary", params)

    def get_site_id_by_name(self, name: str, limit: int = 5) -> Optional[Union[str, List[str]]]:
        """
        Helper to find Site ID(s) by searching for a name using sites/summary endpoint.
        Uses the proper AirQo API search flow.

        Args:
            name: Location name to search for (e.g., "Gulu University", "Kampala")
            limit: Maximum number of site IDs to return (default 5)

        Returns:
            Single site ID string if one result, list of IDs if multiple, or None if not found
        """
        try:
            # Try to get from cache first
            cache_key = f"site_id_map:{name.lower()}"
            cached_id = self.cache_service.get("airqo", cache_key)
            if cached_id:
                return cached_id

            # Use sites/summary endpoint with search parameter
            response = self.get_sites_summary(search=name, limit=limit)
            
            if response.get("success") and response.get("sites"):
                sites = response["sites"]
                site_ids = [site.get("_id") for site in sites if site.get("_id")]
                
                if site_ids:
                    # Cache the first result
                    self.cache_service.set("airqo", cache_key, site_ids[0], 3600)
                    # Return single ID if one result, otherwise return list
                    return site_ids[0] if len(site_ids) == 1 else site_ids

            return None
        except Exception as e:
            print(f"Error finding site ID for '{name}': {e}")
            return None

    def get_air_quality_by_location(self, latitude: float, longitude: float, limit_sites: int = 3) -> dict[str, Any]:
        """
        Enhanced method to get air quality data for coordinates using AirQo's site-based approach.
        This method prioritizes AirQo data for African locations by:
        1. First reverse geocode to get city name, then search for sites
        2. If sites found, get measurements using site IDs
        3. If no sites, try coordinate-based search
        4. If still no sites, try grid-based data for the region
        5. Return formatted data with location context

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            limit_sites: Maximum number of sites to query (default 3)

        Returns:
            Formatted air quality data with measurements from available sites
        """
        try:
            # Step 1: Reverse geocode to get city name first
            city_name = self._reverse_geocode(latitude, longitude)

            if city_name:
                sites_response = self.get_sites_summary(search=city_name, limit=limit_sites)

                if sites_response.get("success") and sites_response.get("sites"):
                    sites = sites_response["sites"]
                    site_ids = [site.get("_id") for site in sites if site.get("_id")]

                    if site_ids:
                        # Step 2: Get measurements for found sites
                        params = {"site_id": ",".join(site_ids)}
                        measurements_data = self._make_request("devices/readings/recent", params)

                        # Add location context to the response
                        if measurements_data.get("success"):
                            measurements_data["coordinates"] = {"lat": latitude, "lon": longitude}
                            measurements_data["city_found"] = city_name
                            measurements_data["sites_found"] = len(site_ids)
                            measurements_data["site_ids_used"] = site_ids

                        return format_air_quality_data(measurements_data, source="airqo")

            # Step 2: If reverse geocoding didn't work or no sites found, try coordinate-based search
            location_query = f"{latitude:.4f},{longitude:.4f}"
            sites_response = self.get_sites_summary(search=location_query, limit=limit_sites)

            if sites_response.get("success") and sites_response.get("sites"):
                sites = sites_response["sites"]
                site_ids = [site.get("_id") for site in sites if site.get("_id")]

                if site_ids:
                    # Get measurements for found sites
                    params = {"site_id": ",".join(site_ids)}
                    measurements_data = self._make_request("devices/readings/recent", params)

                    # Add location context to the response
                    if measurements_data.get("success"):
                        measurements_data["coordinates"] = {"lat": latitude, "lon": longitude}
                        measurements_data["sites_found"] = len(site_ids)
                        measurements_data["site_ids_used"] = site_ids
                        measurements_data["search_method"] = "coordinates"

                    return format_air_quality_data(measurements_data, source="airqo")

            # Step 3: If no sites found, try grid-based search for the region
            grids_response = self.get_grids_summary(search=city_name or location_query, limit=5)

            if grids_response.get("success") and grids_response.get("grids"):
                grids = grids_response["grids"]
                grid_ids = [grid.get("_id") for grid in grids if grid.get("_id")]

                if grid_ids:
                    # Get measurements for first available grid
                    grid_data = self._make_request(f"devices/measurements/grids/{grid_ids[0]}/recent")

                    if grid_data.get("success"):
                        grid_data["coordinates"] = {"lat": latitude, "lon": longitude}
                        grid_data["city_searched"] = city_name
                        grid_data["grid_used"] = grid_ids[0]
                        grid_data["search_method"] = "grid_fallback"

                    return format_air_quality_data(grid_data, source="airqo")

            # Step 4: No sites or grids found
            return {
                "success": False,
                "message": f"No AirQo monitoring sites or grids found near coordinates ({latitude:.4f}, {longitude:.4f}). "
                          f"AirQo primarily covers East African countries. The coordinates may be outside the coverage area.",
                "coordinates": {"lat": latitude, "lon": longitude},
                "city_attempted": city_name,
                "search_method": "none_found"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error retrieving AirQo data for coordinates ({latitude:.4f}, {longitude:.4f}): {str(e)}",
                "coordinates": {"lat": latitude, "lon": longitude},
                "error": str(e)
            }

    def get_recent_measurements(
        self,
        site_id: Optional[str] = None,
        device_id: Optional[str] = None,
        grid_id: Optional[str] = None,
        cohort_id: Optional[str] = None,
        country: str = "UG",
        city: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get recent measurements using the proper AirQo API flow:
        1. Search for sites using the sites/summary endpoint with search parameter
        2. Extract site IDs from the response
        3. Use those IDs with the readings/recent endpoint

        Args:
            site_id: Direct site ID (if known)
            device_id: Direct device ID (if known)
            grid_id: Direct grid ID (if known)
            cohort_id: Direct cohort ID (if known)
            country: Country code (default 'UG')
            city: City or location name to search for
            search: Direct search query for sites

        Returns:
            Recent measurements with full details including health tips, AQI ranges, etc.
        """
        # 1. If direct site_id provided, use the readings/recent endpoint
        if site_id:
            params = {"site_id": site_id}
            data = self._make_request("devices/readings/recent", params)
            return format_air_quality_data(data, source="airqo")

        # 2. If device_id, grid_id, or cohort_id provided (legacy support)
        if device_id:
            data = self._make_request(f"devices/measurements/devices/{device_id}/recent")
            return format_air_quality_data(data, source="airqo")
        elif grid_id:
            data = self._make_request(f"devices/measurements/grids/{grid_id}/recent")
            return format_air_quality_data(data, source="airqo")
        elif cohort_id:
            data = self._make_request(f"devices/measurements/cohorts/{cohort_id}/recent")
            return format_air_quality_data(data, source="airqo")

        # 3. Search for sites using city or search parameter
        search_query = search or city
        if search_query:
            try:
                # Use sites/summary endpoint to find matching sites
                sites_response = self.get_sites_summary(search=search_query, limit=10)
                
                if sites_response.get("success") and sites_response.get("sites"):
                    sites = sites_response["sites"]
                    
                    # Extract site IDs from matching sites
                    site_ids = [site.get("_id") for site in sites if site.get("_id")]
                    
                    if site_ids:
                        # Use the readings/recent endpoint with multiple site_ids
                        # This endpoint accepts comma-separated site_ids
                        params = {"site_id": ",".join(site_ids[:5])}  # Limit to first 5 sites
                        data = self._make_request("devices/readings/recent", params)
                        
                        # Add search context to help AI understand the data
                        if data.get("success"):
                            data["search_location"] = search_query
                            data["sites_queried"] = len(site_ids[:5])
                        
                        return format_air_quality_data(data, source="airqo")
                
                # If no sites found, return helpful error with coverage info
                return {
                    "success": False,
                    "message": f"AirQo monitoring network does not have active stations in '{search_query}'. AirQo covers major East African cities including Kampala, Gulu, Mbale, Jinja, Nairobi, Dar es Salaam, and Kigali. Try checking WAQI or OpenMeteo for this location.",
                    "location_searched": search_query,
                    "sites": [],
                    "suggestion": "Try using WAQI (get_city_air_quality) or OpenMeteo as alternative data sources."
                }
            except Exception as e:
                logger.error(f"Error searching AirQo sites for {search_query}: {e}")
                return {
                    "success": False,
                    "message": f"Error searching for AirQo monitoring sites in '{search_query}': {str(e)}",
                    "location_searched": search_query,
                    "error": str(e),
                    "suggestion": "Try using WAQI (get_city_air_quality) or OpenMeteo as alternative data sources."
                }

        raise ValueError("Must provide site_id, device_id, grid_id, cohort_id, city, or search parameter.")

    def search_sites_by_location(self, location: str, limit: int = 5) -> dict[str, Any]:
        """
        Search for monitoring sites by location name.
        Returns detailed site information from the sites/summary endpoint.

        Args:
            location: Location name to search for
            limit: Maximum number of results

        Returns:
            Dictionary with success status and sites array
        """
        try:
            response = self.get_sites_summary(search=location, limit=limit)
            
            if response.get("success") and response.get("sites"):
                return response
            
            return {
                "success": False,
                "message": f"No monitoring sites found for '{location}'",
                "sites": []
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error searching for sites: {str(e)}",
                "sites": []
            }

    def get_sites(self, country: str | None = None, city: str | None = None) -> dict[str, Any]:
        """
        Get list of monitoring sites

        Args:
            country: Filter by country code (e.g., 'UG' for Uganda)
            city: Filter by city name (e.g., 'Gulu')

        Returns:
            List of sites with metadata
        """
        params = {}
        if country:
            params["country"] = country
        if city:
            params["city"] = city

        return self._make_request("devices/sites", params)

    def get_devices(self, site_id: str | None = None) -> dict[str, Any]:
        """
        Get list of devices

        Args:
            site_id: Filter by site ID

        Returns:
            List of devices with metadata
        """
        params = {}
        if site_id:
            params["site_id"] = site_id

        return self._make_request("devices", params)

    def _reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Reverse geocode coordinates to get city name using OpenStreetMap Nominatim API
        """
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "zoom": 10  # City level
            }
            headers = {"User-Agent": "AirQoAgent/1.0"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and "address" in data:
                    address = data["address"]
                    # Try to get city name from various possible fields, preferring cleaner names
                    city = (address.get("city") or
                           address.get("town") or
                           address.get("village") or
                           address.get("municipality") or
                           address.get("county"))
                    # Clean up the city name by removing qualifiers like "Capital City"
                    if city:
                        city = city.replace(" Capital City", "").replace(" City", "").strip()
                    return city
        except Exception as e:
            print(f"Error reverse geocoding coordinates ({latitude}, {longitude}): {e}")
        return None
