import logging
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
from src.db.repository import (
    add_message,
    delete_session,
    get_all_sessions,
    get_recent_session_history,
    get_session,
)
from src.services.agent_service import AgentService
from src.services.airqo_service import AirQoService
from src.services.waqi_service import WAQIService

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

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
    """
    List all chat sessions ordered by most recent first.
    
    Args:
        limit: Maximum number of sessions to return (default: 50, max: 200)
        
    Returns:
        List of sessions with id, created_at, and message count
    """
    limit = min(limit, 200)  # Cap at 200
    sessions = get_all_sessions(db, limit)
    
    result = []
    for s in sessions:
        message_count = len(s.messages)
        result.append({
            "id": s.id, 
            "created_at": s.created_at,
            "message_count": message_count,
            "updated_at": s.updated_at
        })
    
    return result


@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific session including all messages.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session details with full message history
    """
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = get_recent_session_history(db, session_id, max_messages=1000)
    
    return {
        "id": session.id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(messages),
        "messages": [
            {
                "role": m.role, 
                "content": m.content, 
                "timestamp": m.timestamp
            } 
            for m in messages
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a chat session and all its messages.
    Call this when the user closes a session in the frontend.
    
    Args:
        session_id: Session identifier to delete
        
    Returns:
        Confirmation message
    """
    deleted = delete_session(db, session_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "status": "success",
        "message": f"Session {session_id} and all its messages have been deleted",
        "session_id": session_id
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str, 
    limit: int = 100, 
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get paginated message history for a session.
    
    Args:
        session_id: Session identifier
        limit: Maximum messages to return (default: 100)
        offset: Number of messages to skip (default: 0)
        
    Returns:
        Paginated list of messages
    """
    from src.db.repository import get_session_history
    
    messages = get_session_history(db, session_id, limit=limit, offset=offset)
    
    return {
        "session_id": session_id,
        "count": len(messages),
        "offset": offset,
        "messages": [
            {
                "role": m.role, 
                "content": m.content, 
                "timestamp": m.timestamp
            } 
            for m in messages
        ]
    }


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Chat with the Air Quality AI Agent.
    
    **Session Management (Simplified):**
    - All conversations are automatically saved to the database
    - Provide `session_id` to continue an existing conversation
    - Omit `session_id` to start a new conversation
    - Call `DELETE /sessions/{session_id}` when the user closes the chat
    
    **Cost Optimization:**
    - Recent conversation history (last 20 messages) is used for context
    - Responses are cached to avoid redundant API calls
    - Token usage is tracked and returned in the response
    
    **Example Request:**
    ```json
    {
        "message": "What's the air quality in Kampala?",
        "session_id": "abc-123"  // Optional, for continuing conversations
    }
    ```
    """
    try:
        # Rate limiting
        client_ip = http_request.client.host
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Please try again in a moment."
            )
        
        # Generate or use provided session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Save user message to database
        add_message(db, session_id, "user", request.message)
        
        # Get recent conversation history (last 20 messages for context)
        # This limits token usage while maintaining conversation continuity
        history_objs = get_recent_session_history(db, session_id, max_messages=20)
        
        # Exclude the just-added message (we'll send it separately to the agent)
        history = [
            {"role": m.role, "content": m.content} 
            for m in history_objs[:-1]  # Exclude last message (the current one)
        ]
        
        # Initialize Agent Service
        agent = get_agent()

        # Process message with timing for cost tracking
        start_time = time.time()
        result = await agent.process_message(request.message, history)
        processing_time = time.time() - start_time

        final_response = sanitize_response(result["response"])
        tools_used = result.get("tools_used", [])
        
        # Save assistant response to database
        add_message(db, session_id, "assistant", final_response)
        
        # Estimate tokens for cost tracking
        tokens_used = len(request.message.split()) + len(final_response.split())
        for msg in history:
            tokens_used += len(msg["content"].split())
        tokens_used = int(tokens_used * 1.3)  # Rough multiplier for actual tokens
        
        # Get total message count for this session
        all_messages = get_recent_session_history(db, session_id, max_messages=1000)
        message_count = len(all_messages)
        
        return ChatResponse(
            response=final_response, 
            session_id=session_id, 
            tools_used=tools_used,
            tokens_used=tokens_used,
            cached=result.get("cached", False),
            message_count=message_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/air-quality/query")
async def query_air_quality(request: AirQualityQueryRequest):
    """
    Direct air quality data query endpoint.
    
    **Intelligent Failure Handling:**
    - Only returns successful API responses
    - If one source fails, returns data from the other
    - If both fail, returns 404 with error details
    
    **Example Response (Success):**
    ```json
    {
        "waqi": { ... },
        "airqo": { ... }
    }
    ```
    """
    try:
        results = {}
        errors = {}

        # Try WAQI API
        if "waqi" in settings.ENABLED_DATA_SOURCES:
            try:
                waqi = WAQIService()
                waqi_data = waqi.get_city_feed(request.city)
                if waqi_data and waqi_data.get("status") == "ok":
                    results["waqi"] = sanitize_response(waqi_data)
                else:
                    errors["waqi"] = "No data available"
            except Exception as e:
                logger.warning(f"WAQI API failed for {request.city}: {str(e)}")
                errors["waqi"] = f"WAQI API error: {str(e)}"

        # Try AirQo API
        if "airqo" in settings.ENABLED_DATA_SOURCES:
            try:
                airqo = AirQoService()
                airqo_data = airqo.get_recent_measurements(city=request.city)
                if airqo_data and airqo_data.get("success"):
                    results["airqo"] = sanitize_response(airqo_data)
                else:
                    errors["airqo"] = "No data available"
            except Exception as e:
                logger.warning(f"AirQo API failed for {request.city}: {str(e)}")
                errors["airqo"] = f"AirQo API error: {str(e)}"

        # Return only if we have at least one successful result
        if results:
            return results
        
        # If both failed, return 404 with error details
        raise HTTPException(
            status_code=404, 
            detail={
                "message": f"No air quality data found for {request.city}",
                "errors": errors,
                "suggestion": "Try a different city name or check if the location is covered by our data sources"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Air quality query error: {str(e)}", exc_info=True)
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
