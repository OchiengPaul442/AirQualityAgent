# API Reference

Complete reference for all API endpoints provided by the Air Quality AI Agent.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication. For production deployments, implement API key authentication.

## Endpoints

### Health Check

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

### Chat with Agent

Send a message to the AI agent and receive a response.

**Endpoint:** `POST /api/v1/agent/chat`

**Request Body:**

```json
{
  "message": "What's the air quality in Nairobi?",
  "session_id": "optional-session-id",
  "history": [
    { "role": "user", "content": "Previous message" },
    { "role": "assistant", "content": "Previous response" }
  ],
  "save_to_db": false
}
```

**Parameters:**

- `message` (string, required): The user's question or request
- `session_id` (string, optional): Unique identifier for the conversation session
- `history` (array, optional): Previous conversation messages for context
- `save_to_db` (boolean, optional): Whether to save the conversation to the database (default: false)

**Response:**

```json
{
  "response": "The air quality in Nairobi is currently Good (AQI: 45)...",
  "session_id": "optional-session-id",
  "tools_used": ["get_city_air_quality"],
  "tokens_used": 150,
  "cached": false
}
```

**Response Fields:**

- `response` (string): The agent's response
- `session_id` (string): The session identifier
- `tools_used` (array): List of tools the agent used to generate the response
- `tokens_used` (integer): Number of tokens consumed by the AI model
- `cached` (boolean): Whether the response was served from cache

---

### Direct Air Quality Query

Query air quality data for a specific city without using the agent.

**Endpoint:** `POST /api/v1/air-quality/query`

**Request Body:**

```json
{
  "city": "Kampala",
  "country": "UG"
}
```

**Parameters:**

- `city` (string, required): Name of the city
- `country` (string, optional): ISO country code (recommended for accuracy)

**Response:**

```json
{
  "city": "Kampala",
  "aqi": 78,
  "dominant_pollutant": "pm25",
  "pm25": 25.3,
  "pm10": 42.1,
  "timestamp": "2025-12-30T10:00:00Z",
  "source": "WAQI"
}
```

---

### List Sessions

Retrieve all conversation sessions stored in the database.

**Endpoint:** `GET /api/v1/sessions`

**Query Parameters:**

- `limit` (integer, optional): Maximum number of sessions to return (default: 50)
- `offset` (integer, optional): Number of sessions to skip (default: 0)

**Response:**

```json
{
  "sessions": [
    {
      "id": "session-123",
      "created_at": "2025-12-30T08:00:00Z",
      "message_count": 5,
      "last_message": "Thank you for the information"
    }
  ],
  "total": 10
}
```

---

### MCP Connection Management

Connect to external data sources via Model Context Protocol.

#### Connect to MCP Server

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

- `name` (string, required): Unique name for this connection
- `command` (string, required): Command to start the MCP server
- `args` (array, required): Arguments for the command

#### List MCP Connections

**Endpoint:** `GET /api/v1/mcp/list`

**Response:**

```json
{
  "connections": ["postgres-db", "github-data"]
}
```

#### Disconnect from MCP Server

**Endpoint:** `DELETE /api/v1/mcp/disconnect/{name}`

**Path Parameters:**

- `name` (string, required): Name of the connection to disconnect

---

## Error Responses

All endpoints return standard HTTP status codes and error messages.

**Error Response Format:**

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes:**

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error occurred

## Rate Limiting

The API implements rate limiting to prevent abuse:

- Default: 20 requests per 60 seconds per IP address
- Rate limit headers are included in responses

## Cost Optimization Features

### Response Caching

Educational and general queries are cached for 1 hour to reduce AI API costs. Real-time data queries are never cached to ensure freshness.

### Token Tracking

Every response includes token usage information to help monitor API costs.

### Client-Side Session Management

Store conversation history on the client side to reduce database storage costs by 90%.
