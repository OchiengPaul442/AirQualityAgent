import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from src.config import Settings

from .cache import get_cache

logger = logging.getLogger(__name__)


class UbaService:
    """
    Service for German Federal Environment Agency (UBA) air quality data.
    Provides access to real-time and historical air quality measurements from German monitoring stations.
    """

    BASE_URL = "https://www.umweltbundesamt.de/api/air_data/v2"

    def __init__(self):
        self.settings = Settings()
        self.session = requests.Session()
        self.cache = get_cache()

    def get_measures(self, component: str | None = None, scope: str = "24h") -> dict[str, Any]:
        """
        Get air quality measurements from UBA API.

        Args:
            component: Pollutant component (optional, returns all if not specified)
            scope: Geographic scope: '1h' (1 hour), '24h' (24 hours), 'd' (daily)

        Returns:
            Formatted air quality data
        """
        # Map scope parameter to UBA API scope
        scope_map = {
            "1h": 1,   # 1 hour
            "24h": 2,  # 24 hours
            "d": 3     # daily
        }

        api_scope = scope_map.get(scope, 2)  # Default to 24 hours

        cache_key = f"uba_measures_{component or 'all'}_{scope}"

        # Check cache first
        cached_data = self.cache.get_api_response("uba", "measures", {
            "component": component,
            "scope": scope
        })
        if cached_data:
            logger.info("Retrieved UBA data from cache")
            return cached_data

        try:
            url = f"{self.BASE_URL}/measures/json"
            # UBA API requires date parameters
            now = datetime.now()
            date_from = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            time_from = "00:00"
            date_to = now.strftime("%Y-%m-%d")
            time_to = now.strftime("%H:%M")

            params = {
                "scope": api_scope,
                "date_from": date_from,
                "time_from": time_from,
                "date_to": date_to,
                "time_to": time_to,
                "lang": "en"
            }

            # Add component filter if specified
            if component:
                # Map component names to UBA component IDs
                component_map = {
                    "NO2": 2,
                    "PM10": 6,
                    "O3": 3,
                    "SO2": 1,
                    "CO": 4
                }
                if component.upper() in component_map:
                    params["component"] = component_map[component.upper()]

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Format the data
            formatted_data = self._format_measures_data(data)

            # Cache for 30 minutes
            self.cache.set_api_response("uba", "measures", {
                "component": component,
                "scope": scope
            }, formatted_data, ttl=1800)

            logger.info("Successfully retrieved UBA measures data")
            return formatted_data

        except Exception as e:
            logger.error(f"Error fetching UBA measures data: {e}")
            return {"error": f"Failed to fetch UBA data: {str(e)}"}

    def get_stations(self) -> dict[str, Any]:
        """
        Get list of available monitoring stations.

        Returns:
            List of monitoring stations
        """
        cache_key = "uba_stations"

        # Check cache first
        cached_data = self.cache.get_api_response("uba", "stations", {})
        if cached_data:
            logger.info("Retrieved UBA stations from cache")
            return cached_data

        try:
            url = f"{self.BASE_URL}/stations/json"
            params = {"lang": "en"}

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Format the data
            formatted_data = self._format_stations_data(data)

            # Cache for 24 hours (stations don't change often)
            self.cache.set_api_response("uba", "stations", {}, formatted_data, ttl=86400)

            logger.info("Successfully retrieved UBA stations data")
            return formatted_data

        except Exception as e:
            logger.error(f"Error fetching UBA stations data: {e}")
            return {"error": f"Failed to fetch UBA stations: {str(e)}"}

    def _format_measures_data(self, raw_data: dict) -> dict[str, Any]:
        """
        Format raw UBA measures API response.

        Args:
            raw_data: Raw API response

        Returns:
            Formatted data
        """
        try:
            formatted_stations = {}

            if "data" in raw_data:
                for station_id, station_data in raw_data["data"].items():
                    if isinstance(station_data, dict):
                        measurements = []
                        for timestamp, values in station_data.items():
                            if isinstance(values, list) and len(values) >= 4:
                                component_id = values[0]
                                scope_id = values[1]
                                pollutant_value = values[2]
                                index = values[4] if len(values) > 4 else None

                                if pollutant_value is not None:
                                    measurements.append({
                                        "timestamp": timestamp,
                                        "component_id": component_id,
                                        "pollutant": self._get_pollutant_name(component_id),
                                        "value": float(pollutant_value),
                                        "unit": self._get_unit_for_component(component_id),
                                        "index": index
                                    })

                        if measurements:
                            # Calculate statistics
                            values_list = [m["value"] for m in measurements]
                            formatted_stations[station_id] = {
                                "station_id": station_id,
                                "measurements": measurements,
                                "statistics": {
                                    "average": round(sum(values_list) / len(values_list), 2),
                                    "maximum": max(values_list),
                                    "minimum": min(values_list),
                                    "count": len(measurements)
                                }
                            }

            return {
                "source": "German UBA",
                "timestamp": datetime.now().isoformat(),
                "stations": formatted_stations,
                "total_stations": len(formatted_stations)
            }

        except Exception as e:
            logger.error(f"Error formatting UBA measures data: {e}")
            return {"error": f"Failed to format UBA data: {str(e)}"}

    def _format_stations_data(self, raw_data: dict) -> dict[str, Any]:
        """
        Format raw UBA stations API response.

        Args:
            raw_data: Raw API response

        Returns:
            Formatted stations data
        """
        try:
            stations = []

            if "data" in raw_data:
                for station_id, station_info in raw_data["data"].items():
                    if isinstance(station_info, dict):
                        stations.append({
                            "id": station_id,
                            "name": station_info.get("name", ""),
                            "latitude": station_info.get("latitude"),
                            "longitude": station_info.get("longitude"),
                            "altitude": station_info.get("altitude"),
                            "type": station_info.get("type", ""),
                            "network": station_info.get("network", "")
                        })

            return {
                "source": "German UBA",
                "timestamp": datetime.now().isoformat(),
                "stations": stations,
                "total_stations": len(stations)
            }

        except Exception as e:
            logger.error(f"Error formatting UBA stations data: {e}")
            return {"error": f"Failed to format UBA stations: {str(e)}"}

    def _get_pollutant_name(self, component_id: int) -> str:
        """Get human-readable pollutant name from component ID."""
        names = {
            1: "Sulfur Dioxide (SO2)",
            2: "Nitrogen Dioxide (NO2)",
            3: "Ozone (O3)",
            4: "Carbon Monoxide (CO)",
            5: "Benzene (C6H6)",
            6: "Particulate Matter PM10",
            7: "Particulate Matter PM2.5",
            8: "Arsenic (As)",
            9: "Cadmium (Cd)",
            10: "Nickel (Ni)",
            11: "Benz(a)pyrene (B(a)P)"
        }
        return names.get(component_id, f"Component {component_id}")

    def _get_unit_for_component(self, component_id: int) -> str:
        """Get measurement unit for component."""
        # Most pollutants are measured in µg/m³, CO in mg/m³
        if component_id == 4:  # CO
            return "mg/m³"
        return "µg/m³"
