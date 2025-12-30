# Air Quality AI Agent

## Overview

The Air Quality AI Agent is a sophisticated, scalable AI system designed for air quality monitoring, research, and policy development. It provides real-time data analysis, intelligent recommendations, and comprehensive research capabilities, optimized for enterprise deployments with significant cost reductions through client-side session management and intelligent caching.

## Features

### AI Capabilities

- **Environmental Consultant**: Provides real-time air quality data and health recommendations.
- **Senior Researcher**: Delivers comprehensive research documents with citations and in-depth analysis.
- **Policy Advisor**: Offers evidence-based policy development tailored to regional contexts, with a focus on African regions.

### AI Providers

- **Google Gemini**: For production-grade, high-quality analysis.
- **OpenAI**: Supports direct API or compatible providers (OpenRouter, DeepSeek, Kimi).
- **Ollama**: For local testing and privacy-focused deployments.

### Data Sources

- WAQI (World Air Quality Index)
- AirQo
- Weather Service
- Search Service
- Document Scanner
- Robust Scraper

### Model Context Protocol (MCP)

- **MCP Server**: Exposes agent capabilities for use with MCP clients like Claude Desktop.
- **MCP Client**: Connects to external MCP servers (PostgreSQL, MySQL, GitHub, Slack, etc.).
- **REST API for MCP**: Frontend-friendly endpoints for UI/UX integration.

### Cost Optimization and Scalability

- Client-side session management for reduced storage costs.
- Intelligent response caching to minimize AI API calls.
- Rate limiting to prevent abuse.
- Token tracking for cost visibility.
- Async operations for improved throughput.
- Stateless API design for horizontal scaling.
- Redis-backed caching with in-memory fallback.

## Prerequisites

- Python 3.10 or higher
- Ollama (optional, for local testing)
- Redis (optional, for caching)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/OchiengPaul442/AirQualityAgent.git
   cd AirQualityAgent
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings. Examples:

   - For local testing with Ollama:

     ```
     AI_PROVIDER=ollama
     AI_MODEL=llama3.2
     OLLAMA_BASE_URL=http://localhost:11434
     ```

   - For production with Gemini:

     ```
     AI_PROVIDER=gemini
     AI_MODEL=gemini-2.5-flash
     AI_API_KEY=your_gemini_api_key
     ```

   - For OpenAI:
     ```
     AI_PROVIDER=openai
     AI_MODEL=gpt-4o
     AI_API_KEY=your_openai_api_key
     OPENAI_BASE_URL=https://api.openai.com/v1
     ```

   Additional configurations for OpenRouter, DeepSeek, or Kimi can be set similarly using the OpenAI provider with appropriate base URLs and API keys.

## Running the Agent

The agent can be run in two modes:

### API Server Mode

Provides a REST API for chat and interaction.

```bash
./start_server.sh
# Select option 1
```

Or directly:

```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

For development with auto-reload:

```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### MCP Server Mode

Exposes tools via stdio for MCP clients.

```bash
./start_server.sh
# Select option 2
```

Or directly:

```bash
python src/mcp/server.py
```

## Usage

### Chat Endpoint

Interact with the agent via the REST API.

**Endpoint**: `POST /api/v1/agent/chat`

**Request Body**:

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

**Response**:

```json
{
  "response": "The air quality in Nairobi is...",
  "session_id": "optional-session-id",
  "tools_used": ["waqi_api"],
  "tokens_used": 150,
  "cached": false
}
```

Key features:

- Client-side conversation history management.
- Optional database saving for cost efficiency.
- Token usage tracking.
- Cache status indication.

### MCP Connection API

Manage connections to external data sources.

- **Connect**: `POST /api/v1/mcp/connect`
- **List**: `GET /api/v1/mcp/list`
- **Disconnect**: `DELETE /api/v1/mcp/disconnect/{name}`

### Direct Air Quality Query

Query air quality data directly.

**Endpoint**: `POST /api/v1/air-quality/query`

**Request Body**:

```json
{
  "city": "Kampala",
  "country": "UG"
}
```

### List Sessions

Retrieve session information.

**Endpoint**: `GET /api/v1/sessions`

## Testing

### Unit Tests

Run fast unit tests with mocks:

```bash
python tests/test_all_services.py
```

### Comprehensive Stress Tests

Run tests with real API calls:

```bash
python tests/comprehensive_stress_test.py
```

Test coverage includes all services: AirQo, WAQI, Weather, Scraper, Search, Document Scanner, and Cache.

## Project Structure

- `src/api/`: FastAPI routes and models.
- `src/services/`: Core business logic (Agent, AirQo, WAQI, Weather services).
- `src/tools/`: Utilities (scraper, document scanner).
- `src/mcp/`: MCP server and client implementations.
- `src/db/`: Database models and repository.
- `docs/`: Additional documentation.
- `tests/`: Test suites.

## Security

- API keys are automatically sanitized in all responses.
- Sensitive fields (token, api_key, password) are redacted.
- Use environment variables for credentials.
- Read-only database connections are recommended for MCP.

## Documentation

- `docs/QUICK_START.md`: Get started quickly with examples.
- `docs/IMPLEMENTATION_SUMMARY.md`: Feature overview.
- `docs/CLIENT_INTEGRATION_GUIDE.md`: Integration examples.
- `docs/TESTING_GUIDE.md`: Testing scenarios.
- `docs/ARCHITECTURE.md`: System architecture.
- `docs/COST_OPTIMIZATION_GUIDE.md`: Deployment guide.
- `docs/MCP_CONNECTION_GUIDE.md`: MCP integration.
- Additional guides in the `docs/` directory.

## Development

Format code using:

```bash
black src/
isort src/
```
