"""
Database repository for chat sessions and messages.
Provides efficient, production-ready data access patterns.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.db.models import ChatMessage, ChatSession


def get_session(db: Session, session_id: str) -> ChatSession | None:
    """Get a specific session by ID"""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_all_sessions(db: Session, limit: int = 50) -> list[ChatSession]:
    """Get all chat sessions ordered by most recent first"""
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).limit(limit).all()


def create_session(db: Session, session_id: str) -> ChatSession:
    """Create a new chat session"""
    db_session = ChatSession(id=session_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def add_message(db: Session, session_id: str, role: str, content: str) -> ChatMessage:
    """
    Add a message to a session. Creates session if it doesn't exist.

    Args:
        db: Database session
        session_id: Session identifier
        role: Message role (user, assistant, system)
        content: Message content

    Returns:
        Created ChatMessage
    """
    # Ensure session exists
    if not get_session(db, session_id):
        create_session(db, session_id)

    db_message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def get_session_history(
    db: Session, session_id: str, limit: int | None = None, offset: int = 0
) -> list[ChatMessage]:
    """
    Get conversation history for a session with optional pagination.

    Args:
        db: Database session
        session_id: Session identifier
        limit: Maximum number of messages to return (None for all)
        offset: Number of messages to skip

    Returns:
        List of ChatMessage objects ordered by timestamp
    """
    query = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    )

    if offset > 0:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def get_recent_session_history(
    db: Session, session_id: str, max_messages: int = 20
) -> list[ChatMessage]:
    """
    Get the most recent N messages from a session for context.
    Optimized for AI context windows to reduce token usage.

    Args:
        db: Database session
        session_id: Session identifier
        max_messages: Maximum number of recent messages (default: 20)

    Returns:
        List of recent ChatMessage objects ordered by timestamp
    """
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(max_messages)
        .all()
    )

    # Reverse to get chronological order
    return list(reversed(messages))


def delete_session(db: Session, session_id: str) -> bool:
    """
    Delete a session and all its messages (CASCADE delete).

    Args:
        db: Database session
        session_id: Session identifier

    Returns:
        True if session was deleted, False if not found
    """
    session = get_session(db, session_id)
    if session:
        db.delete(session)
        db.commit()
        return True
    return False


def cleanup_old_sessions(db: Session, days_old: int = 30) -> int:
    """
    Clean up sessions older than specified days.
    Use this for periodic maintenance to prevent database bloat.

    Args:
        db: Database session
        days_old: Delete sessions older than this many days

    Returns:
        Number of sessions deleted
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    old_sessions = db.query(ChatSession).filter(ChatSession.created_at < cutoff_date).all()

    count = len(old_sessions)
    for session in old_sessions:
        db.delete(session)

    db.commit()
    return count
