from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Single conversation message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Current user message")
    session_id: str | None = Field(None, description="Optional session ID for tracking")
    history: list[Message] | None = Field(
        None, 
        description="Optional conversation history sent by client (for stateless chat)"
    )
    save_to_db: bool = Field(
        False, 
        description="Whether to persist this conversation to database (default: False for cost savings)"
    )


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[str] | None = None
    tokens_used: int | None = Field(None, description="Approximate tokens used (for cost tracking)")
    cached: bool = Field(False, description="Whether response was served from cache")


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

