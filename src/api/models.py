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

    Document Upload (Optional):
    - Upload a file (PDF, CSV, Excel) along with your message
    - Use multipart/form-data to send both message and file
    - Agent will analyze the document and respond to your query
    - Max file size: 8MB
    - Files are processed in memory (not saved to disk)
    """

    message: str = Field(..., description="Current user message")
    session_id: str | None = Field(
        None,
        description="Session ID for continuing a conversation. If omitted, a new session is created.",
    )


class ChatResponse(BaseModel):
    """Chat response with session tracking and cost information"""

    response: str = Field(..., description="AI assistant's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    tools_used: list[str] | None = Field(None, description="Tools/APIs called during this response")
    tokens_used: int | None = Field(None, description="Approximate tokens used (for cost tracking)")
    cached: bool = Field(False, description="Whether response was served from cache")
    message_count: int | None = Field(None, description="Total messages in this session")
    document_processed: bool = Field(
        False, description="Whether a document was uploaded and processed"
    )
    document_filename: str | None = Field(None, description="Name of the uploaded document if any")
    thinking_steps: list[str] | None = Field(
        None, 
        description="AI reasoning/thinking steps (for display ONLY during streaming, hidden in final response)"
    )
    reasoning_content: str | None = Field(
        None, 
        description="Full reasoning content as string (for internal use, not displayed to user)"
    )
    chart_data: str | None = Field(
        None,
        description="Base64-encoded chart/graph image (data:image/png;base64,...) if visualization was generated"
    )
    chart_metadata: dict[str, Any] | None = Field(
        None,
        description="Chart metadata including type, columns used, data rows count, etc."
    )


class HealthCheck(BaseModel):
    status: str
    version: str


class AirQualityQueryRequest(BaseModel):
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    forecast_days: int | None = Field(
        None, ge=1, le=7, description="Number of forecast days (1-7) for Open-Meteo"
    )
    include_forecast: bool = Field(False, description="Whether to include forecast data")
    timezone: str = Field("auto", description="Timezone (auto, GMT, or IANA like Europe/Berlin)")


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
