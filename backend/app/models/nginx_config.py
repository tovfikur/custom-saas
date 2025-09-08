from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from .base import BaseModel


class NginxConfig(Base, BaseModel):
    """Nginx configuration model with versioning and safety features"""
    __tablename__ = "nginx_configs"
    
    # Foreign key to VPS host
    vps_id = Column(UUID(as_uuid=True), ForeignKey("vps_hosts.id"), nullable=False)
    
    # Version and identification
    version = Column(Integer, nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    
    # Configuration content (encrypted)
    content_encrypted = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    diff_json = Column(JSON, nullable=True)  # Diff from previous version
    
    # Status and timestamps
    status = Column(String, default="draft", nullable=False)  # draft, applied, rolled_back, failed
    applied_at = Column(DateTime(timezone=True), nullable=True)
    
    # Safety and rollback settings
    watch_window_seconds = Column(Integer, default=120, nullable=False)
    rollback_triggered = Column(Boolean, default=False, nullable=False)
    rollback_reason = Column(Text, nullable=True)
    
    # Validation results
    nginx_test_result = Column(JSON, nullable=True)  # Result of nginx -t
    lint_result = Column(JSON, nullable=True)  # Custom linting results
    
    # Scheduling
    scheduled_apply_at = Column(DateTime(timezone=True), nullable=True)
    
    # Health check results
    health_check_passed = Column(Boolean, nullable=True)
    health_check_details = Column(JSON, nullable=True)
    
    # Template and metadata
    template_used = Column(String, nullable=True)
    config_type = Column(String, nullable=True)  # server_block, upstream, snippet
    config_name = Column(String, nullable=False)  # Friendly name for the config
    
    # Relationships
    vps_host = relationship("VPSHost", back_populates="nginx_configs")
    
    def __repr__(self):
        return f"<NginxConfig(vps_id='{self.vps_id}', version={self.version}, status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if this config version is currently active"""
        return self.status == "applied" and not self.rollback_triggered
    
    @property
    def can_rollback(self) -> bool:
        """Check if this config can be rolled back"""
        return self.status == "applied" and self.applied_at is not None