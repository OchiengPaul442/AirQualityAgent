# API Reference

Complete reference for all API endpoints provided by the Air Quality AI Agent.

---

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

| Endpoint                  | Method | Purpose                            |
| ------------------------- | ------ | ---------------------------------- |
| `/health`                 | GET    | Health check                       |
| `/agent/chat`             | POST   | Chat with AI agent                 |
| `/air-quality/query`      | POST   | Get air quality data (all sources) |
| `/sessions/new`           | POST   | Create new session                 |
| `/sessions`               | GET    | List all sessions                  |
| `/sessions/{id}`          | GET    | Get session details                |
| `/sessions/{id}`          | DELETE | Delete session                     |
| `/sessions/{id}/messages` | GET    | Get paginated messages             |

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

## Chat with Agent

Send a message to the AI agent and receive a response with automatic conversation saving.

**Endpoint:** `POST /api/v1/agent/chat`

### Request

```json
{
  "message": "What's the air quality in Nairobi?",
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df"
}
```

**Parameters:**

| Field        | Type   | Required | Description                                                  |
| ------------ | ------ | -------- | ------------------------------------------------------------ |
| `message`    | string | Yes      | User's question or request                                   |
| `session_id` | string | No       | Session ID for continuing a conversation. Omit to start new. |

### Response

```json
{
  "response": "The air quality in Nairobi is currently Good (AQI: 45)...",
  "session_id": "10a28e5c-9dc2-4e1f-9e21-8109d27ba9df",
  "tools_used": ["airqo_api", "waqi_api"],
  "tokens_used": 245,
  "cached": false,
  "message_count": 6
}
```

**Response Fields:**

| Field           | Type    | Description                                                |
| --------------- | ------- | ---------------------------------------------------------- |
| `response`      | string  | AI agent's response                                        |
| `session_id`    | string  | Session identifier (save this for continuing conversation) |
| `tools_used`    | array   | APIs/tools called during processing                        |
| `tokens_used`   | integer | Approximate tokens consumed (for cost tracking)            |
| `cached`        | boolean | Whether response was served from cache                     |
| `message_count` | integer | Total messages in this session                             |

### Key Features

✅ **Automatic Saving**: All messages are automatically saved to database  
✅ **Context Aware**: Remembers last 20 messages from the session  
✅ **Cost Optimized**: Limited context window reduces token usage  
✅ **Caching**: Identical queries are cached for 5 minutes

📖 **See [SESSION_MANAGEMENT.md](./SESSION_MANAGEMENT.md) for detailed examples**

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

**Routing Logic:**

- If `city` is provided → queries WAQI and AirQo
- If `latitude` and `longitude` provided → queries Open-Meteo
- All successful responses are returned
- Failures are handled gracefully
- If `include_forecast=true` → adds forecast data from Open-Meteo (requires coordinates)

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

**Limits:**

- **20 requests per minute** per IP address
- Applies to all endpoints

**Rate Limit Response (429):**

```json
{
  "detail": "Rate limit exceeded. Please try again in a moment."
}
```

**Best Practice:** Implement exponential backoff in your client.

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

## Summary

| Feature                | Implementation                          |
| ---------------------- | --------------------------------------- |
| **Session Management** | Automatic with 20-message context       |
| **Cost Optimization**  | Caching + token tracking                |
| **Error Handling**     | Standard HTTP codes + detailed messages |
| **Rate Limiting**      | 20 req/min per IP                       |
| **Data Sources**       | WAQI + AirQo with failure tolerance     |
| **Cleanup**            | DELETE endpoint for sessions            |

📖 **For detailed guides, see:**

- [SESSION_MANAGEMENT.md](./SESSION_MANAGEMENT.md)
- [AIR_QUALITY_API.md](./AIR_QUALITY_API.md)
