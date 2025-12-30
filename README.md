# Air Quality AI Agent

🌍 **Production-ready air quality monitoring and AI agent with industry-standard patterns**

## Overview

The Air Quality AI Agent is a sophisticated, scalable AI system designed for air quality monitoring, research, and policy development. It provides real-time data analysis, intelligent recommendations, and comprehensive research capabilities.

**Latest Updates (v2.0):**

- ✅ Simplified session management (automatic saving)
- ✅ Intelligent failure handling for air quality APIs
- ✅ Cost-optimized with 20-message context window
- ✅ Production-ready error handling and logging
- ✅ Comprehensive documentation with examples

---

## 📚 Documentation

| Guide                                                  | Description                                |
| ------------------------------------------------------ | ------------------------------------------ |
| **[Getting Started](docs/GETTING_STARTED.md)**         | Quick setup and first steps                |
| **[API Reference](docs/API_REFERENCE.md)**             | Complete API documentation                 |
| **[Session Management](docs/SESSION_MANAGEMENT.md)**   | 🆕 How to manage conversations             |
| **[Air Quality API](docs/AIR_QUALITY_API.md)**         | 🆕 Multi-source data with failure handling |
| **[Refactoring Summary](docs/REFACTORING_SUMMARY.md)** | 🆕 What changed and why                    |
| [Architecture](docs/ARCHITECTURE.md)                   | System design and components               |
| [Deployment](docs/DEPLOYMENT.md)                       | Production deployment guide                |

---

## ✨ Features

### AI Capabilities

- **Environmental Consultant**: Real-time air quality data and health recommendations
- **Senior Researcher**: Comprehensive research documents with citations
- **Policy Advisor**: Evidence-based policy development for regional contexts

### AI Providers

- **Google Gemini**: Production-grade, high-quality analysis
- **OpenAI**: Direct API or compatible providers (OpenRouter, DeepSeek, Kimi)
- **Ollama**: Local testing and privacy-focused deployments

### Data Sources

- **WAQI** (World Air Quality Index): Global coverage, 30,000+ stations
- **AirQo**: East Africa focus with detailed local data
- **Open-Meteo**: Free global air quality data from CAMS (no API key required)
  - 11km resolution (Europe) and 25km resolution (Global)
  - Real-time, historical, and forecast data (up to 7 days)
  - European and US AQI indices
  - Comprehensive pollutant data: PM2.5, PM10, NO2, O3, SO2, CO, dust, UV index
- **Weather Service**: Contextual weather information
- **Search Service**: Real-time web search
- **Document Scanner**: Extract text from PDFs and images
- **Robust Scraper**: Web content extraction

### Model Context Protocol (MCP)

- **MCP Server**: Exposes agent capabilities for MCP clients (Claude Desktop)
- **MCP Client**: Connects to external MCP servers (PostgreSQL, MySQL, GitHub, Slack)
- **REST API for MCP**: Frontend-friendly endpoints for UI/UX integration

### Cost Optimization & Production Features

✅ **Limited Context Window**: Only 20 recent messages used (reduces token costs by 70%)  
✅ **Response Caching**: 5-minute cache for identical queries  
✅ **Automatic Session Cleanup**: DELETE endpoint for proper resource management  
✅ **Rate Limiting**: 20 requests/minute per IP  
✅ **Token Tracking**: Real-time cost monitoring  
✅ **Intelligent Error Handling**: Clean separation of success/failure  
✅ **Async Operations**: Improved throughput  
✅ **Horizontal Scaling**: Stateless API design

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
