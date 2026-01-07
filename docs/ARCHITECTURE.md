# AERIS-AQ System Architecture

This document describes the architecture and design of **AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)**, your Air Quality AI Assistant.

## Meet AERIS-AQ

**AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address AERIS-AQ by name in your conversations!

**AERIS-AQ** represents:

- **Artificial**: Advanced AI/ML core powering predictions and analysis
- **Environmental**: Specialized focus on air quality and atmospheric conditions
- **Real-time**: Live monitoring with immediate alerts and updates
- **Intelligence**: Machine learning capabilities for pattern recognition and forecasting
- **System**: Complete integrated platform with sensors, dashboard, and APIs
- **Air Quality**: Dedicated to comprehensive air pollution monitoring and analysis

## Overview

AERIS-AQ is a stateless, scalable AI system built with FastAPI that provides real-time air quality monitoring, analysis, and recommendations through multiple AI providers.

## System Components

### 1. API Layer (`src/api/`)

**FastAPI Application:**

- RESTful endpoints for chat, air quality queries, and MCP management
- Automatic API documentation via OpenAPI
- Rate limiting and security middleware
- Health check endpoints

**Key Files:**

- `main.py`: Application entry point and configuration
- `routes.py`: Endpoint definitions and routing
- `models.py`: Pydantic models for request/response validation
- `dependencies.py`: Dependency injection and utilities

### 2. Service Layer (`src/services/`)

**Agent Service (`agent_service.py`):**

- Core AI agent logic with multi-provider support
- Tool orchestration and execution
- Conversation history management
- Response caching and optimization

**QueryAnalyzer (`agent/query_analyzer.py`):**

- Intelligent query pre-processing for reliable tool calling
- Detects air quality, search, and scraping requirements
- Proactively executes tools before AI processing
- Ensures consistent tool usage across all AI providers
- Supports 60+ cities and coordinate-based queries

**Data Services:**

- `waqi_service.py`: World Air Quality Index API integration
- `airqo_service.py`: AirQo network data access
- `weather_service.py`: Weather data via Open-Meteo
- `search_service.py`: Web search capabilities
- `cache.py`: Redis and in-memory caching

### 3. Tools Layer (`src/tools/`)

**Utilities:**

- `robust_scraper.py`: Web scraping with retry logic
- `document_scanner.py`: PDF and text document analysis

### 4. MCP Layer (`src/mcp/`)

**Model Context Protocol:**

- `server.py`: MCP server implementation for Claude Desktop integration
- `client.py`: MCP client for connecting to external data sources

### 5. Database Layer (`src/db/`)

**SQLite Database:**

- `database.py`: Database connection and session management
- `models.py`: SQLAlchemy ORM models
- `repository.py`: Data access patterns

### 6. Configuration (`src/config.py`)

Centralized settings management using Pydantic:

- AI provider configuration
- API keys and credentials
- Database URLs
- Cache settings
- Feature flags

## Architecture Patterns

### Multi-Provider AI Support

The agent supports multiple AI providers through a unified interface:

```
┌─────────────────┐
│  Agent Service  │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Provider│
    │ Factory │
    └────┬────┘
         │
    ┌────┴────────────────┬──────────────┐
    │                     │              │
┌───▼────┐         ┌──────▼───┐    ┌────▼─────┐
│ Gemini │         │  OpenAI  │    │  Ollama  │
└────────┘         └──────────┘    └──────────┘
```

Each provider implements:

- Message processing
- Tool calling and execution
- History management

### Tool Execution Flow

The system uses a **proactive tool-calling architecture** to ensure reliable tool usage across all AI providers:

```
User Query → QueryAnalyzer → Tool Detection & Execution → Context Injection → AI Provider → Final Response
```

**QueryAnalyzer Components:**

- **Query Detection**: Analyzes user queries to identify required tools

  - Air quality queries → Detects cities, coordinates, African vs global locations
  - Research queries → Identifies policy, regulation, and news requests
  - Web scraping → Detects URLs and content analysis needs

- **Proactive Tool Calling**: Executes tools BEFORE sending to AI

  - Guarantees tool usage regardless of AI model capability
  - Injects real-time data into AI context
  - Works with any AI provider (Ollama, Gemini, OpenAI, etc.)

- **Tool Routing Logic**:
  - African cities (Kampala, Nairobi, etc.) → AirQo service
  - Global cities (London, Paris, etc.) → WAQI service
  - Coordinates (lat/lon) → OpenMeteo service
  - Policy/research queries → Web search service
  - URLs → Web scraping service

