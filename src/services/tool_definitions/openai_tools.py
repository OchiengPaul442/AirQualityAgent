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
                "description": """🌍 Get REAL-TIME current air quality data for ONE specific city (NON-AFRICAN cities only).

⚠️ WHEN TO USE THIS TOOL - YOU MUST call this for:
- User asks "what is the air quality in [city]" for non-African cities
- User wants current/now/today air quality for UK, Europe, Americas, Asia
- Examples: London, Paris, New York, Tokyo, Beijing, Delhi, Sydney

❌ DO NOT USE FOR:
- African cities (Uganda, Kenya, Tanzania, Rwanda) → Use get_african_city_air_quality instead

📊 RETURNS: Real-time measurements including:
- Overall AQI (Air Quality Index)
- PM2.5, PM10, NO2, O3, SO2, CO concentrations
- Monitoring station name and location
- Timestamp of measurement
- Data source for citation

💡 FOR COMPARISONS: Call this tool MULTIPLE TIMES (once per city) to compare air quality between cities.
Example: "Compare London and Tokyo" → Call twice: city="London", then city="Tokyo"
You CAN make parallel tool calls - use this for efficiency!

🔄 THIS TOOL PROVIDES LIVE DATA - NOT YOUR TRAINING DATA. ALWAYS USE FOR SPECIFIC CITIES.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name (e.g., 'London', 'Paris', 'New York', 'Beijing'). NOT for African cities.",
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
                "description": """🌍 Get REAL-TIME current air quality for African cities from AirQo monitoring network.

⚠️ MANDATORY USE - YOU MUST call this for ANY African location:
- Uganda: Kampala, Gulu, Jinja, Mbale, Nakasero, Mbarara
- Kenya: Nairobi, Mombasa, Kisumu, Nakuru, Eldoret
- Tanzania: Dar es Salaam, Dodoma, Mwanza, Arusha, Mbeya
- Rwanda: Kigali, Butare, Musanze, Ruhengeri, Gisenyi
- Any mention of African universities, districts, or neighborhoods

❌ DO NOT use get_city_air_quality for African cities - it will fail!
✅ ALWAYS use THIS TOOL for any location in Africa

📊 RETURNS: High-precision local measurements:
- PM2.5 and PM10 concentrations (µg/m³)
- Calculated AQI values
- Device ID and site details
- Exact location coordinates
- Timestamp
- Data source: AirQo monitoring network

💡 This provides MORE ACCURATE data for African cities than global networks.

🔄 THIS TOOL PROVIDES LIVE DATA FROM LOCAL SENSORS - NOT YOUR TRAINING DATA.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "African city/location name (e.g., 'Gulu', 'Kampala', 'Nairobi', 'Dar es Salaam'). REQUIRED.",
                        },
                        "site_id": {
                            "type": "string",
                            "description": "Optional specific site ID if known from previous search results",
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
                "name": "get_air_quality_forecast",
                "description": "Get air quality FORECAST for any city worldwide. Use this when user asks about future air quality, tomorrow's air quality, air quality predictions, or upcoming air quality conditions. Automatically routes to the best available service (WAQI for global cities, AirQo for African cities). Returns 3-8 day forecast with AQI predictions and pollutant levels.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name (e.g., 'London', 'New York', 'Nairobi', 'Tokyo')",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of forecast days (1-8, default: 3)",
                        },
                    },
                    "required": ["city"],
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
                "description": """🔍 Search the web for CURRENT, UP-TO-DATE information.

⚠️ ABSOLUTELY MANDATORY for these topics:
- Policies, regulations, legislation, government actions
- Research studies, WHO/EPA guidelines, standards, recommendations  
- Latest news, recent developments, current events, breaking news
- Questions with 'recent', 'latest', 'new', 'current', 'update', 'up-to-date' keywords
- Questions about specific years (2024, 2025, 2026, etc.)
- Health impacts research, solutions, recommendations
- Staying informed, monitoring changes, regulatory updates

🚫 YOUR TRAINING DATA IS FROM 2023 AND EARLIER
✅ YOU MUST USE THIS TOOL TO GET 2024-2026 INFORMATION

📊 Example queries that REQUIRE this tool:
- "Latest air quality regulations in Uganda 2025"
- "Recent research on PM2.5 health effects"
- "Current WHO air quality guidelines"
- "News about air pollution in East Africa"
- "What are the newest EPA standards?"

💡 Make search queries specific and targeted for best results.

🔄 THIS PROVIDES REAL INTERNET SEARCH RESULTS - NOT YOUR TRAINING DATA.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific, detailed search query for accurate current information (e.g., 'Uganda air quality policy 2025 updates', 'latest WHO PM2.5 guidelines 2024', 'recent studies PM2.5 pregnancy effects')",
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
                "description": """📄 Extract and analyze content from a specific website URL.

