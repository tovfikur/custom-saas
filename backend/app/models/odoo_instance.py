from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from .base import BaseModel


class OdooInstance(Base, BaseModel):
    """Odoo instance model for managing deployed Odoo containers"""
    __tablename__ = "odoo_instances"
    
    # Foreign key to VPS host
    vps_id = Column(UUID(as_uuid=True), ForeignKey("vps_hosts.id"), nullable=False)
    
    # Instance identification
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, index=True)
    container_name = Column(String, nullable=False)
    
    # Odoo version and deployment
    odoo_version = Column(String, nullable=False)  # v13, v14, v15, v16, v17, latest
    git_branch = Column(String, nullable=True)     # If deployed from Git
    docker_image = Column(String, nullable=True)   # If deployed from custom image
    
    # Industry and backup
    industry = Column(String, nullable=False)      # e.g., healthcare, retail, manufacturing
    backup_restored = Column(String, nullable=True)  # Path/name of restored backup
    restore_date = Column(DateTime(timezone=True), nullable=True)
    
    # Container configuration
    port = Column(Integer, nullable=False)         # Internal port
    nginx_port = Column(Integer, default=80, nullable=False)  # External nginx port
    db_name = Column(String, nullable=False)
    
    # Status and health
    status = Column(String, default="pending", nullable=False)  # pending, running, stopped, error, upgrading
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String, nullable=True)  # healthy, unhealthy, unknown
    
    # Configuration and environment
    env_vars = Column(JSON, nullable=True)         # Environment variables (encrypted)
    volumes = Column(JSON, nullable=True)          # Docker volume mappings
    
    # Lifecycle management
    monthly_lifecycle_day = Column(Integer, nullable=True)  # Day of month for lifecycle actions
    lifecycle_status = Column(String, default="active", nullable=False)  # active, warning_sent, admin_started, stopped
    lifecycle_warnings_sent = Column(Integer, default=0, nullable=False)
    last_warning_sent = Column(DateTime(timezone=True), nullable=True)
    
    # Monitoring and alerts
    monitoring_enabled = Column(Boolean, default=True, nullable=False)
    cpu_limit = Column(String, nullable=True)      # Docker CPU limit
    memory_limit = Column(String, nullable=True)   # Docker memory limit
    
    # Backup configuration
    backup_enabled = Column(Boolean, default=True, nullable=False)
    backup_schedule = Column(String, nullable=True)  # Cron expression
    last_backup = Column(DateTime(timezone=True), nullable=True)
    
    # SSL and security
    ssl_enabled = Column(Boolean, default=True, nullable=False)
    ssl_cert_path = Column(String, nullable=True)
    ssl_key_path = Column(String, nullable=True)
    
    # Metadata
    tags = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    vps_host = relationship("VPSHost", back_populates="odoo_instances")
    
    def __repr__(self):
        return f"<OdooInstance(name='{self.name}', domain='{self.domain}', status='{self.status}')>"
    
    @property
    def is_running(self) -> bool:
        """Check if instance is currently running"""
        return self.status == "running"
    
    @property
    def needs_lifecycle_action(self) -> bool:
        """Check if instance needs monthly lifecycle action"""
        return self.lifecycle_status in ["warning_sent", "admin_started"]
    
    @property
    def full_url(self) -> str:
        """Get full URL for the instance"""
        protocol = "https" if self.ssl_enabled else "http"
        port_suffix = f":{self.nginx_port}" if self.nginx_port not in [80, 443] else ""
        return f"{protocol}://{self.domain}{port_suffix}"