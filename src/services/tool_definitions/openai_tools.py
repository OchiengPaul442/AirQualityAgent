"""
Tool definitions for OpenAI provider.

Contains all function declarations for tools available to OpenAI models.
"""


def get_waqi_tools() -> list[dict]:
    """Get WAQI (World Air Quality Index) tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_city_air_quality",
                "description": "Get real-time air quality data for a specific city using WAQI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city (e.g., London, Paris, Kampala)",
                        }
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_waqi_stations",
                "description": "Search for air quality monitoring stations by name or keyword.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Search term (e.g., 'Bangalore', 'US Embassy')",
                        }
                    },
                    "required": ["keyword"],
                },
            },
        },
    ]


def get_airqo_tools() -> list[dict]:
    """Get AirQo tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_african_city_air_quality",
                "description": "**PRIMARY TOOL for African cities** - Get real-time air quality from AirQo monitoring network. Use this FIRST for ANY African location (Uganda, Kenya, Tanzania, Rwanda, etc.). Searches by city/location name (e.g., Gulu, Kampala, Nakasero, Mbale, Nairobi). Returns actual measurements from local monitoring stations. Coverage includes major and minor cities across East Africa.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City or location name in Africa (e.g., 'Gulu', 'Kampala', 'Nakasero', 'Nairobi', 'Dar es Salaam')",
                        },
                        "site_id": {
                            "type": "string",
                            "description": "Optional site ID if known from previous searches",
                        },
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_multiple_african_cities_air_quality",
                "description": "Get real-time air quality for MULTIPLE African cities simultaneously. Use this when user asks about multiple locations (e.g., 'air quality in Kampala and Gulu', 'compare air quality between Nairobi and Dar es Salaam'). Returns data for all requested cities in one response for easy comparison.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of city names in Africa (e.g., ['Gulu', 'Kampala', 'Nairobi'])",
                        },
                    },
                    "required": ["cities"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_airqo_history",
                "description": "Get historical air quality data for a specific site or device. NOTE: AirQo API only provides data for the last 60 days. For older historical data, direct users to the AirQo Analytics platform.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "site_id": {
                            "type": "string",
                            "description": "The ID of the site (optional)",
                        },
                        "device_id": {
                            "type": "string",
                            "description": "The ID of the device (optional)",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS). Must be within last 60 days.",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS). Must be within last 60 days.",
                        },
                        "frequency": {
                            "type": "string",
                            "description": "Frequency: 'hourly', 'daily', or 'raw'",
                        },
                    },
                    "required": ["frequency"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_airqo_forecast",
                "description": "Get air quality forecast for a location, site, or device. Can search by city name or location if site_id is unknown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "site_id": {
                            "type": "string",
                            "description": "The ID of the site (optional)",
                        },
                        "device_id": {
                            "type": "string",
                            "description": "The ID of the device (optional)",
                        },
                        "city": {
                            "type": "string",
                            "description": "City or location name to search for (optional)",
                        },
                        "frequency": {
                            "type": "string",
                            "description": "Frequency: 'daily' or 'hourly'",
                        },
                    },
                    "required": ["frequency"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_airqo_metadata",
                "description": "Get metadata for grids, cohorts, devices, or sites.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "description": "Type of entity: 'grids', 'cohorts', 'devices', 'sites'",
                        }
                    },
                    "required": ["entity_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_air_quality_by_location",
                "description": "Get air quality data for any location using AirQo's enhanced site-based approach. PRIORITY for African locations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Location name (city, town, or specific site name)",
                        },
                        "country": {
                            "type": "string",
                            "description": "Country code (default 'UG' for Uganda)",
                        },
                    },
                    "required": ["location"],
                },
            },
        },
    ]


