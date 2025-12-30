import os
import re
import shutil
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.models import (
    AirQualityQueryRequest,
    ChatRequest,
    ChatResponse,
    HealthCheck,
    MCPConnectionRequest,
    MCPConnectionResponse,
    MCPListResponse,
)
from src.config import get_settings
from src.db.database import get_db
from src.db.repository import add_message, get_all_sessions, get_session_history
from src.services.agent_service import AgentService
from src.services.airqo_service import AirQoService
from src.services.waqi_service import WAQIService

router = APIRouter()
settings = get_settings()

# Global agent instance for MCP connection management
_agent_instance = None

# Rate limiting (in-memory, for production use Redis)
_rate_limit_store = defaultdict(list)
RATE_LIMIT_REQUESTS = 20  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds


def check_rate_limit(client_ip: str) -> bool:
    """
    Simple in-memory rate limiting.
    For production with multiple servers, use Redis.
    """
    now = datetime.now()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    # Clean old requests
    _rate_limit_store[client_ip] = [
        req_time for req_time in _rate_limit_store[client_ip] 
        if req_time > cutoff
    ]
    
    # Check limit
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Add current request
    _rate_limit_store[client_ip].append(now)
    return True


def get_agent():
    """Get or create agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentService()
    return _agent_instance


def sanitize_response(data: any) -> any:
    """
    Remove sensitive API keys from response data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Skip sensitive fields
            if key.lower() in ["token", "api_key", "api_token", "apikey", "secret", "password"]:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_response(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_response(item) for item in data]
    elif isinstance(data, str):
        # Remove tokens from query params in URLs
        return re.sub(r"(token|api_key|apikey)=[^&\s]+", r"\1=***REDACTED***", data)
    return data


@router.get("/health", response_model=HealthCheck)
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/sessions")
async def list_sessions(limit: int = 50, db: Session = Depends(get_db)):
    """List past chat sessions"""
    sessions = get_all_sessions(db, limit)
    return [{"id": s.id, "created_at": s.created_at} for s in sessions]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Get message history for a session"""
    messages = get_session_history(db, session_id)
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages]


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Chat endpoint using the configured AI model (Gemini/OpenAI).
    Supports tool calling for air quality data.
    
    NEW: Client-side session management for cost optimization:
    - Send conversation history in the request to maintain context
    - Set save_to_db=True only when user wants to save conversation
    - This reduces database storage costs dramatically
    """
    try:
        # Rate limiting
        client_ip = http_request.client.host
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Please try again in a moment."
            )
        
        session_id = request.session_id or str(uuid.uuid4())
        
        # Use client-provided history OR fetch from database
        if request.history:
            # Client-side session management (ChatGPT style)
            # Convert Pydantic models to dicts
            history = [{"role": msg.role, "content": msg.content} for msg in request.history]
        else:
            # Fallback to database (for backward compatibility)
            history_objs = get_session_history(db, session_id)
            history = [{"role": m.role, "content": m.content} for m in history_objs]
        
        # Only save to database if explicitly requested
        if request.save_to_db:
            add_message(db, session_id, "user", request.message)
        
        # Initialize Agent Service
        agent = get_agent()

        # Process message with start time for cost tracking
        start_time = time.time()
        result = await agent.process_message(request.message, history)
        processing_time = time.time() - start_time

        final_response = sanitize_response(result["response"])
        tools_used = result["tools_used"]
        
        # Only save assistant response if requested
        if request.save_to_db:
            add_message(db, session_id, "assistant", final_response)
        
        # Estimate tokens for cost tracking (rough estimate)
        tokens_used = len(request.message.split()) + len(final_response.split())
        for msg in history:
            tokens_used += len(msg["content"].split())
        tokens_used = int(tokens_used * 1.3)  # Rough multiplier for actual tokens
        
        return ChatResponse(
            response=final_response, 
            session_id=session_id, 
            tools_used=tools_used,
            tokens_used=tokens_used,
            cached=result.get("cached", False)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/air-quality/query")
async def query_air_quality(request: AirQualityQueryRequest):
    """Direct air quality data query endpoint"""
    try:
        results = {}

        if "waqi" in settings.ENABLED_DATA_SOURCES:
            try:
                waqi = WAQIService()
                waqi_data = waqi.get_city_feed(request.city)
                if waqi_data and waqi_data.get("status") == "ok":
                    results["waqi"] = sanitize_response(waqi_data)
            except Exception as e:
                results["waqi_error"] = str(e)

        if "airqo" in settings.ENABLED_DATA_SOURCES:
            try:
                airqo = AirQoService()
                # Try to get recent measurements for the city
                airqo_data = airqo.get_recent_measurements(city=request.city)
                if airqo_data:
                    results["airqo"] = sanitize_response(airqo_data)
            except Exception as e:
                results["airqo_error"] = str(e)

        if not results or all(k.endswith("_error") for k in results.keys()):
            raise HTTPException(status_code=404, detail="No data found for this location")

        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/mcp/connect", response_model=MCPConnectionResponse)
async def connect_mcp_server(request: MCPConnectionRequest):
    """
    Connect to an external MCP server.
    
    Example:
    {
        "name": "postgres-server", 
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
    }
    """
    try:
        agent = get_agent()
        await agent.connect_mcp_server(request.name, request.command, request.args)
        
        # Try to get available tools from the MCP client
        tools = []
        if request.name in agent.mcp_clients:
            try:
                client = agent.mcp_clients[request.name]
                # Note: This requires the client to be connected
                # We'll return basic info for now
                tools = []
            except Exception:
                pass
        
        return MCPConnectionResponse(
            status="connected",
            name=request.name,
            available_tools=tools
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect MCP server: {str(e)}")


@router.get("/mcp/list", response_model=MCPListResponse)
async def list_mcp_connections():
    """List all connected MCP servers"""
    try:
        agent = get_agent()
        connections = [
            {
                "name": name,
                "status": "connected"
            }
            for name in agent.mcp_clients.keys()
        ]
        return MCPListResponse(connections=connections)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mcp/disconnect/{name}")
async def disconnect_mcp_server(name: str):
    """Disconnect from an MCP server"""
    try:
        agent = get_agent()
        if name in agent.mcp_clients:
            # Remove the client
            # Note: Proper cleanup would require calling disconnect on the client
            del agent.mcp_clients[name]
            return {"status": "disconnected", "name": name}
        else:
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for the agent to scan"""
    try:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"filename": file.filename, "file_path": os.path.abspath(file_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
