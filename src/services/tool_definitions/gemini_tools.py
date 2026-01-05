"""
Tool definitions for Gemini AI provider.

Contains all function declarations for tools available to Gemini models.
"""

from google.genai import types


def get_waqi_tools() -> types.Tool:
    """Get WAQI (World Air Quality Index) tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_city_air_quality",
                description="Get real-time air quality data for a specific city using WAQI.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="The name of the city (e.g., London, Paris, Kampala)",
                        )
                    },
                    required=["city"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_waqi_stations",
                description="Search for air quality monitoring stations by name or keyword.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "keyword": types.Schema(
                            type=types.Type.STRING,
                            description="Search term (e.g., 'Bangalore', 'US Embassy')",
                        )
                    },
                    required=["keyword"],
                ),
            ),
        ]
    )


def get_airqo_tools() -> types.Tool:
    """Get AirQo tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_african_city_air_quality",
                description="**PRIMARY TOOL for African cities** - Get real-time air quality from AirQo monitoring network. Use this FIRST for ANY African location (Uganda, Kenya, Tanzania, Rwanda, etc.). Searches by city/location name (e.g., Gulu, Kampala, Nakasero, Mbale, Nairobi). Returns actual measurements from local monitoring stations. Coverage includes major and minor cities across East Africa.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="City or location name in Africa (e.g., 'Gulu', 'Kampala', 'Nakasero', 'Nairobi', 'Dar es Salaam')",
                        ),
                        "site_id": types.Schema(
                            type=types.Type.STRING,
                            description="Optional site ID if known from previous searches",
                        ),
                    },
                    required=["city"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_multiple_african_cities_air_quality",
                description="Get real-time air quality for MULTIPLE African cities simultaneously. Use this when user asks about multiple locations (e.g., 'air quality in Kampala and Gulu', 'compare air quality between Nairobi and Dar es Salaam'). Returns data for all requested cities in one response for easy comparison.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "cities": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING),
                            description="List of city names in Africa (e.g., ['Gulu', 'Kampala', 'Nairobi'])",
                        ),
                    },
                    required=["cities"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_airqo_history",
                description="Get historical air quality data for a specific site or device. NOTE: AirQo API only provides data for the last 60 days. For older historical data, direct users to the AirQo Analytics platform.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "site_id": types.Schema(
                            type=types.Type.STRING,
                            description="The ID of the site (optional)",
                        ),
                        "device_id": types.Schema(
                            type=types.Type.STRING,
                            description="The ID of the device (optional)",
                        ),
                        "start_time": types.Schema(
                            type=types.Type.STRING,
                            description="Start time in ISO format (YYYY-MM-DDTHH:MM:SS). Must be within last 60 days.",
                        ),
                        "end_time": types.Schema(
                            type=types.Type.STRING,
                            description="End time in ISO format (YYYY-MM-DDTHH:MM:SS). Must be within last 60 days.",
                        ),
                        "frequency": types.Schema(
                            type=types.Type.STRING,
                            description="Frequency: 'hourly', 'daily', or 'raw'",
                        ),
                    },
                    required=["frequency"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_airqo_forecast",
                description="Get air quality forecast for a location, site, or device. Can search by city name or location if site_id is unknown.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "site_id": types.Schema(
                            type=types.Type.STRING,
                            description="The ID of the site (optional)",
                        ),
                        "device_id": types.Schema(
                            type=types.Type.STRING,
                            description="The ID of the device (optional)",
                        ),
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="City or location name to search for (optional)",
                        ),
                        "frequency": types.Schema(
                            type=types.Type.STRING,
                            description="Frequency: 'daily' or 'hourly'",
                        ),
                    },
                    required=["frequency"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_airqo_metadata",
                description="Get metadata for grids, cohorts, devices, or sites.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "entity_type": types.Schema(
                            type=types.Type.STRING,
                            description="Type of entity: 'grids', 'cohorts', 'devices', 'sites'",
                        )
                    },
                    required=["entity_type"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_air_quality_by_location",
                description="Get air quality data for any location using AirQo's enhanced site-based approach. PRIORITY for African locations.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "location": types.Schema(
                            type=types.Type.STRING,
                            description="Location name (city, town, or specific site name)",
                        ),
                        "country": types.Schema(
                            type=types.Type.STRING,
                            description="Country code (default 'UG' for Uganda)",
                        ),
                    },
                    required=["location"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_airqo_sites",
                description="**USE THIS to find monitoring stations in an area** - Search for AirQo monitoring sites by location name. Returns list of available monitoring stations with their names, IDs, and locations. CRITICAL: Use this when user asks 'what stations are in [area]?', 'which monitoring sites?', 'what locations have monitors?'. This tool provides transparency about data sources and helps users understand which stations exist in their area.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "location": types.Schema(
                            type=types.Type.STRING,
                            description="Location name to search for monitoring sites (e.g., 'Wakiso', 'Kampala', 'Gulu', 'Nairobi')",
                        ),
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum number of results to return (default: 50)",
                        ),
                    },
                    required=["location"],
                ),
            ),
        ]
    )


