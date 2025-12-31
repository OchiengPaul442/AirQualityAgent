"""
AQI Conversion Utilities

Converts between AQI (Air Quality Index) and pollutant concentrations (µg/m³).
Uses US EPA AQI breakpoints (updated May 2024).

References:
- EPA AQI Calculator: https://www.airnow.gov/aqi/aqi-calculator/
- EPA Technical Assistance Document: https://www.epa.gov/sites/default/files/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf
- WAQI API Documentation: https://aqicn.org/api/
"""

from typing import Dict, Optional, Tuple

# US EPA AQI Breakpoints (Updated May 6, 2024)
# Format: (AQI_low, AQI_high, Conc_low, Conc_high, Category, Color)
PM25_BREAKPOINTS = [
    (0, 50, 0.0, 9.0, "Good", "Green"),
    (51, 100, 9.1, 35.4, "Moderate", "Yellow"),
    (101, 150, 35.5, 55.4, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 55.5, 125.4, "Unhealthy", "Red"),
    (201, 300, 125.5, 225.4, "Very Unhealthy", "Purple"),
    (301, 400, 225.5, 325.4, "Hazardous", "Maroon"),
    (401, 500, 325.5, 500.4, "Hazardous", "Maroon"),
]

PM10_BREAKPOINTS = [
    (0, 50, 0, 54, "Good", "Green"),
    (51, 100, 55, 154, "Moderate", "Yellow"),
    (101, 150, 155, 254, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 255, 354, "Unhealthy", "Red"),
    (201, 300, 355, 424, "Very Unhealthy", "Purple"),
    (301, 400, 425, 504, "Hazardous", "Maroon"),
    (401, 500, 505, 604, "Hazardous", "Maroon"),
]

O3_8HR_BREAKPOINTS = [
    (0, 50, 0, 54, "Good", "Green"),
    (51, 100, 55, 70, "Moderate", "Yellow"),
    (101, 150, 71, 85, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 86, 105, "Unhealthy", "Red"),
    (201, 300, 106, 200, "Very Unhealthy", "Purple"),
]

O3_1HR_BREAKPOINTS = [
    (101, 150, 125, 164, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 165, 204, "Unhealthy", "Red"),
    (201, 300, 205, 404, "Very Unhealthy", "Purple"),
    (301, 400, 405, 504, "Hazardous", "Maroon"),
    (401, 500, 505, 604, "Hazardous", "Maroon"),
]

CO_BREAKPOINTS = [
    (0, 50, 0.0, 4.4, "Good", "Green"),
    (51, 100, 4.5, 9.4, "Moderate", "Yellow"),
    (101, 150, 9.5, 12.4, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 12.5, 15.4, "Unhealthy", "Red"),
    (201, 300, 15.5, 30.4, "Very Unhealthy", "Purple"),
    (301, 400, 30.5, 40.4, "Hazardous", "Maroon"),
    (401, 500, 40.5, 50.4, "Hazardous", "Maroon"),
]

NO2_BREAKPOINTS = [
    (0, 50, 0, 53, "Good", "Green"),
    (51, 100, 54, 100, "Moderate", "Yellow"),
    (101, 150, 101, 360, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 361, 649, "Unhealthy", "Red"),
    (201, 300, 650, 1249, "Very Unhealthy", "Purple"),
    (301, 400, 1250, 1649, "Hazardous", "Maroon"),
    (401, 500, 1650, 2049, "Hazardous", "Maroon"),
]

SO2_BREAKPOINTS = [
    (0, 50, 0, 35, "Good", "Green"),
    (51, 100, 36, 75, "Moderate", "Yellow"),
    (101, 150, 76, 185, "Unhealthy for Sensitive Groups", "Orange"),
    (151, 200, 186, 304, "Unhealthy", "Red"),
    (201, 300, 305, 604, "Very Unhealthy", "Purple"),
    (301, 400, 605, 804, "Hazardous", "Maroon"),
    (401, 500, 805, 1004, "Hazardous", "Maroon"),
]


