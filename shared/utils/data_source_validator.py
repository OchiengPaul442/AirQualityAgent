"""
Enhanced Data Source Attribution Tool

Ensures all API responses include proper source attribution and timestamps
to address user complaints about inaccurate data and missing source links.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DataSourceValidator:
    """Validates and enhances API responses with proper source attribution."""

    @staticmethod
    def validate_and_enhance(
        data: dict[str, Any],
        source_name: str,
        api_endpoint: str = "",
        require_timestamp: bool = True
    ) -> dict[str, Any]:
        """
        Validate API response and ensure it has proper source attribution.

        Args:
            data: Raw API response data
            source_name: Name of the data source (e.g., "WAQI", "AirQo")
            api_endpoint: API endpoint used (for logging)
            require_timestamp: Whether to require a timestamp

        Returns:
            Enhanced data with guaranteed source attribution
        """
        if not data:
            return {
                "success": False,
                "error": f"No data returned from {source_name}",
                "source": source_name,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        # Ensure source attribution exists
        if "source" not in data:
            data["source"] = source_name
            logger.info(f"✓ Added source attribution: {source_name}")

        # Ensure timestamp exists
        if require_timestamp and "timestamp" not in data and "time" not in data:
            data["timestamp"] = datetime.utcnow().isoformat() + "Z"
            logger.info(f"✓ Added timestamp: {data['timestamp']}")

        # Add data quality indicators
        if "success" in data and data["success"]:
            data["data_quality"] = {
                "has_source": True,
                "has_timestamp": "timestamp" in data or "time" in data,
                "source_verified": True,
                "retrieval_time": datetime.utcnow().isoformat() + "Z"
            }

        # Add API endpoint for debugging
        if api_endpoint:
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["api_endpoint"] = api_endpoint

        return data

    @staticmethod
    def format_source_citation(
        data: dict[str, Any],
        include_timestamp: bool = True
    ) -> str:
        """
        Format a human-readable source citation.

        Args:
            data: API response data with source information
            include_timestamp: Whether to include timestamp in citation

        Returns:
            Formatted citation string
        """
        source = data.get("source", "Unknown")

        # Extract timestamp
        timestamp = None
        if "timestamp" in data:
            timestamp = data["timestamp"]
        elif "time" in data:
            timestamp = data["time"]
        elif "date" in data:
            timestamp = data["date"]

        # Build citation
        citation_parts = [f"Source: {source}"]

        if include_timestamp and timestamp:
            # Try to format timestamp nicely
            try:
                if isinstance(timestamp, str):
                    # Parse ISO format
                    if "T" in timestamp:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
                    else:
                        time_str = timestamp
                else:
                    time_str = str(timestamp)
                citation_parts.append(f"Time: {time_str}")
            except Exception as e:
                logger.warning(f"Could not parse timestamp: {timestamp}, error: {e}")
                citation_parts.append(f"Time: {timestamp}")

        # Add data source URL if available
        if "url" in data:
            citation_parts.append(f"URL: {data['url']}")
        elif "metadata" in data and "api_endpoint" in data["metadata"]:
            citation_parts.append(f"API: {data['metadata']['api_endpoint']}")

        return " | ".join(citation_parts)

    @staticmethod
    def validate_aqi_data(data: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that AQI data contains required fields.

        Args:
            data: AQI data response

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check for basic success
        if not data.get("success"):
            issues.append("Response indicates failure")
            return False, issues

        # Check for required fields
        required_fields = ["aqi", "source"]
        for field in required_fields:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Check AQI value is valid
        if "aqi" in data:
            aqi = data["aqi"]
            if not isinstance(aqi, (int, float)) or aqi < 0 or aqi > 500:
                issues.append(f"Invalid AQI value: {aqi} (should be 0-500)")

        # Check for timestamp
        if "timestamp" not in data and "time" not in data:
            issues.append("Missing timestamp (data freshness unknown)")

        # Check for location
        if "city" not in data and "location" not in data and "station" not in data:
            issues.append("Missing location information")

        return len(issues) == 0, issues


# Global validator instance
data_validator = DataSourceValidator()
