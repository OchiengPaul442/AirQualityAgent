"""
Geocoding Service

Provides geocoding functionality using OpenStreetMap Nominatim API.
Free geocoding service with no API key required.
"""

import logging
from typing import Any, Dict, Optional

import requests

from .cache import get_cache

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and reverse geocoding coordinates."""

    BASE_URL = "https://nominatim.openstreetmap.org"

    def __init__(self):
        """Initialize geocoding service."""
        self.session = requests.Session()
        # Set user agent as required by Nominatim
        self.session.headers.update({
            'User-Agent': 'Aeris-AirQualityAgent/1.0'
        })
        self.cache_service = get_cache()

    def geocode_address(self, address: str, limit: int = 1) -> Dict[str, Any]:
        """
        Geocode an address to coordinates.

        Args:
            address: The address to geocode
            limit: Maximum number of results to return

        Returns:
            Dict containing geocoding results with success/message format
        """
        try:
            params = {
                'q': address,
                'format': 'json',
                'limit': limit,
                'addressdetails': 1,
                'extratags': 1
            }

            response = self.session.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if not data:
                return {"success": False, "message": "No results found for the given address"}

            # Return the first result
            result = data[0]
            return {
                "success": True,
                "message": "Address geocoded successfully",
                "latitude": float(result.get("lat", 0)),
                "longitude": float(result.get("lon", 0)),
                "display_name": result.get("display_name", ""),
                "address": result.get("address", {}),
                "importance": result.get("importance", 0),
                "type": result.get("type", ""),
                "class": result.get("class", "")
            }

        except requests.RequestException as e:
            logger.error(f"Geocoding request failed: {e}")
            return {"success": False, "message": f"Geocoding service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return {"success": False, "message": f"Failed to geocode address: {str(e)}"}

    def reverse_geocode(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Reverse geocode coordinates to address.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Dict containing reverse geocoding results with success/message format
        """
        try:
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1,
                'extratags': 1
            }

            response = self.session.get(
                f"{self.BASE_URL}/reverse",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if not data or 'error' in data:
                return {"success": False, "message": "No address found for the given coordinates"}

            return {
                "success": True,
                "message": "Coordinates reverse geocoded successfully",
                "display_name": data.get("display_name", ""),
                "address": data.get("address", {}),
                "latitude": float(data.get("lat", latitude)),
                "longitude": float(data.get("lon", longitude)),
                "type": data.get("type", ""),
                "class": data.get("class", "")
            }

        except requests.RequestException as e:
            logger.error(f"Reverse geocoding request failed: {e}")
            return {"success": False, "message": f"Reverse geocoding service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            return {"success": False, "message": f"Failed to reverse geocode coordinates: {str(e)}"}

    def get_location_from_ip(self, ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get location information from IP address using free IP geolocation API.

        Args:
            ip_address: IP address to geolocate (optional, uses caller's IP if not provided)

        Returns:
            Dict containing location information with success/message format
        """
        try:
            # Using freeipapi.com for IP geolocation
            url = "https://freeipapi.com/api/json"
            if ip_address:
                url += f"/{ip_address}"

            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Validate the response
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            country_name = data.get("countryName")
            city = data.get("city")

            # Check if we got valid coordinates
            if not latitude or not longitude:
                return {"success": False, "message": "Unable to determine location from IP address"}

            # Check if coordinates are reasonable (not null island or obviously wrong)
            if latitude == 0.0 and longitude == 0.0:
                return {"success": False, "message": "IP address does not provide valid location data"}

            # Check if this looks like a datacenter/server location
            # Many cloud providers have specific IP ranges that might not represent user location
            if not city and not country_name:
                return {"success": False, "message": "IP address location data is incomplete or from a server"}

            result = {
                "success": True,
                "message": "Location determined from IP address (approximate)",
                "ip": data.get("ip"),
                "country_name": country_name,
                "country_code": data.get("countryCode"),
                "city": city,
                "region": data.get("regionName"),
                "latitude": latitude,
                "longitude": longitude,
                "zip_code": data.get("zipCode"),
                "time_zone": data.get("timeZone"),
                "isp": data.get("isp")
            }

            return result

        except requests.RequestException as e:
            logger.error(f"IP geolocation request failed: {e}")
            return {"success": False, "message": f"IP geolocation service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"IP geolocation error: {e}")
            return {"success": False, "message": f"Failed to get location from IP: {str(e)}"}