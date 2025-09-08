from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from .base import BaseModel


class VPSHost(Base, BaseModel):
    """VPS host model for managing remote servers"""
    __tablename__ = "vps_hosts"
    
    name = Column(String, nullable=False)
    hostname = Column(String, nullable=False)
    ip_address = Column(String, nullable=False, index=True)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String, nullable=False)
    
    # SSH connection details (encrypted)
    private_key_encrypted = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)
    
    # Status and health
    status = Column(String, default="pending", nullable=False)  # pending, active, inactive, error, requires_manual_intervention
    last_ping = Column(DateTime(timezone=True), nullable=True)
    last_successful_connection = Column(DateTime(timezone=True), nullable=True)
    
    # System information
    os_info = Column(JSON, nullable=True)
    docker_version = Column(String, nullable=True)
    nginx_version = Column(String, nullable=True)
    
    # Configuration
    max_odoo_instances = Column(Integer, default=10, nullable=False)
    nginx_managed_dir = Column(String, default="/etc/nginx/managed.d", nullable=False)
    nginx_drafts_dir = Column(String, default="/etc/nginx/managed.d/drafts", nullable=False)
    nginx_config_checksum = Column(String, nullable=True)
    
    # Monitoring
    monitoring_enabled = Column(Boolean, default=True, nullable=False)
    alert_email = Column(String, nullable=True)
    
    # Metadata
    tags = Column(JSON, nullable=True)  # For grouping and filtering
    notes = Column(Text, nullable=True)
    
    # Relationships
    odoo_instances = relationship("OdooInstance", back_populates="vps_host", cascade="all, delete-orphan")
    nginx_configs = relationship("NginxConfig", back_populates="vps_host", cascade="all, delete-orphan")
    docker_schedules = relationship("DockerSchedule", back_populates="vps_host", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<VPSHost(name='{self.name}', ip='{self.ip_address}', status='{self.status}')>"
    
    @property
    def is_healthy(self) -> bool:
        """Check if VPS is considered healthy"""
        return self.status == "active" and self.last_successful_connection is not None
    
    @property
    def connection_string(self) -> str:
        """Get SSH connection string"""
        return f"{self.username}@{self.ip_address}:{self.port}"