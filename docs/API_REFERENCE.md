# AERIS-AQ API Reference

Complete reference for all API endpoints provided by **AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)**, your Air Quality AI Assistant.

---

## Meet AERIS-AQ

**AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address AERIS-AQ by name in your conversations!

**AERIS-AQ** represents:

- **Artificial**: Advanced AI/ML core powering predictions and analysis
- **Environmental**: Specialized focus on air quality and atmospheric conditions
- **Real-time**: Live monitoring with immediate alerts and updates
- **Intelligence**: Machine learning capabilities for pattern recognition and forecasting
- **System**: Complete integrated platform with sensors, dashboard, and APIs
- **Air Quality**: Dedicated to comprehensive air pollution monitoring and analysis

---

## Base URL

## Base URL

```
http://localhost:8000/api/v1
```

---

## Authentication

Currently, the API does not require authentication. For production deployments, implement API key authentication.

---

## Quick Links

- 📘 [Session Management Guide](./SESSION_MANAGEMENT.md) - Detailed guide on managing conversations
- 🌍 [Air Quality API Guide](./AIR_QUALITY_API.md) - Comprehensive guide for air quality data

---

## Endpoints Overview

| Endpoint                      | Method | Purpose                            |
| ----------------------------- | ------ | ---------------------------------- |
| `/health`                     | GET    | Health check                       |
| `/agent/chat`                 | POST   | Chat with AI agent                 |
| `/air-quality/query`          | POST   | Get air quality data (all sources) |
| `/sessions/new`               | POST   | Create new session                 |
| `/sessions`                   | GET    | List all sessions                  |
| `/sessions/{id}`              | GET    | Get session details                |
| `/sessions/{id}`              | DELETE | Delete session                     |
| `/sessions/{id}/messages`     | GET    | Get paginated messages             |
| `/visualization/from-search`  | POST   | Visualize search results           |
| `/visualization/from-file`    | POST   | Visualize uploaded file            |
| `/visualization/capabilities` | GET    | Get visualization capabilities     |

---

## Health Check

Check if the service is running.

**Endpoint:** `GET /health`

**Response:**

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Check Model Capabilities

Check if the current AI model supports specific features like vision (image input).

**Endpoint:** `GET /api/v1/agent/capabilities`

**Response:**

```json
{
  "provider": "gemini",
  "model": "gemini-1.5-flash",
  "supports_vision": true,
  "supports_reasoning": true,
  "max_image_size_mb": 10,
  "allowed_image_formats": ["jpg", "jpeg", "png", "gif", "webp", "bmp"],
  "cost_optimization_enabled": true,
  "cache_hit_rate_pct": 45.2
}
```

**Response Fields:**

| Field                       | Type    | Description                          |
| --------------------------- | ------- | ------------------------------------ |
| `provider`                  | string  | AI provider (gemini, openai, ollama) |
| `model`                     | string  | AI model name                        |
| `supports_vision`           | boolean | Whether model can process images     |
| `max_image_size_mb`         | integer | Maximum image size in megabytes      |
| `allowed_image_formats`     | array   | Supported image file formats         |
| `cost_optimization_enabled` | boolean | Whether cost optimization is active  |
| `cache_hit_rate_pct`        | float   | Cache effectiveness percentage       |

---

## Chat with Agent

Send a message to the AI agent and receive a response with automatic conversation saving. **Now supports document upload** for file analysis.

**Endpoint:** `POST /api/v1/agent/chat`

### Request

**Content-Type:** `multipart/form-data` (when uploading file) or `application/json` (text only)

**Form Fields:**

