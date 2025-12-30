import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Service for fetching weather data using Open-Meteo API (Free, no key required).
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def get_coordinates(self, city: str) -> dict[str, float] | None:
        """Get coordinates for a city name."""
        try:
            params = {"name": city, "count": 1, "language": "en", "format": "json"}
            response = requests.get(self.GEOCODING_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("results"):
                return None

            result = data["results"][0]
            return {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "name": result["name"],
                "country": result.get("country", ""),
            }
        except Exception as e:
            logger.error(f"Error fetching coordinates for {city}: {e}")
            return None

    def get_current_weather(self, city: str) -> dict[str, Any]:
        """Get current weather for a city."""
        coords = self.get_coordinates(city)
        if not coords:
            return {"error": f"Could not find coordinates for city: {city}"}

        try:
            params = {
                "latitude": coords["latitude"],
                "longitude": coords["longitude"],
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "rain",
                    "weather_code",
                    "wind_speed_10m",
                ],
                "timezone": "auto",
            }

            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            units = data.get("current_units", {})

            return {
                "location": f"{coords['name']}, {coords['country']}",
                "temperature": f"{current.get('temperature_2m')} {units.get('temperature_2m')}",
                "feels_like": f"{current.get('apparent_temperature')} {units.get('apparent_temperature')}",
                "humidity": f"{current.get('relative_humidity_2m')} {units.get('relative_humidity_2m')}",
                "wind_speed": f"{current.get('wind_speed_10m')} {units.get('wind_speed_10m')}",
                "precipitation": f"{current.get('precipitation')} {units.get('precipitation')}",
                "condition_code": current.get("weather_code"),
            }

        except Exception as e:
            logger.error(f"Error fetching weather for {city}: {e}")
            return {"error": str(e)}