def get_weather_tools() -> list[dict]:
    """Get weather tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_city_weather",
                "description": "Get current weather conditions for any city. Returns temperature, humidity, wind, precipitation, and weather conditions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city",
                        }
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather_forecast",
                "description": "**Get detailed weather FORECAST for any city** - Use this when user asks for weather forecast, future weather, upcoming weather, or weather predictions. Returns hourly and daily forecasts up to 16 days including temperature, precipitation, humidity, wind, sunrise/sunset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city (e.g., 'London', 'New York', 'Tokyo')",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of forecast days (1-16, default: 7)",
                        },
                    },
                    "required": ["city"],
                },
            },
        },
    ]


def get_search_tools() -> list[dict]:
    """Get web search tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "MANDATORY TOOL: Use this for ANY question requiring research, current information, health data, policy information, solutions, safety guidelines, or general knowledge. ALWAYS use this instead of saying 'data not available' or giving generic advice. Search for specific, accurate information from reliable sources. Use for health impacts, cost-effective solutions, policy effectiveness, safety recommendations, research findings, and any topic needing up-to-date web information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific search query for accurate, current information. Make it detailed and targeted for best results (e.g., 'air pollution effects on pregnancy and fetal development 2025 studies', 'cost effective indoor PM2.5 reduction methods research', 'effective traffic pollution reduction policies near schools')",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def get_scraper_tools() -> list[dict]:
    """Get web scraping tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "scrape_website",
                "description": "Scrape content from a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to scrape",
                        }
                    },
                    "required": ["url"],
                },
            },
        }
    ]


def get_openmeteo_tools() -> list[dict]:
    """Get OpenMeteo tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_openmeteo_current_air_quality",
                "description": "Get current air quality data from OpenMeteo. Fallback option after WAQI and AirQo for global locations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude coordinate",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude coordinate",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Timezone (default: 'auto')",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_openmeteo_forecast",
                "description": "Get air quality forecast from OpenMeteo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude coordinate",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude coordinate",
                        },
                        "forecast_days": {
                            "type": "integer",
                            "description": "Number of forecast days (1-7)",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Timezone (default: 'auto')",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_openmeteo_historical",
                "description": "Get historical air quality data from OpenMeteo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude coordinate",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude coordinate",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Timezone (default: 'auto')",
                        },
                    },
                    "required": ["latitude", "longitude", "start_date", "end_date"],
                },
            },
        },
    ]


def get_carbon_intensity_tools() -> list[dict]:
    """Get UK Carbon Intensity tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_uk_carbon_intensity_current",
                "description": "Get current carbon intensity for the UK national grid.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_uk_carbon_intensity_today",
                "description": "Get carbon intensity for today with forecasts.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_uk_carbon_intensity_regional",
                "description": "Get carbon intensity for a specific UK region.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "UK region (e.g., 'London', 'Scotland')",
                        }
                    },
                    "required": ["region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_uk_generation_mix",
                "description": "Get current UK electricity generation mix.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_uk_carbon_intensity_factors",
                "description": "Get carbon intensity factors and methodology.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]


def get_defra_tools() -> list[dict]:
    """Get DEFRA (UK air quality) tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_defra_site_data",
                "description": "Get air quality data from a specific DEFRA monitoring site.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "site_code": {
                            "type": "string",
                            "description": "DEFRA site code",
                        }
                    },
                    "required": ["site_code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_defra_sites",
                "description": "Get list of all DEFRA monitoring sites.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_defra_species_codes",
                "description": "Get pollutant species codes used by DEFRA.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]


def get_uba_tools() -> list[dict]:
    """Get UBA (German air quality) tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_uba_measures",
                "description": "Get air quality measurements from German UBA network.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "description": "Pollutant component (e.g., 'pm10', 'no2')",
                        },
                        "scope": {
                            "type": "string",
                            "description": "Time scope: '1h', '8h', '24h'",
                        },
                    },
                    "required": ["component"],
                },
            },
        },
    ]


def get_document_tools() -> list[dict]:
    """Get document scanning tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "scan_document",
                "description": "Scan and extract data from uploaded documents (PDF, CSV, Excel).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the document file",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        },
    ]


def get_all_tools() -> list[dict]:
    """
    Get all tool definitions for OpenAI.

    Returns:
        List of tool dictionaries with all function declarations
    """
    all_tools = []
    all_tools.extend(get_waqi_tools())
    all_tools.extend(get_airqo_tools())
    all_tools.extend(get_weather_tools())
    all_tools.extend(get_search_tools())
    all_tools.extend(get_scraper_tools())
    all_tools.extend(get_openmeteo_tools())
    all_tools.extend(get_carbon_intensity_tools())
    all_tools.extend(get_defra_tools())
    all_tools.extend(get_uba_tools())
    all_tools.extend(get_document_tools())
    return all_tools