| Field        | Type   | Required | Description                                                                                        |
| ------------ | ------ | -------- | -------------------------------------------------------------------------------------------------- |
| `message`    | string | Yes      | User's question or request                                                                         |
| `session_id` | string | No       | Session ID for continuing a conversation. Omit to start new.                                       |
| `file`       | file   | No       | Optional document upload (PDF, CSV, Excel) - Max 8MB                                               |
| `image`      | file   | No       | Optional image upload (JPG, PNG, WebP, etc.) - Max 10MB. Only available with vision-capable models |
| `latitude`   | float  | No       | GPS latitude (-90 to 90) for precise location-based queries                                        |
| `longitude`  | float  | No       | GPS longitude (-180 to 180) for precise location-based queries                                     |
| `role`       | string | No       | Response style: `general`, `executive`, `technical`, `simple`, `policy`                            |

**Without File (JSON):**

```json
{
  "message": "What's the air quality in Nairobi?",
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df"
}
```

**With File (multipart/form-data):**

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -F "message=Analyze this air quality data and find trends" \
  -F "session_id=10a28e5c-9dc2-4e1f-9e21-8109d27ba9df" \
  -F "file=@/path/to/data.csv"
```

**With GPS Location (multipart/form-data):**

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -F "message=What's the air quality here?" \
  -F "latitude=40.7128" \
  -F "longitude=-74.0060"
```

**With Role Specification (multipart/form-data):**

```bash
# Executive summary style
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -F "message=What's the air quality in Tokyo?" \
  -F "role=executive"

# Technical analysis style
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -F "message=Explain PM2.5 pollution" \
  -F "role=technical"

# Simple explanations
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -F "message=What causes air pollution?" \
  -F "role=simple"
```

### Response

```json
{
  "response": "Based on the uploaded data, I found the following trends...",
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df",
  "tools_used": ["document_scanner", "airqo_api"],
  "tokens_used": 345,
  "cached": false,
  "message_count": 6,
  "document_processed": true,
  "document_filename": "data.csv"
}
```

**Response Fields:**

| Field                | Type    | Description                                                        |
| -------------------- | ------- | ------------------------------------------------------------------ |
| `response`           | string  | AI agent's response                                                |
| `session_id`         | string  | Session identifier (save this for continuing conversation)         |
| `tools_used`         | array   | APIs/tools called during processing (guaranteed via QueryAnalyzer) |
| `tokens_used`        | integer | Approximate tokens consumed (for cost tracking)                    |
| `cached`             | boolean | Whether response was served from cache                             |
| `message_count`      | integer | Total messages in this session                                     |
| `document_processed` | boolean | Whether a document was uploaded and processed                      |
| `document_filename`  | string  | Name of uploaded file (if any)                                     |
| `image_processed`    | boolean | Whether an image was uploaded and analyzed                         |
| `vision_capable`     | boolean | Whether current model supports image input                         |
| `chart_data`         | string  | **NEW**: Base64-encoded chart image (data:image/png;base64,...)    |
| `chart_metadata`     | object  | **NEW**: Chart metadata (type, data rows, columns used, etc.)      |
| `cost_info`          | object  | Cost optimization stats (tokens, cache hits, session usage)        |

### Cost Info Object

The `cost_info` object provides real-time token usage and warnings:

```json
{
  "cost_info": {
    "session_id": "abc123",
    "tokens_used": 450,
    "total_tokens": 8500,
    "max_tokens": 100000,
    "usage_percentage": 8.5,
    "total_cost_usd": 0.085,
    "warning": null,
    "recommendation": null
  }
}
```

**Warning Thresholds:**

- **75% usage**: "Your conversation has used 75% of tokens. Consider starting a new chat soon"
- **90% usage**: "Your conversation is at 90% of the token limit. Please start a new chat to continue"

**Best Practice:** Display warnings to users and prompt them to start a new session when approaching limits.

### Document Session Persistence

When documents are uploaded, the content is cached for the entire session (24 hours) instead of the standard 5-minute cache:

- **Standard cache**: 5 minutes (3600 seconds)
- **Document session cache**: 24 hours (86400 seconds)
- Users can ask multiple questions about uploaded documents without re-uploading
- Cache automatically cleared when session is deleted

### Tool Calling Guarantee

