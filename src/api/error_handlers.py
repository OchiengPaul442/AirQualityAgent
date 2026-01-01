"""
Global Error Handlers for FastAPI Application

Provides centralized error handling with user-friendly messages:
- Database connection errors
- External service timeouts
- Network failures
- Rate limiting
- General exceptions
- All errors logged to file for monitoring
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from src.utils.error_logger import get_error_logger

logger = logging.getLogger(__name__)
error_logger = get_error_logger()


async def database_timeout_handler(request: Request, exc: SQLAlchemyTimeoutError) -> JSONResponse:
    """Handle database connection timeout errors"""
    error_data = error_logger.log_database_error(
        exc, operation="database_query", endpoint=str(request.url.path), method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            **error_data,
            "detail": "Our system is experiencing high traffic. Please wait a few seconds and retry your request.",
            "retry_after": 5,
        },
    )


async def database_operational_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    """Handle database operational errors"""
    error_data = error_logger.log_database_error(
        exc, operation="database_connection", endpoint=str(request.url.path), method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            **error_data,
            "detail": "Our database is temporarily unavailable. We're working to restore service.",
            "retry_after": 10,
        },
    )


async def database_integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database integrity errors (unique constraints, foreign keys, etc.)"""
    error_data = error_logger.log_database_error(
        exc, operation="data_validation", endpoint=str(request.url.path), method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={**error_data, "detail": "Please check your input and try again."},
    )


async def general_database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle general database errors"""
    error_data = error_logger.log_database_error(
        exc, operation="database_operation", endpoint=str(request.url.path), method=request.method
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            **error_data,
            "detail": "Please try again. If the problem persists, contact support.",
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other uncaught exceptions"""
    error_data = error_logger.log_error(
        exc,
        context={
            "endpoint": str(request.url.path),
            "method": request.method,
            "error_category": "unhandled",
        },
        user_message="An unexpected error occurred. Our team has been notified.",
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            **error_data,
            "detail": "We've logged this issue and will investigate. Please try again later.",
        },
    )


def register_error_handlers(app):
    """
    Register all error handlers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(SQLAlchemyTimeoutError, database_timeout_handler)
    app.add_exception_handler(OperationalError, database_operational_error_handler)
    app.add_exception_handler(IntegrityError, database_integrity_error_handler)
    app.add_exception_handler(DatabaseError, general_database_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("✓ Global error handlers registered")
