#!/bin/bash
# Air Quality AI Agent - Stable Startup Script
# Use this script to start the server without auto-reload for testing

echo "🚀 Starting Air Quality AI Agent..."
echo "📍 Server will be available at: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "⚠️  Running in STABLE mode (no auto-reload)"
echo "   To enable auto-reload for development, add --reload flag"
echo ""

# Start the server without auto-reload
# python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# To run the MCP Server:
# python src/mcp/server.py

# For now, we default to the API server, but you can switch or run both.
echo "Select mode:"
echo "1. API Server (FastAPI)"
echo "2. MCP Server (Stdio)"
read -p "Enter choice [1]: " choice
choice=${choice:-1}

if [ "$choice" -eq 1 ]; then
    python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
elif [ "$choice" -eq 2 ]; then
    python src/mcp/server.py
else
    echo "Invalid choice"
    exit 1
fi