⚠️ USE THIS TOOL WHEN:
- User provides a specific URL to analyze
- User asks to "scrape", "check", "analyze", "extract from" a website
- User wants information from a specific web page (WHO, EPA, government sites, etc.)

📊 RETURNS: 
- Full text content from the webpage
- Structured data extraction
- Clean, readable format for analysis

💡 Example requests:
- "What does https://who.int/air-quality say about PM2.5?"
- "Scrape the EPA guidelines from this URL"
- "Check this website for air quality standards"

🔄 PROVIDES CURRENT WEB CONTENT - NOT YOUR TRAINING DATA.
✅ ALWAYS cite the source URL in your response after scraping.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The complete URL to scrape (must start with http:// or https://)",
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
                        },
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
                "description": "Scan and extract data from documents stored on disk. IMPORTANT: This tool is ONLY for files that exist on the server's disk with full file paths. Do NOT use this tool if the user uploaded a document in the current conversation - uploaded documents are automatically scanned and their content is already provided to you in the UPLOADED DOCUMENTS section. Do NOT use this tool for documents mentioned by filename only - those must be uploaded through the file upload interface. Only use this tool if the user provides a complete file path (e.g., /path/to/file.csv) AND you can confirm the file exists on disk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute file path to the document file on disk (e.g., /path/to/file.csv). Must be a complete path, not just a filename.",
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


def get_visualization_tools() -> list[dict]:
    """Get chart/visualization generation tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_chart",
                "description": """🎨 Generate professional charts and graphs from data.

⚠️ WHEN TO USE THIS TOOL:
- User explicitly requests "plot a chart", "show me a graph", "visualize this data"
- User wants to see trends over time
- User asks for comparison visualizations
- User uploads CSV/Excel data and requests visual analysis
- User mentions "chart", "graph", "plot", "visualize", "show visually"
- **IMPORTANT**: When user uploads CSV/Excel and asks to "understand the trend", ALWAYS use this tool

📊 SUPPORTED CHART TYPES:
- line: Trends over time (PM2.5 over days, temperature changes)
- bar: Comparisons between categories (cities, pollutants)
- scatter: Correlations (PM2.5 vs temperature)
- histogram: Data distributions (AQI frequency)
- box: Statistical summaries (quartiles, outliers)
- pie: Proportions (pollutant composition)
- area: Cumulative trends (stacked areas)
- timeseries: Time-based data with date parsing

🔄 RETURNS: Base64-encoded PNG image ready for display in UI

💡 WORKFLOW FOR CSV/EXCEL FILES:
1. User uploads file → scan_document to read it
2. User asks for visualization → generate_chart with the parsed data
3. Choose appropriate chart_type based on data structure

Example usage:
User: "Plot PM2.5 levels from the uploaded data"
→ Step 1: scan_document(file)
→ Step 2: generate_chart with data from scan_document""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Array of data objects. Each object should have consistent keys. Example: [{'date': '2025-01-01', 'pm25': 45}, {'date': '2025-01-02', 'pm25': 52}]",
                        },
                        "chart_type": {
                            "type": "string",
                            "enum": [
                                "line",
                                "bar",
                                "scatter",
                                "histogram",
                                "box",
                                "pie",
                                "area",
                                "timeseries",
                            ],
                            "description": "Type of chart to generate",
                        },
                        "x_column": {
                            "type": "string",
                            "description": "Name of the data field for x-axis (e.g., 'date', 'city', 'time')",
                        },
                        "y_column": {
                            "type": "string",
                            "description": "Name of the data field(s) for y-axis (e.g., 'pm25', 'aqi')",
                        },
                        "title": {
                            "type": "string",
                            "description": "Title for the chart (e.g., 'Air Quality (PM2.5) Over Time')",
                        },
                        "x_label": {
                            "type": "string",
                            "description": "Label for x-axis (optional)",
                        },
                        "y_label": {
                            "type": "string",
                            "description": "Label for y-axis (optional)",
                        },
                        "color_column": {
                            "type": "string",
                            "description": "Optional column name for color coding data points",
                        },
                    },
                    "required": ["data", "chart_type", "title"],
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
    all_tools.extend(get_visualization_tools())
    return all_tools
