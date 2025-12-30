from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Single conversation message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """
    Chat request model - simplified for production use.
    
    Session Management:
    - Provide session_id to continue an existing conversation
    - Omit session_id to start a new conversation (server generates ID)
    - All messages are automatically saved to the database
    - Close the session via DELETE /sessions/{session_id} when done
    """
    message: str = Field(..., description="Current user message")
    session_id: str | None = Field(
        None, 
        description="Session ID for continuing a conversation. If omitted, a new session is created."
    )


class ChatResponse(BaseModel):
    """Chat response with session tracking and cost information"""
    response: str = Field(..., description="AI assistant's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    tools_used: list[str] | None = Field(None, description="Tools/APIs called during this response")
    tokens_used: int | None = Field(None, description="Approximate tokens used (for cost tracking)")
    cached: bool = Field(False, description="Whether response was served from cache")
    message_count: int | None = Field(None, description="Total messages in this session")


class HealthCheck(BaseModel):
    status: str
    version: str


class AirQualityQueryRequest(BaseModel):
    city: str
    country: str | None = None


class MCPConnectionRequest(BaseModel):
    """Request to connect to an MCP server"""
    name: str
    command: str
    args: list[str] = []


class MCPConnectionResponse(BaseModel):
    """Response after MCP connection"""
    status: str
    name: str
    available_tools: list[dict[str, Any]] = []


class MCPListResponse(BaseModel):
    """List all connected MCP servers"""
    connections: list[dict[str, Any]]

