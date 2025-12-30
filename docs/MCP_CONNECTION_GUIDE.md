# MCP Connection Guide

## Model Context Protocol (MCP) Integration

This AI agent supports the Model Context Protocol (MCP) for connecting to external data sources and services. MCP allows your agent to access databases, APIs, and other tools through a standardized interface.

## Table of Contents

1. [What is MCP?](#what-is-mcp)
2. [Connection Methods](#connection-methods)
3. [Via REST API (for UI/Frontend)](#via-rest-api-for-uifrontend)
4. [Via stdio (for command line)](#via-stdio-for-command-line)
5. [Available MCP Servers](#available-mcp-servers)
6. [Examples](#examples)
7. [Troubleshooting](#troubleshooting)

---

## What is MCP?

The Model Context Protocol (MCP) is an open protocol that enables AI agents to securely connect to external data sources and tools. Instead of hard-coding integrations, MCP allows dynamic connections to:

- **Databases**: PostgreSQL, MySQL, MongoDB, Redis, etc.
- **APIs**: REST APIs, GraphQL, internal services
- **File Systems**: Local and cloud storage
- **Development Tools**: Git, Docker, package managers
- **Custom Tools**: Any service that implements MCP

**Official MCP Servers**: https://github.com/modelcontextprotocol/servers

---

## Connection Methods

### Method 1: REST API (Recommended for UI/Frontend)

Use the REST API endpoints to manage MCP connections dynamically. This is perfect for web-based UIs where users need to connect to different data sources.

**Base URL**: `http://localhost:8000/api/v1`

#### Endpoints

##### 1. Connect to MCP Server

```http
POST /mcp/connect
Content-Type: application/json

{
  "name": "postgres-db",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://user:pass@localhost:5432/mydb"
  ]
}
```

**Response**:

```json
{
  "status": "connected",
  "name": "postgres-db",
  "available_tools": []
}
```

##### 2. List Connected Servers

```http
GET /mcp/list
```

**Response**:

```json
{
  "connections": [
    {
      "name": "postgres-db",
      "status": "connected"
    }
  ]
}
```

##### 3. Disconnect from Server

```http
DELETE /mcp/disconnect/postgres-db
```

**Response**:

```json
{
  "status": "disconnected",
  "name": "postgres-db"
}
```

---

### Method 2: stdio (Command Line)

For running the agent as an MCP server itself (allowing other AI agents to connect to it):

```bash
# Start agent in MCP server mode
./start_server.sh
# Select option 2: MCP Server

# Or directly:
python -m src.mcp.server
```

This exposes the following tools via MCP:

- `get_air_quality`: Get current air quality data
- `get_air_quality_forecast`: Get air quality forecasts
- `get_air_quality_history`: Get historical air quality data
- `scrape_webpage`: Extract data from web pages
- `search_airqo_sites`: Search for AirQo monitoring sites

---

## Available MCP Servers

### Database Servers

#### PostgreSQL

```json
{
  "name": "postgres",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://username:password@localhost:5432/database"
  ]
}
```

**Features**: Query execution, schema inspection, table management

#### MySQL

```json
{
  "name": "mysql",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-mysql",
    "mysql://username:password@localhost:3306/database"
  ]
}
```

#### MongoDB

```json
{
  "name": "mongodb",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-mongodb",
    "mongodb://localhost:27017/database"
  ]
}
```

### File System Servers

#### Local Files

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-filesystem",
    "/path/to/allowed/directory"
  ]
}
```

#### Google Drive

```json
{
  "name": "gdrive",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-gdrive"]
}
```

### API Servers

#### GitHub

```json
{
  "name": "github",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"]
}
```

**Environment Variables**: Set `GITHUB_PERSONAL_ACCESS_TOKEN`

#### Slack

```json
{
  "name": "slack",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-slack"]
}
```

**Environment Variables**: Set `SLACK_BOT_TOKEN` and `SLACK_TEAM_ID`

---

## Examples

### Example 1: Connect to PostgreSQL Database (JavaScript/TypeScript Frontend)

```javascript
// Connect to database
const response = await fetch("http://localhost:8000/api/v1/mcp/connect", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    name: "warehouse-db",
    command: "npx",
    args: [
      "-y",
      "@modelcontextprotocol/server-postgres",
      "postgresql://readonly:password@db.example.com:5432/warehouse",
    ],
  }),
});

const data = await response.json();
console.log("Connected:", data);

// Now the agent can access this database via natural language
// Example: "Show me the top 10 customers by revenue from the warehouse database"
```

### Example 2: Connect to Local Files (Python)

```python
import requests

# Connect to local filesystem
response = requests.post('http://localhost:8000/api/v1/mcp/connect', json={
    "name": "project-docs",
    "command": "npx",
    "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/home/user/projects/docs"
    ]
})

print(response.json())

# Agent can now: "Read the README.md from project-docs"
```

### Example 3: Connect to GitHub (React Frontend)

```jsx
import React, { useState } from "react";

function MCPConnector() {
  const [connected, setConnected] = useState(false);

  const connectGitHub = async () => {
    const response = await fetch("http://localhost:8000/api/v1/mcp/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "github-repo",
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-github"],
      }),
    });

    if (response.ok) {
      setConnected(true);
      alert("Connected to GitHub!");
    }
  };

  return (
    <div>
      <button onClick={connectGitHub}>
        {connected ? "Connected ✓" : "Connect GitHub"}
      </button>
    </div>
  );
}
```

### Example 4: Multiple Connections

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Connect to multiple data sources
connections = [
    {
        "name": "analytics-db",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres",
                 "postgresql://user:pass@localhost:5432/analytics"]
    },
    {
        "name": "customer-files",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem",
                 "/data/customers"]
    },
    {
        "name": "github-repos",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"]
    }
]

for conn in connections:
    response = requests.post(f"{BASE_URL}/mcp/connect", json=conn)
    print(f"Connected {conn['name']}: {response.status_code}")

# List all connections
list_response = requests.get(f"{BASE_URL}/mcp/list")
print("Active connections:", list_response.json())
```

