# AERIS-AQ MCP Integration Guide

Model Context Protocol (MCP) allows **AERIS-AQ (Artificial Environmental Real-time Intelligence System - Air Quality)**, your Air Quality AI Assistant, to connect to external data sources and expose its capabilities to MCP clients like Claude Desktop.

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

Aeris supports MCP in two ways:

1. **As an MCP Server**: Exposes air quality tools to MCP clients
2. **As an MCP Client**: Connects to external MCP servers (databases, APIs, etc.)

## Using Aeris as an MCP Server

### Setup for Claude Desktop

1. Start the MCP server:

   ```bash
   python src/mcp/server.py
   ```

2. Configure Claude Desktop to use the server.

3. Add to your Claude Desktop configuration (`claude_desktop_config.json`):

   ```json
   {
     "mcpServers": {
       "airquality": {
         "command": "python",
         "args": ["path/to/AirQualityAgent/src/mcp/server.py"]
       }
     }
   }
   ```

4. Restart Claude Desktop.

### Available Tools via MCP Server

When running as an MCP server, the agent exposes these tools:

- `get_city_air_quality`: Get air quality data for any city worldwide (WAQI + AirQo + OpenAQ)
- `search_waqi_stations`: Search for monitoring stations
- `get_african_city_air_quality`: Get AirQo network data for African cities
- `get_city_weather`: Get weather data for any city
- `search_web`: Search the web for information
- `scrape_website`: Extract content from websites

**Data Source Integration:**

- **Current**: WAQI, AirQo, OpenAQ APIs
- **Planned**: WHO Ambient Air Quality Database, openAFRICA datasets, Copernicus CAMS satellite data
- **Research Sources**: State of Global Air reports, WRI resources, IQAir data

## Connecting to External MCP Servers

The agent can connect to external MCP servers to access additional data sources.

### Via REST API

#### Connect to PostgreSQL

```bash
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-db",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/db"]
  }'
```

#### Connect to MySQL

```bash
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mysql-db",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-mysql", "mysql://user:pass@localhost/db"]
  }'
```

#### Connect to GitHub

```bash
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_TOKEN": "your_github_token"
    }
  }'
```

#### List Active Connections

```bash
curl http://localhost:8000/api/v1/mcp/list
```

#### Disconnect

```bash
curl -X DELETE http://localhost:8000/api/v1/mcp/disconnect/postgres-db
```

### Available MCP Servers

Common MCP servers you can connect to:

| Server       | Package                                   | Description                |
| ------------ | ----------------------------------------- | -------------------------- |
| PostgreSQL   | `@modelcontextprotocol/server-postgres`   | Query PostgreSQL databases |
| MySQL        | `@modelcontextprotocol/server-mysql`      | Query MySQL databases      |
| GitHub       | `@modelcontextprotocol/server-github`     | Access GitHub repositories |
| Slack        | `@modelcontextprotocol/server-slack`      | Read Slack messages        |
| Google Drive | `@modelcontextprotocol/server-gdrive`     | Access Google Drive files  |
| Filesystem   | `@modelcontextprotocol/server-filesystem` | Access local files         |

### Security Considerations

When connecting to external MCP servers:

1. **Use read-only connections** when possible
2. **Validate credentials** before connecting
3. **Monitor access logs** for unusual activity
4. **Limit database permissions** to only necessary operations
5. **Use environment variables** for sensitive credentials

### Example Use Cases

#### 1. Query Air Quality Database

Connect to your PostgreSQL database with historical air quality data:

```bash
# Connect to database
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "airquality-history",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://readonly:pass@localhost/airquality"]
  }'

# Now ask the agent:
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Compare air quality trends in Nairobi over the past 6 months using our database"
  }'
```

#### 2. Combine Multiple Data Sources

```bash
# Connect to weather database
curl -X POST http://localhost:8000/api/v1/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "weather-db",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://readonly:pass@localhost/weather"]
  }'

# Ask the agent to correlate data
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze the correlation between temperature and air quality in Kampala"
  }'
```

## Troubleshooting

### Connection Fails

- Verify the MCP server package is installed (`npx` will install automatically)
- Check database credentials and connectivity
- Ensure firewall allows connections
- Review server logs for detailed error messages

### Permission Errors

- Grant appropriate database permissions
- Use read-only accounts when possible
- Check file system permissions for filesystem MCP

### Performance Issues

- Limit query result sizes
- Use connection pooling
- Consider caching for frequently accessed data
- Monitor database query performance

## Advanced Configuration

### Custom MCP Servers

You can create custom MCP servers for proprietary data sources:

