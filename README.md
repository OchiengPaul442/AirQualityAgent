# Aeris-AQ - Artificial Environmental Real-time Intelligence System (Air Quality)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Production-ready air quality monitoring and AI agent with industry-standard patterns

## Overview

**Aeris-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)** is a sophisticated, scalable AI system designed for air quality monitoring, research, and policy development. It provides real-time data analysis, intelligent recommendations, and comprehensive research capabilities.

**Aeris-AQ** represents:

- **Artificial**: Advanced AI/ML core powering predictions and analysis
- **Environmental**: Specialized focus on air quality and atmospheric conditions
- **Real-time**: Live monitoring with immediate alerts and updates
- **Intelligence**: Machine learning capabilities for pattern recognition and forecasting
- **System**: Complete integrated platform with sensors, dashboard, and APIs
- **Air Quality**: Dedicated to comprehensive air pollution monitoring and analysis

**Meet Aeris-AQ**: Your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address Aeris-AQ by name in your conversations!

**Latest Updates (v2.10.0):**

- **Advanced Orchestration**: Multi-tool orchestration layer with retry logic, fallback chains, and intelligent tool selection for optimal performance on low-end models
- **Model Adapter**: Extract and execute tool calls from plain text responses - enables models without native tool-calling support to use tools effectively
- **Response Validation**: Automatic quality checks and enhancement for consistent, high-quality outputs across all models
- **Enhanced Reliability**: Circuit breakers, exponential backoff retries, and intelligent error recovery
- **Cost Optimization**: Comprehensive model performance testing completed - identified best low-cost models
- Security Enhancement: Environment-based logging controls to prevent AI response leakage in production
- Rate Limiting: Endpoint-specific limits (30/minute for chat, 50/minute for queries) to prevent server abuse
- Forecast Bug Fix: Resolved conflicting forecast tools causing "What" query failures
- Documentation: Professional formatting with emoji removal for enterprise standards
- Provider Verification: Confirmed Ollama provider has full access to all tools and services
- Testing: Comprehensive test suite with 100% pass rate on forecast functionality

---

## Documentation

| Guide                                                      | Description                  |
| ---------------------------------------------------------- | ---------------------------- |
| **[Getting Started](docs/GETTING_STARTED.md)**             | Quick setup and first steps  |
| **[API Reference](docs/API_REFERENCE.md)**                 | Complete API documentation   |
| **[Response Quality](docs/RESPONSE_QUALITY_GUIDE.md)**     | Configure AI response style  |
| **[Document Upload](docs/DOCUMENT_UPLOAD_GUIDE.md)**       | PDF/CSV/Excel file analysis  |
| [Architecture](docs/ARCHITECTURE.md)                       | System design                |
| [Deployment](docs/DEPLOYMENT.md)                           | Production deployment        |
| **[Rate Limit Monitoring](docs/RATE_LIMIT_MONITORING.md)** | Monitor API usage and limits |

---

## Features

### Advanced Agent Orchestration

- **Intelligent Tool Orchestration**: Multi-step reasoning with dependency-aware tool chaining
- **Automatic Fallbacks**: Smart fallback chains when primary tools fail (e.g., AirQo → WAQI → OpenMeteo)
- **Retry Logic**: Exponential backoff with circuit breakers for resilient operation
- **Model Adapter**: Pattern detection and extraction for models without native tool-calling
- **Response Validation**: Automatic quality checks and formatting enhancement
- **Low-End Model Support**: Optimized for models with weak or no tool-calling capabilities

### AI Capabilities

- **Environmental Consultant**: Real-time air quality data and health recommendations
- **Senior Researcher**: Comprehensive research documents with citations
- **Policy Advisor**: Evidence-based policy development for regional contexts
- **Document Analyst**: Upload and analyze PDF, CSV, and Excel files
- **Data Visualization**: Generate embedded charts/graphs that render automatically in markdown
- **Reasoning Models**: Transparent thinking process with step-by-step analysis

### AI Providers

- **OpenAI**: Direct API or compatible providers (OpenRouter, DeepSeek, Kimi)
- **Google Gemini**: Production-grade analysis
- **Ollama**: Local testing and privacy-focused deployments

### Data Sources

