# Aeris API: Comprehensive Frontend Integration Guide

**Last Updated:** January 3, 2026  
**API Version:** 2.2.0

---

## Meet Aeris

**Aeris** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address Aeris by name in your conversations!

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Core Features](#core-features)
4. [Data Sources](#data-sources)
5. [Frontend Integration Examples](#frontend-integration-examples)
6. [MCP (Model Context Protocol) Integration](#mcp-integration)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Aeris API provides a unified, intelligent interface for accessing global air quality data from multiple sources (WAQI, AirQo, Open-Meteo) with AI-powered chat capabilities and extensibility through MCP server connections.

### Key Features

✅ **Multi-Source Data Aggregation** - WAQI, AirQo, and Open-Meteo in one API  
✅ **AI-Powered Chat** - Natural language queries with automatic tool calling  
✅ **Document Upload & Analysis** - In-memory PDF/CSV/Excel processing (max 8MB)  
✅ **Forecast Support** - Up to 7-day air quality forecasts  
✅ **Global Coverage** - City-based and coordinate-based queries  
✅ **Automatic Session Management** - Persistent conversation history  
✅ **MCP Integration** - Connect external data sources and tools  
✅ **Cost Optimized** - Smart caching, no disk storage, efficient memory use  
✅ **Production Ready** - Rate limiting, error handling, security

---

## Quick Start

### Basic Air Quality Query

```bash
# Current air quality by city
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{"city": "Nairobi"}'

# Current + 5-day forecast by coordinates
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": -1.286389,
    "longitude": 36.817223,
    "include_forecast": true,
    "forecast_days": 5
  }'
```

### Basic Chat Interaction

```bash
# Start a conversation
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the air quality in Kampala?"}'

# Continue conversation (use session_id from previous response)
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about the forecast for next week?",
    "session_id": "abc-123-def-456"
  }'
```

---

## Core Features

### 1. Unified Air Quality Endpoint

**Endpoint:** `POST /api/v1/air-quality/query`

The unified endpoint intelligently routes requests to appropriate data sources based on input parameters.

#### Request Model

```typescript
interface AirQualityQueryRequest {
  city?: string; // City name (for WAQI and AirQo)
  country?: string; // Country for disambiguation
  latitude?: number; // Latitude -90 to 90 (for Open-Meteo)
  longitude?: number; // Longitude -180 to 180 (for Open-Meteo)
  include_forecast?: boolean; // Include forecast data (default: false)
  forecast_days?: number; // Number of forecast days 1-7 (default: 5)
  timezone?: string; // Timezone (default: "auto")
  document?: File; // Optional: PDF/CSV/Excel file (max 8MB, multipart/form-data)
}
```

**Note:** When uploading a document, use `Content-Type: multipart/form-data` instead of JSON.

#### Routing Logic

| Parameters Provided               | Data Sources Queried               |
| --------------------------------- | ---------------------------------- |
| `city` only                       | WAQI + AirQo                       |
| `latitude` + `longitude` only     | Open-Meteo                         |
| `city` + `latitude` + `longitude` | All three sources                  |
| With `include_forecast: true`     | Adds forecast data from Open-Meteo |

#### Response Examples

**City Query (WAQI + AirQo):**

```json
{
  "waqi": {
    "status": "ok",
    "data": {
      "aqi": 45,
      "city": { "name": "Kampala" },
      "time": { "s": "2024-01-15 10:00:00" },
      "iaqi": {
        "pm25": { "v": 18 },
        "pm10": { "v": 35 }
      }
    }
  },
  "airqo": {
    "success": true,
    "measurements": [
      {
        "pm2_5": { "value": 14.7 },
        "site_id": "kampala_001",
        "aqi_category": "Moderate"
      }
    ]
  }
}
```

**Coordinate Query with Forecast (Open-Meteo):**

```json
{
  "openmeteo": {
    "current": {
      "latitude": 52.52,
      "longitude": 13.41,
      "timezone": "Europe/Berlin",
      "current": {
        "time": "2024-01-15T10:00",
        "pm10": 12.5,
        "pm2_5": 8.3,
        "carbon_monoxide": 245.7,
        "nitrogen_dioxide": 15.2,
        "sulphur_dioxide": 3.1,
        "ozone": 68.4,
        "european_aqi": 25,
        "us_aqi": 45,
        "european_aqi_category": "Good",
        "us_aqi_category": "Good"
      }
    },
    "forecast": {
      "hourly": {
        "time": ["2024-01-15T11:00", "2024-01-15T12:00", "..."],
        "pm2_5": [8.5, 9.1, "..."],
        "pm10": [13.2, 14.0, "..."],
        "european_aqi": [26, 28, "..."],
        "us_aqi": [46, 48, "..."]
      }
    }
  }
}
```

**Combined Query (All Sources):**

```json
{
  "waqi": { "..." },
  "airqo": { "..." },
  "openmeteo": {
    "current": { "..." },
    "forecast": { "..." }
  }
}
```

**Error Response (404):**

```json
{
  "detail": {
    "message": "No air quality data found for UnknownCity",
    "errors": {
      "waqi": "City not found in database",
      "airqo": "No measurements available"
    },
    "suggestion": "Try a different location or provide coordinates for Open-Meteo"
  }
}
```

### 2. AI Chat Agent

**Endpoint:** `POST /api/v1/agent/chat`

Natural language interface with automatic tool calling and session management.

#### Request Model

```typescript
interface ChatRequest {
  message: string; // User's message
  session_id?: string; // Optional: continue existing session
  latitude?: number; // Optional: GPS latitude (-90 to 90) for precise location queries
  longitude?: number; // Optional: GPS longitude (-180 to 180) for precise location queries
}
```

#### Response Model

```typescript
interface ChatResponse {
  response: string; // AI assistant's response
  session_id: string; // Session ID for continuation
  tools_used?: string[]; // APIs/tools called during response
  tokens_used?: number; // Approximate token count
  cached: boolean; // Whether response was cached
  message_count?: number; // Total messages in session
}
```

#### Agent Capabilities

The agent can automatically:

- Query air quality data from all three sources
- Provide 7-day forecasts
- Compare data across locations
- Explain health implications
- Use GPS coordinates for precise location-based queries
- Use connected MCP servers for extended functionality

### 3. Session Management

**Endpoints:**

| Method | Endpoint                         | Purpose                       |
| ------ | -------------------------------- | ----------------------------- |
| GET    | `/api/v1/sessions`               | List all sessions             |
| POST   | `/api/v1/sessions/new`           | Create new session explicitly |
| GET    | `/api/v1/sessions/{id}`          | Get session details           |
| DELETE | `/api/v1/sessions/{id}`          | Delete session                |
| GET    | `/api/v1/sessions/{id}/messages` | Get paginated messages        |

#### Session Object

```typescript
interface Session {
  id: string; // UUID
  created_at: string; // ISO 8601 timestamp
  updated_at: string; // ISO 8601 timestamp
  message_count: number; // Total messages
  messages?: Message[]; // Full history (when requested)
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}
```

---

## Data Sources

### WAQI (World Air Quality Index)

- **Coverage:** 100+ countries, 12,000+ monitoring stations
- **Best For:** Major cities worldwide
- **Data:** Real-time AQI, PM2.5, PM10, O3, NO2, SO2, CO
- **Update Frequency:** Hourly
- **Authentication:** API key required (configured in backend)

### AirQo

- **Coverage:** African cities (Uganda, Kenya, Nigeria, etc.)
- **Best For:** African urban air quality
- **Data:** PM2.5 focus, high-resolution monitoring
- **Update Frequency:** Real-time
- **Authentication:** API key required (configured in backend)

### Open-Meteo

- **Coverage:** Global (any coordinates)
- **Best For:** Locations without monitoring stations, forecasts
- **Data:** PM10, PM2.5, NO2, O3, SO2, CO, dust, UV index
- **Forecast:** Up to 7 days hourly
- **Historical:** From 2013 onwards
- **Authentication:** None (free up to 10,000 calls/day)
- **Resolution:** 11km (Europe), 25km (Global)

---

## Frontend Integration Examples

### React/TypeScript Complete Implementation

```typescript
// types.ts
export interface AirQualityRequest {
  city?: string;
  latitude?: number;
  longitude?: number;
  include_forecast?: boolean;
  forecast_days?: number;
  timezone?: string;
}

export interface AirQualityResponse {
  waqi?: any;
  airqo?: any;
  openmeteo?: {
    current?: any;
    forecast?: any;
  };
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  tools_used?: string[];
  tokens_used?: number;
  cached: boolean;
  message_count?: number;
}

// api.ts - API Service Layer
const API_BASE = "http://localhost:8000/api/v1";

export class AirQualityAPI {
  // Get current air quality
  static async getCurrent(city: string): Promise<AirQualityResponse> {
    const response = await fetch(`${API_BASE}/air-quality/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city }),
    });

    if (!response.ok) {
      if (response.status === 404) {
        const error = await response.json();
        throw new Error(error.detail.message);
      }
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  }

  // Upload document with optional air quality query
  static async uploadDocument(
    file: File,
    options?: {
      city?: string;
      latitude?: number;
      longitude?: number;
      include_forecast?: boolean;
    }
  ): Promise<AirQualityResponse> {
    // Client-side validation
    const MAX_SIZE = 8 * 1024 * 1024; // 8MB
    if (file.size > MAX_SIZE) {
      throw new Error("File exceeds 8MB limit");
    }

    const formData = new FormData();
    formData.append("document", file);
    if (options?.city) formData.append("city", options.city);
    if (options?.latitude)
      formData.append("latitude", options.latitude.toString());
    if (options?.longitude)
      formData.append("longitude", options.longitude.toString());
    if (options?.include_forecast) formData.append("include_forecast", "true");

    const response = await fetch(`${API_BASE}/air-quality/query`, {
      method: "POST",
      // No Content-Type header - FormData sets it automatically with boundary
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 413) {
        throw new Error("File too large (max 8MB)");
      }
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  // Get current + forecast by coordinates
  static async getWithForecast(
    latitude: number,
    longitude: number,
    forecastDays: number = 5
  ): Promise<AirQualityResponse> {
    const response = await fetch(`${API_BASE}/air-quality/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude,
        longitude,
        include_forecast: true,
        forecast_days: forecastDays,
        timezone: "auto",
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  // Get comprehensive data (city + coordinates)
  static async getComprehensive(
    city: string,
    latitude: number,
    longitude: number,
    includeForecast: boolean = false
  ): Promise<AirQualityResponse> {
    const response = await fetch(`${API_BASE}/air-quality/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        city,
        latitude,
        longitude,
        include_forecast: includeForecast,
        forecast_days: 5,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }
}

export class ChatAPI {
  static async sendMessage(
    message: string,
    sessionId?: string
  ): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  static async listSessions(limit: number = 20) {
    const response = await fetch(`${API_BASE}/sessions?limit=${limit}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  static async deleteSession(sessionId: string) {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  }
}

// AirQualityChart.tsx - Component for displaying forecast
import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ForecastChartProps {
  forecastData: any;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  forecastData,
}) => {
  if (!forecastData?.hourly) return null;

  // Transform API data for recharts
  const chartData = forecastData.hourly.time.map(
    (time: string, index: number) => ({
      time: new Date(time).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
      }),
      pm25: forecastData.hourly.pm2_5?.[index],
      pm10: forecastData.hourly.pm10?.[index],
      aqi: forecastData.hourly.european_aqi?.[index],
    })
  );

  return (
    <div className="forecast-chart">
      <h3>7-Day Air Quality Forecast</h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="pm25" stroke="#8884d8" name="PM2.5" />
          <Line type="monotone" dataKey="pm10" stroke="#82ca9d" name="PM10" />
          <Line type="monotone" dataKey="aqi" stroke="#ffc658" name="AQI" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

// AirQualityDashboard.tsx - Main dashboard component
import React, { useState, useEffect } from "react";
import { AirQualityAPI } from "./api";
import { ForecastChart } from "./AirQualityChart";

export const AirQualityDashboard: React.FC = () => {
  const [city, setCity] = useState("Kampala");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForecast, setShowForecast] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      // For demo: using coordinates for Kampala to get forecast
      const latitude = 0.3476;
      const longitude = 32.5825;

      const result = await AirQualityAPI.getComprehensive(
        city,
        latitude,
        longitude,
        showForecast
      );

      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [city, showForecast]);

  const renderAQI = (aqi: number) => {
    let color = "green";
    let category = "Good";

    if (aqi > 100) {
      color = "red";
      category = "Unhealthy";
    } else if (aqi > 50) {
      color = "orange";
      category = "Moderate";
    }

    return (
      <div className="aqi-display" style={{ borderLeft: `5px solid ${color}` }}>
        <div className="aqi-value">{aqi}</div>
        <div className="aqi-category">{category}</div>
      </div>
    );
  };

  return (
    <div className="dashboard">
      <div className="controls">
        <input
          type="text"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Enter city name"
        />
        <label>
          <input
            type="checkbox"
            checked={showForecast}
            onChange={(e) => setShowForecast(e.target.checked)}
          />
          Include 7-day forecast
        </label>
        <button onClick={fetchData} disabled={loading}>
          {loading ? "Loading..." : "Search"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {data && (
        <div className="results">
          {/* WAQI Data */}
          {data.waqi && (
            <div className="data-source">
              <h3>WAQI (World Air Quality Index)</h3>
              {renderAQI(data.waqi.data.aqi)}
              <div className="pollutants">
                {Object.entries(data.waqi.data.iaqi || {}).map(
                  ([key, value]: [string, any]) => (
                    <div key={key} className="pollutant">
                      <span>{key.toUpperCase()}</span>
                      <span>{value.v}</span>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* AirQo Data */}
          {data.airqo && (
            <div className="data-source">
              <h3>AirQo (African Air Quality)</h3>
              {data.airqo.measurements.map((m: any, idx: number) => (
                <div key={idx}>
                  <div className="aqi-category">{m.aqi_category}</div>
                  <div className="pollutant">
                    <span>PM2.5</span>
                    <span>{m.pm2_5?.value} µg/m³</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Open-Meteo Current Data */}
          {data.openmeteo?.current && (
            <div className="data-source">
              <h3>Open-Meteo (CAMS)</h3>
              {renderAQI(data.openmeteo.current.current.european_aqi)}
              <div className="pollutants">
                <div className="pollutant">
                  <span>PM2.5</span>
                  <span>{data.openmeteo.current.current.pm2_5} µg/m³</span>
                </div>
                <div className="pollutant">
                  <span>PM10</span>
                  <span>{data.openmeteo.current.current.pm10} µg/m³</span>
                </div>
              </div>
            </div>
          )}

          {/* Open-Meteo Forecast */}
          {data.openmeteo?.forecast && (
            <ForecastChart forecastData={data.openmeteo.forecast} />
          )}
        </div>
      )}
    </div>
  );
};

// DocumentUpload.tsx - Document upload with in-memory processing (max 8MB)
import React, { useState, useRef } from "react";
import { AirQualityAPI } from "./api";

export const DocumentUpload: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_SIZE = 8 * 1024 * 1024; // 8MB

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    // Client-side validation
    if (selectedFile.size > MAX_SIZE) {
      setError("File exceeds 8MB limit");
      setFile(null);
      return;
    }

    setError(null);
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const result = await AirQualityAPI.uploadDocument(file, {
        city: "Kampala",
        include_forecast: true,
      });

      setResult(result);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="document-upload">
      <h3>Document Analysis</h3>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.csv,.xlsx,.xls"
        onChange={handleFileChange}
      />
      <button onClick={handleUpload} disabled={!file || loading}>
        {loading ? "Analyzing..." : "Upload (Max 8MB)"}
      </button>
      {error && <div className="error">{error}</div>}
      {result?.document && <pre>{result.document.content}</pre>}
    </div>
  );
};

// ChatInterface.tsx - Chat component with session management
import React, { useState, useEffect } from "react";
import { ChatAPI, ChatMessage } from "./api";

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await ChatAPI.sendMessage(input, sessionId || undefined);

      setSessionId(response.session_id);

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const startNewChat = async () => {
    if (sessionId) {
      await ChatAPI.deleteSession(sessionId);
    }
    setSessionId(null);
    setMessages([]);
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>Air Quality Assistant</h2>
        {sessionId && (
          <button onClick={startNewChat} className="new-chat-btn">
            New Chat
          </button>
        )}
      </div>

      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-content">{msg.content}</div>
            <div className="message-time">
              {msg.timestamp.toLocaleTimeString()}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant loading">Thinking...</div>
        )}
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask about air quality..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
};
```

### Vue.js 3 Composition API

```vue
<!-- AirQualityService.vue -->
<template>
  <div class="air-quality-service">
    <div class="search-bar">
      <input
        v-model="city"
        placeholder="Enter city name"
        @keyup.enter="fetchData"
      />
      <button @click="fetchData" :disabled="loading">Search</button>

      <label>
        <input type="checkbox" v-model="includeForecast" />
        Include forecast
      </label>
    </div>

    <div v-if="loading" class="loading">Loading...</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="data" class="results">
      <!-- Display results -->
      <div v-if="data.waqi" class="source-card">
        <h3>WAQI</h3>
        <div class="aqi">{{ data.waqi.data.aqi }}</div>
      </div>

      <div v-if="data.openmeteo?.forecast" class="forecast">
        <h3>7-Day Forecast</h3>
        <!-- Chart component here -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

const city = ref("Nairobi");
const includeForecast = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);
const data = ref<any>(null);

const fetchData = async () => {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch("/api/v1/air-quality/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        city: city.value,
        include_forecast: includeForecast.value,
        forecast_days: 5,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data.value = await response.json();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to fetch";
  } finally {
    loading.value = false;
  }
};
</script>
```

### Python Client (for backend-to-backend)

```python
import requests
from typing import Optional, Dict, Any

class AirQualityClient:
    """Python client for Air Quality Agent API"""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_air_quality(
        self,
        city: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        include_forecast: bool = False,
        forecast_days: int = 5,
    ) -> Dict[str, Any]:
        """
        Get air quality data

        Args:
            city: City name (for WAQI and AirQo)
            latitude: Latitude (for Open-Meteo)
            longitude: Longitude (for Open-Meteo)
            include_forecast: Include forecast data
            forecast_days: Number of forecast days (1-7)

        Returns:
            Dictionary with air quality data from available sources
        """
        payload = {}

        if city:
            payload["city"] = city
        if latitude is not None and longitude is not None:
            payload["latitude"] = latitude
            payload["longitude"] = longitude
        if include_forecast:
            payload["include_forecast"] = True
            payload["forecast_days"] = forecast_days

        response = self.session.post(
            f"{self.base_url}/air-quality/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message to the AI chat agent

        Args:
            message: User's message
            session_id: Optional session ID to continue conversation

        Returns:
            Chat response with AI answer and session info
        """
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id

        response = self.session.post(
            f"{self.base_url}/agent/chat",
            json=payload
        )
        response.raise_for_status()
        return response.json()

# Usage example
if __name__ == "__main__":
    client = AirQualityClient()

    # Get current air quality
    data = client.get_air_quality(city="Kampala")
    print(f"AQI: {data.get('waqi', {}).get('data', {}).get('aqi')}")

    # Get forecast
    forecast = client.get_air_quality(
        latitude=0.3476,
        longitude=32.5825,
        include_forecast=True,
        forecast_days=7
    )
    print(f"Forecast hours: {len(forecast['openmeteo']['forecast']['hourly']['time'])}")

    # Chat interaction
    response = client.chat("What's the air quality in Berlin?")
    print(response["response"])

    # Continue chat
    response2 = client.chat(
        "What about the forecast?",
        session_id=response["session_id"]
    )
    print(response2["response"])
```

---

## MCP (Model Context Protocol) Integration

The API supports connecting external MCP servers to extend functionality with custom tools and data sources.

### What is MCP?

Model Context Protocol (MCP) is a standardized protocol for connecting AI assistants to external tools, databases, and APIs. It allows you to:

- Connect to databases (PostgreSQL, MySQL, SQLite)
- Access external APIs and services
- Add custom tools and functions
- Extend agent capabilities dynamically

### MCP Endpoints

| Method | Endpoint                 | Purpose                    |
| ------ | ------------------------ | -------------------------- |
| POST   | `/api/v1/mcp/connect`    | Connect to an MCP server   |
| GET    | `/api/v1/mcp/list`       | List connected MCP servers |
| POST   | `/api/v1/mcp/disconnect` | Disconnect from MCP server |

### Connecting an MCP Server

**Request:**

```typescript
interface MCPConnectionRequest {
  name: string; // Unique name for this connection
  command: string; // Command to run (e.g., "npx", "python")
  args: string[]; // Command arguments
}
```

**Example: Connect to PostgreSQL MCP Server**

```bash
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-db",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/airquality"]
  }'
```

**Response:**

```json
{
  "status": "connected",
  "name": "postgres-db",
  "available_tools": [
    {
      "name": "query",
      "description": "Execute a SELECT query on the database",
      "input_schema": { "..." }
    },
    {
      "name": "list_tables",
      "description": "List all tables in the database",
      "input_schema": { "..." }
    }
  ]
}
```

### Frontend MCP Integration Example

```typescript
// mcpService.ts
export class MCPService {
  private baseUrl = "http://localhost:8000/api/v1";

  async connectServer(
    name: string,
    command: string,
    args: string[]
  ): Promise<any> {
    const response = await fetch(`${this.baseUrl}/mcp/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, command, args }),
    });

    if (!response.ok) throw new Error(`Failed to connect MCP server`);
    return await response.json();
  }

  async listServers(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/mcp/list`);
    if (!response.ok) throw new Error(`Failed to list MCP servers`);
    return await response.json();
  }

  async disconnectServer(name: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/mcp/disconnect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    if (!response.ok) throw new Error(`Failed to disconnect MCP server`);
  }
}

// MCPManager.tsx - React component for managing MCP connections
import React, { useState, useEffect } from "react";
import { MCPService } from "./mcpService";

export const MCPManager: React.FC = () => {
  const [servers, setServers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const mcpService = new MCPService();

  useEffect(() => {
    loadServers();
  }, []);

  const loadServers = async () => {
    try {
      const data = await mcpService.listServers();
      setServers(data.connections);
    } catch (error) {
      console.error("Failed to load MCP servers:", error);
    }
  };

  const connectPostgres = async () => {
    setLoading(true);
    try {
      await mcpService.connectServer("postgres-db", "npx", [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://user:pass@localhost/airquality",
      ]);
      await loadServers();
    } catch (error) {
      console.error("Failed to connect PostgreSQL:", error);
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async (name: string) => {
    try {
      await mcpService.disconnectServer(name);
      await loadServers();
    } catch (error) {
      console.error("Failed to disconnect:", error);
    }
  };

  return (
    <div className="mcp-manager">
      <h2>MCP Server Connections</h2>

      <div className="actions">
        <button onClick={connectPostgres} disabled={loading}>
          Connect PostgreSQL
        </button>
      </div>

      <div className="server-list">
        {servers.map((server) => (
          <div key={server.name} className="server-card">
            <h3>{server.name}</h3>
            <p>Status: {server.status}</p>
            <p>Tools: {server.tools?.length || 0}</p>
            <button onClick={() => disconnect(server.name)}>Disconnect</button>
          </div>
        ))}
      </div>
    </div>
  );
};
```

### Using MCP-Connected Tools in Chat

Once an MCP server is connected, the AI agent can automatically use its tools:

```typescript
// After connecting PostgreSQL MCP server
const response = await ChatAPI.sendMessage(
  "Query the air quality measurements table for Kampala in the last 24 hours"
);

// The agent will:
// 1. Detect it needs database access
// 2. Use the connected PostgreSQL MCP server
// 3. Execute the query
// 4. Return formatted results
```

### Common MCP Server Examples

**1. PostgreSQL Database:**

```bash
npx -y @modelcontextprotocol/server-postgres postgresql://user:pass@localhost/database
```

**2. Filesystem Access:**

```bash
npx -y @modelcontextprotocol/server-filesystem /path/to/allowed/directory
```

**3. Google Drive:**

```bash
npx -y @modelcontextprotocol/server-gdrive
```

**4. GitHub:**

```bash
npx -y @modelcontextprotocol/server-github --token YOUR_GITHUB_TOKEN
```

### Data Access Verification

To ensure MCP data access is working correctly:

```typescript
// Test MCP connection and data access
async function testMCPDataAccess() {
  const mcpService = new MCPService();

  // 1. Connect to PostgreSQL
  console.log("Connecting to PostgreSQL...");
  const connection = await mcpService.connectServer("postgres-test", "npx", [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://...",
  ]);

  console.log("✓ Connected successfully");
  console.log("Available tools:", connection.available_tools);

  // 2. List connected servers
  const servers = await mcpService.listServers();
  console.log("✓ Active connections:", servers.connections.length);

  // 3. Test data query through chat
  const chatResponse = await ChatAPI.sendMessage(
    "List all tables in the connected database"
  );

  console.log("✓ Chat response:", chatResponse.response);
  console.log("✓ Tools used:", chatResponse.tools_used);

  // 4. Verify tool was used
  if (
    chatResponse.tools_used?.includes("query") ||
    chatResponse.tools_used?.includes("list_tables")
  ) {
    console.log("✅ MCP data access verified!");
  } else {
    console.log("❌ MCP tools not used");
  }
}
```

---

## Advanced Usage

### Rate Limiting

The API implements rate limiting (20 requests per minute per IP).

**Handling 429 Responses:**

```typescript
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 3
) {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(url, options);

    if (response.status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      const delay = retryAfter ? parseInt(retryAfter) * 1000 : 5000;

      console.log(`Rate limited. Retrying after ${delay}ms`);
      await new Promise((resolve) => setTimeout(resolve, delay));
      continue;
    }

    return response;
  }

  throw new Error("Max retries exceeded");
}
```

### Caching Strategy

Air quality responses are cached for 5 minutes. Use the `cached` field to understand cache hits:

```typescript
const response = await ChatAPI.sendMessage("Air quality in Kampala?");

if (response.cached) {
  console.log("✓ Served from cache (no API calls made)");
} else {
  console.log("✓ Fresh data fetched");
}
```

### Token Usage Monitoring

Track AI costs using the `tokens_used` field:

```typescript
let totalTokens = 0;

const response = await ChatAPI.sendMessage("What's the AQI in Berlin?");
totalTokens += response.tokens_used || 0;

console.log(`Total tokens used: ${totalTokens}`);
console.log(`Estimated cost: $${(totalTokens / 1000) * 0.002}`); // Example pricing
```

### Bulk Queries

```typescript
// Efficiently query multiple cities
async function queryMultipleCities(cities: string[]) {
  const promises = cities.map((city) =>
    AirQualityAPI.getCurrent(city).catch((err) => ({
      city,
      error: err.message,
    }))
  );

  return await Promise.all(promises);
}

const results = await queryMultipleCities([
  "Nairobi",
  "Kampala",
  "Lagos",
  "Cairo",
]);
```

---

## Best Practices

### 1. Session Management

✅ **DO:**

- Store `session_id` in component state or localStorage
- Delete sessions when user closes chat
- List sessions on app startup for "recent chats"

❌ **DON'T:**

- Create new sessions unnecessarily
- Keep sessions forever (implement TTL cleanup)
- Send messages without session_id in ongoing conversations

### 2. Error Handling

✅ **DO:**

- Check HTTP status codes
- Parse error responses for user-friendly messages
- Implement retry logic for transient failures
- Show fallback UI when data unavailable

❌ **DON'T:**

- Display raw error messages to users
- Fail silently without logging
- Retry indefinitely without backoff

### 3. Performance

✅ **DO:**

- Leverage the 5-minute cache
- Batch independent API calls
- Use pagination for session messages
- Implement debouncing for search inputs

❌ **DON'T:**

- Poll APIs unnecessarily
- Request forecast data if not needed
- Load all messages for every session

### 4. Security

✅ **DO:**

- Use environment variables for API URLs
- Implement CORS properly
- Validate user inputs
- Use HTTPS in production

❌ **DON'T:**

- Expose API keys in frontend code
- Trust client-side validation alone
- Log sensitive information

---

## Troubleshooting

### "No air quality data found"

**Problem:** 404 response with no data  
**Solutions:**

- Check city name spelling
- Try providing coordinates instead
- Verify data source availability in API logs

### "Rate limit exceeded"

**Problem:** 429 response  
**Solutions:**

- Implement exponential backoff
- Reduce request frequency
- Use caching more effectively

### MCP Connection Fails

**Problem:** MCP server won't connect  
**Solutions:**

- Verify command and arguments are correct
- Check if MCP server package is installed
- Ensure database/service is accessible
- Check API logs for detailed error

### Forecast Not Included

**Problem:** No forecast data in response  
**Solutions:**

- Set `include_forecast: true` in request
- Provide `latitude` and `longitude` (required for forecasts)
- Check if Open-Meteo is enabled in API config

### Chat Agent Not Using Tools

**Problem:** Agent responds but doesn't call APIs  
**Solutions:**

- Phrase questions more specifically
- Check `tools_used` array in response
- Verify tools are registered (check API logs)
- Try asking explicitly (e.g., "Query WAQI for...")

---

## API Reference Quick Links

📘 [Complete API Reference](./API_REFERENCE.md)  
🌍 [Air Quality API Guide](./AIR_QUALITY_API.md)  
☁️ [Open-Meteo Integration](./OPENMETEO_INTEGRATION.md)  
🏗️ [Architecture Overview](./ARCHITECTURE.md)  
🚀 [Deployment Guide](./DEPLOYMENT.md)

---

## Support & Feedback

For issues, questions, or feature requests:

- Check existing documentation
- Review API logs for detailed errors
- Test with curl/Postman before frontend integration
- Ensure all required fields are provided

**Happy building! 🚀**