---

## Environment Setup for MCP Servers

Some MCP servers require environment variables:

```bash
# GitHub
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"

# Slack
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_TEAM_ID="T01234567"

# Google Drive (requires OAuth setup)
export GOOGLE_DRIVE_CLIENT_ID="your-client-id"
export GOOGLE_DRIVE_CLIENT_SECRET="your-secret"

# Custom API
export CUSTOM_API_KEY="your-api-key"
```

---

## Security Best Practices

1. **Never expose credentials in API requests**

   - Use environment variables
   - Store connection strings in secure vaults (AWS Secrets Manager, Azure Key Vault)
   - Use read-only database credentials when possible

2. **API keys are automatically redacted**

   - The agent sanitizes all responses to remove `token`, `api_key`, `password` fields
   - Logs are cleaned of sensitive data

3. **Restrict filesystem access**

   - Only allow access to specific directories
   - Use read-only permissions when possible

4. **Network security**
   - Use VPNs or SSH tunnels for remote databases
   - Enable SSL/TLS for database connections
   - Firewall rules for production deployments

---

## Troubleshooting

### Connection Fails

**Problem**: `Failed to connect MCP server: Command not found`

**Solution**: Ensure `npx` is installed (comes with Node.js):

```bash
node --version  # Should show v18+ or v20+
npm --version
```

Install Node.js: https://nodejs.org/

---

### Server Not Responding

**Problem**: MCP server connects but doesn't respond to queries

**Solution**:

1. Check the command is correct (run manually to test)
2. Verify environment variables are set
3. Check server logs in terminal
4. Ensure the tool is listed in `/mcp/list`

---

### Database Connection Errors

**Problem**: `Connection refused` or `Authentication failed`

**Solution**:

1. Verify connection string format
2. Check database is running: `pg_isready` (PostgreSQL) or `mysql -u user -p` (MySQL)
3. Verify credentials and network access
4. Check firewall rules

---

### npm/npx Issues

**Problem**: `npx` command fails with permissions error

**Solution**:

```bash
# Fix npm permissions (Linux/Mac)
sudo chown -R $USER ~/.npm

# Or use a version manager (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 20
nvm use 20
```

---

## Advanced: Custom MCP Server

You can create custom MCP servers for your own services:

```typescript
// custom-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server(
  { name: "custom-service", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_data",
      description: "Fetch data from custom API",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string" },
        },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  // Your custom logic here
  return { content: [{ type: "text", text: "Result" }] };
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

**Connect**:

```json
{
  "name": "my-service",
  "command": "node",
  "args": ["path/to/custom-server.js"]
}
```

---

## Support

- **Official MCP Documentation**: https://modelcontextprotocol.io/
- **MCP Server Registry**: https://github.com/modelcontextprotocol/servers
- **Issue Tracker**: https://github.com/yourusername/agent2/issues

---

## Summary

✅ **Easy Integration**: Connect data sources via REST API or command line  
✅ **Secure**: Automatic credential redaction, environment variable support  
✅ **Flexible**: Works with PostgreSQL, MySQL, MongoDB, GitHub, Slack, and more  
✅ **Frontend-Friendly**: Simple HTTP endpoints for UI/UX integration  
✅ **Extensible**: Create custom MCP servers for any service

**Next Steps**:

1. Install Node.js 18+ if not already installed
2. Choose an MCP server from the registry
3. Connect via `/mcp/connect` API endpoint
4. Start asking the agent questions about your data!