AERIS-AQ uses **QueryAnalyzer** - an intelligent pre-processing system that proactively detects query intent and calls appropriate tools BEFORE sending to the AI. This ensures:

- **100% tool calling success rate** across all AI providers
- **Real-time data** always used instead of training data
- **Consistent behavior** regardless of AI model capabilities
- **Automatic detection** of air quality, research, and scraping queries

**Tool Detection Examples:**

- "What's the air quality in Kampala?" → `["get_african_city_air_quality"]`
- "Air quality policies in Kenya?" → `["search_web"]`
- "Analyze this EPA report: https://..." → `["search_web", "scrape_website"]`
  | `tokens_used` | integer | **Accurately counted** tokens using tiktoken (world-standard precision) |
  | `cached` | boolean | Whether response was served from cache |
  | `message_count` | integer | Total messages in this session |
  | `document_processed` | boolean | Whether a document was uploaded and processed |
  | `document_filename` | string | Name of uploaded file (if any) |

### Cost Info Object

---

## Chart Generation & Visualization 📊 **NEW**

**AERIS-AQ can now generate professional charts and graphs** automatically when you ask for visualizations. The AI uses the `generate_chart` tool to create charts from data.

### Supported Chart Types

| Chart Type   | Best For                          | Example Request                                  |
| ------------ | --------------------------------- | ------------------------------------------------ |
| `line`       | Trends over time                  | "Plot PM2.5 levels over the past week"           |
| `bar`        | Comparisons between categories    | "Compare AQI across different cities"            |
| `scatter`    | Correlations between variables    | "Show correlation between PM2.5 and temperature" |
| `histogram`  | Data distributions                | "Show distribution of AQI values"                |
| `box`        | Statistical summaries             | "Box plot of PM2.5 by city"                      |
| `pie`        | Proportions/percentages           | "Show pollutant composition breakdown"           |
| `area`       | Cumulative trends                 | "Area chart of cumulative emissions"             |
| `timeseries` | Time-based data with date parsing | "Time series of air quality from uploaded CSV"   |

### How to Request Charts

Simply ask AERIS-AQ to visualize data in natural language:

**Examples:**

- "Generate a chart showing PM2.5 trends from the uploaded data"
- "Plot a line graph of air quality over time"
- "Create a bar chart comparing pollution levels across cities"
- "Visualize the data as a scatter plot"

**Response with Chart:**

```json
{
  "response": "I've generated a line chart showing PM2.5 levels over time...",
  "session_id": "abc123",
  "tools_used": ["scan_document", "generate_chart"],
  "chart_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA...",
  "chart_metadata": {
    "chart_type": "line",
    "data_rows": 30,
    "columns_used": {
      "x": "date",
      "y": "pm25"
    },
    "format": "png",
    "engine": "matplotlib",
    "timestamp": "2026-01-09T10:30:00Z"
  }
}
```

### Displaying Charts in Your Frontend

The `chart_data` field contains a base64-encoded PNG image that can be directly displayed:

**React/JavaScript:**

```jsx
{
  response.chart_data && (
    <img
      src={response.chart_data}
      alt="Generated Chart"
      style={{ maxWidth: "100%", height: "auto" }}
    />
  );
}
```

**HTML:**

```html
<img src="data:image/png;base64,iVBORw0..." alt="Chart" />
```

### Chart Generation Workflow

1. **Upload Data**: Upload a CSV/Excel file with air quality data
2. **Request Visualization**: Ask AERIS-AQ to plot/visualize the data
3. **AI Generates Chart**: AI calls `generate_chart` tool automatically
4. **Receive Image**: Get base64-encoded chart in `chart_data` field
5. **Display to User**: Render the image in your UI

**Complete Example:**