def get_weather_tools() -> types.Tool:
    """Get weather tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_city_weather",
                description="Get current weather conditions for any city. Returns temperature, humidity, wind, precipitation, and weather conditions.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="The name of the city",
                        )
                    },
                    required=["city"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_weather_forecast",
                description="**Get detailed weather FORECAST for any city** - Use this when user asks for weather forecast, future weather, upcoming weather, or weather predictions. Returns hourly and daily forecasts up to 16 days including temperature, precipitation, humidity, wind, sunrise/sunset.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="The name of the city (e.g., 'London', 'New York', 'Tokyo')",
                        ),
                        "days": types.Schema(
                            type=types.Type.INTEGER,
                            description="Number of forecast days (1-16, default: 7)",
                        ),
                    },
                    required=["city"],
                ),
            ),
        ]
    )


def get_search_tools() -> types.Tool:
    """Get web search tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_web",
                description="CRITICAL MANDATORY TOOL for research and policy questions. YOU MUST USE THIS TOOL FOR: (1) ANY question about policies, regulations, legislation, government actions - even if you know general information, SEARCH for current details. (2) Questions with 'recent', 'latest', 'new', 'current' keywords - YOUR TRAINING DATA IS OUTDATED. (3) Research studies, WHO/EPA guidelines, standards - these update frequently. (4) Questions about specific years beyond 2023. (5) Health impacts, solutions, recommendations - SEARCH for latest evidence-based information. DO NOT rely on your training data for these topics - it becomes outdated quickly. ALWAYS search to get current, accurate information from reliable sources.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Specific search query for accurate, current information. Make it detailed and targeted for best results (e.g., 'air pollution effects on pregnancy and fetal development 2025 studies', 'cost effective indoor PM2.5 reduction methods research', 'effective traffic pollution reduction policies near schools', 'Uganda air quality policy 2024')",
                        )
                    },
                    required=["query"],
                ),
            ),
        ]
    )


def get_scraper_tools() -> types.Tool:
    """Get web scraping tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="scrape_website",
                description="Scrape content from a specific URL.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "url": types.Schema(
                            type=types.Type.STRING,
                            description="The URL to scrape",
                        )
                    },
                    required=["url"],
                ),
            )
        ]
    )


def get_openmeteo_tools() -> types.Tool:
    """Get OpenMeteo tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_openmeteo_current_air_quality",
                description="Get current air quality data from OpenMeteo. Fallback option after WAQI and AirQo for global locations.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "latitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Latitude coordinate",
                        ),
                        "longitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Longitude coordinate",
                        ),
                        "timezone": types.Schema(
                            type=types.Type.STRING,
                            description="Timezone (default: 'auto')",
                        ),
                    },
                    required=["latitude", "longitude"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_openmeteo_forecast",
                description="Get air quality forecast from OpenMeteo.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "latitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Latitude coordinate",
                        ),
                        "longitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Longitude coordinate",
                        ),
                        "forecast_days": types.Schema(
                            type=types.Type.INTEGER,
                            description="Number of forecast days (1-7)",
                        ),
                        "timezone": types.Schema(
                            type=types.Type.STRING,
                            description="Timezone (default: 'auto')",
                        ),
                    },
                    required=["latitude", "longitude"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_openmeteo_historical",
                description="Get historical air quality data from OpenMeteo.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "latitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Latitude coordinate",
                        ),
                        "longitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Longitude coordinate",
                        ),
                        "start_date": types.Schema(
                            type=types.Type.STRING,
                            description="Start date in YYYY-MM-DD format",
                        ),
                        "end_date": types.Schema(
                            type=types.Type.STRING,
                            description="End date in YYYY-MM-DD format",
                        ),
                        "timezone": types.Schema(
                            type=types.Type.STRING,
                            description="Timezone (default: 'auto')",
                        ),
                    },
                    required=["latitude", "longitude", "start_date", "end_date"],
                ),
            ),
        ]
    )


def get_carbon_intensity_tools() -> types.Tool:
    """Get UK Carbon Intensity tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_uk_carbon_intensity_current",
                description="Get current carbon intensity for the UK national grid.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_uk_carbon_intensity_today",
                description="Get carbon intensity for today with forecasts.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_uk_carbon_intensity_regional",
                description="Get carbon intensity for a specific UK region.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "region": types.Schema(
                            type=types.Type.STRING,
                            description="UK region (e.g., 'London', 'Scotland')",
                        )
                    },
                    required=["region"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_uk_generation_mix",
                description="Get current UK electricity generation mix.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_uk_carbon_intensity_factors",
                description="Get carbon intensity factors and methodology.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
        ]
    )


def get_defra_tools() -> types.Tool:
    """Get DEFRA (UK air quality) tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_defra_site_data",
                description="Get air quality data from a specific DEFRA monitoring site.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "site_code": types.Schema(
                            type=types.Type.STRING,
                            description="DEFRA site code",
                        )
                    },
                    required=["site_code"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_defra_sites",
                description="Get list of all DEFRA monitoring sites.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_defra_species_codes",
                description="Get pollutant species codes used by DEFRA.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
        ]
    )


