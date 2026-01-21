"""
Error Handling Module - Three-Tier Error Sanitization

Implements comprehensive error handling to:
- Prevent stack trace leaks to users
- Provide helpful user-facing messages
- Log detailed errors for debugging
- Handle graceful degradation
- Support fallback mechanisms

Based on production API best practices and security guidelines.
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification and handling."""
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    NETWORK_ERROR = "network_error"
    DATA_PROCESSING = "data_processing"
    INTERNAL_ERROR = "internal_error"
    EXTERNAL_SERVICE = "external_service"


class ErrorResponse:
    """
    Structured error response with three levels:
    1. User-facing: Safe, helpful message
    2. Internal logging: Full diagnostic information
    3. Monitoring: Structured data for alerting
    """
    
    def __init__(
        self,
        user_message: str,
        error_category: ErrorCategory,
        severity: ErrorSeverity,
        error_code: Optional[str] = None,
        internal_message: Optional[str] = None,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize error response.
        
        Args:
            user_message: Safe message to show to users
            error_category: Category of the error
            severity: Severity level
            error_code: Optional error code for reference
            internal_message: Detailed message for logging
            exception: Original exception if available
            context: Additional context for debugging
        """
        # Initialize timestamp FIRST (needed for error_code generation)
        self.timestamp = datetime.now(timezone.utc)
        
        self.user_message = user_message
        self.error_category = error_category
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.internal_message = internal_message or user_message
        self.exception = exception
        self.context = context or {}
        self.stack_trace = self._get_stack_trace() if exception else None
    
    def _generate_error_code(self) -> str:
        """Generate a unique error code for tracking."""
        import hashlib
        unique_id = hashlib.md5(
            f"{self.timestamp.isoformat()}{self.error_category.value}".encode()
        ).hexdigest()[:8]
        return f"{self.error_category.value.upper()}_{unique_id}"
    
    def _get_stack_trace(self) -> Optional[str]:
        """Extract stack trace from exception."""
        if not self.exception:
            return None
        return ''.join(traceback.format_exception(
            type(self.exception),
            self.exception,
            self.exception.__traceback__
        ))
    
    def to_user_dict(self) -> Dict[str, Any]:
        """
        Get user-facing error dictionary (SAFE for external consumption).
        
        Returns:
            Dictionary with safe error information
        """
        return {
            "error": True,
            "message": self.user_message,
            "error_code": self.error_code,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_internal_dict(self) -> Dict[str, Any]:
        """
        Get internal error dictionary (for logging and debugging).
        
        Returns:
            Dictionary with full diagnostic information
        """
        return {
            "error_code": self.error_code,
            "user_message": self.user_message,
            "internal_message": self.internal_message,
            "category": self.error_category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "exception_type": type(self.exception).__name__ if self.exception else None,
            "exception_message": str(self.exception) if self.exception else None,
            "stack_trace": self.stack_trace,
            "context": self.context
        }
    
    def log(self, session_id: Optional[str] = None):
        """
        Log error with appropriate level based on severity.
        
        Args:
            session_id: Optional session ID for correlation
        """
        log_extra = self.to_internal_dict()
        if session_id:
            log_extra["session_id"] = session_id
        
        log_message = f"[{self.error_code}] {self.internal_message}"
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra=log_extra)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(log_message, extra=log_extra)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message, extra=log_extra)
        else:
            logger.info(log_message, extra=log_extra)


class ErrorHandler:
    """
    Centralized error handler with predefined responses for common scenarios.
    """
    
    @staticmethod
    def handle_api_error(
        service_name: str,
        exception: Exception,
        fallback_available: bool = False,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle external API errors with fallback suggestions.
        
        Args:
            service_name: Name of the failing service (e.g., "WAQI", "AirQo")
            exception: The exception that occurred
            fallback_available: Whether fallback options are available
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        # User-facing message
        if fallback_available:
            user_message = (
                f"The {service_name} service is temporarily unavailable. "
                f"I'm trying alternative data sources to get you the information you need."
            )
        else:
            user_message = (
                f"I'm unable to retrieve data from {service_name} right now. "
                f"Please try again in a few moments, or I can provide general information "
                f"about air quality in your area."
            )
        
        # Internal message
        internal_message = f"{service_name} API failed: {str(exception)}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.MEDIUM if fallback_available else ErrorSeverity.HIGH,
            internal_message=internal_message,
            exception=exception,
            context={"service": service_name, "fallback_available": fallback_available}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_rate_limit(
        service_name: str,
        retry_after: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle rate limiting errors.
        
        Args:
            service_name: Name of the service being rate limited
            retry_after: Seconds until retry is allowed
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        if retry_after:
            user_message = (
                f"I'm receiving too many requests right now. "
                f"Please try again in {retry_after} seconds."
            )
        else:
            user_message = (
                f"I'm experiencing high demand right now. "
                f"Please try again in a moment."
            )
        
        internal_message = f"Rate limit exceeded for {service_name}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            internal_message=internal_message,
            context={"service": service_name, "retry_after": retry_after}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_validation_error(
        field: str,
        reason: str,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle input validation errors.
        
        Args:
            field: Field that failed validation
            reason: Reason for validation failure
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        user_message = (
            f"I need a valid {field} to help you. {reason}"
        )
        
        internal_message = f"Validation error for {field}: {reason}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.LOW,
            internal_message=internal_message,
            context={"field": field, "reason": reason}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_database_error(
        operation: str,
        exception: Exception,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle database errors.
        
        Args:
            operation: Database operation that failed
            exception: The exception that occurred
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        user_message = (
            "I'm experiencing a temporary issue accessing your conversation history. "
            "Your request has been noted, but I may not have full context from our previous conversation."
        )
        
        internal_message = f"Database {operation} failed: {str(exception)}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.DATABASE_ERROR,
            severity=ErrorSeverity.HIGH,
            internal_message=internal_message,
            exception=exception,
            context={"operation": operation}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_network_error(
        target: str,
        exception: Exception,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle network connectivity errors.
        
        Args:
            target: Target service/URL that failed
            exception: The exception that occurred
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        user_message = (
            "I'm having trouble connecting to the data source right now. "
            "This could be a temporary network issue. Please try again shortly."
        )
        
        internal_message = f"Network error connecting to {target}: {str(exception)}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.NETWORK_ERROR,
            severity=ErrorSeverity.HIGH,
            internal_message=internal_message,
            exception=exception,
            context={"target": target}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_data_processing_error(
        data_type: str,
        exception: Exception,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle data processing/parsing errors.
        
        Args:
            data_type: Type of data being processed
            exception: The exception that occurred
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        user_message = (
            f"I received data that I couldn't process correctly. "
            f"Let me try a different approach to get you the information you need."
        )
        
        internal_message = f"Failed to process {data_type}: {str(exception)}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.DATA_PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            internal_message=internal_message,
            exception=exception,
            context={"data_type": data_type}
        )
        
        error_response.log(session_id)
        return error_response
    
    @staticmethod
    def handle_internal_error(
        component: str,
        exception: Exception,
        session_id: Optional[str] = None
    ) -> ErrorResponse:
        """
        Handle unexpected internal errors.
        
        Args:
            component: Component where error occurred
            exception: The exception that occurred
            session_id: Optional session ID
            
        Returns:
            ErrorResponse object
        """
        user_message = (
            "I encountered an unexpected issue while processing your request. "
            "I've noted this error, and our team will investigate. "
            "Please try rephrasing your question or try again shortly."
        )
        
        internal_message = f"Internal error in {component}: {str(exception)}"
        
        error_response = ErrorResponse(
            user_message=user_message,
            error_category=ErrorCategory.INTERNAL_ERROR,
            severity=ErrorSeverity.CRITICAL,
            internal_message=internal_message,
            exception=exception,
            context={"component": component}
        )
        
        error_response.log(session_id)
        return error_response


# Decorator for automatic error handling
def handle_errors(
    component: str,
    fallback_message: Optional[str] = None,
    reraise: bool = False
):
    """
    Decorator for automatic error handling in functions.
    
    Args:
        component: Name of the component for error logging
        fallback_message: Optional custom fallback message
        reraise: Whether to reraise the exception after handling
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get session_id if available in kwargs
                session_id = kwargs.get('session_id') or kwargs.get('session')
                
                # Handle the error
                error_response = ErrorHandler.handle_internal_error(
                    component=f"{component}.{func.__name__}",
                    exception=e,
                    session_id=session_id
                )
                
                # Custom fallback message if provided
                if fallback_message:
                    error_response.user_message = fallback_message
                
                # Reraise if requested
                if reraise:
                    raise
                
                # Return error response
                return error_response.to_user_dict()
        
        return wrapper
    return decorator
