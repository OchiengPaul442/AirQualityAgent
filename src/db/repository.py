from sqlalchemy.orm import Session

from src.db.models import ChatMessage, ChatSession


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_all_sessions(db: Session, limit: int = 50) -> list[ChatSession]:
    """Get all chat sessions ordered by creation time"""
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).limit(limit).all()


def create_session(db: Session, session_id: str) -> ChatSession:
    db_session = ChatSession(id=session_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def add_message(db: Session, session_id: str, role: str, content: str):
    # Ensure session exists
    if not get_session(db, session_id):
        create_session(db, session_id)

    db_message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def get_session_history(db: Session, session_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
        .all()
    )
