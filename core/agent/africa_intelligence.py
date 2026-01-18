"""
Africa-Specific Operational Intelligence

Provides region-specific air quality context including:
- Seasonal pollution patterns (Harmattan, biomass burning, rainy seasons)
- City-specific pollution profiles and peak hours
- Data confidence tiers for sparse monitoring infrastructure
- Local source profiles (charcoal cooking, generators, traffic patterns)
- Practical mitigation strategies for African context

Author: Production AI Engineering Team
Date: January 2026
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DataConfidenceTier(Enum):
    """Data quality tiers for African air quality measurements."""
    HIGH = "high"  # Station <1km, <1h old, calibrated <3mo
    MEDIUM = "medium"  # Station 1-5km OR 1-6h old OR satellite
    LOW = "low"  # Station >50km OR >12h old
    MODELED = "modeled"  # No measurements, seasonal patterns + WHO estimates


class Season(Enum):
    """African seasonal patterns."""
    HARMATTAN = "harmattan"  # Nov-Mar, West Africa
    DRY_SEASON = "dry_season"  # Region-specific
    RAINY_SEASON = "rainy_season"  # Region-specific
    BIOMASS_BURNING = "biomass_burning"  # Jul-Oct East, May-Sep Southern


# City-specific pollution profiles
CITY_PROFILES = {
    "Nairobi": {
        "country": "Kenya",
        "primary_sources": ["vehicle_emissions", "matatu_diesel", "unpaved_road_dust"],
        "peak_hours": ["06:00-09:00", "17:00-20:00"],
        "clean_hours": ["05:00-06:00"],
        "micro_variations": "Industrial Area 40-60 µg/m³ higher than Westlands/Karen",
        "seasonal_notes": "June-August dry season = worst AQ (PM2.5 70-100 µg/m³)",
        "baseline_pm25": 45,  # Typical µg/m³
        "airqo_coverage": "excellent",  # 50+ stations
    },
    "Kampala": {
        "country": "Uganda",
        "primary_sources": ["charcoal_cooking", "vehicle_emissions", "swamp_burning"],
        "peak_hours": ["18:00-20:00", "07:00-09:00"],  # Evening cooking, morning traffic
        "clean_hours": ["05:00-07:00"],
        "micro_variations": "Central Business District worst, hills (Kololo, Nakasero) better",
        "seasonal_notes": "Dry seasons (Dec-Feb, Jun-Aug) worst",
        "baseline_pm25": 50,
        "airqo_coverage": "excellent",  # Densest network in Africa
    },
    "Lagos": {
        "country": "Nigeria",
        "primary_sources": ["vehicle_emissions", "generator_use", "industrial_apapa"],
        "peak_hours": ["06:00-10:00", "16:00-21:00"],  # Traffic + generators during blackouts
        "clean_hours": ["04:00-06:00"],
        "micro_variations": "Lagos Island vs Mainland vs Ikoyi = 60 µg/m³ range",
        "seasonal_notes": "Harmattan (Nov-Feb) adds 40-80 µg/m³ PM10",
        "baseline_pm25": 65,
        "airqo_coverage": "limited",
    },
    "Accra": {
        "country": "Ghana",
        "primary_sources": ["vehicle_emissions", "e_waste_burning", "domestic_cooking"],
        "peak_hours": ["06:00-09:00", "17:00-20:00"],
        "clean_hours": ["05:00-06:00"],
        "micro_variations": "Agbogbloshie area avoid during burning hours (toxic fumes)",
        "seasonal_notes": "Harmattan (Dec-Feb) severe dust (PM10 >200 µg/m³)",
        "baseline_pm25": 55,
        "airqo_coverage": "moderate",
    },
    "Addis Ababa": {
        "country": "Ethiopia",
        "primary_sources": ["vehicle_emissions", "construction_dust", "eucalyptus_burning"],
        "peak_hours": ["07:00-09:00", "17:00-19:00"],
        "clean_hours": ["05:00-07:00"],
        "micro_variations": "Altitude effect: 2,400m elevation = lower O3 formation",
        "seasonal_notes": "Rainy season (Jun-Sep) = cleanest period",
        "baseline_pm25": 40,
        "airqo_coverage": "very_limited",
    },
    "Dar es Salaam": {
        "country": "Tanzania",
        "primary_sources": ["vehicle_emissions", "industrial", "biomass_burning"],
        "peak_hours": ["06:00-09:00", "17:00-20:00"],
        "clean_hours": ["05:00-06:00"],
        "seasonal_notes": "Dry season (Jun-Oct) worst, coastal winds help dispersion",
        "baseline_pm25": 35,
        "airqo_coverage": "limited",
    },
    "Kigali": {
        "country": "Rwanda",
        "primary_sources": ["vehicle_emissions", "construction", "cooking"],
        "peak_hours": ["06:00-09:00", "17:00-19:00"],
        "clean_hours": ["05:00-06:00"],
        "seasonal_notes": "Hilly terrain creates micro-variations, valleys trap pollution",
        "baseline_pm25": 30,
        "airqo_coverage": "good",
    },
}

# Seasonal pollution patterns
SEASONAL_PATTERNS = {
    Season.HARMATTAN: {
        "months": ["November", "December", "January", "February", "March"],
        "regions": ["West Africa"],
        "countries": ["Nigeria", "Ghana", "Benin", "Togo", "Burkina Faso", "Mali", "Senegal"],
        "characteristics": "Saharan dust transport, PM10 spikes 50-150 µg/m³ above baseline",
        "pollutant_profile": "PM10 dominant, less toxic than PM2.5 combustion particles",
        "visibility": "Low visibility, respiratory irritation",
        "mitigation": "Cloth masks reduce larger particles, stay indoors during peak dust",
        "typical_aqi_increase": 80,
    },
    Season.BIOMASS_BURNING: {
        "months": {
            "East Africa": ["July", "August", "September", "October"],
            "Southern Africa": ["May", "June", "July", "August", "September"],
        },
        "regions": ["East Africa", "Southern Africa"],
        "countries": ["Kenya", "Tanzania", "Uganda", "Zambia", "Zimbabwe", "Mozambique"],
        "characteristics": "Agricultural waste burning, PM2.5 spikes from crop residue combustion",
        "pollutant_profile": "PM2.5 60-120 µg/m³, highly toxic combustion particles",
        "visibility": "Smoke haze, visibility reduction",
        "mitigation": "N95 masks essential, avoid outdoor activity, asthma triggers",
        "typical_aqi_increase": 100,
    },
    Season.RAINY_SEASON: {
        "months": "Varies by region (Apr-May, Oct-Nov common)",
        "regions": ["All Africa"],
        "characteristics": "Wet deposition improves AQI 30-50%",
        "pollutant_profile": "Lower PM2.5 and PM10, but mold spores increase",
        "visibility": "Improved",
        "mitigation": "Best time for outdoor activities for respiratory patients",
        "typical_aqi_improvement": -40,  # Negative = improvement
        "caveat": "Unpaved road dust when roads dry, temporary spikes",
    },
}


@dataclass
class CityIntelligence:
    """City-specific air quality intelligence."""
    city: str
    country: str
    primary_sources: list[str]
    peak_hours: list[str]
    clean_hours: list[str]
    micro_variations: str
    seasonal_notes: str
    baseline_pm25: float
    airqo_coverage: str


@dataclass
class DataQualityAssessment:
    """Assessment of data quality for a measurement."""
    tier: DataConfidenceTier
    explanation: str
    uncertainty_range: Optional[tuple[float, float]]
    recommendations: list[str]


class AfricaIntelligence:
    """
    Provide Africa-specific operational intelligence for air quality assessments.
    """

    @staticmethod
    def get_city_profile(city: str) -> Optional[CityIntelligence]:
        """
        Get detailed city-specific pollution profile.

        Args:
            city: City name (case-insensitive)

        Returns:
            CityIntelligence or None if city not in database
        """
        city_key = city.title()
        if city_key not in CITY_PROFILES:
            return None

        profile = CITY_PROFILES[city_key]
        return CityIntelligence(
            city=city_key,
            country=profile["country"],
            primary_sources=profile["primary_sources"],
            peak_hours=profile["peak_hours"],
            clean_hours=profile["clean_hours"],
            micro_variations=profile["micro_variations"],
            seasonal_notes=profile["seasonal_notes"],
            baseline_pm25=profile["baseline_pm25"],
            airqo_coverage=profile["airqo_coverage"],
        )

    @staticmethod
    def assess_data_quality(
        station_distance_km: float,
        data_age_hours: float,
        sensor_calibrated_months_ago: Optional[float] = None,
        is_satellite: bool = False,
    ) -> DataQualityAssessment:
        """
        Assess data quality based on African monitoring infrastructure reality.

        Args:
            station_distance_km: Distance to nearest station
            data_age_hours: Age of data in hours
            sensor_calibrated_months_ago: Months since last calibration
            is_satellite: Whether data is from satellite

        Returns:
            DataQualityAssessment with tier and guidance
        """
        # TIER 1 - High Confidence
        if (
            station_distance_km < 1
            and data_age_hours < 1
            and (sensor_calibrated_months_ago is None or sensor_calibrated_months_ago < 3)
        ):
            return DataQualityAssessment(
                tier=DataConfidenceTier.HIGH,
                explanation=f"High confidence: Station {station_distance_km:.1f}km away, data {int(data_age_hours*60)} minutes old",
                uncertainty_range=(0.9, 1.1),  # ±10%
                recommendations=[],
            )

        # TIER 2 - Medium Confidence
        if (
            (station_distance_km < 5 or is_satellite)
            and data_age_hours < 6
        ):
            explanation = "Medium confidence: "
            if is_satellite:
                explanation += "Satellite data (11-25km resolution)"
            else:
                explanation += f"Station {station_distance_km:.1f}km away, {int(data_age_hours)} hours old"

            return DataQualityAssessment(
                tier=DataConfidenceTier.MEDIUM,
                explanation=explanation,
                uncertainty_range=(0.7, 1.3),  # ±30%
                recommendations=["Cross-reference with local observations if possible"],
            )

        # TIER 3 - Low Confidence
        if station_distance_km < 50 and data_age_hours < 12:
            return DataQualityAssessment(
                tier=DataConfidenceTier.LOW,
                explanation=f"Low confidence: Station {station_distance_km:.0f}km away, {int(data_age_hours)} hours old",
                uncertainty_range=(0.5, 1.5),  # ±50%
                recommendations=[
                    "Significant spatial/temporal uncertainty",
                    "Use seasonal context to verify",
                    "Consider waiting for fresher data",
                ],
            )

        # TIER 4 - Modeled Estimate
        return DataQualityAssessment(
            tier=DataConfidenceTier.MODELED,
            explanation="No direct measurements available. Based on regional patterns and WHO estimates.",
            uncertainty_range=None,
            recommendations=[
                "This is an ESTIMATE, not measured data",
                "Actual conditions may vary significantly",
                "Seek ground-truth data when available",
            ],
        )

    @staticmethod
    def get_seasonal_context(city: str, month: int) -> Optional[dict]:
        """
        Get seasonal pollution context for a city and month.

        Args:
            city: City name
            month: Month number (1-12)

        Returns:
            Seasonal context dictionary or None
        """
        profile = CITY_PROFILES.get(city.title())
        if not profile:
            return None

        country = profile["country"]
        seasonal_info = []

        # Check for Harmattan (West Africa)
        if country in SEASONAL_PATTERNS[Season.HARMATTAN]["countries"]:
            if month in [11, 12, 1, 2, 3]:  # Nov-Mar
                seasonal_info.append({
                    "season": "Harmattan",
                    "impact": SEASONAL_PATTERNS[Season.HARMATTAN]["characteristics"],
                    "aqi_change": f"+{SEASONAL_PATTERNS[Season.HARMATTAN]['typical_aqi_increase']} AQI",
                    "mitigation": SEASONAL_PATTERNS[Season.HARMATTAN]["mitigation"],
                })

        # Check for biomass burning
        biomass_months = SEASONAL_PATTERNS[Season.BIOMASS_BURNING]["months"]
        if country in SEASONAL_PATTERNS[Season.BIOMASS_BURNING]["countries"]:
            region = "East Africa" if country in ["Kenya", "Tanzania", "Uganda"] else "Southern Africa"
            if any(m.lower() == [
                "january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december"
            ][month - 1] for m in biomass_months.get(region, [])):
                seasonal_info.append({
                    "season": "Biomass Burning Season",
                    "impact": SEASONAL_PATTERNS[Season.BIOMASS_BURNING]["characteristics"],
                    "aqi_change": f"+{SEASONAL_PATTERNS[Season.BIOMASS_BURNING]['typical_aqi_increase']} AQI",
                    "mitigation": SEASONAL_PATTERNS[Season.BIOMASS_BURNING]["mitigation"],
                })

        # Rainy season (general improvement)
        if month in [4, 5, 10, 11]:  # Common rainy months
            seasonal_info.append({
                "season": "Rainy Season",
                "impact": SEASONAL_PATTERNS[Season.RAINY_SEASON]["characteristics"],
                "aqi_change": f"{SEASONAL_PATTERNS[Season.RAINY_SEASON]['typical_aqi_improvement']} AQI (improvement)",
                "mitigation": SEASONAL_PATTERNS[Season.RAINY_SEASON]["mitigation"],
            })

        return {
            "city": city.title(),
            "country": country,
            "month": month,
            "seasonal_factors": seasonal_info,
        }

    @staticmethod
    def get_practical_mitigation(city: str, current_aqi: float) -> list[str]:
        """
        Get practical mitigation strategies for African context.

        Args:
            city: City name
            current_aqi: Current AQI

        Returns:
            List of practical mitigation strategies
        """
        strategies = []
        profile = CITY_PROFILES.get(city.title())

        if profile:
            # Timing strategies based on city profile
            clean_hours = profile["clean_hours"]
            if clean_hours:
                strategies.append(
                    f"Early morning ({', '.join(clean_hours)}) has cleanest air - best for outdoor activities"
                )

            peak_hours = profile["peak_hours"]
            if peak_hours:
                strategies.append(
                    f"Avoid outdoor activity during peak pollution hours: {', '.join(peak_hours)}"
                )

        # General African context strategies
        if current_aqi > 100:
            strategies.extend([
                "Indoor refuge: Stay indoors with windows closed",
                "N95 masks: Effective for PM2.5 if available (cloth masks only help with large dust)",
                "Avoid traffic corridors: Can be 40-80 µg/m³ higher than residential areas",
            ])

        if current_aqi > 150:
            strategies.extend([
                "CRITICAL: Seek filtered indoor space",
                "Medical alert: If you experience symptoms, seek medical attention",
                "Wet cloth over windows: Can reduce indoor pollution when AC unavailable",
            ])

        return strategies


def get_city_profile(city: str) -> Optional[dict]:
    """
    Convenience function to get city profile as dictionary.

    Args:
        city: City name

    Returns:
        City profile dictionary or None
    """
    return CITY_PROFILES.get(city.title())


def assess_data_quality(
    station_distance_km: float, data_age_hours: float
) -> dict:
    """
    Convenience function for data quality assessment.

    Args:
        station_distance_km: Distance to station in km
        data_age_hours: Age of data in hours

    Returns:
        Assessment dictionary
    """
    assessment = AfricaIntelligence.assess_data_quality(
        station_distance_km, data_age_hours
    )
    return {
        "tier": assessment.tier.value,
        "explanation": assessment.explanation,
        "recommendations": assessment.recommendations,
    }