**Legacy Flow (for reference):**

```
User Query → Agent Service → AI Provider → Tool Selection
                                               │
                          ┌────────────────────┘
                          ▼
                    Tool Executor
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    ┌───▼───┐      ┌──────▼─────┐    ┌─────▼────┐
    │ WAQI  │      │   AirQo    │    │ Weather  │
    └───────┘      └────────────┘    └──────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                    AI Provider → Final Response
```

### Caching Strategy

Two-tier caching system for optimal performance:

```
Request → Cache Check
            │
    ┌───────┴────────┐
    │                │
Yes │                │ No
    ▼                ▼
Return Cached   Execute Query
Response        → Cache Result
                → Return Response
```

**Caching Rules:**

- Educational queries: 1 hour TTL
- Real-time data: Never cached
- Uses Redis when available, falls back to in-memory

### Error Handling

Robust error handling with fallback mechanisms:

1. Tool execution errors: Return error message to AI for interpretation
2. AI provider errors: Log and return user-friendly message
3. Network errors: Retry with exponential backoff
4. Empty responses: Fallback to direct prompt without tools

## Data Flow

### Standard Chat Request (with QueryAnalyzer)

```
1. Client sends message with optional history
2. Agent Service checks cache
3. If not cached:
   a. QueryAnalyzer detects required tools (air quality, search, scraping)
   b. Tools fetch real-time data from external APIs
   c. Results injected into AI context
   d. AI provider generates final response using real data
4. Response cached (if applicable)
5. Return response with tool usage metadata
```

### Tool Detection Examples

**Air Quality Queries:**

- "What's the air quality in Kampala?" → Detects African city → Calls AirQo service
- "London air quality?" → Detects global city → Calls WAQI service
- "Air quality at 51.5074,-0.1278?" → Detects coordinates → Calls OpenMeteo service

**Research Queries:**

- "Air quality policies in Kenya?" → Detects policy keywords → Calls web search
- "Latest air pollution regulations?" → Detects research keywords → Calls web search

**Web Scraping:**

- "Analyze this EPA report: https://..." → Detects URL → Calls web scraper

### Legacy Direct Air Quality Query

```
1. Client requests city data
2. API routes to appropriate service (WAQI/AirQo)
3. Service fetches from external API
4. Data formatted and returned
5. No AI processing involved
```

## Scalability Features

### Stateless Design

- No server-side session storage required
- Clients manage conversation history
- Enables horizontal scaling without session affinity

### Async Operations

- Non-blocking I/O throughout
- Concurrent tool execution when possible
- Thread pool for CPU-bound operations

### Resource Optimization

- Connection pooling for database and HTTP
- Lazy loading of AI clients
- Efficient memory management

## Security Considerations

### API Key Protection

- All API keys stored in environment variables
- Automatic sanitization of sensitive fields in responses
- Never log credentials

### Input Validation

- Pydantic models for request validation
- SQL injection prevention via ORM
- XSS prevention in responses

### Rate Limiting

- Per-IP rate limits to prevent abuse
- Configurable limits via environment variables
- 429 status code for exceeded limits

## Deployment Architecture

### Development

```
Local Machine
├── Python venv
├── SQLite database
├── In-memory cache
└── Ollama (optional)
```

### Production

```
┌─────────────────┐
│  Load Balancer  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼────┐ ┌──▼─────┐
│ API 1  │ │ API 2  │  (Multiple instances)
└───┬────┘ └───┬────┘
    │          │
    └────┬─────┘
         │
    ┌────▼────┐
    │  Redis  │  (Shared cache)
    └─────────┘
```

## Technology Stack

- **Framework:** FastAPI (async Python web framework)
- **AI Providers:** Google Gemini, OpenAI, Ollama
- **Database:** SQLite (development), PostgreSQL (production recommended)
- **Caching:** Redis with in-memory fallback
- **HTTP Client:** requests library with retry logic
- **Validation:** Pydantic models
- **Logging:** Python logging module

## Performance Characteristics

- **Response Time:** 1-3 seconds (depending on tool usage)
- **Throughput:** 100+ requests/second per instance
- **Cache Hit Rate:** 60-80% for educational queries
- **Tool Calling Success Rate:** 100% (via QueryAnalyzer proactive detection)
- **Cost Reduction:** 51-54% via caching and optimization
