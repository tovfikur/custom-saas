from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from .base import BaseModel


class AuditLog(Base, BaseModel):
    """Audit log model for tracking all admin actions and system events"""
    __tablename__ = "audit_logs"
    
    # Action identification
    task_id = Column(String, nullable=False, index=True)  # Unique task identifier
    action = Column(String, nullable=False, index=True)    # e.g., "nginx_config_apply", "vps_onboard"
    resource_type = Column(String, nullable=False)        # e.g., "nginx_config", "vps_host", "odoo_instance"
    resource_id = Column(UUID(as_uuid=True), nullable=True)  # ID of the resource being acted upon
    
    # Actor information
    actor_id = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)  # Admin who performed action
    actor_ip = Column(String, nullable=True)              # IP address of actor
    user_agent = Column(String, nullable=True)            # User agent string
    
    # Action details
    description = Column(Text, nullable=False)            # Human-readable description
    details = Column(JSON, nullable=True)                 # Additional structured data
    
    # Results and status
    status = Column(String, nullable=False)               # success, failed, pending, rolled_back
    result = Column(JSON, nullable=True)                  # Structured result data
    error_message = Column(Text, nullable=True)           # Sanitized error message
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Context
    context = Column(JSON, nullable=True)                 # Additional context (e.g., VPS details, config diff)
    
    # Relationships
    actor = relationship("Admin")
    
    def __repr__(self):
        return f"<AuditLog(task_id='{self.task_id}', action='{self.action}', status='{self.status}')>"
    
    @property
    def is_sensitive_action(self) -> bool:
        """Check if this action involves sensitive operations"""
        sensitive_actions = [
            "nginx_config_apply",
            "vps_onboard", 
            "ssh_key_update",
            "password_change",
            "backup_restore"
        ]
        return self.action in sensitive_actions
    
    @property
    def duration(self) -> int:
        """Get action duration in seconds"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return self.duration_seconds or 0