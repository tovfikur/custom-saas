from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from typing import Dict, Any, Optional
import time
import logging
from fastapi import Response
from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and exposing Prometheus metrics"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._init_metrics()
        
    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        
        # HTTP Request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Nginx configuration metrics
        self.nginx_config_operations_total = Counter(
            'nginx_config_operations_total',
            'Total nginx configuration operations',
            ['operation', 'status', 'vps_id'],
            registry=self.registry
        )
        
        self.nginx_config_validation_duration_seconds = Histogram(
            'nginx_config_validation_duration_seconds',
            'Nginx configuration validation duration',
            registry=self.registry
        )
        
        self.nginx_config_auto_rollbacks_total = Counter(
            'nginx_config_auto_rollbacks_total',
            'Total automatic rollbacks triggered',
            ['vps_id', 'reason'],
            registry=self.registry
        )
        
        # VPS management metrics
        self.vps_bootstrap_operations_total = Counter(
            'vps_bootstrap_operations_total',
            'Total VPS bootstrap operations',
            ['status'],
            registry=self.registry
        )
        
        self.vps_health_checks_total = Counter(
            'vps_health_checks_total',
            'Total VPS health checks',
            ['vps_id', 'status'],
            registry=self.registry
        )
        
        self.vps_connection_errors_total = Counter(
            'vps_connection_errors_total',
            'Total VPS connection errors',
            ['vps_id'],
            registry=self.registry
        )
        
        # Authentication metrics
        self.auth_attempts_total = Counter(
            'auth_attempts_total',
            'Total authentication attempts',
            ['status'],
            registry=self.registry
        )
        
        self.auth_failures_total = Counter(
            'auth_failures_total',
            'Total authentication failures',
            ['reason'],
            registry=self.registry
        )
        
        # System metrics
        self.active_vps_hosts = Gauge(
            'active_vps_hosts',
            'Number of active VPS hosts',
            registry=self.registry
        )
        
        self.active_odoo_instances = Gauge(
            'active_odoo_instances',
            'Number of active Odoo instances',
            registry=self.registry
        )
        
        self.database_connections = Gauge(
            'database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        # Task queue metrics
        self.background_tasks_total = Counter(
            'background_tasks_total',
            'Total background tasks processed',
            ['task_type', 'status'],
            registry=self.registry
        )
        
        self.background_task_duration_seconds = Histogram(
            'background_task_duration_seconds',
            'Background task duration in seconds',
            ['task_type'],
            registry=self.registry
        )
    
    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        self.http_requests_total.labels(
            method=method, 
            endpoint=endpoint, 
            status=str(status)
        ).inc()
        
        self.http_request_duration_seconds.labels(
            method=method, 
            endpoint=endpoint
        ).observe(duration)
    
    def record_nginx_operation(self, operation: str, status: str, vps_id: str, duration: Optional[float] = None):
        """Record nginx configuration operation"""
        self.nginx_config_operations_total.labels(
            operation=operation,
            status=status,
            vps_id=vps_id
        ).inc()
        
        if duration is not None and operation == 'validate':
            self.nginx_config_validation_duration_seconds.observe(duration)
    
    def record_auto_rollback(self, vps_id: str, reason: str):
        """Record automatic rollback"""
        self.nginx_config_auto_rollbacks_total.labels(
            vps_id=vps_id,
            reason=reason
        ).inc()
    
    def record_vps_bootstrap(self, status: str):
        """Record VPS bootstrap operation"""
        self.vps_bootstrap_operations_total.labels(status=status).inc()
    
    def record_vps_health_check(self, vps_id: str, status: str):
        """Record VPS health check"""
        self.vps_health_checks_total.labels(vps_id=vps_id, status=status).inc()
    
    def record_vps_connection_error(self, vps_id: str):
        """Record VPS connection error"""
        self.vps_connection_errors_total.labels(vps_id=vps_id).inc()
    
    def record_auth_attempt(self, status: str, reason: Optional[str] = None):
        """Record authentication attempt"""
        self.auth_attempts_total.labels(status=status).inc()
        
        if status == 'failed' and reason:
            self.auth_failures_total.labels(reason=reason).inc()
    
    def update_system_gauges(self, active_vps: int, active_odoo: int, db_connections: int):
        """Update system gauge metrics"""
        self.active_vps_hosts.set(active_vps)
        self.active_odoo_instances.set(active_odoo)
        self.database_connections.set(db_connections)
    
    def record_background_task(self, task_type: str, status: str, duration: float):
        """Record background task metrics"""
        self.background_tasks_total.labels(
            task_type=task_type,
            status=status
        ).inc()
        
        self.background_task_duration_seconds.labels(
            task_type=task_type
        ).observe(duration)
    
    def get_metrics(self) -> Response:
        """Get metrics in Prometheus format"""
        data = generate_latest(self.registry)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    
    def start_metrics_server(self, port: int = 8001):
        """Start standalone metrics server (for development)"""
        try:
            start_http_server(port, registry=self.registry)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")


# Global metrics instance
metrics_service = MetricsService()


class MetricsMiddleware:
    """FastAPI middleware for automatic metrics collection"""
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        start_time = time.time()
        method = scope["method"]
        path = scope["path"]
        
        # Normalize path for metrics (remove IDs)
        normalized_path = self._normalize_path(path)
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time
                
                metrics_service.record_http_request(
                    method=method,
                    endpoint=normalized_path,
                    status=status_code,
                    duration=duration
                )
            
            await send(message)
        
        return await self.app(scope, receive, send_wrapper)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (replace IDs with placeholders)"""
        import re
        
        # Replace UUIDs and numeric IDs with placeholders
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        path = re.sub(r'/\d+', '/{id}', path)
        
        return path


def create_metrics_middleware(app):
    """Create and return metrics middleware"""
    return MetricsMiddleware(app)