def get_uba_tools() -> types.Tool:
    """Get UBA (German air quality) tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_uba_measures",
                description="Get air quality measurements from German UBA network.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "component": types.Schema(
                            type=types.Type.STRING,
                            description="Pollutant component (e.g., 'pm10', 'no2')",
                        ),
                        "scope": types.Schema(
                            type=types.Type.STRING,
                            description="Time scope: '1h', '8h', '24h'",
                        ),
                    },
                    required=["component"],
                ),
            ),
        ]
    )


def get_nsw_tools() -> types.Tool:
    """Get NSW (New South Wales) air quality tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_nsw_air_quality",
                description="Get current air quality data from NSW monitoring network. Provides raw pollutant concentrations and Air Quality Categories.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "location": types.Schema(
                            type=types.Type.STRING,
                            description="Optional location filter (city, region, or site name). If not provided, returns data from all sites.",
                        ),
                    },
                    required=[],
                ),
            ),
            types.FunctionDeclaration(
                name="get_nsw_sites",
                description="Get list of all air quality monitoring sites in NSW with their locations and details.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                    required=[],
                ),
            ),
            types.FunctionDeclaration(
                name="get_nsw_pollutant_data",
                description="Get recent pollutant concentration data for a specific pollutant across NSW sites.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "pollutant": types.Schema(
                            type=types.Type.STRING,
                            description="Pollutant code: 'PM2.5', 'PM10', 'O3', 'NO2', 'SO2', 'CO'",
                            enum=["PM2.5", "PM10", "O3", "NO2", "SO2", "CO"],
                        ),
                        "hours": types.Schema(
                            type=types.Type.INTEGER,
                            description="Number of hours of historical data (default: 24)",
                        ),
                    },
                    required=["pollutant"],
                ),
            ),
        ]
    )


def get_document_tools() -> types.Tool:
    """Get document scanning tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="scan_document",
                description="Scan and extract data from documents stored on disk. IMPORTANT: Do NOT use this tool if the user uploaded a document in the current conversation - uploaded documents are automatically scanned and their content is already provided to you in the UPLOADED DOCUMENTS section. Only use this tool if the user asks you to read a specific file from a file path on the server's disk.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "file_path": types.Schema(
                            type=types.Type.STRING,
                            description="Absolute file path to the document file on disk (e.g., /path/to/file.csv)",
                        )
                    },
                    required=["file_path"],
                ),
            ),
        ]
    )


def get_geocoding_tools() -> types.Tool:
    """Get geocoding tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="geocode_address",
                description="Convert an address or location name to geographic coordinates (latitude/longitude). Use this to find coordinates for cities, addresses, or landmarks. Essential for air quality queries that need precise location data.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "address": types.Schema(
                            type=types.Type.STRING,
                            description="The address, city, or location name to geocode (e.g., 'London, UK', '1600 Pennsylvania Avenue, Washington DC')",
                        ),
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum number of results to return (default: 1)",
                        ),
                    },
                    required=["address"],
                ),
            ),
            types.FunctionDeclaration(
                name="reverse_geocode",
                description="Convert geographic coordinates (latitude/longitude) to a human-readable address. Use this to identify the location name for given coordinates.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "latitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Latitude coordinate (e.g., 51.5074 for London)",
                        ),
                        "longitude": types.Schema(
                            type=types.Type.NUMBER,
                            description="Longitude coordinate (e.g., -0.1278 for London)",
                        ),
                    },
                    required=["latitude", "longitude"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_location_from_ip",
                description="Get approximate location information from an IP address. Use this as a fallback when user location is needed but not provided. Note: IP geolocation is approximate and may not reflect the user's actual current location.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "ip_address": types.Schema(
                            type=types.Type.STRING,
                            description="IP address to geolocate (optional - uses request IP if not provided)",
                        ),
                    },
                    required=[],
                ),
            ),
        ]
    )


def get_all_tools() -> list[types.Tool]:
    """
    Get all tool definitions for Gemini.

    Returns:
        List of Tool objects with all function declarations
    """
    return [
        get_waqi_tools(),
        get_airqo_tools(),
        get_weather_tools(),
        get_search_tools(),
        get_scraper_tools(),
        get_openmeteo_tools(),
        get_carbon_intensity_tools(),
        get_defra_tools(),
        get_uba_tools(),
        get_nsw_tools(),
        get_document_tools(),
        get_geocoding_tools(),
    ]
