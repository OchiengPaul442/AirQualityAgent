# Aeris System Architecture

This document describes the architecture and design of **Aeris**, your Air Quality AI Assistant.

## Meet Aeris

**Aeris** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address Aeris by name in your conversations!

## Overview

Aeris is a stateless, scalable AI system built with FastAPI that provides real-time air quality monitoring, analysis, and recommendations through multiple AI providers.

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

### Standard Chat Request

```
1. Client sends message with optional history
2. Agent Service checks cache
3. If not cached:
   a. Format message for AI provider
   b. AI selects and calls tools
   c. Tools fetch data from external APIs
   d. AI generates final response
4. Response cached (if applicable)
5. Return response with metadata
```

### Direct Air Quality Query

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
- **Cost Reduction:** 51-54% via caching and optimization
