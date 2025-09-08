import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from app.core.config import settings
from app.core.security import sanitize_error_message

logger = logging.getLogger(__name__)


class AlertingService:
    """Service for sending alerts and notifications"""
    
    def __init__(self):
        self.webhook_timeout = 30
        self.email_enabled = hasattr(settings, 'SMTP_HOST') and settings.SMTP_HOST
        self.alert_cooldown = {}  # Track alert cooldowns
        
    async def send_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send alert through configured channels"""
        
        alert_id = f"{alert_type}_{hash(title + message)}"
        
        # Check cooldown
        if self._is_in_cooldown(alert_id, severity):
            return {
                "success": True,
                "message": "Alert suppressed due to cooldown",
                "alert_id": alert_id
            }
        
        alert_data = {
            "alert_id": alert_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "timezone": settings.TIMEZONE
        }
        
        results = {}
        
        # Send email alerts
        if self.email_enabled and recipients:
            email_result = await self._send_email_alert(alert_data, recipients)
            results["email"] = email_result
        
        # Send webhook alerts (for Slack, Discord, etc.)
        webhook_result = await self._send_webhook_alerts(alert_data)
        results["webhook"] = webhook_result
        
        # Log alert
        await self._log_alert(alert_data)
        
        # Set cooldown
        self._set_cooldown(alert_id, severity)
        
        return {
            "success": any(r.get("success", False) for r in results.values()),
            "alert_id": alert_id,
            "results": results
        }
    
    async def send_nginx_config_alert(
        self,
        vps_id: str,
        vps_name: str,
        operation: str,
        status: str,
        task_id: str,
        error_message: Optional[str] = None,
        config_version: Optional[str] = None
    ):
        """Send nginx configuration-specific alert"""
        
        if status == "success":
            severity = "info"
            title = f"Nginx Config {operation.title()} Successful"
            message = f"Nginx configuration {operation} completed successfully on VPS {vps_name}"
        else:
            severity = "critical" if operation == "rollback" else "warning"
            title = f"Nginx Config {operation.title()} Failed"
            message = f"Nginx configuration {operation} failed on VPS {vps_name}"
            
            if error_message:
                # Sanitize error message
                sanitized = sanitize_error_message(error_message, task_id)
                message += f"\n\nError: {sanitized['error']}"
        
        details = {
            "vps_id": vps_id,
            "vps_name": vps_name,
            "operation": operation,
            "status": status,
            "task_id": task_id,
            "config_version": config_version
        }
        
        return await self.send_alert(
            alert_type="nginx_config",
            severity=severity,
            title=title,
            message=message,
            details=details
        )
    
    async def send_vps_health_alert(
        self,
        vps_id: str,
        vps_name: str,
        vps_ip: str,
        health_status: str,
        services_status: Dict[str, Any]
    ):
        """Send VPS health-related alert"""
        
        if health_status in ["healthy", "active"]:
            severity = "info"
            title = f"VPS {vps_name} Health Restored"
            message = f"VPS {vps_name} ({vps_ip}) is now healthy"
        elif health_status == "degraded":
            severity = "warning"
            title = f"VPS {vps_name} Health Degraded"
            message = f"VPS {vps_name} ({vps_ip}) is experiencing issues"
        else:
            severity = "critical"
            title = f"VPS {vps_name} Down"
            message = f"VPS {vps_name} ({vps_ip}) is unreachable or unhealthy"
        
        details = {
            "vps_id": vps_id,
            "vps_name": vps_name,
            "vps_ip": vps_ip,
            "health_status": health_status,
            "services_status": services_status
        }
        
        return await self.send_alert(
            alert_type="vps_health",
            severity=severity,
            title=title,
            message=message,
            details=details
        )
    
    async def send_security_alert(
        self,
        alert_type: str,
        actor_ip: str,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Send security-related alert"""
        
        title = f"Security Alert: {alert_type.replace('_', ' ').title()}"
        message = f"Security event detected from IP {actor_ip}"
        
        if user_agent:
            message += f"\nUser Agent: {user_agent}"
        
        alert_details = {
            "actor_ip": actor_ip,
            "user_agent": user_agent,
            "details": details or {}
        }
        
        return await self.send_alert(
            alert_type="security",
            severity="critical",
            title=title,
            message=message,
            details=alert_details
        )
    
    async def send_auto_rollback_alert(
        self,
        vps_id: str,
        vps_name: str,
        config_name: str,
        rollback_reason: str,
        original_task_id: str,
        rollback_task_id: str
    ):
        """Send automatic rollback alert"""
        
        title = f"Automatic Rollback Triggered - {vps_name}"
        message = f"Nginx configuration '{config_name}' was automatically rolled back on VPS {vps_name}"
        message += f"\n\nReason: {rollback_reason}"
        
        details = {
            "vps_id": vps_id,
            "vps_name": vps_name,
            "config_name": config_name,
            "rollback_reason": rollback_reason,
            "original_task_id": original_task_id,
            "rollback_task_id": rollback_task_id
        }
        
        return await self.send_alert(
            alert_type="auto_rollback",
            severity="warning",
            title=title,
            message=message,
            details=details
        )
    
    async def _send_email_alert(self, alert_data: Dict[str, Any], recipients: List[str]) -> Dict[str, Any]:
        """Send email alert"""
        try:
            # This would be implemented with actual SMTP settings
            # For now, we'll just log it
            logger.info(f"Email alert would be sent to {recipients}: {alert_data['title']}")
            
            return {
                "success": True,
                "message": "Email alert logged (SMTP not configured)",
                "recipients": recipients
            }
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_webhook_alerts(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook alerts to configured endpoints"""
        
        # Example webhook payloads for different services
        webhook_configs = [
            # Slack webhook example
            {
                "url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                "payload": self._format_slack_payload(alert_data),
                "headers": {"Content-Type": "application/json"}
            },
            # Discord webhook example
            {
                "url": "https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK",
                "payload": self._format_discord_payload(alert_data),
                "headers": {"Content-Type": "application/json"}
            }
        ]
        
        results = []
        
        for webhook in webhook_configs:
            try:
                # Skip if URL is placeholder
                if "YOUR" in webhook["url"]:
                    continue
                    
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook["url"],
                        json=webhook["payload"],
                        headers=webhook["headers"],
                        timeout=aiohttp.ClientTimeout(total=self.webhook_timeout)
                    ) as response:
                        if response.status < 400:
                            results.append({"success": True, "status": response.status})
                        else:
                            results.append({"success": False, "status": response.status})
                            
            except Exception as e:
                logger.error(f"Webhook alert failed: {e}")
                results.append({"success": False, "error": str(e)})
        
        return {
            "success": any(r.get("success", False) for r in results),
            "results": results
        }
    
    def _format_slack_payload(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for Slack"""
        color = {
            "critical": "danger",
            "warning": "warning", 
            "info": "good"
        }.get(alert_data["severity"], "warning")
        
        return {
            "text": alert_data["title"],
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert_data["severity"].upper(),
                            "short": True
                        },
                        {
                            "title": "Type",
                            "value": alert_data["alert_type"],
                            "short": True
                        },
                        {
                            "title": "Message",
                            "value": alert_data["message"],
                            "short": False
                        }
                    ],
                    "footer": "SaaS Orchestrator",
                    "ts": int(datetime.fromisoformat(alert_data["timestamp"].replace('Z', '+00:00')).timestamp())
                }
            ]
        }
    
    def _format_discord_payload(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for Discord"""
        color = {
            "critical": 0xFF0000,  # Red
            "warning": 0xFFA500,   # Orange
            "info": 0x00FF00       # Green
        }.get(alert_data["severity"], 0xFFA500)
        
        return {
            "embeds": [
                {
                    "title": alert_data["title"],
                    "description": alert_data["message"],
                    "color": color,
                    "fields": [
                        {
                            "name": "Severity",
                            "value": alert_data["severity"].upper(),
                            "inline": True
                        },
                        {
                            "name": "Type", 
                            "value": alert_data["alert_type"],
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "SaaS Orchestrator"
                    },
                    "timestamp": alert_data["timestamp"]
                }
            ]
        }
    
    async def _log_alert(self, alert_data: Dict[str, Any]):
        """Log alert to system logs"""
        logger.warning(f"ALERT [{alert_data['severity'].upper()}] {alert_data['title']}: {alert_data['message']}")
    
    def _is_in_cooldown(self, alert_id: str, severity: str) -> bool:
        """Check if alert is in cooldown period"""
        if alert_id not in self.alert_cooldown:
            return False
        
        last_sent = self.alert_cooldown[alert_id]["last_sent"]
        cooldown_minutes = self._get_cooldown_minutes(severity)
        
        return datetime.utcnow() < (last_sent + timedelta(minutes=cooldown_minutes))
    
    def _set_cooldown(self, alert_id: str, severity: str):
        """Set cooldown for alert"""
        self.alert_cooldown[alert_id] = {
            "last_sent": datetime.utcnow(),
            "severity": severity
        }
    
    def _get_cooldown_minutes(self, severity: str) -> int:
        """Get cooldown period in minutes based on severity"""
        return {
            "critical": 5,   # 5 minutes
            "warning": 15,   # 15 minutes
            "info": 60       # 1 hour
        }.get(severity, 15)


# Global alerting service instance
alerting_service = AlertingService()