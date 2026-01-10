import json
import logging
import os
import re
import time
import uuid
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.api.models import (
    AirQualityQueryRequest,
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
    get_session_message_count,
)
from src.services.agent_service import AgentService
from src.services.airqo_service import AirQoService
from src.services.openmeteo_service import OpenMeteoService
from src.services.waqi_service import WAQIService
from src.utils.markdown_formatter import MarkdownFormatter
from src.utils.security import ResponseFilter, validate_request_data
from src.utils.token_counter import get_token_counter

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Global agent instance for MCP connection management
_agent_instance = None


def get_agent():
    """Get or create agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentService()
    return _agent_instance


def sanitize_response(data: Any) -> Any:
    """
    Remove sensitive API keys from response data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():  # type: ignore
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
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

    try:
        limit = min(limit, 200)  # Cap at 200
        sessions = get_all_sessions(db, limit)

        result = []
        for s in sessions:
            message_count = len(s.messages)
            result.append(
                {
                    "id": s.id,
                    "created_at": s.created_at,
                    "message_count": message_count,
                    "updated_at": s.updated_at,
                }
            )

        return result
    except SQLAlchemyTimeoutError as e:
        logger.error(f"Database timeout while listing sessions: {e}")
        raise HTTPException(
            status_code=503, detail="The database is currently busy. Please try again in a moment."
        )
    except OperationalError as e:
        logger.error(f"Database operational error while listing sessions: {e}")
        raise HTTPException(
            status_code=503, detail="Unable to connect to the database. Please try again later."
        )
    except Exception as e:
        logger.error(f"Unexpected error listing sessions: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while retrieving sessions."
        )


@router.post("/sessions/new")
async def create_new_session(db: Session = Depends(get_db)):
    """
    Create a new chat session explicitly.
    Use this when user clicks 'New Chat' button in the frontend.

    Returns:
        New session ID that should be used for subsequent messages
    """
    new_session_id = str(uuid.uuid4())
    from src.db.repository import create_session

    session = create_session(db, new_session_id)

    return {
        "session_id": session.id,
        "created_at": session.created_at,
        "message": "New session created successfully. Use this session_id for your chat messages.",
    }


@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific session including all messages.

    Args:
        session_id: Session identifier

    Returns:
        Session details with full message history
    """
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

    try:
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
                {"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages
            ],
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except SQLAlchemyTimeoutError as e:
        logger.error(f"Database timeout while fetching session {session_id}: {e}")
        raise HTTPException(
            status_code=503, detail="The database is currently busy. Please try again in a moment."
        )
    except OperationalError as e:
        logger.error(f"Database operational error for session {session_id}: {e}")
        raise HTTPException(
            status_code=503, detail="Unable to connect to the database. Please try again later."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching session {session_id}: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while retrieving the session."
        )


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a chat session and all its messages.
    Call this when the user closes a session in the frontend.
    Also cleans up agent memory for this session.

    Args:
        session_id: Session identifier to delete

    Returns:
        Confirmation message
    """
    try:
        # Delete from database
        deleted = delete_session(db, session_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")

        # Clean up agent session context
        agent = get_agent()
        if hasattr(agent, "session_manager"):
            agent.session_manager.clear_session(session_id)
            logger.info(f"Cleaned up agent session context for {session_id[:8]}...")

        return {
            "status": "success",
            "message": f"Session {session_id} and all its messages have been deleted",
            "session_id": session_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}") from e


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)
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
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

    from src.db.repository import get_session_history

    try:
        messages = get_session_history(db, session_id, limit=limit, offset=offset)

        return {
            "session_id": session_id,
            "count": len(messages),
            "offset": offset,
            "messages": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages
            ],
        }
    except SQLAlchemyTimeoutError as e:
        logger.error(f"Database timeout while fetching messages for session {session_id}: {e}")
        raise HTTPException(
            status_code=503, detail="The database is currently busy. Please try again in a moment."
        )
    except OperationalError as e:
        logger.error(f"Database operational error for session {session_id}: {e}")
        raise HTTPException(
            status_code=503, detail="Unable to connect to the database. Please try again later."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching messages for session {session_id}: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while retrieving messages."
        )


