"""AirQo API Service.

Provides access to AirQo air quality monitoring network data.

Docs:
- https://docs.airqo.net/airqo-rest-api-documentation/

Notes:
- AirQo uses query param `token` for authentication.
- Measurements endpoints are entity-specific (site/device/grid/cohort).
- Summary endpoints (sites/cohorts/grids) are used to discover `_id` values.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from infrastructure.cache.cache_service import get_cache
from shared.utils.data_formatter import format_air_quality_data
from shared.utils.provider_errors import ProviderServiceError, provider_unavailable_message

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
        from shared.config.settings import get_settings

        settings = get_settings()
        self.api_token = api_token or settings.AIRQO_API_TOKEN
        self.session = requests.Session()
        self.cache_service = get_cache()
        self.cache_ttl = settings.CACHE_TTL_SECONDS

    def _get_headers(self) -> dict[str, str]:
        """Get request headers"""
        return {"Content-Type": "application/json"}

    def _sanitize_token(self, data: Any) -> Any:
        """Remove API tokens from response data to prevent leakage"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key == "token":
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, str) and self.api_token and self.api_token in value:
                    # Replace token in URLs and strings
                    sanitized[key] = value.replace(self.api_token, "[REDACTED]")
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_token(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_token(item) for item in data]
        elif isinstance(data, str) and self.api_token and self.api_token in data:
            return data.replace(self.api_token, "[REDACTED]")
        return data

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        Make authenticated request to AirQo API

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data
        """

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        # Add authentication token to params
        request_params = params.copy() if params else {}
        if self.api_token:
            request_params["token"] = self.api_token

        # Check Redis cache
        cached_data = self.cache_service.get_api_response("airqo", endpoint, request_params)
        if cached_data is not None:
            # Ensure cached data is also sanitized (in case it was cached before sanitization was added)
            return self._sanitize_token(cached_data)

        try:
            response = self.session.get(
                url, headers=self._get_headers(), params=request_params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Sanitize token from response before caching and returning
            sanitized_data = self._sanitize_token(data)

            # Cache the sanitized result in Redis
            self.cache_service.set_api_response(
                "airqo", endpoint, request_params, sanitized_data, self.cache_ttl
            )
            return sanitized_data

        except requests.exceptions.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            body = getattr(getattr(e, "response", None), "text", None)
            logger.warning(
                "AirQo request failed",
                extra={"endpoint": endpoint, "status": status},
            )
            raise ProviderServiceError(
                provider="airqo",
                public_message=provider_unavailable_message("AirQo"),
                internal_message=f"RequestException: {e}; status={status}; body={body}",
                http_status=status,
            ) from e

    def _paginate_skip_limit(
        self,
        endpoint: str,
        params: dict[str, Any],
        items_key: str,
        max_pages: int = 50,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        """Fetch paginated results using AirQo's `skip`/`limit` meta fields.

        Works even when `meta.nextPage` is absent.
        """

        page_params = params.copy()
        page_params.setdefault("skip", 0)
        page_params.setdefault("limit", 100)

        first = self._make_request(endpoint, page_params)
        if not first.get("success"):
            return first

        items = list(first.get(items_key, []) or [])
        meta = first.get("meta", {}) or {}

        total = (
            meta.get("total")
            or meta.get("totalResults")
            or meta.get("total_results")
            or len(items)
        )

        pages_fetched = 1
        while pages_fetched < max_pages:
            if max_items is not None and len(items) >= max_items:
                break

            skip = int(page_params.get("skip", 0))
            limit = int(page_params.get("limit", 0))
            if skip + limit >= int(total):
                break

            page_params["skip"] = skip + limit
            next_page = self._make_request(endpoint, page_params)
            if not next_page.get("success"):
                break

            next_items = next_page.get(items_key, []) or []
            if not next_items:
                break

            items.extend(next_items)
            meta = next_page.get("meta", meta) or meta
            total = (
                meta.get("total")
                or meta.get("totalResults")
                or meta.get("total_results")
                or total
            )
            pages_fetched += 1

        first[items_key] = items if max_items is None else items[:max_items]
        first.setdefault("meta", {})
        first["meta"]["totalResults"] = len(first[items_key])
        first["meta"]["pagesFetched"] = pages_fetched
        return first

    def get_measurements(
        self,
        site_id: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        frequency: str = "hourly",
        limit: int = 100,
        fetch_all: bool = True,
    ) -> dict[str, Any]:
        """
        Get air quality measurements (General endpoint)

        Args:
            site_id: Specific site/location ID
            device_id: Specific device ID
            start_time: Start of time range
            end_time: End of time range
            frequency: Data frequency (hourly, daily, raw)
            limit: Maximum number of records per page
            fetch_all: If True, automatically fetch all pages via pagination (default True)

        Returns:
            Measurements data with PM2.5, PM10, etc.
        """
        if not (site_id or device_id):
            raise ValueError("One of site_id or device_id must be provided")

        # If a time window is provided, use the documented historical endpoints.
        if start_time is not None or end_time is not None:
            return format_air_quality_data(
                self.get_historical_measurements(
                    site_id=site_id,
                    device_id=device_id,
                    start_time=start_time,
                    end_time=end_time,
                    frequency=frequency,
                    limit=max(1, int(limit)),
                    fetch_all=fetch_all,
                ),
                source="airqo",
            )

        # Otherwise use the documented recent endpoints.
        return format_air_quality_data(
            self.get_recent_measurements(
                site_id=site_id,
                device_id=device_id,
                limit=max(1, int(limit)),
                fetch_all=fetch_all,
            ),
            source="airqo",
        )

    def get_historical_measurements(
        self,
        site_id: str | None = None,
        device_id: str | None = None,
        grid_id: str | None = None,
        cohort_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        frequency: str = "hourly",
        limit: int = 1000,
        fetch_all: bool = True,
    ) -> dict[str, Any]:
        """
        Get historical measurements by Site, Device, Grid, or Cohort ID.

        Note: AirQo API only provides historical data for the last 60 days.
        For older data, use the AirQo Analytics platform: https://analytics.airqo.net

        Args:
            site_id: Site ID to get measurements for
            device_id: Device ID to get measurements for
            grid_id: Grid ID to get measurements for
            cohort_id: Cohort ID to get measurements for
            start_time: Start time for historical data
            end_time: End time for historical data
            frequency: Data frequency ('hourly', 'daily', 'raw')
            fetch_all: If True, automatically fetch all pages via pagination (default True)

        Returns:
            Historical measurements data
        """
        params: dict[str, Any] = {"frequency": frequency, "limit": limit, "skip": 0}
        if start_time:
            params["startTime"] = start_time.isoformat()
        if end_time:
            params["endTime"] = end_time.isoformat()

        # Determine the endpoint
        if site_id:
            endpoint = f"devices/measurements/sites/{site_id}/historical"
        elif device_id:
            endpoint = f"devices/measurements/devices/{device_id}/historical"
        elif grid_id:
            endpoint = f"devices/measurements/grids/{grid_id}/historical"
        elif cohort_id:
            endpoint = f"devices/measurements/cohorts/{cohort_id}/historical"
        else:
            raise ValueError("One of site_id, device_id, grid_id, or cohort_id must be provided.")

        try:
            if not fetch_all:
                response = self._make_request(endpoint, params)
                return response

            return self._paginate_skip_limit(endpoint, params, items_key="measurements", max_pages=50)

        except Exception as e:
            error_msg = str(e)
            # Check if this is the "query too old" error
            if "Query too old" in error_msg or "oldest_supported" in error_msg:
                return {
                    "success": False,
                    "error": "Historical data request too old",
                    "message": "AirQo API only provides historical data for the last 60 days. For older data, please use the AirQo Analytics platform.",
                    "analytics_platform_url": "https://analytics.airqo.net",
                    "support_email": "support@airqo.net",
                    "requested_date_range": {
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                        "frequency": frequency,
                    },
                }
            else:
                # Re-raise other errors
                raise

    def get_forecast(
        self,
        site_id: str | None = None,
        device_id: str | None = None,
        city: str | None = None,
        search: str | None = None,
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
                        "message": f"No monitoring sites found for '{search_query}' to generate forecast.",
                    }
            else:
                raise ValueError(
                    "Either site_id, device_id, city, or search must be provided for forecast."
                )

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

    def get_sites_summary(
        self, search: str | None = None, limit: int = 80, fetch_all: bool = True
    ) -> dict[str, Any]:
        """
        Get sites summary - returns detailed site information including online status.
        This is more comprehensive than metadata/sites.
        Supports automatic pagination to fetch all available results.

        Args:
            search: Optional search query to filter sites
            limit: Results per page (default 80)
            fetch_all: If True, automatically fetches all pages via pagination (default True)

        Returns:
            Dictionary with sites array containing detailed site information
        """
        params: dict[str, Any] = {"limit": limit, "skip": 0, "tenant": "airqo", "detailLevel": "summary"}
        if search:
            params["search"] = search

        if not fetch_all:
            return self._make_request("devices/sites/summary", params)

        return self._paginate_skip_limit(
            "devices/sites/summary",
            params,
            items_key="sites",
            max_pages=50,
        )

    def get_grids_summary(
        self, search: str | None = None, limit: int = 80, fetch_all: bool = True
    ) -> dict[str, Any]:
        """
        Get grids summary - returns grids with their associated sites.
        Each grid contains a list of sites with their details.
        Supports automatic pagination to fetch all available results.

        Args:
            search: Optional search query to filter grids
            limit: Results per page (default 80)
            fetch_all: If True, automatically fetches all pages via pagination (default True)

        Returns:
            Dictionary with grids array, each containing sites
        """
        params: dict[str, Any] = {"limit": limit, "skip": 0, "tenant": "airqo", "detailLevel": "summary"}
        if search:
            params["search"] = search

        if not fetch_all:
            return self._make_request("devices/grids/summary", params)

        return self._paginate_skip_limit(
            "devices/grids/summary",
            params,
            items_key="grids",
            max_pages=50,
        )

    def get_cohorts_summary(
        self, search: str | None = None, limit: int = 80, fetch_all: bool = True
    ) -> dict[str, Any]:
        """Get cohorts summary to discover `cohort_id` values (cohorts[*]._id)."""

        params: dict[str, Any] = {"limit": limit, "skip": 0, "tenant": "airqo", "detailLevel": "summary"}
        if search:
            params["search"] = search

        if not fetch_all:
            return self._make_request("devices/cohorts/summary", params)

        return self._paginate_skip_limit(
            "devices/cohorts/summary",
            params,
            items_key="cohorts",
            max_pages=50,
        )

    def get_site_id_by_name(self, name: str, limit: int = 80) -> str | list[str] | None:
        """
        Helper to find Site ID(s) by searching for a name using sites/summary endpoint.
        Uses the proper AirQo API search flow.

        Args:
            name: Location name to search for (e.g., "Gulu University", "Kampala")
            limit: Maximum number of site IDs to return (default 80)

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
        except Exception:
            logger.exception("Error finding site ID", extra={"name": name})
            return None

    def get_grid_id_by_name(self, name: str, limit: int = 80) -> str | list[str] | None:
        """Helper to find Grid ID(s) by searching grids summary (grids[*]._id)."""

        try:
            cache_key = f"grid_id_map:{name.lower()}"
            cached_id = self.cache_service.get("airqo", cache_key)
            if cached_id:
                return cached_id

            response = self.get_grids_summary(search=name, limit=limit)
            if response.get("success") and response.get("grids"):
                grids = response["grids"]
                grid_ids = [g.get("_id") for g in grids if g.get("_id")]
                if grid_ids:
                    self.cache_service.set("airqo", cache_key, grid_ids[0], 3600)
                    return grid_ids[0] if len(grid_ids) == 1 else grid_ids
            return None
        except Exception:
            logger.exception("Error finding grid ID", extra={"name": name})
            return None

    def get_cohort_id_by_name(self, name: str, limit: int = 80) -> str | list[str] | None:
        """Helper to find Cohort ID(s) by searching cohorts summary (cohorts[*]._id)."""

        try:
            cache_key = f"cohort_id_map:{name.lower()}"
            cached_id = self.cache_service.get("airqo", cache_key)
            if cached_id:
                return cached_id

            response = self.get_cohorts_summary(search=name, limit=limit)
            if response.get("success") and response.get("cohorts"):
                cohorts = response["cohorts"]
                cohort_ids = [c.get("_id") for c in cohorts if c.get("_id")]
                if cohort_ids:
                    self.cache_service.set("airqo", cache_key, cohort_ids[0], 3600)
                    return cohort_ids[0] if len(cohort_ids) == 1 else cohort_ids
            return None
        except Exception:
            logger.exception("Error finding cohort ID", extra={"name": name})
            return None

    def get_air_quality_by_location(
        self, latitude: float, longitude: float, limit_sites: int = 3
    ) -> dict[str, Any]:
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
        # Validate coordinates
        if latitude is None or longitude is None:
            return {
                "success": False,
                "message": "Invalid coordinates: latitude and longitude are required",
                "error": "missing_coordinates",
            }

        try:
            # Step 1: Reverse geocode to get city name first
            city_name = self._reverse_geocode(latitude, longitude)

            if city_name:
                sites_response = self.get_sites_summary(search=city_name, limit=limit_sites)

                if sites_response.get("success") and sites_response.get("sites"):
                    sites = sites_response["sites"]
                    site_ids = [site.get("_id") for site in sites if site.get("_id")]

                    if site_ids:
                        # Step 2: Get measurements for the best matching site (bounded)
                        best_site_id = site_ids[0]
                        measurements_data = self.get_recent_measurements(site_id=best_site_id)
                        if measurements_data.get("success"):
                            measurements_data["coordinates"] = {"lat": latitude, "lon": longitude}
                            measurements_data["city_found"] = city_name
                            measurements_data["site_id_used"] = best_site_id
                        return measurements_data

            # Step 2: If reverse geocoding didn't work or no sites found, try coordinate-based search
            location_query = f"{latitude:.4f},{longitude:.4f}"
            sites_response = self.get_sites_summary(search=location_query, limit=limit_sites)

            if sites_response.get("success") and sites_response.get("sites"):
                sites = sites_response["sites"]
                site_ids = [site.get("_id") for site in sites if site.get("_id")]

                if site_ids:
                    best_site_id = site_ids[0]
                    measurements_data = self.get_recent_measurements(site_id=best_site_id)
                    if measurements_data.get("success"):
                        measurements_data["coordinates"] = {"lat": latitude, "lon": longitude}
                        measurements_data["site_id_used"] = best_site_id
                        measurements_data["search_method"] = "coordinates"
                    return measurements_data

            # Step 3: If no sites found, try grid-based search for the region
            grids_response = self.get_grids_summary(search=city_name or location_query, limit=80)

            if grids_response.get("success") and grids_response.get("grids"):
                grids = grids_response["grids"]
                grid_ids = [grid.get("_id") for grid in grids if grid.get("_id")]

                if grid_ids:
                    # Get measurements for first available grid
                    grid_data = self._make_request(
                        f"devices/measurements/grids/{grid_ids[0]}/recent"
                    )

                    if grid_data.get("success"):
                        grid_data["coordinates"] = {"lat": latitude, "lon": longitude}
                        grid_data["city_searched"] = city_name
                        grid_data["grid_used"] = grid_ids[0]
                        grid_data["search_method"] = "grid_fallback"

                    return format_air_quality_data(grid_data, source="airqo")

            # Step 4: No sites or grids found
            return {
                "success": False,
                "message": (
                    f"No AirQo monitoring sites or grids found near coordinates ({latitude:.4f}, {longitude:.4f}). "
                    "AirQo primarily covers East African countries; the coordinates may be outside coverage."
                ),
                "coordinates": {"lat": latitude, "lon": longitude},
                "city_attempted": city_name,
                "search_method": "none_found",
            }

        except ProviderServiceError as e:
            return {
                "success": False,
                "message": e.public_message,
            }
        except Exception:
            return {
                "success": False,
                "message": provider_unavailable_message("AirQo"),
            }

    def get_recent_measurements(
        self,
        site_id: str | None = None,
        device_id: str | None = None,
        grid_id: str | None = None,
        cohort_id: str | None = None,
        country: str = "UG",
        city: str | None = None,
        search: str | None = None,
        limit: int = 1000,
        fetch_all: bool = True,
        max_sites: int = 3,
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
        params: dict[str, Any] = {"limit": limit, "skip": 0}

        # 1) Direct entity IDs (documented endpoints)
        if site_id:
            endpoint = f"devices/measurements/sites/{site_id}/recent"
            data = (
                self._paginate_skip_limit(endpoint, params, "measurements")
                if fetch_all
                else self._make_request(endpoint, params)
            )
            return format_air_quality_data(data, source="airqo")

        if device_id:
            endpoint = f"devices/measurements/devices/{device_id}/recent"
            data = (
                self._paginate_skip_limit(endpoint, params, "measurements")
                if fetch_all
                else self._make_request(endpoint, params)
            )
            return format_air_quality_data(data, source="airqo")

        if grid_id:
            endpoint = f"devices/measurements/grids/{grid_id}/recent"
            data = (
                self._paginate_skip_limit(endpoint, params, "measurements")
                if fetch_all
                else self._make_request(endpoint, params)
            )
            return format_air_quality_data(data, source="airqo")

        if cohort_id:
            endpoint = f"devices/measurements/cohorts/{cohort_id}/recent"
            data = (
                self._paginate_skip_limit(endpoint, params, "measurements")
                if fetch_all
                else self._make_request(endpoint, params)
            )
            return format_air_quality_data(data, source="airqo")

        # 2) Search for sites using city or search parameter
        search_query = search or city
        if search_query:
            try:
                # Use sites/summary endpoint to find matching sites
                sites_response = self.get_sites_summary(search=search_query, limit=80)

                if sites_response.get("success") and sites_response.get("sites"):
                    sites = sites_response["sites"]

                    # Extract site IDs from matching sites
                    site_ids = [site.get("_id") for site in sites if site.get("_id")]

                    if site_ids:
                        # Bounded multi-site fetch to avoid overload.
                        selected_sites = sites[: max(1, min(max_sites, 10))]
                        aggregated: list[dict[str, Any]] = []

                        for site in selected_sites:
                            sid = site.get("_id")
                            if not sid:
                                continue
                            endpoint = f"devices/measurements/sites/{sid}/recent"
                            site_data = (
                                self._paginate_skip_limit(endpoint, params, "measurements")
                                if fetch_all
                                else self._make_request(endpoint, params)
                            )
                            if site_data.get("success") and site_data.get("measurements"):
                                aggregated.extend(site_data.get("measurements", []))

                        result = {
                            "success": bool(aggregated),
                            "message": "successfully returned the measurements" if aggregated else "No measurements found",
                            "meta": {"sitesQueried": len(selected_sites), "totalResults": len(aggregated)},
                            "measurements": aggregated,
                            "search_location": search_query,
                        }
                        return format_air_quality_data(result, source="airqo")

                # If no sites found, return helpful error with coverage info
                return {
                    "success": False,
                    "message": (
                        f"No AirQo monitoring sites found for '{search_query}'. "
                        "Try WAQI or OpenMeteo for wider geographic coverage."
                    ),
                    "location_searched": search_query,
                    "sites": [],
                }
            except Exception as e:
                logger.error(f"Error searching AirQo sites for {search_query}: {e}")
                return {
                    "success": False,
                    "message": provider_unavailable_message("AirQo"),
                    "location_searched": search_query,
                }

        raise ValueError(
            "Must provide site_id, device_id, grid_id, cohort_id, city, or search parameter."
        )

    def get_multiple_cities_air_quality(self, cities: list[str]) -> dict[str, Any]:
        """
        Get air quality data for multiple cities simultaneously.

        Args:
            cities: List of city names

        Returns:
            Dictionary with air quality data for each city
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, Any] = {}
        cities_limited = cities[:50]  # safety cap

        def fetch_city(city_name: str) -> dict[str, Any]:
            try:
                return self.get_recent_measurements(city=city_name)
            except ProviderServiceError as e:
                return {"success": False, "message": e.public_message}
            except Exception:
                return {"success": False, "message": provider_unavailable_message("AirQo")}

        with ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(fetch_city, c): c for c in cities_limited}
            for fut in as_completed(future_map):
                city_name = future_map[fut]
                try:
                    results[city_name] = fut.result()
                except Exception:
                    results[city_name] = {"success": False, "message": provider_unavailable_message("AirQo")}

        return {"success": True, "cities": results, "count": len(results), "source": "airqo"}

    def search_sites_by_location(self, location: str, limit: int = 80) -> dict[str, Any]:
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
                "sites": [],
            }
        except Exception:
            return {
                "success": False,
                "message": provider_unavailable_message("AirQo"),
                "sites": [],
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

    def _reverse_geocode(self, latitude: float, longitude: float) -> str | None:
        """
        Reverse geocode coordinates to get city name using OpenStreetMap Nominatim API
        """
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params: dict[str, Any] = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "zoom": 10,
            }  # City level
            headers = {"User-Agent": "AirQoAgent/1.0"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and "address" in data:
                    address = data["address"]
                    # Try to get city name from various possible fields, preferring cleaner names
                    city = (
                        address.get("city")
                        or address.get("town")
                        or address.get("village")
                        or address.get("municipality")
                        or address.get("county")
                    )
                    # Clean up the city name by removing qualifiers like "Capital City"
                    if city:
                        city = city.replace(" Capital City", "").replace(" City", "").strip()
                    return city
        except Exception as e:
            print(f"Error reverse geocoding coordinates ({latitude}, {longitude}): {e}")
        return None
