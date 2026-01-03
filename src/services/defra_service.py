import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from src.config import Settings

from .cache import get_cache

logger = logging.getLogger(__name__)


class DefraService:
    """
    Service for UK DEFRA air quality data.
    Provides access to real-time and historical air quality measurements from UK monitoring stations.
    """

    BASE_URL = "https://uk-air.defra.gov.uk"

    def __init__(self):
        self.settings = Settings()
        self.session = requests.Session()
        self.cache = get_cache()

    def get_station_data(self, site_id: str, species_code: str = "PM25",
                        start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """
        Get air quality data for a specific monitoring station.

        Args:
            site_id: DEFRA site identifier (e.g., "ABD", "ABD7")
            species_code: Pollutant code (PM25, PM10, NO2, SO2, O3, CO)
            start_date: Start date in YYYY-MM-DD format (default: yesterday)
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            Formatted air quality data
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        cache_key = f"defra_{site_id}_{species_code}_{start_date}_{end_date}"

        # Check cache first
        cached_data = self.cache.get_api_response("defra", f"site-data/{site_id}", {
            "species_code": species_code,
            "start_date": start_date,
            "end_date": end_date
        })
        if cached_data:
            logger.info(f"Retrieved DEFRA data from cache for site {site_id}")
            return cached_data

        try:
            url = f"{self.BASE_URL}/data/site-data"
            params = {
                "site_id": site_id,
                "species_code": species_code,
                "start_date": start_date,
                "end_date": end_date
            }

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Format the data
            formatted_data = self._format_station_data(data, site_id, species_code)

            # Cache for 1 hour
            self.cache.set_api_response("defra", f"site-data/{site_id}", {
                "species_code": species_code,
                "start_date": start_date,
                "end_date": end_date
            }, formatted_data, ttl=3600)

            logger.info(f"Successfully retrieved DEFRA data for site {site_id}")
            return formatted_data

        except Exception as e:
            logger.error(f"Error fetching DEFRA data for site {site_id}: {e}")
            return {"error": f"Failed to fetch DEFRA data: {str(e)}"}

    def get_multiple_stations(self, site_ids: list[str], species_code: str = "PM25",
                            start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """
        Get air quality data for multiple monitoring stations.

        Args:
            site_ids: List of DEFRA site identifiers
            species_code: Pollutant code
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Combined data from multiple stations
        """
        results = {}
        for site_id in site_ids:
            try:
                data = self.get_station_data(site_id, species_code, start_date, end_date)
                if data and "error" not in data:
                    results[site_id] = data
            except Exception as e:
                logger.warning(f"Failed to get data for site {site_id}: {e}")
                continue

        return {
            "source": "UK DEFRA",
            "timestamp": datetime.now().isoformat(),
            "stations": results,
            "total_stations": len(results)
        }

    def _format_station_data(self, raw_data: dict, site_id: str, species_code: str) -> dict[str, Any]:
        """
        Format raw DEFRA API response into standardized format.

        Args:
            raw_data: Raw API response
            site_id: Station identifier
            species_code: Pollutant code

        Returns:
            Formatted data
        """
        try:
            # DEFRA API returns data in a specific format
            # Extract measurements from the response
            measurements = []

            if "data" in raw_data and isinstance(raw_data["data"], list):
                for entry in raw_data["data"]:
                    if isinstance(entry, dict) and len(entry) >= 2:
                        timestamp = list(entry.keys())[0]
                        values = list(entry.values())[0]

                        if isinstance(values, list) and len(values) >= 2:
                            value = values[1]  # Measurement value
                            if value is not None:
                                measurements.append({
                                    "timestamp": timestamp,
                                    "value": float(value),
                                    "unit": self._get_unit_for_species(species_code)
                                })

            # Calculate statistics
            if measurements:
                values = [m["value"] for m in measurements]
                stats = {
                    "average": round(sum(values) / len(values), 2),
                    "maximum": max(values),
                    "minimum": min(values),
                    "count": len(measurements)
                }
            else:
                stats = {"average": None, "maximum": None, "minimum": None, "count": 0}

            return {
                "source": "UK DEFRA",
                "station_id": site_id,
                "pollutant": species_code,
                "pollutant_name": self._get_pollutant_name(species_code),
                "unit": self._get_unit_for_species(species_code),
                "measurements": measurements,
                "statistics": stats,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error formatting DEFRA data: {e}")
            return {"error": f"Failed to format DEFRA data: {str(e)}"}

    def _get_pollutant_name(self, species_code: str) -> str:
        """Get human-readable pollutant name."""
        names = {
            "PM25": "PM2.5",
            "PM10": "PM10",
            "NO2": "Nitrogen Dioxide",
            "SO2": "Sulphur Dioxide",
            "O3": "Ozone",
            "CO": "Carbon Monoxide",
            "NOX": "Nitrogen Oxides"
        }
        return names.get(species_code, species_code)

    def _get_unit_for_species(self, species_code: str) -> str:
        """Get measurement unit for pollutant."""
        units = {
            "PM25": "µg/m³",
            "PM10": "µg/m³",
            "NO2": "µg/m³",
            "SO2": "µg/m³",
            "O3": "µg/m³",
            "CO": "mg/m³",
            "NOX": "µg/m³"
        }
        return units.get(species_code, "µg/m³")

    def get_sites(self) -> dict[str, Any]:
        """
        Get list of available DEFRA monitoring sites.
        
        Note: DEFRA does not provide a public API endpoint for listing all sites.
        This method returns a curated list of major monitoring sites based on 
        DEFRA's public data. For a complete list, users should check the DEFRA website.
        
        Returns:
            Dictionary containing site information
        """
        # Curated list of major DEFRA monitoring sites
        # Based on DEFRA's public monitoring network data
        sites = [
            # London and South East
            {"code": "LON1", "name": "London Bloomsbury", "region": "London", "type": "Urban Background"},
            {"code": "LON6", "name": "London Eltham", "region": "London", "type": "Suburban"},
            {"code": "LON7", "name": "London Hillingdon", "region": "London", "type": "Urban Background"},
            {"code": "LON8", "name": "London N. Kensington", "region": "London", "type": "Urban Background"},
            {"code": "LON9", "name": "London Westminster", "region": "London", "type": "Urban Background"},

            # North West England
            {"code": "MAN3", "name": "Manchester Piccadilly", "region": "North West", "type": "Urban Background"},
            {"code": "LIV1", "name": "Liverpool Speke", "region": "North West", "type": "Urban Background"},

            # West Midlands
            {"code": "BIR1", "name": "Birmingham Centre", "region": "West Midlands", "type": "Urban Background"},
            {"code": "BIR3", "name": "Birmingham Tyburn", "region": "West Midlands", "type": "Urban Background"},

            # Yorkshire and Humber
            {"code": "LEED", "name": "Leeds Centre", "region": "Yorkshire", "type": "Urban Background"},
            {"code": "SHE1", "name": "Sheffield Tinsley", "region": "Yorkshire", "type": "Urban Background"},

            # Scotland
            {"code": "GLA4", "name": "Glasgow Centre", "region": "Scotland", "type": "Urban Background"},
            {"code": "EDI1", "name": "Edinburgh St Leonards", "region": "Scotland", "type": "Urban Background"},

            # Wales
            {"code": "CAR1", "name": "Cardiff Centre", "region": "Wales", "type": "Urban Background"},
            {"code": "SWA1", "name": "Swansea", "region": "Wales", "type": "Urban Background"},

            # South West
            {"code": "BRI1", "name": "Bristol St Pauls", "region": "South West", "type": "Urban Background"},
            {"code": "PLY1", "name": "Plymouth Centre", "region": "South West", "type": "Urban Background"},

            # East of England
            {"code": "CAM1", "name": "Cambridge Centre", "region": "East of England", "type": "Urban Background"},
            {"code": "NOR1", "name": "Norwich Lakenfields", "region": "East of England", "type": "Urban Background"},

            # South East (non-London)
            {"code": "BHT1", "name": "Brighton Preston Park", "region": "South East", "type": "Urban Background"},
            {"code": "SOU1", "name": "Southampton Centre", "region": "South East", "type": "Urban Background"},

            # East Midlands
            {"code": "NOT1", "name": "Nottingham Centre", "region": "East Midlands", "type": "Urban Background"},
            {"code": "LEI1", "name": "Leicester Centre", "region": "East Midlands", "type": "Urban Background"},

            # North East
            {"code": "NCA1", "name": "Newcastle Centre", "region": "North East", "type": "Urban Background"},
            {"code": "MID1", "name": "Middlesbrough", "region": "North East", "type": "Urban Background"},
        ]

        return {
            "source": "UK DEFRA",
            "sites": sites,
            "total_sites": len(sites),
            "timestamp": datetime.now().isoformat(),
            "note": "This is a curated list of major DEFRA monitoring sites. DEFRA does not provide a public API for site discovery. For the complete list, visit https://uk-air.defra.gov.uk/networks/site-info"
        }

    def get_species_codes(self) -> dict[str, Any]:
        """
        Get list of pollutant species codes used by DEFRA.
        """
        species = [
            {"code": "PM25", "name": "PM2.5", "unit": "µg/m³"},
            {"code": "PM10", "name": "PM10", "unit": "µg/m³"},
            {"code": "NO2", "name": "Nitrogen Dioxide", "unit": "µg/m³"},
            {"code": "SO2", "name": "Sulphur Dioxide", "unit": "µg/m³"},
            {"code": "O3", "name": "Ozone", "unit": "µg/m³"},
            {"code": "CO", "name": "Carbon Monoxide", "unit": "mg/m³"},
            {"code": "NOX", "name": "Nitrogen Oxides", "unit": "µg/m³"},
        ]

        return {
            "source": "UK DEFRA",
            "species": species,
            "total_species": len(species),
            "timestamp": datetime.now().isoformat()
        }
