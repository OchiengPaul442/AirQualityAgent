"""
EPA 2024 AQI Calculator - Official Standards
Updated: May 6, 2024 per EPA Final Rule

Implements the official EPA Air Quality Index calculation using the 2024 breakpoints
that reflect the strengthened National Ambient Air Quality Standards (NAAQS) for PM2.5.

References:
- EPA Final Rule (February 7, 2024): https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf
- Implementation Date: May 6, 2024
- WHO Air Quality Guidelines 2021
"""

from typing import Dict, Tuple


class AQICalculator:
    """
    Official EPA 2024 AQI Calculator
    
    Uses piecewise linear function as specified in EPA Technical Assistance Document:
    I_p = [(I_hi - I_lo) / (BP_hi - BP_lo)] * (C_p - BP_lo) + I_lo
    
    Where:
    - I_p = AQI value for pollutant p
    - C_p = Concentration of pollutant p
    - BP_hi = Breakpoint ≥ C_p
    - BP_lo = Breakpoint ≤ C_p
    - I_hi = AQI value corresponding to BP_hi
    - I_lo = AQI value corresponding to BP_lo
    """
    
    # EPA 2024 PM2.5 Breakpoints (µg/m³, 24-hour average)
    # Updated May 6, 2024 to reflect strengthened NAAQS
    PM25_BREAKPOINTS = [
        # (C_lo, C_hi, AQI_lo, AQI_hi, Category, Color, Health Message)
        (0.0, 9.0, 0, 50, "Good", "#00E400", 
         "Air quality is satisfactory, and air pollution poses little or no risk."),
        (9.1, 35.4, 51, 100, "Moderate", "#FFFF00",
         "Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution."),
        (35.5, 55.4, 101, 150, "Unhealthy for Sensitive Groups", "#FF7E00",
         "Members of sensitive groups may experience health effects. The general public is less likely to be affected."),
        (55.5, 125.4, 151, 200, "Unhealthy", "#FF0000",
         "Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects."),
        (125.5, 225.4, 201, 300, "Very Unhealthy", "#8F3F97",
         "Health alert: The risk of health effects is increased for everyone."),
        (225.5, 325.4, 301, 400, "Hazardous", "#7E0023",
         "Health warning of emergency conditions: everyone is more likely to be affected."),
        (325.5, 500.0, 401, 500, "Hazardous", "#7E0023",
         "Health warning of emergency conditions: everyone is more likely to be affected."),
    ]
    
    # PM10 Breakpoints (24-hour average)
    PM10_BREAKPOINTS = [
        (0, 54, 0, 50, "Good", "#00E400"),
        (55, 154, 51, 100, "Moderate", "#FFFF00"),
        (155, 254, 101, 150, "Unhealthy for Sensitive Groups", "#FF7E00"),
        (255, 354, 151, 200, "Unhealthy", "#FF0000"),
        (355, 424, 201, 300, "Very Unhealthy", "#8F3F97"),
        (425, 504, 301, 400, "Hazardous", "#7E0023"),
        (505, 604, 401, 500, "Hazardous", "#7E0023"),
    ]
    
    # O3 Breakpoints (8-hour average, ppm)
    O3_8HR_BREAKPOINTS = [
        (0.000, 0.054, 0, 50, "Good", "#00E400"),
        (0.055, 0.070, 51, 100, "Moderate", "#FFFF00"),
        (0.071, 0.085, 101, 150, "Unhealthy for Sensitive Groups", "#FF7E00"),
        (0.086, 0.105, 151, 200, "Unhealthy", "#FF0000"),
        (0.106, 0.200, 201, 300, "Very Unhealthy", "#8F3F97"),
    ]
    
    # NO2 Breakpoints (1-hour average, ppb)
    NO2_BREAKPOINTS = [
        (0, 53, 0, 50, "Good", "#00E400"),
        (54, 100, 51, 100, "Moderate", "#FFFF00"),
        (101, 360, 101, 150, "Unhealthy for Sensitive Groups", "#FF7E00"),
        (361, 649, 151, 200, "Unhealthy", "#FF0000"),
        (650, 1249, 201, 300, "Very Unhealthy", "#8F3F97"),
        (1250, 1649, 301, 400, "Hazardous", "#7E0023"),
        (1650, 2049, 401, 500, "Hazardous", "#7E0023"),
    ]
    
    @classmethod
    def calculate_pm25_aqi(cls, concentration: float) -> Dict:
        """
        Calculate AQI for PM2.5 using EPA 2024 breakpoints.
        
        Args:
            concentration: PM2.5 concentration in µg/m³ (24-hour average)
            
        Returns:
            dict: {
                'aqi': int,
                'category': str,
                'color': str,
                'health_message': str,
                'concentration': float,
                'pollutant': 'PM2.5',
                'breakpoint_used': tuple,
                'calculation_method': 'EPA 2024'
            }
        """
        if concentration < 0:
            raise ValueError("Concentration cannot be negative")
        
        # Handle extreme values
        if concentration > 500.0:
            return {
                'aqi': 500,
                'category': 'Hazardous',
                'color': '#7E0023',
                'health_message': 'Health warning of emergency conditions: everyone is more likely to be affected.',
                'concentration': concentration,
                'pollutant': 'PM2.5',
                'breakpoint_used': 'Beyond AQI',
                'calculation_method': 'EPA 2024',
                'note': 'Concentration exceeds AQI scale (500+). Actual health risk is severe.'
            }
        
        # Find appropriate breakpoint
        for bp in cls.PM25_BREAKPOINTS:
            c_lo, c_hi, aqi_lo, aqi_hi, category, color, health_msg = bp
            
            if c_lo <= concentration <= c_hi:
                # EPA piecewise linear formula
                aqi = ((aqi_hi - aqi_lo) / (c_hi - c_lo)) * (concentration - c_lo) + aqi_lo
                aqi = round(aqi)
                
                return {
                    'aqi': aqi,
                    'category': category,
                    'color': color,
                    'health_message': health_msg,
                    'concentration': concentration,
                    'pollutant': 'PM2.5',
                    'breakpoint_used': f'{c_lo}-{c_hi} µg/m³',
                    'calculation_method': 'EPA 2024 (Updated May 6, 2024)',
                    'sensitive_groups': cls._get_sensitive_groups(category)
                }
        
        # Should never reach here if breakpoints are correct
        raise ValueError(f"No breakpoint found for concentration {concentration}")
    
    @classmethod
    def calculate_pm10_aqi(cls, concentration: float) -> Dict:
        """Calculate AQI for PM10 using EPA breakpoints."""
        if concentration < 0:
            raise ValueError("Concentration cannot be negative")
        
        if concentration > 604:
            return {
                'aqi': 500,
                'category': 'Hazardous',
                'color': '#7E0023',
                'concentration': concentration,
                'pollutant': 'PM10',
                'calculation_method': 'EPA 2024'
            }
        
        for bp in cls.PM10_BREAKPOINTS:
            c_lo, c_hi, aqi_lo, aqi_hi, category, color = bp
            
            if c_lo <= concentration <= c_hi:
                aqi = ((aqi_hi - aqi_lo) / (c_hi - c_lo)) * (concentration - c_lo) + aqi_lo
                aqi = round(aqi)
                
                return {
                    'aqi': aqi,
                    'category': category,
                    'color': color,
                    'concentration': concentration,
                    'pollutant': 'PM10',
                    'breakpoint_used': f'{c_lo}-{c_hi} µg/m³',
                    'calculation_method': 'EPA 2024'
                }
        
        raise ValueError(f"No breakpoint found for concentration {concentration}")
    
    @staticmethod
    def _get_sensitive_groups(category: str) -> list:
        """Return sensitive groups for given AQI category."""
        if category in ["Good", "Moderate"]:
            return []
        elif category == "Unhealthy for Sensitive Groups":
            return ["People with heart or lung disease", "Older adults", "Children", "Pregnant women"]
        elif category == "Unhealthy":
            return ["Everyone", "Especially people with heart or lung disease", "Older adults", "Children"]
        else:  # Very Unhealthy or Hazardous
            return ["Everyone"]
    
    @staticmethod
    def get_health_recommendations(aqi: int, category: str) -> Dict:
        """
        Get activity recommendations based on AQI.
        
        Returns recommendations for general public and sensitive groups.
        """
        if aqi <= 50:  # Good
            return {
                'general_public': 'Air quality is ideal for outdoor activities.',
                'sensitive_groups': 'Air quality is ideal for outdoor activities.',
                'outdoor_activities': 'No restrictions'
            }
        elif aqi <= 100:  # Moderate
            return {
                'general_public': 'Air quality is acceptable for most outdoor activities.',
                'sensitive_groups': 'Consider reducing prolonged or heavy outdoor exertion if you experience symptoms.',
                'outdoor_activities': 'Generally acceptable'
            }
        elif aqi <= 150:  # Unhealthy for Sensitive Groups
            return {
                'general_public': 'Air quality is acceptable for most people.',
                'sensitive_groups': 'Reduce prolonged or heavy outdoor exertion. Schedule activities when air quality improves.',
                'outdoor_activities': 'Limit prolonged exertion'
            }
        elif aqi <= 200:  # Unhealthy
            return {
                'general_public': 'Reduce prolonged or heavy outdoor exertion. Take more breaks, do less intense activities.',
                'sensitive_groups': 'Avoid prolonged or heavy outdoor exertion. Move activities indoors or reschedule.',
                'outdoor_activities': 'Avoid prolonged exertion'
            }
        elif aqi <= 300:  # Very Unhealthy
            return {
                'general_public': 'Avoid prolonged or heavy outdoor exertion. Consider moving activities indoors.',
                'sensitive_groups': 'Avoid all outdoor physical activities. Move activities indoors.',
                'outdoor_activities': 'Move indoors'
            }
        else:  # Hazardous
            return {
                'general_public': 'Avoid all outdoor physical activities. Remain indoors and keep windows closed.',
                'sensitive_groups': 'Remain indoors and keep activity levels low. Follow advice from health officials.',
                'outdoor_activities': 'Stay indoors'
            }
    
    @staticmethod
    def compare_to_standards(pm25_concentration: float) -> Dict:
        """
        Compare PM2.5 concentration to international standards.
        
        Returns comparison to WHO 2021 guidelines and EPA 2024 NAAQS.
        """
        who_24hr = 15.0  # WHO 2021 interim target (24-hour)
        who_annual = 5.0  # WHO 2021 guideline (annual)
        epa_24hr = 35.0  # EPA 2024 NAAQS (24-hour)
        epa_annual = 9.0  # EPA 2024 NAAQS (annual, revised Feb 2024)
        
        return {
            'who_24hr_guideline': {
                'value': who_24hr,
                'comparison': f'{pm25_concentration / who_24hr:.1f}x WHO 24-hour guideline',
                'meets_standard': pm25_concentration <= who_24hr
            },
            'who_annual_guideline': {
                'value': who_annual,
                'note': 'Annual guideline shown for reference (this is 24-hour measurement)',
                'meets_standard': pm25_concentration <= who_annual
            },
            'epa_24hr_standard': {
                'value': epa_24hr,
                'comparison': f'{pm25_concentration / epa_24hr:.1f}x EPA 24-hour standard',
                'meets_standard': pm25_concentration <= epa_24hr
            },
            'epa_annual_standard': {
                'value': epa_annual,
                'note': 'Annual standard (revised 2024) shown for reference',
                'meets_standard': pm25_concentration <= epa_annual
            }
        }


# Convenience function for quick AQI calculation
def calculate_aqi(pollutant: str, concentration: float) -> Dict:
    """
    Calculate AQI for any supported pollutant.
    
    Args:
        pollutant: 'PM2.5', 'PM10', 'O3', 'NO2'
        concentration: Pollutant concentration in appropriate units
        
    Returns:
        AQI calculation result dictionary
    """
    pollutant = pollutant.upper().replace('.', '')
    
    if pollutant == 'PM25':
        return AQICalculator.calculate_pm25_aqi(concentration)
    elif pollutant == 'PM10':
        return AQICalculator.calculate_pm10_aqi(concentration)
    else:
        raise ValueError(f"Unsupported pollutant: {pollutant}. Supported: PM2.5, PM10")
