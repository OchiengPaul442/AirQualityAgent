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
                description="🌍 Get REAL-TIME current air quality data for ONE specific city (NON-AFRICAN cities). YOU MUST USE THIS TOOL for user queries about air quality in UK, Europe, Americas, Asia cities (e.g., London, Paris, New York, Tokyo). Returns: AQI, PM2.5, PM10, NO2, O3, SO2, CO, station details, timestamp. For African cities, use get_african_city_air_quality instead. For comparisons, call this tool multiple times (once per city). THIS PROVIDES LIVE DATA - NOT YOUR TRAINING DATA.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="City name (e.g., 'London', 'Paris', 'New York', 'Tokyo'). NOT for African cities.",
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
                description="🌍 Get REAL-TIME air quality for African cities from AirQo network. **MANDATORY USE** - YOU MUST call this for ANY African location: Uganda (Kampala, Gulu, Jinja, Mbale), Kenya (Nairobi, Mombasa, Kisumu), Tanzania (Dar es Salaam, Dodoma, Mwanza), Rwanda (Kigali, Butare, Musanze). DO NOT use get_city_air_quality for African cities. Returns: PM2.5, PM10, AQI, device ID, site details, timestamp, coordinates. Source: AirQo monitoring network. THIS PROVIDES LIVE DATA FROM LOCAL SENSORS - NOT YOUR TRAINING DATA.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="African city/location name (e.g., 'Gulu', 'Kampala', 'Nairobi', 'Dar es Salaam')",
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
                name="get_air_quality_forecast",
                description="Get air quality FORECAST for any city worldwide. Use this when user asks about future air quality, tomorrow's air quality, air quality predictions, or upcoming air quality conditions. Automatically routes to the best available service (WAQI for global cities, AirQo for African cities). Returns 3-8 day forecast with AQI predictions and pollutant levels.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "city": types.Schema(
                            type=types.Type.STRING,
                            description="City name (e.g., 'London', 'New York', 'Nairobi', 'Tokyo')",
                        ),
                        "days": types.Schema(
                            type=types.Type.INTEGER,
                            description="Number of forecast days (1-8, default: 3)",
                        ),
                    },
                    required=["city"],
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
                description="🔍 Search the web for CURRENT, UP-TO-DATE information. **ABSOLUTELY MANDATORY** for: policies, regulations, legislation, research studies, WHO/EPA guidelines, latest news, recent developments, questions with 'recent'/'latest'/'new'/'current'/'update' keywords, questions about 2024-2026. YOUR TRAINING DATA IS FROM 2023. YOU MUST USE THIS TOOL for current information. Example queries requiring this: 'Latest air quality regulations 2025', 'Recent PM2.5 research', 'Current WHO guidelines', 'News about air pollution'. THIS PROVIDES REAL INTERNET SEARCH - NOT YOUR TRAINING DATA.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Specific, detailed search query (e.g., 'Uganda air quality policy 2025', 'latest WHO PM2.5 guidelines 2024', 'recent PM2.5 pregnancy studies')",
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
                description="📄 Extract and analyze content from a specific website URL. USE THIS TOOL when user provides a URL or asks to 'scrape', 'check', 'analyze' a website. Returns full text content from webpage. Example: 'What does https://who.int/air-quality say?'. ALWAYS cite the source URL in your response after scraping. THIS PROVIDES CURRENT WEB CONTENT - NOT YOUR TRAINING DATA.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "url": types.Schema(
                            type=types.Type.STRING,
                            description="Complete URL to scrape (must start with http:// or https://)",
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
                description="Scan and extract data from documents stored on disk. IMPORTANT: This tool is ONLY for files that exist on the server's disk with full file paths. Do NOT use this tool if the user uploaded a document in the current conversation - uploaded documents are automatically scanned and their content is already provided to you in the UPLOADED DOCUMENTS section. Do NOT use this tool for documents mentioned by filename only - those must be uploaded through the file upload interface. Only use this tool if the user provides a complete file path (e.g., /path/to/file.csv) AND you can confirm the file exists on disk.",
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


def get_visualization_tools() -> types.Tool:
    """Get chart/visualization generation tool definitions."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="generate_chart",
                description="🎨 Generate professional charts and graphs from data. Use this when the user requests visualizations like 'plot a chart', 'show me a graph', 'visualize this data', 'create a chart showing trends', etc. Returns a base64-encoded image (data:image/png;base64,...) in chart_data field that should be embedded in your response as ![Chart](data:image/png;base64,...) for automatic rendering. Supports line charts, bar charts, scatter plots, histograms, box plots, pie charts, area charts, and time series. IMPORTANT: After calling this tool, include the returned chart_data as a markdown image in your response so it displays inline!",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "data": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.OBJECT),
                            description="Array of data objects to visualize. Each object should have consistent keys. Example: [{'date': '2025-01-01', 'pm25': 45}, {'date': '2025-01-02', 'pm25': 52}]",
                        ),
                        "chart_type": types.Schema(
                            type=types.Type.STRING,
                            description="Type of chart: 'line' (trends over time), 'bar' (comparisons), 'scatter' (correlations), 'histogram' (distributions), 'box' (statistical summary), 'pie' (proportions), 'area' (cumulative trends), 'timeseries' (time-based data)",
                        ),
                        "x_column": types.Schema(
                            type=types.Type.STRING,
                            description="Name of the data field to use for x-axis (e.g., 'date', 'city', 'time')",
                        ),
                        "y_column": types.Schema(
                            type=types.Type.STRING,
                            description="Name of the data field(s) to use for y-axis (e.g., 'pm25', 'aqi'). Can be a single column or multiple columns separated by commas.",
                        ),
                        "title": types.Schema(
                            type=types.Type.STRING,
                            description="Title for the chart (e.g., 'Air Quality (PM2.5) Over Time')",
                        ),
                        "x_label": types.Schema(
                            type=types.Type.STRING,
                            description="Label for x-axis (optional, defaults to x_column name)",
                        ),
                        "y_label": types.Schema(
                            type=types.Type.STRING,
                            description="Label for y-axis (optional, defaults to y_column name)",
                        ),
                        "color_column": types.Schema(
                            type=types.Type.STRING,
                            description="Optional: Name of column to use for color coding data points",
                        ),
                    },
                    required=["data", "chart_type", "title"],
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
        get_visualization_tools(),
    ]