```python
import requests
import base64
from io import BytesIO
from PIL import Image

# Upload data and request chart
with open('air_quality_data.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/agent/chat',
        data={
            'message': 'Generate a line chart showing PM2.5 trends over time from this data',
            'session_id': 'your-session-id'
        },
        files={'file': f}
    )

data = response.json()

# Extract and display chart
if data.get('chart_data'):
    # Remove data URL prefix
    chart_base64 = data['chart_data'].split(',')[1]

    # Decode and save/display
    chart_bytes = base64.b64decode(chart_base64)
    image = Image.open(BytesIO(chart_bytes))
    image.show()  # Or save: image.save('chart.png')

    print(f"Chart type: {data['chart_metadata']['chart_type']}")
    print(f"Data rows: {data['chart_metadata']['data_rows']}")
```

### Chart Quality & Features

- **High Resolution**: 100 DPI PNG images, professional quality
- **Professional Styling**: Clean, readable charts with proper labels
- **Auto-Sizing**: Charts automatically sized for readability
- **Color Coding**: Support for color-coded data points
- **Multiple Series**: Can plot multiple data series on same chart
- **Date Parsing**: Automatic parsing of date/time columns

---

### Key Features

✅ **Automatic Saving**: All messages are automatically saved to database  
✅ **Context Aware**: Remembers last 20 messages from the session  
✅ **Document Upload**: Upload PDF, CSV, or Excel files for analysis (max 8MB)  
✅ **GPS Location Support**: Provide latitude/longitude for precise location-based air quality queries  
✅ **In-Memory Processing**: Files processed in memory, never stored on disk  
✅ **Cost Optimized**: Limited context window reduces token usage  
✅ **Caching**: Identical queries are cached for 1 hour

### Supported Document Formats

| Type  | Extensions      | Max Size | Best For         |
| ----- | --------------- | -------- | ---------------- |
| PDF   | `.pdf`          | 8MB      | Reports, papers  |
| CSV   | `.csv`          | 8MB      | Time-series data |
| Excel | `.xlsx`, `.xls` | 8MB      | Multi-sheet data |

### Document Upload Example

```python
import requests

# Upload document with query
with open('air_quality_data.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/agent/chat',
        data={
            'message': 'Analyze this data and summarize the PM2.5 trends',
            'session_id': 'your-session-id'
        },
        files={'file': f}
    )

result = response.json()
print(result['response'])
print(f"Document: {result['document_filename']}")
```

📖 **See [SESSION_MANAGEMENT.md](./SESSION_MANAGEMENT.md) and [DOCUMENT_UPLOAD_GUIDE.md](./DOCUMENT_UPLOAD_GUIDE.md) for detailed examples**

---

## Air Quality Query

Get air quality data from multiple sources with intelligent failure handling and global coverage.

**Endpoint:** `POST /api/v1/air-quality/query`

### Request

```json
{
  "city": "Kampala",
  "country": "Uganda",
  "latitude": 0.3476,
  "longitude": 32.5825
}
```

**Parameters:**

| Field              | Type    | Required | Description                               |
| ------------------ | ------- | -------- | ----------------------------------------- |
| `city`             | string  | No\*     | City name for WAQI and AirQo              |
| `country`          | string  | No       | Country for disambiguation                |
| `latitude`         | float   | No\*     | Latitude for Open-Meteo (-90 to 90)       |
| `longitude`        | float   | No\*     | Longitude for Open-Meteo (-180 to 180)    |
| `include_forecast` | boolean | No       | Include forecast data (default: false)    |
| `forecast_days`    | integer | No       | Number of forecast days 1-7 (default: 5)  |
| `timezone`         | string  | No       | Timezone for Open-Meteo (default: "auto") |

\*Either `city` or both `latitude`+`longitude` must be provided

### Data Source Strategy

The endpoint intelligently routes to multiple data sources:

1. **WAQI** (World Air Quality Index) - City-based queries
2. **AirQo** - African cities with PM2.5 focus
3. **Open-Meteo** - Global coordinate-based queries (no API key)
4. **OpenAQ** - Global air quality data (free API, 10,000+ locations)
5. **WHO Ambient Air Quality Database** - Official ground measurements (downloadable)
6. **openAFRICA** - African air quality datasets (free access)
7. **Copernicus CAMS** - Satellite-based air quality monitoring (free basic access)