```python
# Example: Custom air quality data MCP server
from mcp.server import Server

server = Server()

@server.tool("get_custom_data")
async def get_custom_data(location: str):
    # Your custom data logic
    return {"data": "custom air quality data"}

if __name__ == "__main__":
    server.run()
```

### Environment Variables for MCP

Pass environment variables to MCP servers:

```json
{
  "name": "secure-db",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-postgres"],
  "env": {
    "DATABASE_URL": "postgresql://...",
    "SSL_MODE": "require"
  }
}
```

## Best Practices

1. **Separate Credentials**: Use different credentials for MCP access vs direct access
2. **Monitor Usage**: Track which MCP tools are being called and how often
3. **Limit Scope**: Only connect to necessary data sources
4. **Regular Audits**: Review connected MCP servers periodically
5. **Documentation**: Document all MCP connections and their purposes

---

## AI Response Optimization (Jan 2026 Update)

### Problem Solved

**Issue**: AI exposed internal reasoning ("The user wants...") and wasn't helpful when tools failed.

**Solution**: Enhanced system instructions + runtime detection for helpful, option-oriented responses.

### Critical Rules

**1. NO internal reasoning exposure**

- ❌ BAD: "The user wants...", "The assistant should..."
- ✅ GOOD: Jump straight to helpful response

**2. Be solution-oriented** - Always show OPTIONS:

```
❌ "I couldn't get location. Please provide it."
✅ "I can help! Options:
   • Share city/ZIP for local data
   • Ask about specific location
   • Get general air quality info"
```

**3. Prevent loops** - Say once, then alternatives.

### Response Patterns

| Scenario         | Action                  |
| ---------------- | ----------------------- |
| Educational      | Answer directly         |
| Location query   | Real-time data + health |
| Data unavailable | 3 alternatives          |
| Error            | Show capabilities       |

### Implementation

- **System**: [`system_instructions.py`](../src/services/prompts/system_instructions.py) - Rules + examples
- **Runtime**: [`agent_service.py`](../src/services/agent_service.py) - Detection + filtering
- **Tests**: `pytest tests/test_agent.py -v`

### Key Principles

1. Answer first, explain later
2. Options > Apologies
3. No reasoning exposure
4. Cite sources always

---

## Chart Generation & Visualization (Jan 2026)

### How It Works

Charts are now **embedded directly in markdown responses** for automatic rendering:

1. 📊 **AI generates chart** using `generate_chart` tool
2. 🖼️ **Tool returns base64 image** as `data:image/png;base64,...`
3. ✅ **AI embeds in response** using markdown syntax: `![Chart](data:image/png;base64,...)`
4. 🎉 **Frontend renders automatically** - no special handling needed!

### Best Practices (Like ChatGPT)

✅ **Embedded Images**: Charts are inline markdown images, not separate fields  
✅ **Auto-Rendering**: Markdown formatters display charts automatically  
✅ **Data URI Format**: Base64-encoded PNG embedded directly in response  
✅ **Self-Contained**: Single markdown response contains both text and visualization

### Technical Implementation

**1. Data Sampling**: Max 1000 rows (was 5000), prioritizing recent data  
**2. Font Fix**: DejaVu Sans for Unicode support (PM₂.₅)  
**3. Error Handling**: Graceful fallback for all 3 providers  
**4. Markdown Embedding**: Charts included as `![Chart](data:image/...)` in response  
**5. No Stripping**: Markdown formatter preserves chart images

| Provider | Error Handling         | Chart Embedding |
| -------- | ---------------------- | --------------- |
| Ollama   | ✅ 500 errors          | ✅ Yes          |
| OpenAI   | ✅ Exceptions          | ✅ Yes          |
| Gemini   | ✅ Generation failures | ✅ Yes          |

### Results

- ✅ <2 second chart generation (was timing out)
- ✅ Charts render inline with text
- ✅ No special frontend handling needed
- ✅ Compatible with all markdown renderers
- ✅ **Works like ChatGPT - embed & render**
- ✅ User notified when data sampled
- ✅ Helpful alternatives on errors
- ✅ **Consistent across all 3 providers**
- ✅ No more infinite loading

### Example Response

```markdown
📊 Here's your PM2.5 trend visualization:

![PM2.5 Trend Chart](data:image/png;base64,iVBORw0KG...)

Key insights:
• Peak levels on Jan 5th (65 µg/m³)
• Improving trend over last 3 days
• Currently at "Moderate" level

Need specific data points or date ranges?
```

**The chart displays automatically when the markdown is rendered!**
