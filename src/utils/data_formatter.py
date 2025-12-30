"""
Data formatting utilities for accurate and consistent data presentation
"""

from typing import Any


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
    Preserves exact API values, formats to 1 decimal place.
    
    Args:
        data: Raw air quality data from API
        source: Data source name (waqi, airqo)
    
    Returns:
        Formatted data dictionary
    """
    formatted = data.copy()
    
    # Format numeric fields commonly found in air quality data
    numeric_fields = [
        "aqi", "pm25", "pm10", "no2", "so2", "o3", "co",
        "temperature", "humidity", "pressure", "wind_speed",
        "value", "pm2_5", "pm2.5", "standard_pm2_5", "calibrated_pm2_5"
    ]
    
    def format_nested(obj: Any) -> Any:
        """Recursively format nested structures"""
        if isinstance(obj, dict):
            return {k: format_nested(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [format_nested(item) for item in obj]
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            # Only format if it's a reasonable air quality value
            if -100 <= obj <= 10000:  # Reasonable range for AQ data
                return float(format_number(obj, 1))
            return obj
        return obj
    
    # Process specific fields if they exist
    if "data" in formatted and isinstance(formatted["data"], dict):
        formatted["data"] = format_nested(formatted["data"])
    
    # Format top-level measurements
    if "measurements" in formatted and isinstance(formatted["measurements"], list):
        formatted["measurements"] = format_nested(formatted["measurements"])
    
    # Add metadata
    formatted["_formatted"] = True
    formatted["_source"] = source
    formatted["_accuracy_note"] = "Values formatted to 1 decimal place from exact API data"
    
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
