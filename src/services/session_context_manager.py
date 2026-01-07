"""
Session Context Manager - Enhanced conversation memory for long sessions

This module provides intelligent context management for long conversations:
- Smart summarization of old messages to prevent token overflow
- Document memory across conversations
- Session cleanup and memory leak prevention
"""

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class SessionContextManager:
    """
    Manages conversation context for long sessions with intelligent memory management.
    
    Features:
    - Maintains full conversation history in memory with automatic cleanup
    - Summarizes old messages to reduce token usage while preserving context
    - Tracks document uploads across the session
    - Prevents memory leaks through automatic cleanup
    """
    
    def __init__(self, max_contexts: int = 50, context_ttl: int = 3600):
        """
        Initialize session context manager.
        
        Args:
            max_contexts: Maximum number of session contexts to keep in memory
            context_ttl: Time-to-live for inactive sessions (seconds)
        """
        self.session_contexts: dict[str, dict[str, Any]] = {}
        self.max_contexts = max_contexts
        self.context_ttl = context_ttl
        logger.info(f"SessionContextManager initialized (max_contexts={max_contexts}, ttl={context_ttl}s)")
    
    def get_or_create_context(self, session_id: str) -> dict[str, Any]:
        """
        Get or create a session context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session context dictionary
        """
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {
                "documents": [],
                "conversation_summary": "",
                "last_access": time.time(),
                "created_at": time.time(),
                "message_count": 0
            }
            logger.info(f"Created new session context for {session_id[:8]}...")
        else:
            # Update last access time
            self.session_contexts[session_id]["last_access"] = time.time()
        
        # Cleanup if too many contexts
        self._cleanup_old_contexts()
        
        return self.session_contexts[session_id]
    
    def add_document_to_session(self, session_id: str, document: dict[str, Any]) -> None:
        """
        Add a document to the session context.
        
        Args:
            session_id: Session identifier
            document: Document metadata and content
        """
        context = self.get_or_create_context(session_id)
        
        # Avoid duplicates by filename
        filename = document.get("filename", "")
        existing_filenames = {doc.get("filename", "") for doc in context["documents"]}
        
        if filename and filename not in existing_filenames:
            context["documents"].append(document)
            logger.info(f"Added document '{filename}' to session {session_id[:8]}...")
            
            # Limit to last 3 documents to prevent memory bloat
            if len(context["documents"]) > 3:
                removed_doc = context["documents"].pop(0)
                logger.info(f"Removed oldest document '{removed_doc.get('filename')}' from session {session_id[:8]}...")
    
    def get_session_documents(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get all documents for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of documents
        """
        context = self.get_or_create_context(session_id)
        return context.get("documents", [])
    
    def update_summary(self, session_id: str, recent_messages: list[dict[str, str]]) -> None:
        """
        Update conversation summary for token-efficient context retrieval.
        
        Args:
            session_id: Session identifier
            recent_messages: Recent conversation messages
        """
        context = self.get_or_create_context(session_id)
        
        # Only summarize if we have enough messages
        if len(recent_messages) > 10:
            # Keep last 10 messages verbatim, summarize older ones
            older_messages = recent_messages[:-10]
            
            # Extract key topics from older messages
            topics = set()
            for msg in older_messages:
                content = msg.get("content", "").lower()
                # Simple keyword extraction (can be enhanced with NLP)
                if "air quality" in content or "aqi" in content:
                    topics.add("air quality monitoring")
                if "pm2.5" in content or "pm10" in content:
                    topics.add("particulate matter")
                if "ozone" in content or "o3" in content:
                    topics.add("ozone levels")
                if "document" in content or "file" in content or "csv" in content:
                    topics.add("document analysis")
                if "location" in content or "city" in content:
                    topics.add("location queries")
            
            if topics:
                context["conversation_summary"] = f"Previous conversation covered: {', '.join(topics)}"
                logger.debug(f"Updated summary for session {session_id[:8]}: {context['conversation_summary']}")
        
        context["message_count"] = len(recent_messages)
    
    def get_context_summary(self, session_id: str) -> str:
        """
        Get conversation summary for context injection.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary string
        """
        if session_id not in self.session_contexts:
            return ""
        
        context = self.session_contexts[session_id]
        summary = context.get("conversation_summary", "")
        
        if summary:
            return f"\n\n=== SESSION CONTEXT ===\n{summary}\n=== END SESSION CONTEXT ===\n"
        
        return ""
    
    def _cleanup_old_contexts(self) -> None:
        """Clean up expired session contexts to prevent memory leaks."""
        current_time = time.time()
        sessions_to_remove = []
        
        # Remove expired sessions
        for session_id, context in self.session_contexts.items():
            last_access = context.get("last_access", 0)
            if current_time - last_access > self.context_ttl:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.session_contexts[session_id]
            logger.info(f"Cleaned up expired session context: {session_id[:8]}...")
        
        # If still too many, remove oldest
        if len(self.session_contexts) > self.max_contexts:
            sorted_sessions = sorted(
                self.session_contexts.items(),
                key=lambda x: x[1].get("last_access", 0)
            )
            
            excess = len(self.session_contexts) - self.max_contexts
            for session_id, _ in sorted_sessions[:excess]:
                del self.session_contexts[session_id]
                logger.info(f"Removed excess session context: {session_id[:8]}...")
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a specific session context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was found and cleared
        """
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
            logger.info(f"Cleared session context: {session_id[:8]}...")
            return True
        return False
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about session contexts.
        
        Returns:
            Dictionary with statistics
        """
        total_documents = sum(
            len(ctx.get("documents", []))
            for ctx in self.session_contexts.values()
        )
        
        return {
            "active_sessions": len(self.session_contexts),
            "total_documents": total_documents,
            "max_contexts": self.max_contexts,
            "context_ttl": self.context_ttl
        }
