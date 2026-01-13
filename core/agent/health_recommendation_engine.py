"""
Health Recommendation Engine - WHO 2021 + EPA 2024 Guidelines

Implements activity-specific, duration-modeled, sensitivity-stratified thresholds
for health-critical air quality recommendations.

Guidelines:
- WHO 2021 Global Air Quality Guidelines
- EPA 2024 NAAQS (National Ambient Air Quality Standards)
- Peer-reviewed research on exposure thresholds

Author: Production AI Engineering Team
Date: January 2026
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActivityLevel(Enum):
    """Activity levels with corresponding breathing rate multipliers."""
    SEDENTARY_INDOOR = "sedentary_indoor"  # Office work, reading (minimal outdoor exposure)
    LIGHT_OUTDOOR = "light_outdoor"  # Slow walking, shopping (2-3x resting rate)
    MODERATE_EXERCISE = "moderate_exercise"  # Brisk walking, cycling (5-8x resting rate)
    VIGOROUS_EXERCISE = "vigorous_exercise"  # Running, sports (15-20x resting rate)


class SensitivityLevel(Enum):
    """User sensitivity levels based on health conditions."""
    STANDARD = "standard"  # Healthy adults
    SENSITIVE = "sensitive"  # Children, elderly, or specific conditions


class ExposureDuration(Enum):
    """Exposure duration categories."""
    SHORT = "short"  # <30 minutes
    MODERATE = "moderate"  # 2-4 hours
    EXTENDED = "extended"  # >6 hours all-day


# WHO 2021 + EPA 2024 Guideline Values (µg/m³)
GUIDELINE_VALUES = {
    "PM2.5": {
        "who_annual": 5,
        "who_24h": 15,
        "epa_annual": 9,  # Updated Feb 2024
    },
    "PM10": {
        "who_annual": 15,
        "who_24h": 45,
    },
    "NO2": {
        "who_annual": 10,
        "who_24h": 25,
    },
    "O3": {
        "who_peak_season": 60,
        "who_8h": 100,
    },
    "SO2": {
        "who_24h": 40,
    },
    "CO": {
        "who_24h": 4000,  # mg/m³
    },
}

# Activity-Specific AQI Thresholds
ACTIVITY_THRESHOLDS = {
    ActivityLevel.SEDENTARY_INDOOR: {
        SensitivityLevel.STANDARD: {
            "safe": 100,  # Moderate is acceptable
            "avoid": 150,
        },
        SensitivityLevel.SENSITIVE: {
            "safe": 75,
            "avoid": 100,
        },
    },
    ActivityLevel.LIGHT_OUTDOOR: {
        SensitivityLevel.STANDARD: {
            "safe": 75,
            "avoid": 100,
        },
        SensitivityLevel.SENSITIVE: {
            "safe": 50,
            "avoid": 75,
        },
    },
    ActivityLevel.MODERATE_EXERCISE: {
        SensitivityLevel.STANDARD: {
            "safe": 50,
            "avoid": 75,
        },
        SensitivityLevel.SENSITIVE: {
            "safe": 35,
            "avoid": 50,
        },
    },
    ActivityLevel.VIGOROUS_EXERCISE: {
        SensitivityLevel.STANDARD: {
            "safe": 35,  # Good air quality only
            "avoid": 50,  # Even moderate is too high
        },
        SensitivityLevel.SENSITIVE: {
            "safe": 25,  # Effectively "Good" only
            "avoid": 35,
        },
    },
}

# Duration modifiers (added to safe threshold)
DURATION_MODIFIERS = {
    ExposureDuration.SHORT: 25,  # Can tolerate +25 AQI
    ExposureDuration.MODERATE: 0,  # Use standard thresholds
    ExposureDuration.EXTENDED: -20,  # Stricter by -20 AQI
}

# Sensitive health conditions
SENSITIVE_CONDITIONS = [
    "asthma",
    "copd",
    "cardiovascular_disease",
    "diabetes",
    "pregnancy",
    "immunocompromised",
    "child_under_14",
    "elderly_over_65",
]


@dataclass
class HealthRecommendation:
    """Structured health recommendation output."""
    is_safe: bool
    current_aqi: float
    safe_threshold: float
    recommendation: str
    reasoning: str
    alternatives: list[str]
    when_to_recheck: Optional[str]
    confidence_level: str


class HealthRecommendationEngine:
    """
    Calculate personalized health recommendations based on:
    - Activity level and breathing rate
    - Health conditions and sensitivity
    - Exposure duration
    - Current and forecast AQI
    """

    @staticmethod
    def calculate_safe_threshold(
        activity: ActivityLevel,
        health_conditions: list[str],
        duration: ExposureDuration = ExposureDuration.MODERATE
    ) -> float:
        """
        Calculate personalized safe AQI threshold.

        Args:
            activity: Activity level (sedentary to vigorous)
            health_conditions: List of health conditions
            duration: Expected exposure duration

        Returns:
            Safe AQI threshold for this user
        """
        # Determine sensitivity level
        is_sensitive = any(
            condition.lower().replace(" ", "_") in SENSITIVE_CONDITIONS
            for condition in health_conditions
        )
        sensitivity = SensitivityLevel.SENSITIVE if is_sensitive else SensitivityLevel.STANDARD

        # Get base threshold for activity + sensitivity
        base_threshold = ACTIVITY_THRESHOLDS[activity][sensitivity]["safe"]

        # Apply duration modifier
        duration_modifier = DURATION_MODIFIERS[duration]
        adjusted_threshold = base_threshold + duration_modifier

        # Never go below 25 AQI (even with extended exposure)
        return max(25, adjusted_threshold)

    @staticmethod
    def get_recommendation(
        current_aqi: float,
        forecast_aqi: Optional[float],
        activity: ActivityLevel,
        health_conditions: list[str],
        duration: ExposureDuration = ExposureDuration.MODERATE,
        location: str = ""
    ) -> HealthRecommendation:
        """
        Generate comprehensive health recommendation.

        Args:
            current_aqi: Current AQI measurement
            forecast_aqi: Forecast AQI (optional)
            activity: Planned activity level
            health_conditions: User's health conditions
            duration: Expected exposure duration
            location: Location name for context

        Returns:
            HealthRecommendation with detailed guidance
        """
        # Calculate thresholds
        safe_threshold = HealthRecommendationEngine.calculate_safe_threshold(
            activity, health_conditions, duration
        )

        is_sensitive = any(
            condition.lower().replace(" ", "_") in SENSITIVE_CONDITIONS
            for condition in health_conditions
        )
        sensitivity = SensitivityLevel.SENSITIVE if is_sensitive else SensitivityLevel.STANDARD

        avoid_threshold = ACTIVITY_THRESHOLDS[activity][sensitivity]["avoid"]

        # Determine safety
        is_safe = current_aqi <= safe_threshold

        # Build recommendation
        if is_safe:
            recommendation = f"{activity.value.replace('_', ' ').title()} is safe today."
        elif current_aqi <= avoid_threshold:
            recommendation = f"{activity.value.replace('_', ' ').title()} is risky today. Consider reducing duration or intensity."
        else:
            recommendation = f"Avoid {activity.value.replace('_', ' ')} today. Air quality is unhealthy."

        # Build reasoning
        breathing_rates = {
            ActivityLevel.SEDENTARY_INDOOR: "minimal outdoor exposure",
            ActivityLevel.LIGHT_OUTDOOR: "2-3x resting breathing rate",
            ActivityLevel.MODERATE_EXERCISE: "5-8x resting breathing rate",
            ActivityLevel.VIGOROUS_EXERCISE: "15-20x resting breathing rate (critical exposure)",
        }

        reasoning = (
            f"Current AQI is {current_aqi:.0f}. Your safe threshold is {safe_threshold:.0f} AQI "
            f"(activity: {activity.value.replace('_', ' ')}, {breathing_rates[activity]})"
        )

        if is_sensitive:
            reasoning += f". Your health condition(s) require stricter limits."

        # Build alternatives
        alternatives = []
        if not is_safe:
            if forecast_aqi and forecast_aqi < safe_threshold:
                alternatives.append(
                    f"Wait for better air quality (forecast: {forecast_aqi:.0f} AQI)"
                )

            # Suggest lower-intensity alternatives
            if activity == ActivityLevel.VIGOROUS_EXERCISE:
                alternatives.append("Try light walking instead of running")
                alternatives.append("Indoor gym with air filtration")
            elif activity == ActivityLevel.MODERATE_EXERCISE:
                alternatives.append("Light outdoor activity only")
                alternatives.append("Indoor alternative")

            # Timing alternatives
            alternatives.append("Early morning (5-7am) typically has cleaner air")

        # When to recheck
        when_to_recheck = None
        if not is_safe:
            if forecast_aqi:
                when_to_recheck = "Check forecast for improvement window"
            else:
                when_to_recheck = "Check back in 3-6 hours"

        # Confidence level
        confidence = "high" if current_aqi < 150 else "medium"

        return HealthRecommendation(
            is_safe=is_safe,
            current_aqi=current_aqi,
            safe_threshold=safe_threshold,
            recommendation=recommendation,
            reasoning=reasoning,
            alternatives=alternatives,
            when_to_recheck=when_to_recheck,
            confidence_level=confidence,
        )

    @staticmethod
    def get_pollutant_specific_guidance(pollutant: str, concentration: float) -> str:
        """
        Get pollutant-specific mitigation guidance.

        Args:
            pollutant: Pollutant name (PM2.5, PM10, O3, NO2)
            concentration: Concentration in µg/m³

        Returns:
            Specific guidance string
        """
        guidance = {
            "PM2.5": (
                "Primary concern: Deep lung penetration, cardiovascular effects. "
                "Mitigation: N95 masks effective, indoor air filtration, avoid traffic areas."
            ),
            "PM10": (
                "Primary concern: Upper respiratory irritation, asthma triggers. "
                "Mitigation: Cloth masks partially effective, avoid dusty areas, indoor refuge."
            ),
            "O3": (
                "Primary concern: Lung tissue damage, asthma exacerbation. "
                "Mitigation: Exercise in morning (O3 peaks 2-6pm), indoor alternative, masks ineffective."
            ),
            "NO2": (
                "Primary concern: Airway inflammation, infection susceptibility. "
                "Mitigation: Avoid roadways, time activities for low-traffic hours."
            ),
        }

        return guidance.get(pollutant, "General air quality precautions apply.")


def calculate_safe_threshold(
    activity: str, health_conditions: list[str], duration: str = "moderate"
) -> float:
    """
    Convenience function for calculating safe threshold.

    Args:
        activity: Activity level (sedentary_indoor, light_outdoor, moderate_exercise, vigorous_exercise)
        health_conditions: List of health conditions
        duration: Duration (short, moderate, extended)

    Returns:
        Safe AQI threshold
    """
    activity_enum = ActivityLevel(activity)
    duration_enum = ExposureDuration(duration)

    return HealthRecommendationEngine.calculate_safe_threshold(
        activity_enum, health_conditions, duration_enum
    )