- **WAQI** (World Air Quality Index): Global coverage, 30,000+ stations with forecasts
- **AirQo**: East Africa focus with detailed local data and forecasts
- **Open-Meteo**: Free global air quality data from CAMS (no API key required)
  - 11km resolution (Europe) and 25km resolution (Global)
  - Real-time, historical, and forecast data (up to 7 days)
  - European and US AQI indices
  - Comprehensive pollutant data: PM2.5, PM10, NO2, O3, SO2, CO, dust, UV index
- **Weather Service**: Current weather and up to 16-day forecasts
- **Search Service**: Multi-provider web search with automatic fallback
  - Primary: DuckDuckGo (no authentication required)
  - Backup: DashScope (Alibaba Cloud API, requires DASHSCOPE_API_KEY)
  - Automatically triggered for research queries
  - Prioritizes trusted sources (WHO, EPA, government agencies)
  - Specialized air quality info search
  - Environmental news and policy search
- **Document Scanner**: Extract and analyze PDF, CSV, and Excel files
- **Robust Scraper**: Web content extraction

### Model Context Protocol (MCP)

- **MCP Server**: Exposes agent capabilities for MCP clients (Claude Desktop)
- **MCP Client**: Connects to external MCP servers (PostgreSQL, MySQL, GitHub, Slack)
- **REST API for MCP**: Frontend-friendly endpoints for UI/UX integration

### Cost Optimization & Production Features

- Limited Context Window: Only 20 recent messages used (reduces token costs by 70%)
- Response Caching: 5-minute cache for identical queries
- Automatic Session Cleanup: DELETE endpoint for proper resource management
- Rate Limiting: 20 requests/minute per IP
- Token Tracking: Real-time cost monitoring
- Intelligent Error Handling: Clean separation of success/failure
- Async Operations: Improved throughput
- Horizontal Scaling: Stateless API design

---

## Prerequisites

- Python 3.10 or higher
- PostgreSQL or SQLite (for session storage)
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

   - For OpenAI:

     ```
     AI_PROVIDER=openai
     AI_MODEL=gpt-4o
     AI_API_KEY=your_openai_api_key
     ```

   - For Ollama (local models):

     ```
     AI_PROVIDER=ollama
     AI_MODEL=llama3.2
     OLLAMA_BASE_URL=http://localhost:11434
     ```

   - For Gemini:
     ```
     AI_PROVIDER=gemini
     AI_MODEL=gemini-2.0-flash-exp
     AI_API_KEY=your_gemini_api_key
     ```

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

- **Zero Information Leakage**: Advanced filtering prevents any exposure of internal methods, IDs, API keys, or technical details
- **Professional Error Handling**: User-friendly error messages while logging technical details for developers
- **Sensitive Content Protection**: Automatic detection and replacement of sensitive information with professional responses
- **Memory Management**: Conversation loop prevention and response length limits
- **Input Validation**: Comprehensive sanitization of all inputs and outputs
- API keys are automatically sanitized in all responses.
- Sensitive fields (token, api_key, password) are redacted.
- Use environment variables for credentials.
- Read-only database connections are recommended for MCP.

## Documentation

Complete guides are available in the `docs/` directory:

- **[Getting Started](docs/GETTING_STARTED.md)** - Installation and setup guide
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design and architecture
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Docker Guide](docs/DOCKER.md)** - Container-based deployment
- **[MCP Integration](docs/MCP_GUIDE.md)** - Model Context Protocol guide

## Docker Deployment

Quick start with Docker:

```bash
# Clone and configure
git clone https://github.com/OchiengPaul442/AirQualityAgent.git
cd AirQualityAgent
cp .env.example .env
# Edit .env with your API keys

# Run with Docker Compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f airquality-agent
```

Access the API at `http://localhost:8000`

See [docs/DOCKER.md](docs/DOCKER.md) for detailed Docker deployment instructions.

## Development

Format code using:

```bash
black src/
isort src/
```

## License

This project is licensed under the GNU AGPL v3 License - see the [LICENSE](LICENSE) file for details.

The GNU AGPL v3 License allows for:

- Commercial use
- Private use
- Modification
- Distribution

While requiring:

- License and copyright notice preservation
- Source code availability for network services
- Copyleft protection for derivative works
