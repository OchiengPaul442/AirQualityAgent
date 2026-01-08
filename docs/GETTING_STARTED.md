# Getting Started with AERIS-AQ

This guide will help you set up and run **AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)**, your Air Quality AI Assistant.

## Meet AERIS-AQ

**AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)** is your friendly, knowledgeable Air Quality AI Assistant dedicated to helping you understand air quality data, environmental health, and pollution monitoring. Simply address AERIS-AQ by name in your conversations!

**AERIS-AQ** represents:

- **Artificial**: Advanced AI/ML core powering predictions and analysis
- **Environmental**: Specialized focus on air quality and atmospheric conditions
- **Real-time**: Live monitoring with immediate alerts and updates
- **Intelligence**: Machine learning capabilities for pattern recognition and forecasting
- **System**: Complete integrated platform with sensors, dashboard, and APIs
- **Air Quality**: Dedicated to comprehensive air pollution monitoring and analysis

## Prerequisites

- Python 3.10 or higher
- Git
- One of the following AI providers:
  - Google Gemini API key (recommended for production)
  - OpenAI API key
  - Ollama installed locally (for development/testing)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/OchiengPaul442/AirQualityAgent.git
   cd AirQualityAgent
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv

   # On Windows:
   .venv\Scripts\activate

   # On Linux/Mac:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Create a `.env` file in the project root:

   ```bash
   cp .env.example .env
   ```

2. Configure your AI provider in `.env`:

   **For Google Gemini (Recommended for Production):**

   ```env
   AI_PROVIDER=gemini
   AI_MODEL=gemini-2.5-flash
   AI_API_KEY=your_gemini_api_key_here
   ```

   **For OpenAI:**

   ```env
   AI_PROVIDER=openai
   AI_MODEL=gpt-4o
   AI_API_KEY=your_openai_api_key_here
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

   **For Ollama (Local Testing):**

   ```env
   AI_PROVIDER=ollama
   AI_MODEL=llama3.2
   OLLAMA_BASE_URL=http://localhost:11434
   ```

3. Configure data sources (optional but recommended):

   ```env
   WAQI_API_KEY=your_waqi_api_key
   AIRQO_API_TOKEN=your_airqo_token
   ```

   To obtain API keys:

   - WAQI: Register at [aqicn.org](https://aqicn.org/data-platform/token/)
   - AirQo: Contact [AirQo](https://airqo.net) for access
   - **AirQo Analytics Dashboard**: [https://analytics.airqo.net](https://analytics.airqo.net) - Interactive dashboard for data visualization and downloads

4. Configure Redis (optional, for production caching):
   ```env
   REDIS_ENABLED=true
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

## Running the Agent

### API Server Mode

Start the FastAPI server:

```bash
# Using the startup script (recommended):
./start_server.sh  # Select option 1

# Or directly with uvicorn:
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# For development with auto-reload:
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### MCP Server Mode

Run as an MCP server for use with Claude Desktop:

```bash
# Using the startup script:
./start_server.sh  # Select option 2

# Or directly:
python src/mcp/server.py
```

## Testing the API

### Comprehensive Test Suite

Run the full test suite to verify all functionality:

```bash
python tests/comprehensive_test_suite.py
```

**Test Coverage:**

- ✅ Tool calling verification (air quality, web search, web scraping)
- ✅ Security tests (information leakage prevention)
- ✅ Performance tests (response time, concurrency)
- ✅ Conversation memory and context handling
- ✅ Fallback mechanisms for unavailable data
- ✅ Edge cases and error handling

**Expected Results:** 22/22 tests passing with 100% success rate

### Individual API Tests

#### Health Check

```bash
curl http://localhost:8000/health
```

#### Chat Endpoint with Tool Calling

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the air quality in Nairobi?",
    "session_id": "test-session"
  }'
```

**Note:** The system now uses intelligent query analysis to automatically detect when tools are needed and call them proactively, ensuring reliable tool usage across all AI providers.

### Query Air Quality Directly

```bash
curl -X POST http://localhost:8000/api/v1/air-quality/query \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Kampala",
    "country": "UG"
  }'
```

## Next Steps

- Read the [API Documentation](./API_REFERENCE.md) for detailed endpoint information
- Try [Data Visualization](#data-visualization-quick-start) features with CSV/Excel files
- Check [Architecture](./ARCHITECTURE.md) to understand the system design
- See [Deployment Guide](./DEPLOYMENT.md) for production deployment instructions

## Data Visualization Quick Start

Upload a CSV file and generate charts:

```bash
curl -X POST http://localhost:8000/api/v1/visualization/from-file \
  -F "file=@air_quality_data.csv" \
  -F "user_prompt=Show me PM2.5 trends over time" \
  -F "chart_type=line"
```

The agent can also:

- Automatically detect best chart types for your data
- Visualize search results directly
- Support CSV, Excel (xlsx/xls), and PDF files
- Generate interactive charts (line, bar, scatter, histogram, box, heatmap, pie, area, violin)

**Example conversation:**

```
User: "Can you analyze this air quality data?" [uploads CSV]
Agent: "I'll create a visualization for you..." [generates chart]
```
