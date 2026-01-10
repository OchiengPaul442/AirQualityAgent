# Aeris-AQ Developer Guide

## AI Agent Architecture & Workflows

**Version**: 2.10.3  
**Last Updated**: January 10, 2026  
**Based on**: [Anthropic's Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

---

## Table of Contents

1. [Overview](#overview)
2. [Agent Architecture](#agent-architecture)
3. [Chain-of-Thought (Real-time Transparency)](#chain-of-thought-real-time-transparency)
4. [Workflow Patterns](#workflow-patterns)
5. [Tool System (ACI)](#tool-system-aci)
6. [Session Management](#session-management)
7. [Chart Visualization](#chart-visualization)
8. [Cost Management](#cost-management)
9. [Best Practices](#best-practices)
10. [Common Patterns](#common-patterns)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Aeris-AQ is an **agentic system** that combines multiple Anthropic workflow patterns:

- **Routing**: Classifies queries (educational, real-time data, visualization, forecast)
- **Tool Selection**: Dynamically chooses appropriate data sources
- **Fallback Chains**: Tries multiple sources with circuit breaker protection
- **Prompt Chaining**: Document processing → Analysis → Visualization
- **Orchestrator Pattern**: Central agent delegates to specialized services

### Architecture Type

**Workflow + Agent Hybrid**:

- **Workflows**: Predefined paths for common patterns (e.g., chart generation from CSV)
- **Agent**: Dynamic tool selection and fallback handling for data retrieval

Per Anthropic: _"Start simple, add complexity only when needed."_ Aeris-AQ uses workflows where predictable, agents where flexible decision-making adds value.

---

## Agent Architecture

### Session Management Architecture (NEW)

**Hybrid Approach** (Custom + LangChain):

AERIS-AQ now uses a hybrid session management system combining custom performance-optimized components with LangChain's production-grade memory features:

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Manager                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           SessionContextManager (Custom)                │ │
│  │  • Document accumulation across sessions                │ │
│  │  • Context TTL management (3600s)                       │ │
│  │  • Fast in-memory caching                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │        LangChainSessionMemory (Enhanced)                │ │
│  │  • Token-aware truncation (2000 token limit)            │ │
│  │  • Redis persistence (survives restarts)                │ │
│  │  • LangSmith tracing integration                        │ │
│  │  • Memory types: window | token_buffer | summary        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Key Features**:

- **Token-aware**: Automatic truncation at 2000 tokens
- **Persistent**: Redis backend (sessions survive restarts)
- **Monitored**: LangSmith tracing for production visibility
- **Backward Compatible**: No breaking changes to existing API

**Usage**:

```python
# Automatic - no code changes needed
response = await agent_service.process_message(
    message="What's the AQI in London?",
    session_id="user-123"  # LangChain tracks automatically
)

# Memory stats included in response
print(f"Memory tokens: {response.get('memory_tokens')}")
```

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI API Layer                        │
│  /chat, /query, /health, /sessions, /upload-document       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Service                             │
│  • Query Analysis (Routing)                                  │
│  • Session Management                                        │
│  • Document Context Injection                                │
│  • Cost Tracking                                             │
│  • Security Filtering                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│  AI Provider      │      │  Tool Executor   │
│  (Gemini/GPT-4/  │      │  • 8-tier        │
│   Claude/Ollama)  │      │    fallback      │
│                   │      │  • Circuit       │
│  • System prompt  │      │    breaker       │
│  • Tool calling   │      │  • Result cache  │
│  • Context window │      │                  │
└──────────────────┘      └──────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │ Data Sources │  │   Search &   │  │ Visualization│
          │              │  │   Scraping   │  │   Service    │
          │ • AirQo      │  │              │  │              │
          │ • WAQI       │  │ • DuckDuckGo │  │ • Matplotlib │
          │ • OpenMeteo  │  │ • Trafilatura│  │ • Plotly     │
          │ • DEFRA      │  │ • BeautifulSoup│ • Seaborn   │
          │ • UBA        │  │              │  │              │
          │ • NSW        │  │              │  │ • 10 chart   │
          │ • Carbon     │  │              │  │   types      │
          └──────────────┘  └──────────────┘  └──────────────┘
```

### Request Flow

```
1. User sends request → API endpoint
2. AgentService.process_message():
   a. Load session history (up to 50 messages)
   b. Inject document context if CSV/PDF uploaded
   c. Query Analysis (routing) - classify intent
   d. Check cost limits
   e. Check cache (TTL: 30min real-time, 2h educational)
3. QueryAnalyzer.analyze_comprehensive():
   - Educational? Answer directly
   - Real-time data? Select appropriate tools
   - Chart request? Prepare for generate_chart
4. AI Provider (Gemini/GPT/Claude):
   - Receives system instruction + user message + history
   - Selects tools based on query type
   - Returns response + tool calls
5. ToolExecutor.execute_tools():
   - Runs tools in sequence/parallel
   - Applies fallback chains with circuit breaker
   - Returns structured results
6. AgentService post-processing:
   - Embed charts if generated
   - Filter sensitive data
   - Cache response (appropriate TTL)
   - Track costs
7. Return to user via API
```

---

## Chain-of-Thought (Real-time Transparency)

### Overview

Aeris-AQ implements **real-time chain-of-thought streaming** to provide full transparency into the agent's decision-making process. Based on Anthropic's principle of "explicitly showing the agent's planning steps," the system streams thinking events as they occur, not after completion.

**Key Principles** (from Anthropic's Guide):

1. **Transparency First** - Users see how the agent thinks in real-time
2. **Simplicity** - No over-engineering, straightforward event emission
3. **Optimized for Low-Cost Models** - Works brilliantly with models that lack native reasoning capabilities (Gemini Flash, Llama, etc.)
4. **Production-Ready** - Minimal overhead, resource-efficient

### Why Real-Time Streaming?

Unlike traditional "thinking mode" implementations that collect thoughts and return them after processing, our approach streams thoughts **as they happen**:

- **Better UX**: Users see progress immediately (like Claude, ChatGPT)
- **Lower Latency**: First thoughts arrive within milliseconds
- **Transparency**: Shows exactly what the agent is considering at each step
- **Trust Building**: Users understand the agent's decision-making process
- **Debugging**: Developers can see where issues occur in the pipeline

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ThoughtStream Module                      │
│  • Lightweight async event emitter                           │
│  • Queue-based for real-time delivery                        │
│  • Typed events (query_analysis, tool_selection, etc.)      │
└─────────────┬────────────────────────────────────────────────┘
              │
              │ emit()
              ▼
┌──────────────────────────────────────────────────────────────┐
│              AgentService.process_message()                  │
│                                                              │
│  1. emit_query_analysis("Understanding your question...")   │
│  2. emit_tool_selection("Selecting data sources...")        │
│  3. emit_tool_execution("Executing: get_air_quality...")    │
│  4. emit_data_retrieval("Retrieved 2.5KB from WAQI...")    │
│  5. emit_response_synthesis("Synthesizing response...")     │
│  6. complete("Response ready")                              │
└──────────────────────────────────────────────────────────────┘
              │
              │ stream()
              ▼
┌──────────────────────────────────────────────────────────────┐
│         Frontend (Server-Sent Events - SSE)                  │
│                                                              │
│  EventSource("/api/v1/agent/chat/stream")                   │
│    ├─ event: thought                                        │
│    │  data: {"type": "query_analysis", "title": "..."}     │
│    ├─ event: thought                                        │
│    │  data: {"type": "tool_execution", "title": "..."}     │
│    └─ event: complete                                       │
│       data: {"response": "...", "tokens": 150}              │
└──────────────────────────────────────────────────────────────┘
```

### Event Types

```python
class ThoughtType(Enum):
    QUERY_ANALYSIS = "query_analysis"       # Understanding the question
    TOOL_SELECTION = "tool_selection"       # Choosing data sources
    TOOL_EXECUTION = "tool_execution"       # Running tools
    DATA_RETRIEVAL = "data_retrieval"       # Processing results
    RESPONSE_SYNTHESIS = "response_synthesis"  # Generating answer
    ERROR = "error"                         # Handling failures
    COMPLETE = "complete"                   # Finished
```

### Example Event Flow

```json
// Event 1: Query Analysis (0ms)
{
  "type": "query_analysis",
  "title": "Understanding your question",
  "details": {
    "query_preview": "What's the air quality in London?",
    "detected_intent": "real_time_air_quality",
    "complexity": "simple",
    "requires_external_data": true
  },
  "timestamp": "2026-01-10T15:30:00.123Z"
}

// Event 2: Tool Selection (50ms)
{
  "type": "tool_selection",
  "title": "Selecting data sources",
  "details": {
    "query_classification": "air_quality_current",
    "confidence_score": 0.95,
    "selected_sources": ["get_city_air_quality", "geocode_location"],
    "selection_rationale": "WAQI provides real-time AQI with global coverage"
  },
  "timestamp": "2026-01-10T15:30:00.173Z"
}

// Event 3: Tool Execution (500ms)
{
  "type": "tool_execution",
  "title": "Executing: get_city_air_quality",
  "details": {
    "tool": "get_city_air_quality",
    "status": "success",
    "result": "Retrieved AQI 45 (Good) from WAQI London station"
  },
  "timestamp": "2026-01-10T15:30:00.623Z"
}

// Event 4: Data Retrieval (550ms)
{
  "type": "data_retrieval",
  "title": "Retrieved and processed data",
  "details": {
    "sources_queried": ["WAQI API"],
    "data_size_chars": 1250,
    "quality_assessment": "high",
    "integration_method": "Direct API response with fallback"
  },
  "timestamp": "2026-01-10T15:30:00.673Z"
}

// Event 5: Response Synthesis (1200ms)
{
  "type": "response_synthesis",
  "title": "Synthesizing response",
  "details": {
    "synthesis_approach": "Data-driven with health context",
    "data_sources": ["WAQI"],
    "estimated_tokens": 150
  },
  "timestamp": "2026-01-10T15:30:01.323Z"
}

// Event 6: Complete (2000ms)
{
  "type": "complete",
  "title": "Response ready",
  "details": {
    "status": "completed",
    "total_time_ms": 2000,
    "tokens_used": 145,
    "cost_estimate": 0.0002
  },
  "timestamp": "2026-01-10T15:30:02.123Z"
}
```

### Implementation Details

**ThoughtStream** (`core/agent/thought_stream.py`):

- Lightweight async event emitter
- Queue-based for real-time delivery
- Minimal memory footprint
- Type-safe events

**Integration Points**:

- `AgentService.process_message()` - Main orchestrator
- `QueryAnalyzer` - Query understanding phase
- `ToolExecutor` - Tool execution phase
- `AI Providers` - Response generation phase

**Performance**:

- First event: <50ms
- Total overhead: <10ms per request
- Memory: ~1KB per thought stream
- No impact on response quality

### Frontend Integration

**Server-Sent Events (SSE)** endpoint:

```javascript
const eventSource = new EventSource("/api/v1/agent/chat/stream");

eventSource.addEventListener("thought", (e) => {
  const thought = JSON.parse(e.data);
  console.log(`[${thought.type}] ${thought.title}`);
  // Update UI with thinking step
});

eventSource.addEventListener("complete", (e) => {
  const result = JSON.parse(e.data);
  console.log("Final response:", result.response);
  // Display final answer
  eventSource.close();
});
```

**Benefits**:

- Real-time progress indicators
- User confidence (seeing the agent "think")
- Better error handling (know where failures occur)
- Educational (learn how AI agents work)

### Best Practices

1. **Don't Overdo It**: Emit only meaningful steps (4-6 events per request)
2. **Keep Details Concise**: Users want progress, not technical dumps
3. **Handle Errors Gracefully**: Emit error events with recovery plans
4. **Test Performance**: Ensure streaming doesn't slow down responses
5. **Make it Optional**: Default to enabled, but allow disabling for API clients

---

## Workflow Patterns

### 1. Routing (Query Classification)

**Pattern**: Classify input → Route to specialized handler

**Implementation**: `QueryAnalyzer.analyze_comprehensive()`

```python
# Classifies queries into:
- educational: Definitions, explanations (no tools)
- real_time: Current air quality (fetch live data)
- forecast: Future predictions (forecast tools)
- visualization: Chart requests (document + generate_chart)
- comparison: Multiple cities (parallel tool calls)
- search: Research queries (search_web)
```

**Why**: Optimizes for accuracy and cost. Educational queries answered from knowledge (no API calls), real-time queries use appropriate data sources.

**Anthropic Principle**: "Separation of concerns—specialized prompts for distinct categories perform better."

### 2. Fallback Chain (8-Tier)

**Pattern**: Try primary source → Fallback1 → Fallback2 → ... → Final fallback

**Implementation**: `ToolExecutor._get_city_air_quality_with_fallback()`

```
Priority Order:
1. AirQo (if African city detected - 48+ indicators)
2. WAQI (global coverage, 30k+ stations)
3. AirQo (fallback for non-African)
4. Geocode + OpenMeteo (coordinates-based)
5. DEFRA (UK specific)
6. UBA (German specific)
7. NSW (Australian specific)
8. Carbon Intensity (UK only)
```

**Circuit Breaker**: If a source fails 3 times in 5 minutes, skip it for 10 minutes

**Why**: Resilience. No single point of failure. Geographic optimization (African cities get better data from AirQo).

**Anthropic Principle**: "Agents should recover from errors gracefully with fallback strategies."

### 3. Prompt Chaining (Document Analysis)

**Pattern**: Upload → Parse → Analyze → Visualize

**Implementation**:

1. User uploads CSV/Excel/PDF
2. `DocumentScanner` extracts content (first 2000 chars shown, full content cached)
3. Content injected into system prompt AND user message
4. AI receives: "DOCUMENTS ARE UPLOADED - DATA IS HERE" (capital emphasis)
5. If user says "visualize", AI calls `generate_chart` with parsed data
6. Chart embedded in response automatically

**Why**: LLMs sometimes ignore context in system prompts. Dual injection (system + user message) ensures visibility.

**Anthropic Principle**: "Make task context unavoidable—inject it where the model will see it."

### 4. Parallelization (Multi-City Comparison)

**Pattern**: Independent tasks → Run in parallel → Aggregate

**Implementation**: When user asks "Compare London and Paris":

```python
# Sequential execution for now (parallel would be optimization)
london_data = get_city_air_quality("London")
paris_data = get_city_air_quality("Paris")
# AI synthesizes comparison
```

**Future Optimization**: True parallel execution with `asyncio.gather()`

**Anthropic Principle**: "Parallelize independent subtasks for speed and focused attention."

---

## Tool System (ACI)

**Agent-Computer Interface (ACI)** = How the agent uses tools

### Tool Design Principles (Anthropic)

1. **Make it obvious**: Clear names, descriptions, examples
2. **Poka-yoke**: Design to prevent errors (e.g., absolute paths only)
3. **Natural format**: Match what LLM has seen in training data
4. **Enough tokens to think**: Don't box the model into corners

### Tool Categories

#### 1. Air Quality Data Tools

| Tool                           | Description                                      | Use Case                       | Source                |
| ------------------------------ | ------------------------------------------------ | ------------------------------ | --------------------- |
| `get_african_city_air_quality` | African cities (Uganda, Kenya, Tanzania, Rwanda) | "Kampala air quality"          | AirQo                 |
| `get_city_air_quality`         | Global cities                                    | "London air quality"           | WAQI → Fallback chain |
| `get_coordinates_air_quality`  | GPS-based                                        | "Air quality at 51.5°N, 0.1°W" | OpenMeteo             |
| `get_forecast`                 | 3-day forecast                                   | "Forecast for NYC"             | OpenMeteo             |

**Why separate African tool?**: AirQo has better coverage/accuracy for East Africa. Routing optimization.

#### 2. Search & Research Tools

| Tool             | Description             | Use Case                       |
| ---------------- | ----------------------- | ------------------------------ |
| `search_web`     | DuckDuckGo search       | "Recent air pollution studies" |
| `scrape_website` | Extract webpage content | "Summarize this WHO report"    |

#### 3. Utility Tools

| Tool               | Description           | Use Case            |
| ------------------ | --------------------- | ------------------- |
| `geocode_location` | City → Coordinates    | "Where is Kampala?" |
| `scan_document`    | Read uploaded files   | "Analyze this CSV"  |
| `generate_chart`   | Create visualizations | "Plot PM2.5 trends" |

### Tool Documentation Format

**Good** (Aeris-AQ current):

```python
{
    "name": "get_african_city_air_quality",
    "description": """Get REAL-TIME air quality for African cities from AirQo.

USE FOR: Uganda, Kenya, Tanzania, Rwanda cities
RETURNS: PM2.5, PM10, AQI, timestamp, location
EXAMPLE: "What's Kampala's air quality?"

This provides MORE ACCURATE data for African cities than global networks.""",
    "parameters": {...}
}
```

**Bad** (what to avoid):

```python
{
    "name": "get_airqo",  # Unclear name
    "description": "Gets air quality",  # Too vague
    # Missing: When to use, what it returns, examples
}
```

### Tool Usage Rules

**System Prompt Enforces**:

- ❌ Educational questions: NO TOOLS (answer from knowledge)
- ✅ Real-time data: USE TOOLS
- ❌ "What is PM2.5?": NO TOOLS
- ✅ "What's PM2.5 in London now?": USE get_city_air_quality

**Why**: Cost optimization. Every tool call adds latency and expense.

---

## Session Management

### Session Lifecycle

```
1. User starts conversation → SessionContextManager.create_session()
2. Each message → SessionContextManager.add_message()
3. Document upload → add_document_to_session()
4. Context retrieval → get_session_context(session_id, max_messages=50)
5. Session expires after 24h inactivity (configurable)
```

### Context Window Management

**Problem**: LLMs have token limits (Gemini: 1M, GPT-4: 128K, Claude: 200K)

**Solution**: Intelligent truncation in `BaseAIProvider._truncate_context_intelligently()`

```python
# Priority order:
1. System instruction (always included)
2. Last 2 messages (immediate context)
3. Document content (if provided)
4. Recent history (up to 50 messages)
5. Summarize older messages if needed
```

**Token Budgets**:

- System instruction: ~2K tokens
- Each message: ~200-500 tokens average
- Document injection: Up to 10K tokens (2000 chars × 5 docs max)
- Reserve: 4K tokens for AI response

**When to Create New Session**:

Per Anthropic best practices:

- After 50 message exchanges (context degradation)
- When switching topics completely
- When session history > 80% of context window
- After complex multi-chart tasks (recommended)

**API Pattern**:

```bash
# Check current session message count
GET /api/v1/agent/sessions/{session_id}

# If messages >= 50, create new session
POST /api/v1/agent/chat
{
  "message": "...",
  "session_id": null  # Creates new session
}
```

---

## Chart Visualization

### Supported Chart Types

| Type         | Use Case                       | Example                    |
| ------------ | ------------------------------ | -------------------------- |
| `line`       | Trends over time               | PM2.5 daily trends         |
| `bar`        | Comparisons                    | City AQI comparison        |
| `scatter`    | Correlations                   | PM2.5 vs Temperature       |
| `histogram`  | Distributions                  | AQI frequency distribution |
| `box`        | Statistical summary            | Pollution quartiles        |
| `pie`        | Proportions                    | Pollutant composition      |
| `area`       | Cumulative trends              | Stacked pollutants         |
| `timeseries` | Time-based (auto date parsing) | Historical AQI             |
| `violin`     | Distribution + density         | AQI spread across cities   |
| `heatmap`    | Matrix data                    | Hourly pollution patterns  |

### Chart Generation Flow

```
1. User uploads data.csv
2. DocumentScanner extracts content → SessionContextManager caches
3. User: "Show PM2.5 trends"
4. AI parses CSV columns from injected document content
5. AI calls: generate_chart(data=[...], chart_type='line', x_column='date', y_column='pm25')
6. VisualizationService:
   - Samples data if >1000 rows (last 70% + first 20% + random 10%)
   - Generates chart with matplotlib/plotly
   - Returns base64 PNG: "data:image/png;base64,iVBORw0KG..."
7. AgentService.process_message():
   - Detects "generate_chart" in tools_used
   - Auto-embeds: ![Generated Chart](data:image/png;base64,...)
8. API returns response with embedded chart
9. Frontend displays chart inline
```

### Why Charts Sometimes Fail

**Issue**: "Showing Python code instead of chart"

**Root Causes**:

1. **LLM doesn't call tool**: Thinks it should show code example instead
   - **Fix**: System prompt explicitly forbids code, emphasizes tool usage
2. **Chart not auto-embedded**: Tool returns data but not inserted in response
   - **Fix**: AgentService lines 1175-1216 auto-embed if missing
3. **Data structure mismatch**: CSV columns don't match expected format

   - **Fix**: Auto-detection in VisualizationService, flexible parsing

4. **Large datasets timeout**: 10K+ rows cause memory/time issues
   - **Fix**: Intelligent sampling to 1000 rows (prioritize recent data)

**Debugging**:

```bash
# Check if chart was generated
grep "📊 Chart generated" logs/app.log

# Check if chart was embedded
grep "Chart embedded in markdown" logs/app.log

# Check for tool call
grep "generate_chart" logs/app.log
```

### Best Practices

1. **Data Size**: Keep uploads < 5MB, < 10K rows for best performance
2. **Column Names**: Use clear names ("date", "pm25" better than "col1", "val")
3. **Date Format**: ISO format (YYYY-MM-DD) or common formats (Jan 2025)
4. **Chart Type**: Let AI choose based on data, or specify in request

---

## Cost Management

### Cost Tracker

**Implementation**: `CostTracker` class tracks token usage and estimates costs

```python
# Per-provider pricing (as of Jan 2026)
PROVIDER_COSTS = {
    "gemini": {"input": 0.00015, "output": 0.0006},  # per 1K tokens
    "gpt-4": {"input": 0.03, "output": 0.06},
    "claude": {"input": 0.003, "output": 0.015},
    "ollama": {"input": 0.0, "output": 0.0}  # Local
}
```

### Daily Limits

Default limits (configurable in `.env`):

- **Max daily cost**: $10.00
- **Max tokens per request**: 150K
- **Max tokens per day**: 1M

**When Limits Hit**:

```json
{
  "response": "I've reached my daily usage limit. ($10 daily budget). Please try again tomorrow or contact support.",
  "error": "cost_limit_exceeded",
  "tokens_used": 0
}
```

### Cost Optimization Strategies

1. **Query Analysis**: Answer educational questions from knowledge (no API calls)
2. **Caching**: 30min TTL for real-time data, 2h for educational
3. **Model Selection**: Use cheaper models for simple queries (future: Haiku routing)
4. **Context Truncation**: Intelligent history pruning (keep last 50 messages)
5. **Document Sampling**: Truncate to 2000 chars, full content via scan_document only if needed

**Monitoring**:

```bash
# Check daily usage
GET /api/v1/agent/cost-usage

# Response:
{
  "tokens_used": 45230,
  "cost_estimate": 1.23,
  "daily_limit": 10.00,
  "percentage_used": 12.3,
  "requests_today": 156
}
```

---

## Best Practices

### 1. System Prompt Design (Anthropic)

**Do**:

- Lead with most important rules (security, no code exposure)
- Use examples for ambiguous instructions
- Be specific about when to use/not use tools
- Format for scannability (headers, bullets, emojis)

**Don't**:

- Write novels (keep < 3K tokens)
- Repeat instructions in different ways
- Use vague language ("try to", "you might")
- Put critical rules at the end

**Aeris-AQ Prompt Structure**:

```
1. Identity & tone (100 tokens)
2. Critical security rules (300 tokens)
3. Tool usage guidelines (500 tokens)
4. Response formatting (400 tokens)
5. Error handling patterns (300 tokens)
Total: ~1600 tokens (conservative)
```

### 2. Error Handling (Anthropic: "No Dead Ends")

**Bad**:

```
"I couldn't find data for Mwanza."
```

**Good**:

```
"No real-time monitors in Mwanza yet, but I can check nearby cities:

• Dar es Salaam (largest city, comprehensive monitoring)
• Dodoma (capital city)
• Mwanza (northern region)

Which would help?"
```

**Pattern**: Acknowledge limitation + Offer 2-3 alternatives + Ask preference

### 3. Response Freshness

**Cache TTLs**:

- **Real-time data**: 30 minutes (air quality changes)
- **Forecasts**: 1 hour (updated less frequently)
- **Educational**: 2 hours (static knowledge)
- **Search results**: 1 hour (web content changes)

**Invalidation**: Manual API endpoint to clear cache for a session

```bash
DELETE /api/v1/agent/cache/{session_id}
```

### 4. Security

**Never Expose**:

- Tool names (get_airqo_measurement, generate_chart)
- API keys or internal URLs
- Database queries or internal IDs
- Code implementation details
- Error stack traces (show user-friendly message)

**Input Validation**:

- Sanitize filenames (remove path traversal)
- Limit file size (10MB max)
- Validate session IDs (UUID format)
- Rate limiting (10 requests/minute per IP)

**Output Filtering**:

- Remove reasoning markers ("The user wants...", "I think...")
- Strip tool call JSON from final response
- Sanitize data source names (show "AirQo" not "airqo_service.py")

### 5. Testing

**Key Test Scenarios**:

1. **Educational Query**: "What is PM2.5?" → No tools called, direct answer
2. **Real-Time Query**: "Kampala air quality" → AirQo called FIRST
3. **Chart Request**: Upload CSV + "visualize" → Chart displays, no code shown
4. **Data Unavailable**: "Mwanza air quality" → 2-3 alternatives offered
5. **Multi-City**: "Compare London and Paris" → Both fetched, table shown
6. **Session Continuity**: 5 messages → Session context maintained
7. **Cost Limits**: Hit daily limit → Graceful error, try tomorrow
8. **Large Dataset**: Upload 10K rows → Sampled to 1K, chart generated

---

## Common Patterns

### Pattern 1: Simple Real-Time Query

```
User: "What's the air quality in London?"

Flow:
1. QueryAnalyzer: real_time=True, location="London"
2. ToolExecutor: get_city_air_quality("London")
3. WAQI returns: {aqi: 45, pm25: 12, ...}
4. AI formats: "London's air quality is good today..."
5. Return in <1 second
```

### Pattern 2: Document + Visualization

```
User: [uploads pollution_data.csv] "Show PM2.5 trends"

Flow:
1. DocumentScanner: Extract content → 500 rows detected
2. Content injected to system prompt + user message
3. AI parses columns: date, pm25, pm10
4. AI calls: generate_chart(data=[...], chart_type='line', x_column='date', y_column='pm25')
5. VisualizationService: Sample to 1K rows, generate PNG
6. AgentService: Auto-embed chart in markdown
7. API returns response with ![Chart](data:image/png;base64,...)
8. Frontend displays inline chart
```

### Pattern 3: Fallback Chain

```
User: "Nairobi air quality"

Flow:
1. ToolExecutor detects "Nairobi" in african_indicators list
2. Try AirQo FIRST: ✅ Success → Return immediately
3. (If AirQo failed:)
   4. Try WAQI: ✅ Success → Return
   5. (If WAQI failed:)
      6. Geocode Nairobi → Get coordinates
      7. Try OpenMeteo with coords → Return
8. Circuit breaker: If all fail 3x, mark degraded
```

---

## Troubleshooting

### Issue: Agent Shows Code Instead of Executing

**Symptoms**:

```python
from tools import get_african_city_air_quality
# Step 1: Fetch data
result = get_african_city_air_quality(city="Lagos")
```

**Diagnosis**:

1. Check system prompt loaded correctly
2. Verify tool definitions include clear "USE THIS" instructions
3. Check if query classified as "educational" incorrectly

**Fix**:

```bash
# Verify system prompt
grep "NEVER show code" core/memory/prompts/system_instructions.py

# Check query classification
# Add logging to QueryAnalyzer.analyze_comprehensive()

# Test with explicit instruction
curl -X POST /api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Get me Lagos air quality data right now", ...}'
```

### Issue: Charts Not Displaying

**Symptoms**: User sees "Chart created" but no image

**Diagnosis**:

1. Check if generate_chart was called: `grep "generate_chart" logs/app.log`
2. Check if chart was embedded: `grep "Chart embedded" logs/app.log`
3. Verify chart_data in response: `curl ... | jq '.response'`

**Fix**:

1. **If chart not generated**: AI didn't call tool
   - Strengthen system prompt chart instructions
   - Ensure document content is visible to AI
2. **If generated but not embedded**: Auto-embed failed

   - Check AgentService lines 1175-1216
   - Verify chart_result in response_data

3. **If embedded but not showing**: Frontend issue
   - Verify markdown parser supports ![](data:image/png;base64,...)
   - Check browser console for errors

### Issue: Session Context Lost

**Symptoms**: Agent forgets previous conversation after ~20 messages

**Diagnosis**:

1. Check session message count: `GET /api/v1/agent/sessions/{session_id}`
2. Verify context window size: `grep "max_messages" core/memory/context_manager.py`
3. Check truncation logs: `grep "Truncating context" logs/app.log`

**Fix**:

```python
# Increase history depth (default: 50)
MAX_HISTORY_MESSAGES = 100  # session_context_manager.py

# Or create new session after 50 messages (recommended)
if message_count >= 50:
    session_id = None  # Force new session
```

### Issue: High Costs

**Symptoms**: Daily limit hit frequently, high token usage

**Diagnosis**:

```bash
# Check usage patterns
GET /api/v1/agent/cost-usage

# Identify expensive queries
grep "tokens_used" logs/app.log | sort -t':' -k2 -nr | head -20
```

**Fix**:

1. **Reduce context window**: Lower MAX_HISTORY_MESSAGES
2. **Increase caching**: Raise TTLs for cacheable queries
3. **Optimize prompts**: Remove verbose examples
4. **Use cheaper models**: Route simple queries to Haiku/GPT-3.5
5. **Document sampling**: Reduce document truncation limit

---

## Model Selection and Optimization

### Supported Providers

The agent supports three AI providers, each optimized for different deployment scenarios:

1. **Ollama (Local Models)** - Zero-cost local inference
2. **OpenAI (Cloud API)** - GPT-4, DeepSeek, OpenRouter compatible
3. **Gemini (Google Cloud)** - Gemini 1.5/2.0 family

### Provider-Specific Optimizations

#### Ollama Provider (Low-End Model Support)

The Ollama provider includes automatic optimizations for low-end models (1B-3B parameters):

**Automatic Detection**:

```python
# Detects model size from name pattern
is_low_end_model = any(size in model_name for size in [":1b", ":3b", ":0.5b"])
```

**Low-End Model Optimizations**:

- **Context Truncation**: Max 8 messages (vs 32 for larger models)
- **Token Limits**: Capped at 800 tokens (vs 1200-1500)
- **Temperature**: Reduced to 0.35 (vs 0.45)
- **Top-P**: Tightened to 0.8 (vs 0.9)
- **Top-K**: Limited to 40 tokens
- **Retry Delays**: Increased to 2.0s (vs 1.0s)

**Example Configuration** (`.env`):

```bash
AI_PROVIDER=ollama
AI_MODEL=qwen2.5:3b
# Optimizations apply automatically
```

**Test Results** (qwen2.5:3b):

- Pass Rate: 100% (29/29 tests)
- Response Time: 3-8s average
- Memory: Optimized with aggressive truncation
- Cost: $0 (fully local)

**Recommended Local Models**:

- **3B Models**: qwen2.5:3b, phi-3-mini (best balance)
- **7B Models**: qwen2.5:7b, mistral:7b (better quality)
- **13B+ Models**: Use default settings (no low-end optimizations)

#### OpenAI Provider

**Optimizations**:

- UTF-8 text sanitization to prevent encoding errors
- Forced tool calling for search/scraping queries
- Automatic retry with exponential backoff
- Context truncation for token limit errors

**Recommended Models**:

- **GPT-4o**: Best quality, higher cost
- **GPT-4o-mini**: Balanced quality/cost
- **GPT-3.5-turbo**: Fast, low-cost for simple queries

#### Gemini Provider

**Optimizations**:

- UTF-8 text sanitization
- Intelligent context truncation on token limit
- Retry logic with delay escalation
- Rate limit detection and logging

**Recommended Models**:

- **gemini-2.0-flash-exp**: Latest experimental (fastest)
- **gemini-1.5-flash**: Production stable (good quality)
- **gemini-1.5-pro**: Best quality (higher cost)

### Response Parameter Tuning

Parameters are defined in `core/memory/prompts/system_instructions.py`:

```python
# Base parameters (optimized for low-end models)
"temperature": 0.4,     # Lower for consistency
"top_p": 0.85,          # Tighter sampling
"top_k": 40,            # Limited vocabulary
"max_tokens": 1200      # Reduced for efficiency
```

**Style-Specific Overrides**:

- **Executive**: temp=0.3, tokens=800 (concise data-driven)
- **Technical**: temp=0.4, tokens=1500 (detailed explanations)
- **General**: temp=0.45, tokens=1200 (balanced)
- **Simple**: temp=0.5, tokens=1000 (approachable language)
- **Policy**: temp=0.3, tokens=1500 (formal citations)

**Low-End Model Capping**:
All style presets are capped for low-end models:

- Max temperature: 0.6
- Max top_p: 0.9
- Max tokens: 1500

### Performance Benchmarks

**Low-End Local (qwen2.5:3b)**:

- Simple queries: 3-4s
- Complex multi-city: 8-10s
- Document analysis: 9-12s
- Cost: $0/1000 tokens

**Cloud API (GPT-4o-mini)**:

- Simple queries: 0.8-1.2s
- Complex multi-city: 2-3s
- Document analysis: 3-5s
- Cost: ~$0.15/1000 tokens (input), ~$0.60/1000 tokens (output)

### Troubleshooting Model Issues

#### Issue: Ollama Model Not Found

**Symptoms**: "Model not found" error with Ollama

**Fix**:

```bash
# List available models
ollama list

# Pull model if missing
ollama pull qwen2.5:3b

# Verify model loaded
curl http://localhost:11434/api/tags
```

#### Issue: OpenAI Rate Limit

**Symptoms**: 429 Too Many Requests error

**Fix**:

```python
# Increase retry delay in config
OPENAI_RETRY_DELAY = 2.0  # seconds
OPENAI_MAX_RETRIES = 5

# Or switch to lower-tier model
AI_MODEL=gpt-3.5-turbo  # vs gpt-4o
```

#### Issue: Gemini Context Length Error

**Symptoms**: "Token limit exceeded" or "Context length" errors

**Fix**:
The agent automatically truncates context intelligently. If issues persist:

```python
# Reduce history depth
MAX_HISTORY_MESSAGES = 20  # vs default 32

# Or start new session
DELETE /api/v1/sessions/{session_id}
```

---

## API Reference

### Key Endpoints

```bash
# Chat with agent
POST /api/v1/agent/chat
Body: {message, session_id?, document?}
Returns: {response, session_id, tools_used, tokens_used, cached}

# Query air quality (direct)
GET /api/v1/agent/query?city=London
Returns: {aqi, pm25, pm10, ...}

# Session management
GET /api/v1/agent/sessions/{session_id}
DELETE /api/v1/agent/sessions/{session_id}

# Cost tracking
GET /api/v1/agent/cost-usage

# Health check
GET /api/v1/health
```

### Response Format

```json
{
  "response": "London's air quality is good today—AQI 45...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "tools_used": ["get_city_air_quality"],
  "tokens_used": 1234,
  "cached": false,
  "message_count": 5,
  "document_processed": false
}
```

---

## Further Reading

1. **Anthropic**: [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
2. **Model Context Protocol**: [MCP Documentation](https://modelcontextprotocol.io/)
3. **Prompt Engineering**: [Anthropic Prompt Library](https://docs.anthropic.com/claude/prompt-library)
4. **Tool Use**: [Function Calling Best Practices](https://platform.openai.com/docs/guides/function-calling)

---

## Contributing

When modifying the agent:

1. **Test pattern changes**: Run full test suite `pytest tests/`
2. **Monitor costs**: Check token usage before/after changes
3. **Update docs**: Keep this guide in sync with code
4. **Follow Anthropic patterns**: Reference their guidelines
5. **Security first**: Never expose internal details to users

---

**Questions?** See [SECURITY_AND_CHART_FIX.md](./SECURITY_AND_CHART_FIX.md) for recent improvements.

**Version History**: See [CHANGELOG.md](../CHANGELOG.md) for all updates.