**Routing Logic:**

- If `city` is provided → queries WAQI and AirQo
- If `latitude` and `longitude` provided → queries Open-Meteo
- All successful responses are returned
- Failures are handled gracefully
- If `include_forecast=true` → adds forecast data from Open-Meteo (requires coordinates)

**Integration Potential:**

- **High Priority**: OpenAQ API (immediate global coverage expansion)
- **Medium Priority**: WHO database, openAFRICA datasets (African research enhancement)
- **Future**: Copernicus CAMS satellite data (supplemental validation)

### Data Limitations

**AirQo Historical Data:**

- Only available for the last 60 days
- For older historical data, use the [AirQo Analytics Platform](https://analytics.airqo.net)
- Contact: support@airqo.net

**WAQI Data:**

- Real-time data only (no historical data available through API)
- Some locations may have limited coverage

**Open-Meteo Data:**

- No API key required
- Historical data available but limited to recent periods
- Forecast data available for 7 days

### Response (Success - 200)

```json
{
  "waqi": {
    "status": "ok",
    "data": {
      "aqi": 45,
      "city": { "name": "Kampala" }
    }
  },
  "airqo": {
    "success": true,
    "measurements": [
      {
        "pm2_5": { "value": 14.7 },
        "aqi_category": "Moderate"
      }
    ]
  },
  "openmeteo": {
    "latitude": 0.3476,
    "longitude": 32.5825,
    "current": {
      "pm10": 12.5,
      "pm2_5": 8.3,
      "european_aqi": 25
    }
  }
}
```

**Key Features:**

✅ **Multi-source aggregation** (WAQI + AirQo + Open-Meteo)  
✅ **Intelligent routing** (city-based and coordinate-based)  
✅ **Graceful degradation** (returns available data if sources fail)  
✅ **Global coverage** (Open-Meteo covers any coordinate worldwide)

### Response (All Failed - 404)

```json
{
  "detail": {
    "message": "No air quality data found for InvalidCity",
    "errors": {
      "waqi": "WAQI API error: Unknown station",
      "airqo": "No measurements found"
    },
    "suggestion": "Try a different location or provide coordinates for Open-Meteo"
  }
}
```

### Integration Examples

**City Query:**

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{"city": "Nairobi"}'
```

**Coordinates Query:**

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{"latitude": 52.52, "longitude": 13.41}'
```

**Combined Query:**

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{"city": "Berlin", "latitude": 52.52, "longitude": 13.41}'
```

**Forecast Query (7 days):**

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 52.52,
    "longitude": 13.41,
    "include_forecast": true,
    "forecast_days": 7,
    "timezone": "Europe/Berlin"
  }'
```

**Response with Forecast:**

```json
{
  "openmeteo": {
    "current": {
      "latitude": 52.52,
      "longitude": 13.41,
      "current": {
        "pm2_5": 8.3,
        "pm10": 12.5,
        "european_aqi": 25
      }
    },
    "forecast": {
      "hourly": {
        "time": ["2024-01-15T11:00", "2024-01-15T12:00", "..."],
        "pm2_5": [8.5, 9.1, "..."],
        "pm10": [13.2, 14.0, "..."],
        "european_aqi": [26, 28, "..."]
      }
    }
  }
}
```

📖 **Additional Resources:**

- [AIR_QUALITY_API.md](./AIR_QUALITY_API.md) - Detailed air quality API guide
- [OPENMETEO_INTEGRATION.md](./OPENMETEO_INTEGRATION.md) - Open-Meteo specific documentation

---

## Session Management

### Create New Session

Explicitly create a new chat session. Use this when user clicks "New Chat" button.

**Endpoint:** `POST /api/v1/sessions/new`

**Request Body:** None

**Response:**

```json
{
  "session_id": "abc-123-def-456",
  "created_at": "2024-01-15T10:30:00Z",
  "message": "New session created successfully. Use this session_id for your chat messages."
}
```

**Use Cases:**

- User clicks "New Chat" button
- Starting fresh conversation while previous session is still open
- Need explicit session creation before sending messages

### List All Sessions

Get all conversation sessions ordered by most recent.

**Endpoint:** `GET /api/v1/sessions`

**Query Parameters:**

| Field   | Type    | Default | Description                       |
| ------- | ------- | ------- | --------------------------------- |
| `limit` | integer | 50      | Max sessions to return (max: 200) |

**Response:**

```json
[
  {
    "id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df",
    "created_at": "2025-12-30T21:03:38.244002",
    "updated_at": "2025-12-30T21:15:22.532001",
    "message_count": 8
  }
]
```

---

### Get Session Details

Get full details of a specific session including all messages.

**Endpoint:** `GET /api/v1/sessions/{session_id}`

**Response:**

```json
{
  "id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df",
  "created_at": "2025-12-30T21:03:38.244002",
  "updated_at": "2025-12-30T21:15:22.532001",
  "message_count": 8,
  "messages": [
    {
      "role": "user",
      "content": "What's the air quality in Kampala?",
      "timestamp": "2025-12-30T21:03:38.244002"
    },
    {
      "role": "assistant",
      "content": "The air quality in Kampala is...",
      "timestamp": "2025-12-30T21:03:42.123456"
    }
  ]
}
```

---

### Get Paginated Messages

Get messages from a session with pagination.

**Endpoint:** `GET /api/v1/sessions/{session_id}/messages`

**Query Parameters:**

| Field    | Type    | Default | Description                |
| -------- | ------- | ------- | -------------------------- |
| `limit`  | integer | 100     | Max messages to return     |
| `offset` | integer | 0       | Number of messages to skip |

**Response:**

```json
{
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df",
  "count": 10,
  "offset": 0,
  "messages": [
    {
      "role": "user",
      "content": "Message content",
      "timestamp": "2025-12-30T21:03:38.244002"
    }
  ]
}
```

---

### Delete Session

Delete a session and all its messages. **Call this when user closes the chat.**

**Endpoint:** `DELETE /api/v1/sessions/{session_id}`

**Response:**

```json
{
  "status": "success",
  "message": "Session 10a28e5c-9dc2-4e1f-9e21-8109d27ba9df and all its messages have been deleted",
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df"
}
```

**Error Response (404):**

```json
{
  "detail": "Session not found"
}
```

---

## MCP Connection Management

Connect to external data sources via Model Context Protocol.

### Connect to MCP Server

**Endpoint:** `POST /api/v1/mcp/connect`

**Request Body:**

```json
{
  "name": "postgres-db",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://user:pass@localhost/db"
  ]
}
```

**Parameters:**

| Field     | Type   | Required | Description                           |
| --------- | ------ | -------- | ------------------------------------- |
| `name`    | string | Yes      | Unique identifier for this connection |
| `command` | string | Yes      | Command to start the MCP server       |
| `args`    | array  | Yes      | Command arguments                     |

**Response:**

```json
{
  "status": "connected",
  "name": "postgres-db",
  "available_tools": []
}
```

---

### List MCP Connections

**Endpoint:** `GET /api/v1/mcp/list`

**Response:**

```json
{
  "connections": [
    {
      "name": "postgres-db",
      "status": "connected"
    }
  ]
}
```

---

### Disconnect from MCP Server

**Endpoint:** `DELETE /api/v1/mcp/disconnect/{name}`

**Path Parameters:**

| Field  | Type   | Required | Description                   |
| ------ | ------ | -------- | ----------------------------- |
| `name` | string | Yes      | Connection name to disconnect |

**Response:**

```json
{
  "status": "disconnected",
  "name": "postgres-db"
}
```

---

## Error Responses

All endpoints return standard HTTP status codes and structured error messages.

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

| Code | Meaning               | When It Happens            |
| ---- | --------------------- | -------------------------- |
| 200  | OK                    | Request successful         |
| 400  | Bad Request           | Invalid request parameters |
| 404  | Not Found             | Resource not found         |
| 429  | Too Many Requests     | Rate limit exceeded        |
| 500  | Internal Server Error | Unexpected server error    |

---

## Rate Limiting

**AERIS-AQ implements comprehensive rate limiting using SlowAPI to ensure fair usage and prevent abuse.**

### Global Rate Limits

- **100 requests per minute** per IP address
- **1,000 requests per hour** per IP address
- Applies to all endpoints by default

### Endpoint-Specific Rate Limits

Different endpoints have tailored rate limits based on resource intensity:

| Endpoint             | Rate Limit        | Reason                                   |
| -------------------- | ----------------- | ---------------------------------------- |
| `/agent/chat`        | 30/minute per IP  | AI-intensive operations                  |
| `/air-quality/query` | 50/minute per IP  | Moderate data retrieval                  |
| `/health`            | No limit          | Lightweight monitoring endpoint          |
| All other endpoints  | 100/minute per IP | Standard operations (sessions, messages) |

### Rate Limit Headers

All responses include rate limit information in headers:

```http
X-RateLimit-Limit: 30           # Total requests allowed in window
X-RateLimit-Remaining: 25        # Remaining requests in current window
X-RateLimit-Reset: 1609459200    # Unix timestamp when limit resets
Retry-After: 45                  # Seconds to wait (only on 429 errors)
```

### Rate Limit Response (429)

When rate limit is exceeded:

```json
{
  "error": "Rate limit exceeded: 30 per 1 minute",
  "detail": "You have exceeded the rate limit. Please try again in 45 seconds.",
  "retry_after": 45
}
```

### Production Configuration

For production deployments with multiple servers, enable Redis for distributed rate limiting:

```env
REDIS_ENABLED=true
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_DB=0
```

Without Redis, rate limiting uses in-memory storage (single-server only).

### Best Practices

1. **Implement exponential backoff** when you receive 429 responses
2. **Monitor rate limit headers** to proactively adjust request patterns
3. **Cache responses** where appropriate to reduce API calls
4. **Use batch endpoints** (e.g., `get_multiple_african_cities_air_quality`) to reduce individual requests
5. **Spread requests** evenly throughout the minute rather than bursting

---

## Cost Optimization Features

### 1. **Response Caching**

- Educational and general queries cached for **5 minutes**
- Real-time air quality data **never cached**
- Cache key based on query content
- Reduces API costs by up to 70% for repeated queries

### 2. **Limited Context Window**

- Only **last 20 messages** used for AI context
- Prevents unlimited token growth
- Maintains conversation quality
- Automatic truncation of older messages

### 3. **Token Usage Tracking**

- Every response includes `tokens_used` field
- Monitor costs in real-time
- Make informed decisions about usage
- Track spending across sessions

### 4. **Automatic Session Cleanup**

- Delete sessions when users close chat
- Prevents database bloat
- Keeps storage costs low
- Simple DELETE endpoint

---

## Best Practices

### ✅ DO

- **Save session IDs** in frontend for conversation continuity
- **Delete sessions** when users close the chat
- **Monitor token usage** via response fields
- **Handle rate limits** with exponential backoff
- **Use pagination** for large message histories

### ❌ DON'T

- Create new sessions for every message
- Keep sessions open indefinitely
- Ignore error responses
- Make excessive requests
- Store session IDs insecurely

---

## Code Examples

### Python

```python
import requests

# Start a conversation
response = requests.post(
    'http://localhost:8000/api/v1/agent/chat',
    json={'message': "What's the air quality in Kampala?"}
)
data = response.json()
session_id = data['session_id']

# Continue conversation
response = requests.post(
    'http://localhost:8000/api/v1/agent/chat',
    json={
        'message': "What about Uganda's trends?",
        'session_id': session_id
    }
)

# Close session
requests.delete(f'http://localhost:8000/api/v1/sessions/{session_id}')
```

### JavaScript/TypeScript

```typescript
// Start conversation
const response = await fetch("/api/v1/agent/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "What's the air quality in Kampala?",
  }),
});

const data = await response.json();
const sessionId = data.session_id;

// Continue conversation
await fetch("/api/v1/agent/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "What about Uganda's trends?",
    session_id: sessionId,
  }),
});

// Close session
await fetch(`/api/v1/sessions/${sessionId}`, {
  method: "DELETE",
});
```

### cURL

```bash
# Start conversation
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the air quality in Kampala?"}'

# Continue with session_id from response
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What about trends?", "session_id": "abc-123"}'

# Delete session
curl -X DELETE "http://localhost:8000/api/v1/sessions/abc-123"
```

---

## Data Visualization

### Visualize Search Results

Generate dynamic charts from search result data.

**Endpoint:** `POST /api/v1/visualization/from-search`

**Request Body:**

```json
{
  "search_results": [
    {
      "title": "Air Quality Monday",
      "content": "PM2.5 levels...",
      "metrics": {
        "date": "2024-01-01",
        "pm25": 45,
        "city": "Nairobi"
      }
    }
  ],
  "user_prompt": "Show me PM2.5 trends over time",
  "chart_type": "line"
}
```

**Response:**

```json
{
  "success": true,
  "chart_image": "base64_encoded_image...",
  "chart_html": "<div>...</div>",
  "reasoning": "Line chart shows trends over time...",
  "chart_type": "line",
  "data_analysis": {
    "shape": [7, 3],
    "columns": ["date", "pm25", "city"],
    "recommended_charts": ["line", "bar"]
  }
}
```

### Visualize Uploaded File

Generate charts from CSV/Excel/PDF files.

**Endpoint:** `POST /api/v1/visualization/from-file`

**Request:** `multipart/form-data`

- `file`: File upload (CSV, XLSX, XLS, PDF)
- `user_prompt`: What to visualize
- `chart_type`: Optional chart type

**Example:**

```bash
curl -X POST "http://localhost:8000/api/v1/visualization/from-file" \
  -F "file=@air_quality_data.csv" \
  -F "user_prompt=Create a bar chart comparing cities" \
  -F "chart_type=bar"
```

**Response:**

```json
{
  "success": true,
  "chart_image": "base64_encoded_image...",
  "chart_html": "<div>...</div>",
  "reasoning": "Bar chart compares categories...",
  "chart_type": "bar"
}
```

### Get Visualization Capabilities

Get supported file formats and chart types.

**Endpoint:** `GET /api/v1/visualization/capabilities`

**Response:**

```json
{
  "supported_formats": ["csv", "xlsx", "xls", "pdf"],
  "description": "I can create dynamic visualizations..."
}
```

**Supported Chart Types:**

- `line` - Trends, time series
- `bar` - Comparisons, rankings
- `scatter` - Relationships, correlations
- `histogram` - Distributions
- `box` - Outliers, quartiles
- `heatmap` - Correlation matrices
- `pie` - Proportions
- `area` - Cumulative trends
- `violin` - Distribution density

---

## Summary

| Feature                | Implementation                          |
| ---------------------- | --------------------------------------- |
| **Session Management** | Automatic with 20-message context       |
| **Cost Optimization**  | Caching + token tracking                |
| **Error Handling**     | Standard HTTP codes + detailed messages |
| **Rate Limiting**      | 20 req/min per IP                       |
| **Data Sources**       | WAQI + AirQo with failure tolerance     |
| **Cleanup**            | DELETE endpoint for sessions            |
| **Visualization**      | Dynamic charts from data files/searches |

📖 **For detailed guides, see:**

- [SESSION_MANAGEMENT.md](./SESSION_MANAGEMENT.md)
- [AIR_QUALITY_API.md](./AIR_QUALITY_API.md)
