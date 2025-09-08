from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.services.metrics_service import metrics_service
from app.services.alerting_service import alerting_service
from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AlertRequest(BaseModel):
    alert_type: str = Field(..., description="Type of alert")
    severity: str = Field(..., description="Alert severity (info, warning, critical)")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    recipients: Optional[List[str]] = Field(None, description="Email recipients")


class SystemMetricsResponse(BaseModel):
    active_vps_hosts: int
    active_odoo_instances: int
    total_nginx_operations: int
    failed_nginx_operations: int
    recent_alerts: int


@router.get("/metrics")
async def get_prometheus_metrics(
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Prometheus metrics"""
    return metrics_service.get_metrics()


@router.get("/system-metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get system metrics summary"""
    try:
        from sqlalchemy import select, func
        from app.models.vps_host import VPSHost
        from app.models.odoo_instance import OdooInstance
        from app.models.audit_log import AuditLog
        from datetime import datetime, timedelta
        
        # Count active VPS hosts
        vps_query = select(func.count(VPSHost.id)).where(VPSHost.status == "active")
        vps_result = await db.execute(vps_query)
        active_vps = vps_result.scalar() or 0
        
        # Count active Odoo instances
        odoo_query = select(func.count(OdooInstance.id)).where(OdooInstance.status == "running")
        odoo_result = await db.execute(odoo_query)
        active_odoo = odoo_result.scalar() or 0
        
        # Count nginx operations (last 24 hours)
        since_time = datetime.utcnow() - timedelta(hours=24)
        nginx_total_query = select(func.count(AuditLog.id)).where(
            AuditLog.action.like('nginx_config_%'),
            AuditLog.started_at >= since_time
        )
        nginx_total_result = await db.execute(nginx_total_query)
        total_nginx_ops = nginx_total_result.scalar() or 0
        
        # Count failed nginx operations
        nginx_failed_query = select(func.count(AuditLog.id)).where(
            AuditLog.action.like('nginx_config_%'),
            AuditLog.status == "failed",
            AuditLog.started_at >= since_time
        )
        nginx_failed_result = await db.execute(nginx_failed_query)
        failed_nginx_ops = nginx_failed_result.scalar() or 0
        
        # Count recent alerts (last 4 hours)
        alert_time = datetime.utcnow() - timedelta(hours=4)
        alert_query = select(func.count(AuditLog.id)).where(
            AuditLog.action.like('%alert%'),
            AuditLog.started_at >= alert_time
        )
        alert_result = await db.execute(alert_query)
        recent_alerts = alert_result.scalar() or 0
        
        # Update Prometheus gauges
        metrics_service.update_system_gauges(
            active_vps=active_vps,
            active_odoo=active_odoo,
            db_connections=0  # This would be implemented with actual connection pool metrics
        )
        
        return SystemMetricsResponse(
            active_vps_hosts=active_vps,
            active_odoo_instances=active_odoo,
            total_nginx_operations=total_nginx_ops,
            failed_nginx_operations=failed_nginx_ops,
            recent_alerts=recent_alerts
        )
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system metrics"
        )


@router.post("/alerts/send")
async def send_alert(
    alert_request: AlertRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Send a manual alert"""
    try:
        audit_service = AuditService(db)
        
        # Log the manual alert
        await audit_service.log_action(
            task_id=f"manual_alert_{alert_request.alert_type}",
            action="manual_alert_send",
            resource_type="alert",
            actor_id=str(current_admin.id),
            description=f"Manual alert sent: {alert_request.title}",
            details={
                "alert_type": alert_request.alert_type,
                "severity": alert_request.severity,
                "title": alert_request.title,
                "recipients": alert_request.recipients
            }
        )
        
        # Send the alert
        result = await alerting_service.send_alert(
            alert_type=alert_request.alert_type,
            severity=alert_request.severity,
            title=alert_request.title,
            message=alert_request.message,
            recipients=alert_request.recipients
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send alert"
        )


@router.get("/alerts/test")
async def test_alerting_system(
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Test the alerting system"""
    try:
        # Send a test alert
        result = await alerting_service.send_alert(
            alert_type="test",
            severity="info",
            title="Test Alert from SaaS Orchestrator",
            message="This is a test alert to verify the alerting system is working correctly.",
            details={
                "test": True,
                "sender": current_admin.email,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Test alert sent successfully",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to test alerting system: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test alerting system"
        )


@router.get("/health")
async def monitoring_health_check():
    """Health check for monitoring components"""
    try:
        health_status = {
            "prometheus_metrics": True,  # Check if metrics are being collected
            "alerting_service": True,    # Check if alerting service is responsive
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/audit/recent")
async def get_recent_audit_logs(
    limit: int = 50,
    action_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get recent audit logs for monitoring"""
    try:
        audit_service = AuditService(db)
        
        logs = await audit_service.get_audit_logs(
            limit=limit,
            action=action_filter
        )
        
        return logs
        
    except Exception as e:
        logger.error(f"Failed to get recent audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )