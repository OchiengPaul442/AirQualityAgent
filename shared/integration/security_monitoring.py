"""
Integration Module for Security and Monitoring Enhancements

This module provides seamless integration of:
- Input sanitization (prompt injection prevention)
- Error handling (three-tier model)
- Token management (context optimization)
- Enhanced search (multi-provider with failover)
- Health monitoring (system observability)

Use this module to wrap agent service calls with enterprise-grade reliability.
"""

import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional

from shared.monitoring.health_monitor import get_health_monitor
from shared.security.error_handler import ErrorCategory, ErrorHandler, ErrorSeverity

# Import all enhancement modules
from shared.security.input_sanitizer import InputSanitizer, get_input_sanitizer
from shared.services.enhanced_search_service import get_enhanced_search_service
from shared.utils.token_manager import TokenManager, get_token_manager

logger = logging.getLogger(__name__)


class AgentServiceIntegration:
    """
    Wrapper that integrates all security and monitoring enhancements
    around the agent service.
    
    Features:
    - Automatic input sanitization
    - Token budget management
    - Error handling and sanitization
    - Performance monitoring
    - Search service enhancement
    """
    
    def __init__(
        self,
        agent_service: Any,
        enable_sanitization: bool = True,
        enable_token_management: bool = True,
        enable_monitoring: bool = True
    ):
        """
        Initialize integration wrapper.
        
        Args:
            agent_service: The AgentService instance to wrap
            enable_sanitization: Enable input sanitization
            enable_token_management: Enable token management
            enable_monitoring: Enable health monitoring
        """
        self.agent = agent_service
        self.enable_sanitization = enable_sanitization
        self.enable_token_management = enable_token_management
        self.enable_monitoring = enable_monitoring
        
        # Initialize components
        if enable_sanitization:
            self.sanitizer = get_input_sanitizer(strictness="balanced")
            logger.info("✓ Input sanitization enabled")
        
        if enable_token_management:
            self.token_manager = get_token_manager(model=agent_service.settings.AI_MODEL)
            logger.info("✓ Token management enabled")
        
        if enable_monitoring:
            self.health_monitor = get_health_monitor()
            logger.info("✓ Health monitoring enabled")
        
        logger.info("Agent service integration initialized successfully")
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        client_ip: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process user message with all enhancements.
        
        Args:
            message: User message
            session_id: Session identifier
            client_ip: Client IP address (optional)
            **kwargs: Additional arguments for agent
            
        Returns:
            Response dictionary with enhanced error handling
        """
        start_time = time.time()
        component = "agent_service"
        
        try:
            # Step 1: Input sanitization
            if self.enable_sanitization:
                sanitization_result = self.sanitizer.sanitize(message, session_id)
                
                if not sanitization_result["is_safe"]:
                    logger.warning(
                        f"Suspicious input detected: {sanitization_result['threats_detected']}",
                        extra={"session_id": session_id, "threats": sanitization_result['threats_detected']}
                    )
                    
                    # Record security event
                    if self.enable_monitoring:
                        self.health_monitor.record_error("security_threat")
                    
                    # Use sanitized input
                    message = sanitization_result["sanitized"]
                    
                    # If heavily sanitized, warn user
                    if sanitization_result["sanitized_length"] < sanitization_result["original_length"] * 0.5:
                        return {
                            "success": False,
                            "response": (
                                "Your message contained content that was filtered for security. "
                                "Please rephrase your question and try again."
                            ),
                            "session_id": session_id
                        }
            
            # Step 2: Token validation
            if self.enable_token_management:
                is_valid, error_msg = self.token_manager.validate_input_size(message, max_tokens=10000)
                if not is_valid:
                    error_response = ErrorHandler.handle_validation_error(
                        field="message",
                        reason=error_msg or "Token validation failed",
                        session_id=session_id
                    )
                    return error_response.to_user_dict()
            
            # Step 3: Process with agent (with error handling)
            try:
                response = await self.agent.process_message(
                    message=message,
                    session_id=session_id,
                    client_ip=client_ip,
                    **kwargs
                )
                
                # Step 4: Record metrics
                if self.enable_monitoring:
                    response_time = (time.time() - start_time) * 1000
                    self.health_monitor.record_response_time("agent_process_message", response_time)
                
                return response
                
            except Exception as e:
                # Handle agent errors gracefully
                logger.error(
                    f"Agent processing error: {str(e)}",
                    extra={"session_id": session_id},
                    exc_info=True
                )
                
                if self.enable_monitoring:
                    self.health_monitor.record_error(component)
                
                # Return user-friendly error
                error_response = ErrorHandler.handle_internal_error(
                    component=component,
                    exception=e,
                    session_id=session_id
                )
                return error_response.to_user_dict()
        
        except Exception as e:
            # Catch-all for unexpected errors
            logger.critical(
                f"Critical error in agent integration: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            
            if self.enable_monitoring:
                self.health_monitor.record_error("integration_critical")
            
            return {
                "success": False,
                "error": "An unexpected error occurred. Please try again.",
                "session_id": session_id
            }
    
    def get_enhanced_search_service(self):
        """Get enhanced search service with multi-provider support."""
        return get_enhanced_search_service()
    
    def get_health_status(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Get system health status.
        
        Args:
            detailed: Include detailed component checks
            
        Returns:
            Health status dictionary
        """
        if not self.enable_monitoring:
            return {"status": "unknown", "message": "Monitoring not enabled"}
        
        import asyncio
        return asyncio.run(self.health_monitor.check_health(detailed=detailed))
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Returns:
            Metrics dictionary
        """
        if not self.enable_monitoring:
            return {"message": "Monitoring not enabled"}
        
        return self.health_monitor.get_metrics()


def integrate_security_monitoring(agent_service: Any) -> AgentServiceIntegration:
    """
    Factory function to create integrated agent service.
    
    Args:
        agent_service: AgentService instance
        
    Returns:
        AgentServiceIntegration wrapper
    """
    return AgentServiceIntegration(
        agent_service=agent_service,
        enable_sanitization=True,
        enable_token_management=True,
        enable_monitoring=True
    )