def aqi_to_concentration(aqi: float, pollutant: str = "pm25") -> float:
    """
    Convert AQI value to pollutant concentration (µg/m³ or ppm).
    
    Args:
        aqi: AQI value (0-500)
        pollutant: Pollutant type (pm25, pm10, o3, co, no2, so2)
    
    Returns:
        Concentration in µg/m³ (for particulates) or ppm (for gases)
    
    Formula:
        C = ((Ihi - Ilo) / (BPhi - BPlo)) * (AQI - Ilo) + BPlo
    Where:
        C = concentration
        AQI = the AQI value
        BPhi = breakpoint concentration >= C
        BPlo = breakpoint concentration <= C
        Ihi = AQI value corresponding to BPhi
        Ilo = AQI value corresponding to BPlo
    """
    pollutant = pollutant.lower().replace(".", "_")
    
    # Select appropriate breakpoint table
    if pollutant == "pm25" or pollutant == "pm2_5":
        breakpoints = PM25_BREAKPOINTS
    elif pollutant == "pm10":
        breakpoints = PM10_BREAKPOINTS
    elif pollutant == "o3" or pollutant == "o3_8hr":
        breakpoints = O3_8HR_BREAKPOINTS
    elif pollutant == "o3_1hr":
        breakpoints = O3_1HR_BREAKPOINTS
    elif pollutant == "co":
        breakpoints = CO_BREAKPOINTS
    elif pollutant == "no2":
        breakpoints = NO2_BREAKPOINTS
    elif pollutant == "so2":
        breakpoints = SO2_BREAKPOINTS
    else:
        raise ValueError(f"Unknown pollutant: {pollutant}")
    
    # Find the appropriate breakpoint range
    for bp_low, bp_high, conc_low, conc_high, category, color in breakpoints:
        if bp_low <= aqi <= bp_high:
            # Calculate concentration using linear interpolation
            concentration = (
                ((conc_high - conc_low) / (bp_high - bp_low)) * (aqi - bp_low) + conc_low
            )
            return round(concentration, 1)
    
    # If AQI is out of range, return approximate value
    if aqi > 500:
        # Beyond hazardous, approximate based on highest breakpoint
        last_bp = breakpoints[-1]
        _, _, _, conc_high, _, _ = last_bp
        return round(conc_high + (aqi - 500) * 0.5, 1)
    
    return 0.0


def concentration_to_aqi(concentration: float, pollutant: str = "pm25") -> int:
    """
    Convert pollutant concentration to AQI value.
    
    Args:
        concentration: Concentration in µg/m³ (for particulates) or ppm (for gases)
        pollutant: Pollutant type (pm25, pm10, o3, co, no2, so2)
    
    Returns:
        AQI value (0-500+)
    """
    pollutant = pollutant.lower().replace(".", "_")
    
    # Select appropriate breakpoint table
    if pollutant == "pm25" or pollutant == "pm2_5":
        breakpoints = PM25_BREAKPOINTS
    elif pollutant == "pm10":
        breakpoints = PM10_BREAKPOINTS
    elif pollutant == "o3" or pollutant == "o3_8hr":
        breakpoints = O3_8HR_BREAKPOINTS
    elif pollutant == "o3_1hr":
        breakpoints = O3_1HR_BREAKPOINTS
    elif pollutant == "co":
        breakpoints = CO_BREAKPOINTS
    elif pollutant == "no2":
        breakpoints = NO2_BREAKPOINTS
    elif pollutant == "so2":
        breakpoints = SO2_BREAKPOINTS
    else:
        raise ValueError(f"Unknown pollutant: {pollutant}")
    
    # Find the appropriate breakpoint range
    for bp_low, bp_high, conc_low, conc_high, category, color in breakpoints:
        if conc_low <= concentration <= conc_high:
            # Calculate AQI using linear interpolation
            aqi = (
                ((bp_high - bp_low) / (conc_high - conc_low)) * (concentration - conc_low) + bp_low
            )
            return round(aqi)
    
    # If concentration is out of range
    if concentration > breakpoints[-1][3]:  # Beyond highest breakpoint
        # Continue the pattern for hazardous levels
        return round(500 + (concentration - breakpoints[-1][3]) * 2)
    
    return 0


