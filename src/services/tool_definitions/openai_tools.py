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
                "description": """Get CURRENT real-time air quality data for ONE SINGLE city at a time.

WHEN TO USE:
- User asks "what is the air quality in [city]"
- User wants current/now/today air quality for a specific location
- City is in UK, Europe, Americas, Asia (NOT Africa - use get_african_city_air_quality for African cities)

IMPORTANT FOR COMPARISONS:
- This tool returns data for ONE city only
- To compare multiple cities: Call this function MULTIPLE TIMES (once per city)
- Example: "Compare London and Tokyo" → Call twice with city="London", then city="Tokyo"
- You CAN make parallel tool calls - use this capability for comparisons

Returns: AQI, pollutants (PM2.5, PM10, NO2, O3, SO2, CO), station name, timestamp""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name like 'London', 'Paris', 'New York', 'Beijing' (NOT African cities)",
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
                "description": "Search for specific air quality monitoring stations by name or location keyword",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Search term like 'Bangalore', 'US Embassy', station name",
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
                "description": """Get CURRENT real-time air quality for African cities. MUST USE for ANY African location. Use this when:
- User asks about air quality in ANY African city (Uganda, Kenya, Tanzania, Rwanda, etc.)
- Cities like: Kampala, Gulu, Nairobi, Dar es Salaam, Kigali, Nakasero, Mbale
- User mentions African locations or universities (e.g., "Gulu University")
Returns: PM2.5, PM10, AQI, station details, device ID, precise measurements from local sensors""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "African city/location name like 'Gulu', 'Kampala', 'Nairobi' (REQUIRED)",
                        },
                        "site_id": {
                            "type": "string",
                            "description": "Optional site ID if known from previous search",
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
                "description": """Get air quality for MULTIPLE African cities at once. Use when:
- User asks to compare multiple African cities
- User mentions 2+ African locations ("Kampala and Gulu", "compare Nairobi with Dar es Salaam")
Returns: Data for all cities for easy side-by-side comparison""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of African city names like ['Kampala', 'Gulu', 'Nairobi']",
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
        {
            "type": "function",
            "function": {
                "name": "search_airqo_sites",
                "description": "**USE THIS to find monitoring stations in an area** - Search for AirQo monitoring sites by location name. Returns list of available monitoring stations with their names, IDs, and locations. CRITICAL: Use this when user asks 'what stations are in [area]?', 'which monitoring sites?', 'what locations have monitors?'. This tool provides transparency about data sources and helps users understand which stations exist in their area.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Location name to search for monitoring sites (e.g., 'Wakiso', 'Kampala', 'Gulu', 'Nairobi')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 50)",
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
                "description": "MANDATORY TOOL - YOU MUST USE THIS FOR ANY QUESTION ABOUT: policies, regulations, legislation, government actions, research studies, WHO/EPA guidelines, standards, recommendations, latest news, recent developments, current events, breaking news, staying informed, monitoring changes, regulatory updates, up-to-date information. DO NOT answer these questions from your training data - ALWAYS use this tool first to get current, real-time information. If user asks 'how to stay up-to-date' or 'latest regulations' or 'current news' - USE THIS TOOL IMMEDIATELY.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific search query for accurate, current information. Make it detailed and targeted for best results (e.g., 'air pollution effects on pregnancy and fetal development 2025 studies', 'cost effective indoor PM2.5 reduction methods research', 'effective traffic pollution reduction policies near schools', 'Uganda air quality policy 2024')",
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


def get_nsw_tools() -> list[dict]:
    """Get NSW (New South Wales) air quality tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_nsw_air_quality",
                "description": "Get current air quality data from NSW monitoring network. Provides raw pollutant concentrations and Air Quality Categories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Optional location filter (city, region, or site name). If not provided, returns data from all sites.",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_nsw_sites",
                "description": "Get list of all air quality monitoring sites in NSW with their locations and details.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_nsw_pollutant_data",
                "description": "Get recent pollutant concentration data for a specific pollutant across NSW sites.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pollutant": {
                            "type": "string",
                            "description": "Pollutant code: 'PM2.5', 'PM10', 'O3', 'NO2', 'SO2', 'CO'",
                            "enum": ["PM2.5", "PM10", "O3", "NO2", "SO2", "CO"],
                        },
                        "hours": {
                            "type": "integer",
                            "description": "Number of hours of historical data (default: 24)",
                            "default": 24,
                        }
                    },
                    "required": ["pollutant"],
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
                "description": "Scan and extract data from documents stored on disk. IMPORTANT: Do NOT use this tool if the user uploaded a document in the current conversation - uploaded documents are automatically scanned and their content is already provided to you in the UPLOADED DOCUMENTS section. Only use this tool if the user asks you to read a specific file from a file path on the server's disk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute file path to the document file on disk (e.g., /path/to/file.csv)",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        },
    ]


def get_geocoding_tools() -> list[dict]:
    """Get geocoding tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "geocode_address",
                "description": "Convert an address or location name to geographic coordinates (latitude/longitude). Use this to find coordinates for cities, addresses, or landmarks. Essential for air quality queries that need precise location data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "The address, city, or location name to geocode (e.g., 'London, UK', '1600 Pennsylvania Avenue, Washington DC')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 1)",
                        },
                    },
                    "required": ["address"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reverse_geocode",
                "description": "Convert geographic coordinates (latitude/longitude) to a human-readable address. Use this to identify the location name for given coordinates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude coordinate (e.g., 51.5074 for London)",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude coordinate (e.g., -0.1278 for London)",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_location_from_ip",
                "description": "Get approximate location information from an IP address. Use this as a fallback when user location is needed but not provided. Note: IP geolocation is approximate and may not reflect the user's actual current location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ip_address": {
                            "type": "string",
                            "description": "IP address to geolocate (optional - uses request IP if not provided)",
                        },
                    },
                    "required": [],
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
    all_tools.extend(get_nsw_tools())
    all_tools.extend(get_document_tools())
    all_tools.extend(get_geocoding_tools())
    return all_tools
