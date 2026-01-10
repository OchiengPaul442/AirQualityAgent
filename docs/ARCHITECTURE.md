# AERIS-AQ AI Agent Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Architectural Patterns](#architectural-patterns)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Design Principles](#design-principles)
6. [Scaling Considerations](#scaling-considerations)

## System Overview

AERIS-AQ is an AI-powered air quality consultation agent built following Anthropic's best practices for effective agents. The system employs a hybrid workflow-agent architecture optimized for reliability, performance, and cost-efficiency.

### Key Capabilities

- Real-time air quality data retrieval from multiple global sources
- Intelligent query routing and tool selection
- Proactive tool orchestration with parallel execution
- Document scanning and data visualization
- Session-based conversation memory with automatic cleanup
- Comprehensive error handling and fallback mechanisms

### System Type Classification

According to Anthropic's framework, AERIS-AQ is a **hybrid agentic system**:

- **Workflow Components**: Proactive tool calling with predefined patterns (routing, parallelization)
- **Agent Components**: Dynamic tool selection and adaptive response generation

## Architectural Patterns

### 1. Routing Pattern

The system employs intelligent query classification to route requests efficiently:

```
User Query
    |
    v
Query Classifier
    |
    +--- Educational Query --> Direct AI Response (no tools)
    +--- Location-Specific --> Air Quality Tools
    +--- Research Query --> Search Tools
    +--- Data Analysis --> Search + Visualization Tools
```

**Implementation**: `src/services/agent/query_analyzer.py`

**Benefits**:

- Reduces unnecessary tool calls (cost optimization)
- Improves response time for simple queries
- Better accuracy through specialized handling

### 2. Parallelization Pattern (Sectioning)

Independent tool calls execute concurrently using asyncio.gather():

```
Composite Query: "Air quality in Kampala AND London"
    |
    v
Parallel Execution
    |
    +--- get_african_city_air_quality("Kampala")  ---+
    |                                                  |
    +--- get_city_air_quality("London")  -------------+--> Aggregate Results
                                                       |
                                                       v
                                                  AI Synthesis
```

**Implementation**: `tool_executor.execute_parallel()`

**Performance Impact**:

- 3 sequential calls at 15s each = 45s total
- 3 parallel calls = max(15s) = 15s total
- 66% latency reduction

### 3. Orchestrator-Workers Pattern

Central agent orchestrates multiple specialized services:

```
Agent Service (Orchestrator)
    |
    +--- Tool Executor (Worker Manager)
    |        |
    |        +--- Air Quality Services (Workers)
    |        +--- Search/Scrape Services (Workers)
    |        +--- Geocoding Services (Workers)
    |        +--- Visualization Services (Workers)
    |
    +--- Query Analyzer (Classification Worker)
    +--- Session Manager (State Worker)
```

**Benefits**:

- Clear separation of concerns
- Independent service scaling
- Simplified testing and maintenance

### 4. Prompt Chaining Pattern

Complex tasks decompose into sequential steps:

```
1. Query Analysis --> Classification + Entity Extraction
2. Proactive Tool Calls --> Data Retrieval
3. Context Injection --> Augmented Prompt
4. AI Processing --> Response Generation
5. Post-Processing --> Format + Sanitize
```

**Implementation**: `agent_service.process_message()`

## Core Components

### 1. Agent Service Layer

**File**: `src/services/agent_service.py`

**Responsibilities**:

- Session management and state tracking
- Message routing and orchestration
- Provider selection (OpenAI, Gemini, Ollama)
- Response post-processing

**Key Methods**:

- `process_message()`: Main entry point for user queries
- `_get_or_create_session()`: Session lifecycle management
- `_check_message_limit()`: Prevent session overflow

**Design Pattern**: Orchestrator (coordinates all other components)

### 2. Query Analyzer

**File**: `src/services/agent/query_analyzer.py`

**Responsibilities**:

- Query type classification (educational, location-specific, research, data analysis)
- Entity extraction (cities, coordinates, time references)
- Proactive tool orchestration
- Search query generation

**Classification Priority** (Anthropic-inspired):

1. Data Analysis (highest - contains "study", "research", "statistics")
2. Research (temporal keywords - "recent", "latest", "2024")
3. Educational (lowest - only if no other triggers)

**Key Methods**:

- `classify_query_type()`: Route queries to appropriate handlers
- `detect_air_quality_query()`: Extract locations and coordinates
- `detect_forecast_query()`: Identify temporal queries
- `proactively_call_tools()`: Execute tools before AI inference

### 3. Tool Executor

**File**: `src/services/agent/tool_executor.py`

**Responsibilities**:

- Tool execution with error handling
- Circuit breaker pattern for failing services
- Parallel execution coordination
- Service health monitoring

**Key Features**:

- **Circuit Breaker**: Prevents cascade failures (threshold: 5 failures, timeout: 5 minutes)
- **Lazy Loading**: Visualization service loaded on-demand
- **Fallback Chain**: Multiple data sources for redundancy

**Tool Categories**:

1. Air Quality Tools (7 sources: AirQo, WAQI, OpenMeteo, DEFRA, UBA, NSW, Carbon Intensity)
2. Weather Tools (current + forecast)
3. Search Tools (web search + scraping)
4. Document Tools (CSV/Excel scanning)
5. Geocoding Tools (address/coordinate conversion)
6. Visualization Tools (chart generation)

**Parallel Execution Example**:

```python
results = await executor.execute_parallel([
    ("get_african_city_air_quality", {"city": "Kampala"}),
    ("get_city_air_quality", {"city": "London"}),
    ("get_openmeteo_current_air_quality", {"latitude": 0.3, "longitude": 32.5})
])
```

### 4. AI Provider Layer

**Files**:

- `src/services/providers/openai_provider.py` (OpenAI, Azure OpenAI)
- `src/services/providers/gemini_provider.py` (Google Gemini)
- `src/services/providers/ollama_provider.py` (Local models)

**Responsibilities**:

- LLM API interaction
- Tool calling protocol handling
- Token counting and cost tracking
- Retry logic with exponential backoff

**Provider Selection Logic**:

```
1. Check AI_PROVIDER env variable
2. Validate required API keys/endpoints
3. Fall back to Ollama if cloud providers unavailable
```

**Cost Optimization**:

- Token counting for all providers
- Configurable model selection per provider
- Automatic retry with backoff
- Provider-specific error handling

### 5. Session Management

**File**: `src/db/repository.py`

**Responsibilities**:

- Conversation history persistence
- Session isolation (prevents contamination)
- Message limit enforcement (100 per session)
- Automatic session cleanup

**Session Lifecycle**:

```
1. Create Session (unique ID)
2. Add Messages (user + assistant)
3. Monitor Count (warning at 90, limit at 100)
4. Archive/Delete (cleanup old sessions)
```

**Database Schema**:

- SQLite with async support (aiosqlite)
- Tables: sessions, messages, session_metadata
- Indexes: session_id, created_at

### 6. Data Services Layer

**Files**: `src/services/*_service.py`

**Design Pattern**: Base class inheritance (eliminates 71% code duplication)

**Base Class** (`base_service.py`):

```python
class BaseAPIService:
    def __init__(self, base_url, api_key, cache_ttl):
        self.http_client = get_http_client()
        self.cache = get_cache()
        self.api_key = api_key
        ...

    async def fetch_with_cache(self, url, params):
        # Standardized caching + error handling
```

**Concrete Services**:

- AirQoService (East Africa monitoring)
- WAQIService (Global WAQI network)
- OpenMeteoService (Weather + AQ)
- SearchService (Brave/Tavily)
- GeocodingService (Nominatim)
- VisualizationService (Matplotlib/Plotly)

## Data Flow

### Standard Query Flow

```
1. User Request
   |
   v
2. API Route Handler (routes.py)
   |
   v
3. Agent Service
   | - Retrieve session
   | - Check message limit
   |
   v
4. Query Analyzer
   | - Classify query type
   | - Extract entities
   | - Decide tool usage
   |
   v
5. Tool Executor (if needed)
   | - Execute tools (parallel if possible)
   | - Format results
   | - Inject into context
   |
   v
6. AI Provider
   | - Build prompt
   | - Call LLM
   | - Parse response
   |
   v
7. Response Post-Processing
   | - Sanitize content
   | - Format markdown
   | - Extract chart data
   |
   v
8. Save to Session
   |
   v
9. Return to User
```

### Proactive Tool Calling Flow

```
User Query: "What's the air quality in Kampala?"
   |
   v
Query Analyzer
   | - Detects: location-specific query
   | - Extracts: city="Kampala"
   | - Classification: African city
   |
   v
Proactive Tool Call (BEFORE LLM)
   | - execute_async("get_african_city_air_quality", {"city": "Kampala"})
   | - Result: {"aqi": 45, "pm25": 12, "source": "AirQo"}
   |
   v
Context Injection
   | - Append formatted result to prompt
   | - "REAL-TIME DATA from AirQo for Kampala: AQI 45 (Good), PM2.5 12 µg/m³"
   |
   v
LLM Processing (with fresh data)
   | - AI synthesizes response using real-time data
   | - Cites source: "According to AirQo..."
   |
   v
User receives accurate, sourced response
```

### Composite Query Flow (Parallel Execution)

```
User Query: "Compare air quality in Kampala, Nairobi, and London"
   |
   v
Query Analyzer
   | - Detects: 2 African cities + 1 global city
   | - Classification: multi-location
   |
   v
Parallel Tool Execution
   | - Task 1: get_african_city_air_quality("Kampala")  ---|
   | - Task 2: get_african_city_air_quality("Nairobi")  ---+-> asyncio.gather()
   | - Task 3: get_city_air_quality("London")           ---|
   |
   | All execute simultaneously (max latency ~15s vs 45s sequential)
   |
   v
Aggregate Results
   | - Kampala: AQI 45
   | - Nairobi: AQI 32
   | - London: AQI 28
   |
   v
Context Injection + LLM
   | - AI compares all three cities
   | - Provides ranking and insights
   |
   v
User receives comprehensive comparison
```

## Design Principles

### 1. Simplicity First (Anthropic Principle #1)

**Implementation**:

- Direct LLM API calls (no heavy frameworks)
- Minimal abstraction layers
- Clear, readable code structure

**Example**: Tool executor uses simple dict returns, not complex custom objects.

### 2. Augmented LLM (Anthropic Building Block)

**Components**:

- **Retrieval**: Real-time data from 7+ sources
- **Tools**: 20+ specialized functions
- **Memory**: Session-based conversation history

**Implementation**: Every LLM call has access to tools and memory through base prompt.

### 3. Agent-Computer Interface (ACI)

Tool definitions follow Anthropic's guidelines:

```python
{
    "name": "get_african_city_air_quality",
    "description": """
    Get REAL-TIME air quality for African cities.

    USE WHEN:
    - User asks about African cities (Uganda, Kenya, Tanzania, Rwanda)
    - Need current PM2.5, PM10, AQI data

    DON'T USE WHEN:
    - Non-African locations (use get_city_air_quality)
    - Historical data requests

    RETURNS:
    - PM2.5 (µg/m³), PM10, AQI, location, timestamp

    EXAMPLES:
    - "What's Kampala air quality?" ✓
    - "London air quality" ✗ (wrong tool)
    """
}
```

**Benefits**:

- Clear usage boundaries
- Examples prevent misuse
- Better performance on weak models

### 4. Transparency

**Implementation**:

- Detailed logging at all levels
- Clear error messages with guidance
- Source attribution in responses
- Explicit tool execution tracking

**Example**: Every tool call logs: `"Proactive call: get_african_city_air_quality for Kampala"`

### 5. Validation and Feedback

**Mechanisms**:

- Circuit breaker for failing services
- Session message limits (prevents runaway conversations)
- Explicit error handling with user guidance
- Comprehensive test suite (25 tests, 100% pass rate)

## Scaling Considerations

### Horizontal Scaling

**Stateless Design**: Each request is independent (session stored in DB, not memory)

**Scaling Strategy**:

```
Load Balancer
    |
    +--- App Server 1 (FastAPI)
    +--- App Server 2 (FastAPI)
    +--- App Server 3 (FastAPI)
            |
            v
    Shared PostgreSQL Database
            |
            v
    Shared Redis Cache
```

### Performance Optimization

**Current Optimizations**:

1. **Parallel Tool Execution**: 66% latency reduction for composite queries
2. **Intelligent Caching**: 5-minute TTL for air quality data
3. **Query Classification**: Skip tools for educational queries
4. **Lazy Loading**: Visualization service loaded on-demand
5. **Circuit Breaker**: Prevent cascade failures

**Future Optimizations**:

1. **Connection Pooling**: Reuse HTTP connections (currently creates new per request)
2. **Response Streaming**: Stream LLM responses chunk-by-chunk
3. **Result Batching**: Group multiple tool results for single LLM call
4. **Caching Layer**: Redis for distributed caching
5. **Rate Limiting**: Per-user/session limits

### Cost Optimization

**Current Strategies**:

1. **Model Selection**: Support for low-cost models (llama3.2:1b works!)
2. **Skip Unnecessary Tools**: Educational queries use AI knowledge only
3. **Efficient Prompts**: Context injection only when needed
4. **Token Counting**: Track usage per provider
5. **Smart Fallbacks**: Cheaper models for simple queries

**Cost Breakdown** (estimated):

- Low-end model (llama3.2:1b): $0/month (self-hosted)
- Mid-tier model (qwen2.5:3b): $0/month (self-hosted)
- Cloud models (Gemini/OpenAI): ~$0.002 per query average

### Reliability Patterns

**Circuit Breaker**:

```
Service fails 5 times --> Open circuit (5 min)
    |                           |
    v                           v
Stop calling service    Allow retry after timeout
```

**Retry Logic**:

```
API Call --> Fails --> Wait 1s --> Retry --> Fails --> Wait 2s --> Retry --> Fails --> Return error
                                                                                             |
                                                                                             v
                                                                                    Log + user guidance
```

**Fallback Chain** (Air Quality):

```
1. Try AirQo (for African cities)
2. If fails, try WAQI
3. If fails, try OpenMeteo
4. If all fail, provide helpful message with alternatives
```

## Security Considerations

**Input Sanitization**:

- SQL injection prevention (parameterized queries)
- XSS prevention (HTML escaping)
- Prompt injection detection
- File path validation

**API Key Management**:

- Environment variables only
- Never logged or exposed
- Per-service key rotation support

**Rate Limiting** (recommended for production):

- Per-IP limits: 60 requests/minute
- Per-session limits: 100 messages total
- Per-user limits: 1000 requests/day

**Content Security**:

- Tool name filtering (never exposed to user)
- Internal reasoning redaction
- Chart data validation
- URL whitelist for scraping

## Monitoring and Observability

**Current Logging**:

- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Context: session_id, user_id, tool_name
- Performance: execution time per tool

**Recommended Metrics**:

1. **Latency**: p50, p95, p99 response times
2. **Throughput**: requests per second
3. **Error Rate**: percentage of failed requests
4. **Tool Usage**: which tools called most frequently
5. **Model Performance**: accuracy, cost per query
6. **Session Duration**: average messages per session

**Health Checks**:

- Database connection
- External API availability
- Model endpoint reachability
- Cache connectivity

## Maintenance Guide

**Regular Tasks**:

1. **Weekly**: Review logs for errors, update API keys if needed
2. **Monthly**: Run comprehensive test suite, check service health
3. **Quarterly**: Update dependencies, review and update tool descriptions
4. **Annually**: Security audit, performance benchmarking

**Common Issues**:

1. **API Rate Limits**: Add retry logic, implement caching
2. **Model Performance**: Tune prompts, try different models
3. **Session Overflow**: Lower message limit, implement cleanup
4. **Tool Failures**: Check API keys, verify endpoint URLs

**Debugging Guide**:

```
1. Check logs: logs/errors.json
2. Verify env vars: .env file
3. Test tool directly: tool_executor.execute()
4. Run test suite: python tests/comprehensive_test_suite.py
5. Check service health: curl http://localhost:8000/health
```

## Version History

- **v2.10.1** (2026-01-10): Added parallel execution, 100% test pass rate achieved
- **v2.10.0** (2026-01-09): Session isolation, code deduplication, lint fixes
- **v2.9.0** (2025-12): Enhanced prompting, multi-model support
- **v2.8.0** (2025-11): Document scanning, visualization service

## References

- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.com/docs)
