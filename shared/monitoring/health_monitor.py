"""
Health Check and Monitoring System

Implements comprehensive health monitoring to:
- Check external service availability
- Monitor system resource usage
- Track response times and error rates
- Provide detailed status endpoints
- Support production observability

Based on production best practices for API health monitoring.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    response_time_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_connections: int
    uptime_seconds: float


class HealthMonitor:
    """
    Comprehensive health monitoring for the application.
    
    Features:
    - External service health checks
    - Database connectivity checks
    - Resource usage monitoring
    - Error rate tracking
    - Response time tracking
    """
    
    def __init__(self):
        """Initialize health monitor."""
        self.start_time = time.time()
        self.component_health: Dict[str, ComponentHealth] = {}
        self.error_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}
        self.max_response_times = 100  # Keep last 100 response times
        
        logger.info("Health monitor initialized")
    
    async def check_health(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Args:
            detailed: Include detailed component checks
            
        Returns:
            Dictionary with health status and metrics
        """
        # Get system metrics
        system_metrics = self._get_system_metrics()
        
        # Check components if detailed
        components = {}
        if detailed:
            components = await self._check_all_components()
        
        # Determine overall status
        overall_status = self._determine_overall_status(components)
        
        # Build response
        response = {
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": time.time() - self.start_time,
            "system": {
                "cpu_percent": system_metrics.cpu_percent,
                "memory_percent": system_metrics.memory_percent,
                "disk_percent": system_metrics.disk_percent,
            }
        }
        
        if detailed:
            response["components"] = {
                name: {
                    "status": comp.status.value,
                    "message": comp.message,
                    "response_time_ms": comp.response_time_ms,
                    "last_check": comp.last_check.isoformat() if comp.last_check else None,
                    "error_count": comp.error_count,
                    "metadata": comp.metadata
                }
                for name, comp in components.items()
            }
        
        return response
    
    def _get_system_metrics(self) -> SystemMetrics:
        """
        Get current system resource metrics.
        
        Returns:
            SystemMetrics object
        """
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            # Get connection count (approximate)
            try:
                connections = len(psutil.net_connections())
            except Exception:
                connections = 0
            
            uptime = time.time() - self.start_time
            
            return SystemMetrics(
                cpu_percent=cpu,
                memory_percent=memory,
                disk_percent=disk,
                active_connections=connections,
                uptime_seconds=uptime
            )
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                active_connections=0,
                uptime_seconds=time.time() - self.start_time
            )
    
    async def _check_all_components(self) -> Dict[str, ComponentHealth]:
        """
        Check health of all components.
        
        Returns:
            Dictionary of component health status
        """
        components = {}
        
        # Check database
        try:
            db_health = await self._check_database()
            components["database"] = db_health
        except Exception as e:
            components["database"] = ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc)
            )
        
        # Check AI providers
        provider_checks = [
            ("gemini", self._check_gemini),
            ("openai", self._check_openai),
            ("ollama", self._check_ollama),
        ]
        
        for provider_name, check_func in provider_checks:
            try:
                provider_health = await check_func()
                components[f"ai_provider_{provider_name}"] = provider_health
            except Exception as e:
                components[f"ai_provider_{provider_name}"] = ComponentHealth(
                    name=f"ai_provider_{provider_name}",
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)[:100]}",
                    last_check=datetime.now(timezone.utc)
                )
        
        # Check data sources
        data_source_checks = [
            ("waqi", self._check_waqi),
            ("airqo", self._check_airqo),
            ("openmeteo", self._check_openmeteo),
        ]
        
        for source_name, check_func in data_source_checks:
            try:
                source_health = await check_func()
                components[f"data_source_{source_name}"] = source_health
            except Exception as e:
                components[f"data_source_{source_name}"] = ComponentHealth(
                    name=f"data_source_{source_name}",
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)[:100]}",
                    last_check=datetime.now(timezone.utc)
                )
        
        return components
    
    async def _check_database(self) -> ComponentHealth:
        """Check database health."""
        start_time = time.time()
        
        try:
            # Import here to avoid circular dependency
            from sqlalchemy import text

            from infrastructure.database.database import engine

            # Simple connection test
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc)
            )
        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc),
                error_count=1
            )
    
    async def _check_gemini(self) -> ComponentHealth:
        """Check Gemini provider health."""
        start_time = time.time()
        
        try:
            from shared.config.settings import get_settings
            settings = get_settings()
            
            if settings.AI_PROVIDER.lower() != "gemini":
                return ComponentHealth(
                    name="gemini",
                    status=HealthStatus.UNKNOWN,
                    message="Not configured as primary provider",
                    last_check=datetime.now(timezone.utc)
                )
            
            if not settings.AI_API_KEY:
                return ComponentHealth(
                    name="gemini",
                    status=HealthStatus.DEGRADED,
                    message="API key not configured",
                    last_check=datetime.now(timezone.utc)
                )
            
            # Simple availability check (not full API call to avoid costs)
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="gemini",
                status=HealthStatus.HEALTHY,
                message="Provider configured and available",
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc)
            )
        except Exception as e:
            return ComponentHealth(
                name="gemini",
                status=HealthStatus.UNHEALTHY,
                message=f"Provider check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc),
                error_count=1
            )
    
    async def _check_openai(self) -> ComponentHealth:
        """Check OpenAI provider health."""
        # Similar to Gemini check
        try:
            from shared.config.settings import get_settings
            settings = get_settings()
            
            if settings.AI_PROVIDER.lower() != "openai":
                return ComponentHealth(
                    name="openai",
                    status=HealthStatus.UNKNOWN,
                    message="Not configured as primary provider",
                    last_check=datetime.now(timezone.utc)
                )
            
            return ComponentHealth(
                name="openai",
                status=HealthStatus.HEALTHY,
                message="Provider configured",
                last_check=datetime.now(timezone.utc)
            )
        except Exception as e:
            return ComponentHealth(
                name="openai",
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_ollama(self) -> ComponentHealth:
        """Check Ollama provider health."""
        try:
            import httpx

            from shared.config.settings import get_settings
            settings = get_settings()
            
            # Try to connect to Ollama
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                    
                    if response.status_code == 200:
                        return ComponentHealth(
                            name="ollama",
                            status=HealthStatus.HEALTHY,
                            message="Ollama server accessible",
                            last_check=datetime.now(timezone.utc)
                        )
            except Exception:
                pass
            
            return ComponentHealth(
                name="ollama",
                status=HealthStatus.DEGRADED,
                message="Ollama server not accessible (optional)",
                last_check=datetime.now(timezone.utc)
            )
        except Exception as e:
            return ComponentHealth(
                name="ollama",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_waqi(self) -> ComponentHealth:
        """Check WAQI API health."""
        try:
            import httpx

            # Simple ping to WAQI API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://api.waqi.info/api/feed/@8776/")
                
                if response.status_code == 200:
                    return ComponentHealth(
                        name="waqi",
                        status=HealthStatus.HEALTHY,
                        message="WAQI API accessible",
                        last_check=datetime.now(timezone.utc)
                    )
                else:
                    return ComponentHealth(
                        name="waqi",
                        status=HealthStatus.DEGRADED,
                        message=f"WAQI API returned status {response.status_code}",
                        last_check=datetime.now(timezone.utc)
                    )
        except Exception as e:
            return ComponentHealth(
                name="waqi",
                status=HealthStatus.UNHEALTHY,
                message=f"WAQI API unreachable: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc),
                error_count=1
            )
    
    async def _check_airqo(self) -> ComponentHealth:
        """Check AirQo API health."""
        try:
            import httpx

            # Simple ping to AirQo API
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://api.airqo.net/api/v2/devices/measurements")
                
                # AirQo might return 400 without proper params, but 400 means it's responding
                if response.status_code in [200, 400]:
                    return ComponentHealth(
                        name="airqo",
                        status=HealthStatus.HEALTHY,
                        message="AirQo API accessible",
                        last_check=datetime.now(timezone.utc)
                    )
                else:
                    return ComponentHealth(
                        name="airqo",
                        status=HealthStatus.DEGRADED,
                        message=f"AirQo API returned status {response.status_code}",
                        last_check=datetime.now(timezone.utc)
                    )
        except Exception as e:
            return ComponentHealth(
                name="airqo",
                status=HealthStatus.DEGRADED,
                message=f"AirQo API check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_openmeteo(self) -> ComponentHealth:
        """Check Open-Meteo API health."""
        try:
            import httpx

            # Simple ping to Open-Meteo
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://air-quality-api.open-meteo.com/v1/air-quality",
                    params={"latitude": 0, "longitude": 0, "current": "pm2_5"}
                )
                
                if response.status_code == 200:
                    return ComponentHealth(
                        name="openmeteo",
                        status=HealthStatus.HEALTHY,
                        message="Open-Meteo API accessible",
                        last_check=datetime.now(timezone.utc)
                    )
                else:
                    return ComponentHealth(
                        name="openmeteo",
                        status=HealthStatus.DEGRADED,
                        message=f"Open-Meteo returned status {response.status_code}",
                        last_check=datetime.now(timezone.utc)
                    )
        except Exception as e:
            return ComponentHealth(
                name="openmeteo",
                status=HealthStatus.DEGRADED,
                message=f"Open-Meteo check failed: {str(e)[:100]}",
                last_check=datetime.now(timezone.utc)
            )
    
    def _determine_overall_status(self, components: Dict[str, ComponentHealth]) -> HealthStatus:
        """
        Determine overall system health based on components.
        
        Args:
            components: Dictionary of component health
            
        Returns:
            Overall HealthStatus
        """
        if not components:
            return HealthStatus.HEALTHY
        
        statuses = [comp.status for comp in components.values()]
        
        # If any critical component is unhealthy, system is unhealthy
        critical_components = ["database"]
        for comp_name in critical_components:
            if comp_name in components:
                if components[comp_name].status == HealthStatus.UNHEALTHY:
                    return HealthStatus.UNHEALTHY
        
        # If majority of components are unhealthy, system is unhealthy
        unhealthy_count = sum(1 for s in statuses if s == HealthStatus.UNHEALTHY)
        if unhealthy_count > len(statuses) // 2:
            return HealthStatus.UNHEALTHY
        
        # If any component is degraded, system is degraded
        if HealthStatus.DEGRADED in statuses or HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def record_response_time(self, endpoint: str, response_time_ms: float):
        """
        Record response time for an endpoint.
        
        Args:
            endpoint: Endpoint name
            response_time_ms: Response time in milliseconds
        """
        if endpoint not in self.response_times:
            self.response_times[endpoint] = []
        
        self.response_times[endpoint].append(response_time_ms)
        
        # Keep only last N measurements
        if len(self.response_times[endpoint]) > self.max_response_times:
            self.response_times[endpoint] = self.response_times[endpoint][-self.max_response_times:]
    
    def record_error(self, component: str):
        """
        Record an error for a component.
        
        Args:
            component: Component name
        """
        if component not in self.error_counts:
            self.error_counts[component] = 0
        
        self.error_counts[component] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = {
            "uptime_seconds": time.time() - self.start_time,
            "error_counts": self.error_counts.copy(),
            "response_times": {}
        }
        
        # Calculate response time statistics
        for endpoint, times in self.response_times.items():
            if times:
                metrics["response_times"][endpoint] = {
                    "count": len(times),
                    "avg_ms": sum(times) / len(times),
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 0 else 0,
                    "p99_ms": sorted(times)[int(len(times) * 0.99)] if len(times) > 0 else 0,
                }
        
        return metrics


# Global instance
_health_monitor_instance = None


def get_health_monitor() -> HealthMonitor:
    """Get or create health monitor instance."""
    global _health_monitor_instance
    if _health_monitor_instance is None:
        _health_monitor_instance = HealthMonitor()
    return _health_monitor_instance
