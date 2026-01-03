"""
Error Logging System with File Storage

Comprehensive error boundary that:
- Catches all unhandled exceptions
- Logs to rotating file (for future integration with monitoring services)
- Provides structured error data
- Tracks error patterns
"""

import json
import logging
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class ErrorLogger:
    """Centralized error logging with file storage"""

    def __init__(self, log_dir: str = "./logs"):
        """
        Initialize error logger.

        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup rotating file handler (10MB max, keep 10 files)
        self.error_log_file = self.log_dir / "errors.log"
        self.json_log_file = self.log_dir / "errors.json"

        # Configure file logger
        self.logger = logging.getLogger("error_boundary")
        self.logger.setLevel(logging.ERROR)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Rotating file handler for text logs
        file_handler = RotatingFileHandler(
            self.error_log_file, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"  # 10MB
        )
        file_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n" "Traceback:\n%(exc_info)s\n"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Also add console handler for visibility
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.logger.info(f"✓ Error logger initialized: {self.error_log_file}")

    def log_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        user_message: str | None = None,
    ) -> dict[str, Any]:
        """
        Log an error with context and return structured error data.

        Args:
            error: The exception that occurred
            context: Additional context (endpoint, user_id, session_id, etc.)
            user_message: User-friendly error message

        Returns:
            Structured error data for API response
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
            "user_message": user_message or "An unexpected error occurred",
        }

        # Log to file (text format)
        self.logger.error(
            f"Error: {error_data['error_type']} - {error_data['error_message']}\n"
            f"Context: {json.dumps(error_data['context'], indent=2)}\n"
            f"Traceback:\n{error_data['traceback']}",
            exc_info=error,
        )

        # Log to JSON file for structured parsing
        self._log_json(error_data)

        return {
            "error": error_data["error_type"],
            "message": error_data["user_message"],
            "timestamp": error_data["timestamp"],
            "context": {
                k: v for k, v in error_data["context"].items() if k in ["endpoint", "session_id"]  # type: ignore
            },
        }

    def _log_json(self, error_data: dict[str, Any]):
        """Append error data to JSON log file"""
        try:
            # Append to JSON file (one JSON object per line for easy parsing)
            with open(self.json_log_file, "a", encoding="utf-8") as f:
                json.dump(error_data, f)
                f.write("\n")
        except Exception as e:
            # If JSON logging fails, just log to regular logger
            self.logger.error(f"Failed to write to JSON log: {e}")

    def log_database_error(
        self, error: Exception, operation: str, table: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Log database-specific errors"""
        context = {"operation": operation, "table": table, "error_category": "database", **kwargs}

        user_message = (
            "A database error occurred. Our team has been notified. "
            "Please try again in a moment."
        )

        return self.log_error(error, context, user_message)

    def log_network_error(
        self, error: Exception, url: str, method: str = "GET", **kwargs
    ) -> dict[str, Any]:
        """Log network/API call errors"""
        context = {"url": url, "method": method, "error_category": "network", **kwargs}

        user_message = (
            "Unable to connect to external service. " "Please check your connection and try again."
        )

        return self.log_error(error, context, user_message)

    def log_ai_error(self, error: Exception, model: str, provider: str, **kwargs) -> dict[str, Any]:
        """Log AI/LLM provider errors"""
        context = {"model": model, "provider": provider, "error_category": "ai_provider", **kwargs}

        user_message = "The AI service is temporarily unavailable. " "Please try again in a moment."

        return self.log_error(error, context, user_message)


# Global error logger instance
_error_logger: ErrorLogger | None = None


def get_error_logger() -> ErrorLogger:
    """Get or create global error logger instance"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


def log_error(
    error: Exception, context: dict[str, Any] | None = None, user_message: str | None = None
) -> dict[str, Any]:
    """
    Convenience function to log errors.

    Args:
        error: The exception that occurred
        context: Additional context
        user_message: User-friendly message

    Returns:
        Structured error data for API response
    """
    logger = get_error_logger()
    return logger.log_error(error, context, user_message)