def get_aqi_category(aqi: int) -> Dict[str, str]:
    """
    Get AQI category information.
    
    Args:
        aqi: AQI value
    
    Returns:
        Dictionary with category, color, and health implications
    """
    if aqi <= 50:
        return {
            "level": "Good",
            "color": "Green",
            "color_hex": "#00E400",
            "health_implications": "Air quality is satisfactory, and air pollution poses little or no risk.",
            "cautionary_statement": "None"
        }
    elif aqi <= 100:
        return {
            "level": "Moderate",
            "color": "Yellow",
            "color_hex": "#FFFF00",
            "health_implications": "Air quality is acceptable. However, there may be a risk for some people, particularly those unusually sensitive to air pollution.",
            "cautionary_statement": "Unusually sensitive people should consider limiting prolonged outdoor exertion."
        }
    elif aqi <= 150:
        return {
            "level": "Unhealthy for Sensitive Groups",
            "color": "Orange",
            "color_hex": "#FF7E00",
            "health_implications": "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
            "cautionary_statement": "Sensitive groups (children, elderly, those with respiratory conditions) should limit prolonged outdoor exertion."
        }
    elif aqi <= 200:
        return {
            "level": "Unhealthy",
            "color": "Red",
            "color_hex": "#FF0000",
            "health_implications": "Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects.",
            "cautionary_statement": "Everyone should limit prolonged outdoor exertion. Sensitive groups should avoid prolonged outdoor exertion."
        }
    elif aqi <= 300:
        return {
            "level": "Very Unhealthy",
            "color": "Purple",
            "color_hex": "#8F3F97",
            "health_implications": "Health alert: The risk of health effects is increased for everyone.",
            "cautionary_statement": "Everyone should avoid prolonged outdoor exertion. Sensitive groups should remain indoors."
        }
    else:
        return {
            "level": "Hazardous",
            "color": "Maroon",
            "color_hex": "#7E0023",
            "health_implications": "Health warning of emergency conditions: everyone is more likely to be affected.",
            "cautionary_statement": "Everyone should avoid all outdoor exertion. Remain indoors with air purification if possible."
        }


def parse_waqi_value(value: float, pollutant: str = "pm25", return_both: bool = True) -> Dict[str, any]:
    """
    Parse WAQI API value which is in AQI format, not raw concentration.
    
    Args:
        value: Value from WAQI API (this is an AQI value, not concentration)
        pollutant: Pollutant type
        return_both: If True, return both AQI and estimated concentration
    
    Returns:
        Dictionary with aqi, concentration (if return_both), and category info
    """
    aqi_value = round(value)
    category = get_aqi_category(aqi_value)
    
    result = {
        "aqi": aqi_value,
        "pollutant": pollutant,
        "category": category["level"],
        "color": category["color"],
        "health_implications": category["health_implications"],
        "cautionary_statement": category["cautionary_statement"],
        "data_type": "aqi"  # Important: mark that this is AQI, not concentration
    }
    
    if return_both:
        # Convert AQI back to approximate concentration
        concentration = aqi_to_concentration(aqi_value, pollutant)
        result["concentration_estimated_ugm3"] = concentration
        result["note"] = f"WAQI provides AQI values. Concentration of {concentration} µg/m³ is estimated from AQI {aqi_value} using EPA conversion."
    
    return result


def format_pollutant_value(
    value: float,
    pollutant: str,
    data_type: str = "concentration",
    include_aqi: bool = True
) -> Dict[str, any]:
    """
    Format a pollutant value with proper context (concentration or AQI).
    
    Args:
        value: The numeric value
        pollutant: Pollutant type (pm25, pm10, etc.)
        data_type: Either "concentration" (µg/m³) or "aqi"
        include_aqi: If data_type is concentration, also calculate AQI
    
    Returns:
        Formatted dictionary with all relevant information
    """
    pollutant = pollutant.lower().replace(".", "_")
    
    if data_type == "aqi":
        return parse_waqi_value(value, pollutant, return_both=True)
    elif data_type == "concentration":
        unit = "µg/m³" if pollutant in ["pm25", "pm2_5", "pm10"] else "ppm"
        
        result = {
            "concentration": round(value, 1),
            "unit": unit,
            "pollutant": pollutant,
            "data_type": "concentration"
        }
        
        if include_aqi:
            aqi = concentration_to_aqi(value, pollutant)
            category = get_aqi_category(aqi)
            result["aqi"] = aqi
            result["category"] = category["level"]
            result["color"] = category["color"]
            result["health_implications"] = category["health_implications"]
            result["cautionary_statement"] = category["cautionary_statement"]
        
        return result
    else:
        raise ValueError(f"Unknown data_type: {data_type}. Must be 'aqi' or 'concentration'")