@router.post("/agent/chat", response_model=ChatResponse)
# @limiter.limit("30/minute", key_func=get_remote_address)  # Stricter limit for AI chat - disabled due to compat issues
async def chat(
    request: Request,
    message: str = Form(..., description="User message text"),
    session_id: str | None = Form(
        None, description="Optional session ID for conversation continuity"
    ),
    file: UploadFile | None = File(None, description="Optional file upload (PDF, CSV, Excel)"),
    latitude: float | None = Form(
        None, description="Optional GPS latitude for location-based queries"
    ),
    longitude: float | None = Form(
        None, description="Optional GPS longitude for location-based queries"
    ),
    role: str | None = Form(
        None, description="Optional agent role/style: general, executive, technical, simple, policy"
    ),
    db: Session = Depends(get_db),
):
    """
    Chat with the Air Quality AI Agent with optional document upload and GPS location.
    
    **Session Management:**
    - All conversations are automatically saved to the database
    - First request: Omit `session_id` - server creates and returns a new session ID
    - Subsequent requests: ALWAYS include the returned `session_id` to maintain conversation context
    - Session closure: Call `DELETE /sessions/{session_id}` when user closes chat or starts new conversation
    
    **Document Upload (Optional):**
    - Upload PDF, CSV, or Excel files along with your message
    - Supported formats: .pdf, .csv, .xlsx, .xls
    - Max file size: 8MB
    
    **Timeout Protection:**
    - Requests are limited to 120 seconds to prevent indefinite waiting
    - If visualization takes too long, data is automatically sampled
    - Files processed in memory (not saved to disk)
    - Agent analyzes document and responds to your query
    
    **GPS Location (Optional):**
    - Provide latitude and longitude for precise location-based air quality queries
    - If provided, takes precedence over IP-based geolocation
    - Enables accurate local air quality data instead of approximate IP-based location
    - Frontend should request browser geolocation permission when user asks about "my location"
    
    **Agent Role/Style (Optional):**
    - Specify the agent's communication style and expertise level
    - Available roles: general, executive, technical, simple, policy
    - general: Professional and complete with clear explanations (default)
    - executive: Data-driven with key insights and bullet points
    - technical: Includes measurements, standards, and methodologies with citations
    - simple: Plain language without jargon, explains concepts clearly
    - policy: Formal, evidence-based with citations and recommendations
    
    **Request Format:**
    - Content-Type: multipart/form-data
    - Fields:
      - message (required): Your question or instruction
      - session_id (optional): Session ID from previous chat
      - file (optional): Document file to analyze
      - latitude (optional): GPS latitude (-90 to 90)
      - longitude (optional): GPS longitude (-180 to 180)
      - role (optional): Agent role/style (general, executive, technical, simple, policy)
    
    **IMPORTANT - Session Persistence:**
    - The agent references previous messages in the session for context-aware responses
    - Always use the same session_id across related messages
    - If session_id changes, the agent loses conversation context
    
    **Cost Optimization:**
    - Recent conversation history (last 20 messages) is used for context
    - Responses are cached to avoid redundant API calls
    - Token usage is tracked and returned in the response
    
    **Example Flow:**
    ```bash
    # First message - no session_id
    curl -X POST http://localhost:8000/api/v1/agent/chat \\
      -F "message=What's the air quality in Kampala?"
    
    # Response includes: {"session_id": "abc-123", ...}
    
    # Continue conversation with session_id
    curl -X POST http://localhost:8000/api/v1/agent/chat \\
      -F "message=What about yesterday?" \\
      -F "session_id=abc-123"
    
    # Upload document with query
    curl -X POST http://localhost:8000/api/v1/agent/chat \\
      -F "message=Analyze this air quality data and summarize the trends" \\
      -F "session_id=abc-123" \\
      -F "file=@/path/to/data.csv"
    
    # Close session when done
    curl -X DELETE http://localhost:8000/api/v1/sessions/abc-123
    ```
    """
    # Initialize variables at the start to prevent UnboundLocalError
    document_data: list[dict[str, Any]] | None = None
    document_filename: str | None = None
    file_content: BytesIO | None = None
    document_filenames: list[str] = []
    MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB limit

    try:
        # Validate and sanitize input data
        try:
            request_data = {"message": message, "session_id": session_id, "file": file}
            sanitized_data = validate_request_data(request_data)
            message = sanitized_data["message"]
            session_id = sanitized_data["session_id"]
        except ValueError as e:
            logger.warning(f"Input validation failed: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

        # Generate or use provided session ID
        session_id = session_id if session_id and session_id.strip() else str(uuid.uuid4())

        # Handle document upload if provided (in-memory processing)
        if file and file.filename:
            document_filename = file.filename

            # Validate file type
            allowed_extensions = {".pdf", ".csv", ".xlsx", ".xls"}
            file_ext = os.path.splitext(file.filename)[1].lower()

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: PDF, CSV, Excel (.xlsx, .xls)",
                )

            try:
                # Read file content in memory with size validation
                file_content = BytesIO()
                chunk_size = 1024 * 1024  # 1MB chunks
                total_size = 0

                # Stream file in chunks to avoid memory spike
                while chunk := await file.read(chunk_size):
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        # Clean up memory before raising error
                        file_content.close()
                        del file_content
                        raise HTTPException(
                            status_code=413,
                            detail="File size exceeds 8MB limit. Please upload a smaller file.",
                        )
                    file_content.write(chunk)

                # Reset position for reading
                file_content.seek(0)

                # Process document in memory
                from src.tools.document_scanner import DocumentScanner

                scanner = DocumentScanner()
                scan_result = scanner.scan_document_from_bytes(file_content, file.filename)

                # Clean up file buffer immediately after processing
                file_content.close()
                del file_content

                if not scan_result.get("success"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to process document: {scan_result.get('error', 'Unknown error')}",
                    )

                # Wrap in list for agent processing (expects list of documents)
                document_data = [scan_result]
                logger.info(
                    f"Document scanned successfully: {file.filename}, type: {scan_result.get('file_type')}, size: {scan_result.get('full_length', 0)} chars"
                )

                # CRITICAL FIX: Prepend document context to user message so AI KNOWS a document was uploaded
                # This ensures the AI doesn't ask "where's the document" when it's already provided
                if not message.strip().lower().startswith(
                    "analyze"
                ) and not message.strip().lower().startswith("scan"):
                    message = f"[DOCUMENT UPLOADED: {file.filename}] {message}"
                    logger.info(f"Prepended document context to user message: {message[:100]}...")

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                logger.error(f"Document processing failed: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500, detail=f"Failed to process document: {str(e)}"
                ) from e

        # Get conversation history BEFORE adding new message
        # Fetch more messages to ensure long conversations maintain context
        try:
            history_objs = get_recent_session_history(db, session_id, max_messages=100)
            # Convert ORM objects to dicts
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in history_objs
            ]
            if len(history) > 0:
                logger.info(
                    f"Retrieved {len(history)} messages from session history for context"
                )
        except Exception as db_error:
            logger.warning(
                f"Failed to fetch session history for {session_id}, starting with empty history: {db_error}"
            )
            history = []

        # Check session message limit - CRITICAL: Stop processing if limit exceeded
        # This must be OUTSIDE the try-except to prevent catching HTTPException
        # Can be disabled for testing via DISABLE_SESSION_LIMIT=True in config
        message_count = get_session_message_count(db, session_id)
        session_warning = None

        # Only enforce session limits if not disabled (useful for comprehensive tests)
        if not settings.DISABLE_SESSION_LIMIT:
            if message_count >= settings.MAX_MESSAGES_PER_SESSION:
                # STOP PROCESSING - Session limit reached
                logger.error(f"Session {session_id} has exceeded limit: {message_count} messages")
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "session_limit_exceeded",
                        "message": (
                            f"Session limit reached ({message_count}/{settings.MAX_MESSAGES_PER_SESSION} messages). "
                            f"Please start a new session to continue. Long sessions affect performance and cost. "
                            f"Use DELETE /sessions/{session_id} to close this session, then start a fresh conversation."
                        ),
                        "session_id": session_id,
                        "message_count": message_count,
                        "max_messages": settings.MAX_MESSAGES_PER_SESSION,
                        "action_required": "start_new_session"
                    }
                )
            elif message_count >= settings.SESSION_LIMIT_WARNING_THRESHOLD:
                session_warning = (
                    f"ℹ️ **Approaching Session Limit** ({message_count}/{settings.MAX_MESSAGES_PER_SESSION} messages) - "
                    "Consider starting a new session soon for better performance."
                )
                logger.info(f"Session {session_id} approaching limit: {message_count} messages")
        else:
            # Session limits disabled - log for debugging
            if message_count >= settings.MAX_MESSAGES_PER_SESSION:
                logger.warning(
                    f"Session {session_id} has {message_count} messages (exceeds limit of {settings.MAX_MESSAGES_PER_SESSION}), "
                    "but DISABLE_SESSION_LIMIT=True"
                )

        # Convert to format expected by agent
        history: list[dict[str, str]] = [
            {"role": str(m.role), "content": str(m.content)} for m in history_objs
        ]

        # Add GPS context to history if available
        if latitude is not None and longitude is not None:
            gps_context = f"SYSTEM: GPS coordinates are available ({latitude:.4f}, {longitude:.4f}). The user has already consented to location sharing by providing GPS data. Use get_location_from_ip tool immediately for air quality data."
            history.insert(0, {"role": "system", "content": gps_context})
            logger.info(f"Added GPS context to conversation history: {gps_context}")

        # Save user message to database AFTER getting history
        try:
            add_message(db, session_id, "user", message)
        except Exception as db_error:
            logger.error(f"Failed to save user message to database: {db_error}")
            # Continue processing even if db save fails

        # Modify message if GPS is available and user is asking about location
        original_message = message
        if latitude is not None and longitude is not None:
            # Check if message is about current location
            location_keywords = [
                "my location",
                "current location",
                "here",
                "this location",
                "where i am",
                "my area",
                "local",
            ]
            if any(keyword in message.lower() for keyword in location_keywords):
                message = f"Get air quality data for GPS coordinates {latitude:.4f}, {longitude:.4f} (user has already consented by providing GPS data)"
                logger.info(
                    f"Modified location query with GPS coordinates: '{original_message}' -> '{message}'"
                )

        # Prepare location data - prefer GPS over IP
        location_data = None
        client_ip = request.client.host if request.client else None
        if latitude is not None and longitude is not None:
            # Validate GPS coordinates
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                location_data = {"source": "gps", "latitude": latitude, "longitude": longitude}
                logger.info(f"Using GPS coordinates: {latitude}, {longitude}")
            else:
                logger.warning(f"Invalid GPS coordinates provided: {latitude}, {longitude}")
        elif client_ip:
            location_data = {"source": "ip", "ip_address": client_ip}
            logger.info(f"Using IP address for location: {client_ip}")

        # Initialize Agent Service
        agent = get_agent()

        # Process message with timing for cost tracking and timeout protection
        start_time = time.time()

        # Add timeout protection for agent processing (110 seconds, slightly less than client timeout)
        try:
            import asyncio
            result = await asyncio.wait_for(
                agent.process_message(
                    message,
                    history,
                    document_data=document_data,
                    style=role or settings.AI_RESPONSE_STYLE,
                    temperature=settings.AI_RESPONSE_TEMPERATURE,
                    top_p=settings.AI_RESPONSE_TOP_P,
                    client_ip=client_ip,
                    location_data=location_data,
                    session_id=session_id,
                ),
                timeout=110.0  # 110 second timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Agent processing timed out after 110 seconds for message: {message[:100]}")
            raise HTTPException(
                status_code=504,
                detail="Request processing timed out. Please try a simpler query or smaller document."
            )

        processing_time = time.time() - start_time

        final_response = sanitize_response(result["response"])
        # Apply response filtering to hide implementation details
        final_response = ResponseFilter.clean_response(final_response)
        # Apply professional markdown formatting
        final_response = MarkdownFormatter.format_response(final_response)
        tools_used = result.get("tools_used", [])

        # Add document processing tool to tools_used if document was processed
        if document_data:
            if "document_scanner" not in tools_used:
                tools_used.append("document_scanner")

        # Save assistant response to database
        try:
            add_message(db, session_id, "assistant", final_response)
        except Exception as db_error:
            logger.error(f"Failed to save assistant response to database: {db_error}")
            # Continue to return response to user even if db save fails

        # Accurate token counting using tiktoken (world-standard precision)
        token_counter = get_token_counter(settings.AI_PROVIDER)

        # Count tokens accurately for each component
        message_tokens = token_counter.count_tokens(message)
        response_tokens = token_counter.count_tokens(final_response)
        history_tokens = token_counter.count_messages_tokens(history)

        # Extract document filenames and count tokens
        document_filenames = []
        document_tokens = 0
        if document_data:
            for doc in document_data:
                if isinstance(doc, dict):
                    document_tokens += token_counter.count_document_tokens(doc)
                    # Track filenames
                    filename = doc.get("filename")
                    if filename:
                        document_filenames.append(filename)

        # Total with accurate counting (no estimation multiplier needed)
        tokens_used = message_tokens + response_tokens + history_tokens + document_tokens

        logger.info(
            f"Accurate token count - Message: {message_tokens}, Response: {response_tokens}, "
            f"History: {history_tokens}, Documents: {document_tokens}, Total: {tokens_used}"
        )

        # Get total message count for this session
        try:
            all_messages = get_recent_session_history(db, session_id, max_messages=1000)
            message_count = len(all_messages)
        except Exception as db_error:
            logger.warning(f"Failed to get message count: {db_error}")
            message_count = len(history) + 2  # Estimate based on history + new messages

        # Clean up document data from memory
        if document_data:
            del document_data

        # Extract chart data if present in result
        # Chart data is now embedded in markdown response, no separate fields needed

        # Prepend session warning to response if needed
        if session_warning:
            final_response = f"{session_warning}\n\n{final_response}"

        # Handle reasoning_content - convert dict to JSON string if needed
        reasoning_content = result.get("reasoning_content")
        if isinstance(reasoning_content, dict):
            reasoning_content = json.dumps(reasoning_content)

        return ChatResponse(
            response=final_response,
            session_id=session_id,
            tools_used=tools_used,
            tokens_used=tokens_used,
            cached=result.get("cached", False),
            message_count=message_count,
            document_processed=bool(document_filenames or document_filename),
            document_filename=document_filenames[0] if document_filenames else document_filename,
            reasoning_content=reasoning_content,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log error with context for monitoring
        from src.utils.error_logger import get_error_logger

        error_logger = get_error_logger()
        error_data = error_logger.log_error(
            e,
            context={
                "endpoint": "/agent/chat",
                "session_id": session_id,
                "message_length": len(message) if message else 0,
                "has_document": document_filename is not None,
                "error_category": "chat_processing",
            },
            user_message="Unable to process your message. Please try again.",
        )

        # Clean up any lingering resources
        if "agent" in locals():
            try:
                agent._manage_memory()  # Force memory cleanup after error
            except Exception as cleanup_error:
                logger.warning(f"Memory cleanup failed after error: {cleanup_error}")

        raise HTTPException(status_code=500, detail=error_data["message"]) from e
    finally:
        # Always attempt cleanup of document data from memory
        try:
            if "document_data" in locals() and document_data is not None:
                del document_data
        except Exception:
            pass
        try:
            if "file_content" in locals() and file_content is not None:
                file_content.close()
                del file_content
        except Exception:
            pass


@router.post("/agent/chat/stream")
async def chat_stream(
    request: Request,
    message: str = Form(..., description="User message"),
    session_id: str = Form(None, description="Session ID for conversation continuity"),
    style: str = Form("general", description="Response style preset"),
    file: UploadFile = File(None, description="Optional document upload"),
    db: Session = Depends(get_db),
):
    """
    🌊 Real-time streaming endpoint with chain-of-thought transparency.
    
    This endpoint provides a COMPLETE streaming experience:
    1. Streams thought process in real-time (query analysis, tool selection, execution)
    2. Sends the FINAL AI response after processing completes
    3. Signals completion so the frontend knows when to close the connection
    
    **Use this endpoint when you want:**
    - Real-time transparency into the agent's thinking process
    - Progressive UI updates as the agent works
    - Full visibility into tool selection and execution
    
    **Use /chat endpoint when you want:**
    - Simple request/response (no streaming)
    - Minimal latency (no thought events)
    - Traditional REST API behavior
    
    **Streaming Format**: Server-Sent Events (SSE)
    
    **Event Types (in order of emission)**:
    1. `thought` events - Real-time thinking process:
       - query_analysis: Understanding the user's question
       - tool_selection: Choosing which tools/data sources to use
       - tool_execution: Executing each tool (with status)
       - data_retrieval: Data fetching progress
       - response_synthesis: Generating the final response
       - complete: Thought process finished (internal signal)
       
    2. `response` event - The FINAL AI response:
       - Contains the actual answer to the user's question
       - Includes metadata (tools used, tokens, cost, session_id)
       
    3. `done` event - Stream completion signal:
       - Indicates the stream has ended
       - Frontend should close the EventSource after receiving this
       
    4. `error` event - If something goes wrong:
       - Contains error details
       - Still followed by `done` event
    
    **Frontend Implementation (React/Next.js)**:
    ```javascript
    const [thoughts, setThoughts] = useState([]);
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    
    const streamQuery = async (message, sessionId) => {
      setLoading(true);
      setThoughts([]);
      setResponse(null);
      
      const formData = new FormData();
      formData.append('message', message);
      if (sessionId) formData.append('session_id', sessionId);
      
      const response = await fetch('/api/v1/agent/chat/stream', {
        method: 'POST',
        body: formData
      });
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\\n');
          
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              const eventType = line.substring(7);
              const dataLine = lines[lines.indexOf(line) + 1];
              
              if (dataLine?.startsWith('data: ')) {
                const data = JSON.parse(dataLine.substring(6));
                
                if (eventType === 'thought') {
                  setThoughts(prev => [...prev, data]);
                } else if (eventType === 'response') {
                  setResponse(data.data);
                } else if (eventType === 'done') {
                  setLoading(false);
                  return data.data; // Return the response
                } else if (eventType === 'error') {
                  console.error('Stream error:', data);
                  setLoading(false);
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    };
    ```
    
    **Event Data Structures**:
    
    Thought event:
    ```json
    {
      "type": "query_analysis",
      "title": "Understanding your question",
      "details": {
        "query_preview": "What's the air quality in...",
        "detected_intent": "air_quality_data",
        "complexity": "simple",
        "requires_external_data": true
      },
      "timestamp": "2026-01-10T10:30:00Z",
      "progress": 0.2
    }
    ```
    
    Response event:
    ```json
    {
      "type": "response",
      "data": {
        "response": "# Air Quality in Kampala\\n\\n...",
        "tools_used": ["get_city_air_quality"],
        "tokens_used": 1234,
        "cost_estimate": 0.0012,
        "cached": false,
        "session_id": "abc-123-..."
      }
    }
    ```
    
    Done event:
    ```json
    {}
    ```
    
    **Session Management**: Same as /chat endpoint
    - First request: Omit session_id, server creates one
    - Subsequent requests: Include session_id from response
    - Close session: DELETE /sessions/{session_id}
    """
    import json

    from src.services.agent.thought_stream import ThoughtStream
    
    async def generate_thoughts():
        """Generate SSE stream of thoughts and final response."""
        stream = None
        try:
            # Validate inputs
            if not message or not message.strip():
                error_event = {
                    "type": "error",
                    "title": "Invalid Input",
                    "details": {"error": "Message cannot be empty"},
                    "timestamp": ""
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
                yield "event: done\ndata: {}\n\n"  # Signal completion
                return
            
            # Create thought stream
            stream = ThoughtStream()
            stream.enable()
            
            # Get conversation history
            history = []
            if session_id:
                try:
                    history_objs = get_recent_session_history(db, session_id, max_messages=10)
                    # Convert ORM objects to dicts
                    history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in history_objs
                    ]
                except Exception as e:
                    logger.warning(f"Failed to load history: {e}")
            
            # Handle document upload (if provided)
            document_data = None
            if file and file.filename:
                from io import BytesIO

                from src.tools.document_scanner import DocumentScanner
                
                try:
                    file_content = BytesIO()
                    while chunk := await file.read(1024 * 1024):
                        file_content.write(chunk)
                    file_content.seek(0)
                    
                    scanner = DocumentScanner()
                    doc_result = scanner.scan_document_from_bytes(file_content, file.filename)
                    
                    if doc_result.get("success"):
                        document_data = [doc_result]
                    
                    file_content.close()
                except Exception as e:
                    logger.error(f"Document processing failed: {e}")
            
            # Process message with streaming
            agent = get_agent()
            
            # Start async task to stream thoughts
            import asyncio

            # Define async processing function that returns result
            async def process_and_respond_internal():
                """Internal function to process message and return result."""
                return await agent.process_message(
                    message=message,
                    history=history,
                    document_data=document_data,
                    style=style,
                    session_id=session_id,
                    stream=stream  # Pass stream for automatic thought emission
                )
            
            # Create background task for processing - this enables TRUE CONCURRENCY
            # Thoughts will stream in real-time WHILE the agent processes
            processing_task = asyncio.create_task(process_and_respond_internal())
            
            # Stream thoughts as they arrive (non-blocking, concurrent with processing)
            thought_count = 0
            stream_completed = False
            
            try:
                async for thought_event in stream.stream():
                    thought_count += 1
                    event_json = json.dumps(thought_event)
                    yield f"event: thought\ndata: {event_json}\n\n"
                    
                    # Break on complete event
                    if thought_event.get('type') == 'complete':
                        logger.info(f"Stream received completion signal after {thought_count} thoughts")
                        stream_completed = True
                        break
                
                # Wait for processing to complete and emit final response
                result = await processing_task
                
                if result is None:
                    raise Exception("Processing returned no result")
                
                # Emit final response event
                response_data = {
                    "response": result.get("response", ""),
                    "tools_used": result.get("tools_used", []),
                    "tokens_used": result.get("tokens_used", 0),
                    "cost_estimate": result.get("cost_estimate", 0.0),
                    "cached": result.get("cached", False),
                    "session_id": session_id
                }
                
                response_json = json.dumps({"data": response_data})
                yield f"event: response\ndata: {response_json}\n\n"
                
                # Save to database
                if session_id:
                    try:
                        add_message(db, session_id=session_id, role="user", content=message)
                        add_message(db, session_id=session_id, role="assistant", content=result.get("response", ""))
                    except Exception as e:
                        logger.warning(f"Failed to save messages: {e}")
                
            except asyncio.CancelledError:
                logger.info("Stream was cancelled by client")
                if not processing_task.done():
                    processing_task.cancel()
                raise
            except Exception as stream_error:
                logger.error(f"Stream processing error: {stream_error}", exc_info=True)
                # Try to get result if processing completed successfully
                if processing_task.done() and not processing_task.exception():
                    try:
                        result = processing_task.result()
                        response_data = {
                            "response": result.get("response", "I encountered an issue while streaming my thoughts, but I was able to process your request."),
                            "tools_used": result.get("tools_used", []),
                            "tokens_used": result.get("tokens_used", 0),
                            "cost_estimate": result.get("cost_estimate", 0.0),
                            "cached": result.get("cached", False),
                            "session_id": session_id
                        }
                        response_json = json.dumps({"data": response_data})
                        yield f"event: response\ndata: {response_json}\n\n"
                    except Exception as e:
                        logger.error(f"Failed to extract result after stream error: {e}")
                        error_response = {
                            "response": "I apologize, but I encountered an error processing your request. Please try again.",
                            "tools_used": [],
                            "tokens_used": 0,
                            "cost_estimate": 0.0,
                            "cached": False,
                            "session_id": session_id
                        }
                        response_json = json.dumps({"data": error_response})
                        yield f"event: response\ndata: {response_json}\n\n"
                else:
                    # Processing also failed
                    error_response = {
                        "response": "I apologize, but I encountered an error processing your request. Please try again.",
                        "tools_used": [],
                        "tokens_used": 0,
                        "cost_estimate": 0.0,
                        "cached": False,
                        "session_id": session_id
                    }
                    response_json = json.dumps({"data": error_response})
                    yield f"event: response\ndata: {response_json}\n\n"
            
            # CRITICAL: Always send final 'done' event to signal stream completion
            yield "event: done\ndata: {}\n\n"
            logger.info(f"Stream completed with {thought_count} thoughts (stream_completed: {stream_completed})")
                
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "title": "Processing Error",
                "details": {"error": str(e)},
                "timestamp": ""
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
            
            # Provide a basic error response
            error_response = {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "tools_used": [],
                "tokens_used": 0,
                "cost_estimate": 0.0,
                "cached": False,
                "session_id": session_id
            }
            response_json = json.dumps({"data": error_response})
            yield f"event: response\ndata: {response_json}\n\n"
            
            # Always send done event even on error
            yield "event: done\ndata: {}\n\n"
        
        finally:
            # Clean up stream if it hasn't been completed by the agent
            if stream and not stream._closed:
                try:
                    await stream.complete({"status": "cleanup"})
                except Exception as cleanup_error:
                    logger.warning(f"Stream cleanup error: {cleanup_error}")
    
    return StreamingResponse(
        generate_thoughts(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/air-quality/query")
# @limiter.limit("50/minute", key_func=get_remote_address)  # Moderate limit for data queries - disabled due to compat issues
async def query_air_quality(request: AirQualityQueryRequest, document: UploadFile = File(None)):
    """
    Unified air quality data query endpoint with intelligent multi-source fallback and document analysis.

    **Data Source Strategy:**
    - Queries WAQI and AirQo by city name
    - Queries Open-Meteo if coordinates provided
    - Returns all successful responses
    - Supports forecast data (Open-Meteo only)
    - Gracefully handles failures

    **Document Analysis:**
    - Upload PDF, CSV, or Excel files for in-memory analysis
    - AI agent analyzes document content with air quality data
    - Supported formats: .pdf, .csv, .xlsx, .xls
    - Max file size: 8MB
    - Files processed in memory (not saved to disk)
    - Efficient streaming approach for cost optimization

    **Request Parameters:**
    - city: City name (for WAQI and AirQo)
    - latitude/longitude: Coordinates (for Open-Meteo)
    - include_forecast: Set to true to include forecast data
    - forecast_days: Number of forecast days (1-7, default: 5)
    - timezone: Timezone for Open-Meteo (default: auto)
    - document: Optional file upload (multipart/form-data, max 8MB)

    **Example Response:**
    {
        "waqi": { ... },
        "airqo": { ... },
        "openmeteo": {
            "current": { ... },
            "forecast": { ... }
        },
        "document": {
            "filename": "data.csv",
            "content": "...",
            "metadata": { ... }
        }
    }
    """
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB limit

    try:
        # Handle document upload if provided (in-memory processing)
        if document and document.filename:
            # Validate file type
            allowed_extensions = {".pdf", ".csv", ".xlsx", ".xls"}
            file_ext = os.path.splitext(document.filename)[1].lower()

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_ext}. Allowed: PDF, CSV, Excel (.xlsx, .xls)",
                )

            try:
                # Read file content in memory with size validation
                file_content = BytesIO()
                chunk_size = 1024 * 1024  # 1MB chunks
                total_size = 0

                # Stream file in chunks to avoid memory spike
                while chunk := await document.read(chunk_size):
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail="File size exceeds 8MB limit. Please upload a smaller file.",
                        )
                    file_content.write(chunk)

                # Reset position for reading
                file_content.seek(0)

                # Process document in memory
                from src.tools.document_scanner import DocumentScanner

                scanner = DocumentScanner()
                document_data = scanner.scan_document_from_bytes(file_content, document.filename)

                if document_data.get("success"):
                    results["document"] = {
                        "filename": document.filename,
                        "file_type": document_data.get("file_type"),
                        "content": document_data.get("content"),
                        "metadata": document_data.get("metadata"),
                        "truncated": document_data.get("truncated", False),
                    }
                else:
                    errors["document"] = document_data.get("error", "Failed to process document")

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                logger.error(f"Document processing failed: {str(e)}")
                errors["document"] = f"Failed to process document: {str(e)}"
            finally:
                # Explicitly release memory
                if "file_content" in locals():
                    file_content.close()
                    del file_content

        # Try WAQI API for city-based queries
        if "waqi" in settings.ENABLED_DATA_SOURCES and request.city:
            try:
                waqi = WAQIService()
                waqi_data = waqi.get_city_feed(request.city)
                if waqi_data and waqi_data.get("status") == "ok":
                    results["waqi"] = sanitize_response(waqi_data)
            except Exception as e:
                logger.warning(f"WAQI API failed for {request.city}: {str(e)}")
                errors["waqi"] = str(e)

        # Try AirQo API for African city queries
        if "airqo" in settings.ENABLED_DATA_SOURCES and request.city:
            try:
                airqo = AirQoService()
                airqo_data = airqo.get_recent_measurements(city=request.city)
                if airqo_data and airqo_data.get("success"):
                    results["airqo"] = sanitize_response(airqo_data)
            except Exception as e:
                logger.warning(f"AirQo API failed for {request.city}: {str(e)}")
                errors["airqo"] = str(e)

        # Try Open-Meteo API if coordinates are provided
        if (
            "openmeteo" in settings.ENABLED_DATA_SOURCES
            and request.latitude is not None
            and request.longitude is not None
        ):
            try:
                openmeteo = OpenMeteoService()
                openmeteo_result = {}

                # Get current air quality (always)
                current_data = openmeteo.get_current_air_quality(
                    latitude=request.latitude,
                    longitude=request.longitude,
                    timezone=request.timezone,
                )
                if current_data:
                    openmeteo_result["current"] = current_data

                # Get forecast if requested
                if request.include_forecast:
                    forecast_days = request.forecast_days or 5
                    forecast_data = openmeteo.get_hourly_forecast(
                        latitude=request.latitude,
                        longitude=request.longitude,
                        forecast_days=forecast_days,
                        timezone=request.timezone,
                    )
                    if forecast_data:
                        openmeteo_result["forecast"] = forecast_data

                if openmeteo_result:
                    results["openmeteo"] = sanitize_response(openmeteo_result)
            except Exception as e:
                logger.warning(f"Open-Meteo API failed: {str(e)}")
                errors["openmeteo"] = str(e)

        # Return results if any source succeeded
        if results:
            return results

        # All sources failed
        location = request.city if request.city else f"({request.latitude}, {request.longitude})"
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"No air quality data found for {location}",
                "errors": errors,
                "suggestion": "Try a different location or provide coordinates for Open-Meteo",
            },
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
        tools: list[dict[str, Any]] = []
        if request.name in agent.mcp_clients:
            try:
                client = agent.mcp_clients[request.name]
                # Note: This requires the client to be connected
                # We'll return basic info for now
                tools = []
            except Exception:
                pass

        return MCPConnectionResponse(status="connected", name=request.name, available_tools=tools)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect MCP server: {str(e)}")


@router.get("/mcp/list", response_model=MCPListResponse)
async def list_mcp_connections():
    """List all connected MCP servers"""
    try:
        agent = get_agent()
        connections = [{"name": name, "status": "connected"} for name in agent.mcp_clients.keys()]
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


# ============================================================================
# VISUALIZATION ENDPOINTS
# ============================================================================


@router.get("/visualization/capabilities")
async def get_visualization_capabilities():
    """Get visualization capabilities and supported formats"""
    return {
        "supported_formats": ["csv", "xlsx", "xls", "pdf"],
        "supported_chart_types": [
            "line",
            "bar",
            "scatter",
            "histogram",
            "box",
            "heatmap",
            "pie",
            "area",
            "violin",
        ],
        "description": "Create dynamic visualizations from CSV, Excel, PDF files or search results",
    }
