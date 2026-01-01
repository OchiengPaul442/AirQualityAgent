"""
Data formatting utilities for accurate and consistent data presentation
"""

from typing import Any, Dict


def format_number(value: Any, decimal_places: int = 1) -> str:
    """
    Format numeric value to specified decimal places.
    Returns original if not a number.

    Args:
        value: The value to format
        decimal_places: Number of decimal places (default: 1)

    Returns:
        Formatted string or original value
    """
    try:
        if value is None or value == "-":
            return "-"

        # Convert to float
        num = float(value)

        # Format to specified decimal places
        return f"{num:.{decimal_places}f}"
    except (ValueError, TypeError):
        return str(value)


def format_air_quality_data(data: dict[str, Any], source: str = "unknown") -> dict[str, Any]:
    """
    Format air quality data to ensure accuracy and consistency.
    CRITICAL: Properly distinguishes between AQI values and concentration values.

    WAQI API IMPORTANT NOTE:
    - WAQI returns AQI values, NOT concentration values
    - iaqi.pm25.v is the PM2.5 AQI (0-500 scale), NOT µg/m³ concentration
    - We must convert these AQI values to concentrations for accurate reporting

    AirQo API IMPORTANT NOTE:
    - AirQo returns actual concentration values in µg/m³
    - pm2_5.value is the actual PM2.5 concentration in µg/m³

    Args:
        data: Raw air quality data from API
        source: Data source name (waqi, airqo, openmeteo)

    Returns:
        Formatted data dictionary with proper AQI and concentration values
    """
    from .aqi_converter import format_pollutant_value, parse_waqi_value

    formatted = data.copy()

    # Handle WAQI data specifically - their values are AQI, not concentrations
    if source == "waqi" and "data" in formatted:
        waqi_data = formatted["data"]

        # Process iaqi (individual pollutant AQI values)
        if "iaqi" in waqi_data and isinstance(waqi_data["iaqi"], dict):
            pollutant_info = {}

            for pollutant, value_obj in waqi_data["iaqi"].items():
                if isinstance(value_obj, dict) and "v" in value_obj:
                    aqi_value = value_obj["v"]

                    # Skip non-pollutant fields
                    if pollutant in ["pm25", "pm10", "o3", "no2", "so2", "co"]:
                        # Parse the AQI value and convert to concentration
                        parsed = parse_waqi_value(aqi_value, pollutant, return_both=True)
                        pollutant_info[pollutant] = {
                            "aqi": parsed["aqi"],
                            "concentration_ugm3": parsed.get("concentration_estimated_ugm3"),
                            "category": parsed["category"],
                            "color": parsed["color"],
                            "note": "WAQI provides AQI values. Concentration estimated using EPA conversion.",
                        }

            # Add enriched pollutant information
            if pollutant_info:
                formatted["data"]["pollutant_details"] = pollutant_info
                formatted["data"][
                    "_data_type_note"
                ] = "WAQI API returns AQI values, not raw concentrations. Concentrations are estimated using EPA AQI breakpoints."

    # Handle AirQo data - their values ARE concentrations
    elif source == "airqo" and "measurements" in formatted:
        for measurement in formatted.get("measurements", []):
            if isinstance(measurement, dict):
                # AirQo gives us actual concentrations
                if "pm2_5" in measurement and isinstance(measurement["pm2_5"], dict):
                    pm25_value = measurement["pm2_5"].get("value")
                    if pm25_value is not None:
                        # This is a concentration, calculate AQI from it
                        formatted_pm25 = format_pollutant_value(
                            pm25_value, "pm25", data_type="concentration", include_aqi=True
                        )
                        measurement["pm2_5"]["value"] = formatted_pm25["concentration"]
                        measurement["pm2_5"]["unit"] = formatted_pm25["unit"]
                        measurement["pm2_5"]["aqi"] = formatted_pm25.get("aqi")
                        measurement["pm2_5"]["category"] = formatted_pm25.get("category")
                        measurement["pm2_5"]["data_type"] = "concentration"

                if "pm10" in measurement and isinstance(measurement["pm10"], dict):
                    pm10_value = measurement["pm10"].get("value")
                    if pm10_value is not None:
                        formatted_pm10 = format_pollutant_value(
                            pm10_value, "pm10", data_type="concentration", include_aqi=True
                        )
                        measurement["pm10"]["value"] = formatted_pm10["concentration"]
                        measurement["pm10"]["unit"] = formatted_pm10["unit"]
                        measurement["pm10"]["aqi"] = formatted_pm10.get("aqi")
                        measurement["pm10"]["category"] = formatted_pm10.get("category")
                        measurement["pm10"]["data_type"] = "concentration"

        formatted["_data_type_note"] = "AirQo API returns actual pollutant concentrations in µg/m³"

    # Handle OpenMeteo data - their values ARE also concentrations
    elif source == "openmeteo":
        formatted["_data_type_note"] = (
            "OpenMeteo API returns actual pollutant concentrations in µg/m³"
        )

        # Process current data if present
        if "current" in formatted and isinstance(formatted["current"], dict):
            current = formatted["current"]

            # PM2.5
            if "pm2_5" in current and current["pm2_5"] is not None:
                pm25_value = current["pm2_5"]
                formatted_pm25 = format_pollutant_value(
                    pm25_value, "pm25", data_type="concentration", include_aqi=True
                )
                current["pm2_5_concentration"] = formatted_pm25["concentration"]
                current["pm2_5_unit"] = formatted_pm25["unit"]
                current["pm2_5_aqi"] = formatted_pm25.get("aqi")
                current["pm2_5_category"] = formatted_pm25.get("category")

            # PM10
            if "pm10" in current and current["pm10"] is not None:
                pm10_value = current["pm10"]
                formatted_pm10 = format_pollutant_value(
                    pm10_value, "pm10", data_type="concentration", include_aqi=True
                )
                current["pm10_concentration"] = formatted_pm10["concentration"]
                current["pm10_unit"] = formatted_pm10["unit"]
                current["pm10_aqi"] = formatted_pm10.get("aqi")
                current["pm10_category"] = formatted_pm10.get("category")

        # Process hourly forecast data if present
        if "hourly" in formatted and isinstance(formatted["hourly"], dict):
            hourly = formatted["hourly"]

            # Add note that these are concentrations
            if "pm2_5" in hourly or "pm10" in hourly:
                formatted["_hourly_note"] = "Hourly values are pollutant concentrations in µg/m³"

    # Format numeric fields (temperature, humidity, etc.)
    numeric_fields = ["temperature", "humidity", "pressure", "wind_speed", "dew", "w"]

    def format_nested(obj: Any) -> Any:
        """Recursively format nested structures (for weather data, not pollutants)"""
        if isinstance(obj, dict):
            return {k: format_nested(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [format_nested(item) for item in obj]
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            # Only format if it's a reasonable weather/environmental value
            if -100 <= obj <= 10000:
                return float(format_number(obj, 1))
            return obj
        return obj

    # Add metadata
    formatted["_formatted"] = True
    formatted["_source"] = source

    return formatted


def round_to_decimal(value: Any, places: int = 1) -> Any:
    """
    Round numeric value to specified decimal places.
    Returns original if not numeric.

    Args:
        value: Value to round
        places: Decimal places

    Returns:
        Rounded value or original
    """
    try:
        if value is None or value == "-":
            return value
        num = float(value)
        return round(num, places)
    except (ValueError, TypeError):
        return value
