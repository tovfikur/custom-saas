from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from .base import BaseModel


class OdooTemplate(Base, BaseModel):
    """Odoo template model for industry-specific templates with backup databases"""
    __tablename__ = "odoo_templates"
    
    # Template identification
    name = Column(String, nullable=False, index=True)
    industry = Column(String, nullable=False, index=True)  # e.g., healthcare, retail, manufacturing
    description = Column(Text, nullable=True)
    version = Column(String, nullable=False)  # Supported Odoo versions: 13, 14, 15, 16, 17, latest
    
    # Template configuration
    docker_image = Column(String, nullable=True)  # Custom docker image if needed
    default_modules = Column(JSON, nullable=True)  # List of modules to install
    config_template = Column(JSON, nullable=True)  # Odoo configuration template
    env_vars_template = Column(JSON, nullable=True)  # Environment variables template
    
    # Backup database
    backup_file_path = Column(String, nullable=True)  # Path to the backup zip file
    backup_file_size = Column(Integer, nullable=True)  # Size in bytes
    backup_created_at = Column(DateTime(timezone=True), nullable=True)
    backup_odoo_version = Column(String, nullable=True)  # Version used to create the backup
    
    # Database credentials for the backup
    backup_db_name = Column(String, nullable=True)  # Original database name in backup
    backup_db_user = Column(String, nullable=True)  # Database username for backup
    backup_db_password = Column(String, nullable=True)  # Encrypted database password
    backup_db_host = Column(String, nullable=True)  # Database host (optional, usually localhost)
    backup_db_port = Column(Integer, default=5432, nullable=True)  # Database port
    
    # Template metadata
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)  # Public templates available to all
    download_count = Column(Integer, default=0, nullable=False)
    deployment_count = Column(Integer, default=0, nullable=False)
    
    # Default deployment settings
    default_port_range_start = Column(Integer, default=8000, nullable=False)
    default_port_range_end = Column(Integer, default=9000, nullable=False)
    default_memory_limit = Column(String, default="1g", nullable=True)
    default_cpu_limit = Column(String, default="1", nullable=True)
    
    # Template tags and categorization
    tags = Column(JSON, nullable=True)  # Tags for filtering and search
    category = Column(String, nullable=True)  # Main category: ERP, CRM, Manufacturing, etc.
    complexity_level = Column(String, default="beginner", nullable=False)  # beginner, intermediate, advanced
    
    # Installation and setup instructions
    setup_instructions = Column(Text, nullable=True)
    post_install_script = Column(Text, nullable=True)  # Script to run after deployment
    required_addons = Column(JSON, nullable=True)  # Additional addons required
    
    # Template screenshots and preview
    screenshots = Column(JSON, nullable=True)  # List of screenshot URLs
    demo_url = Column(String, nullable=True)  # Demo instance URL
    documentation_url = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<OdooTemplate(name='{self.name}', industry='{self.industry}', version='{self.version}')>"
    
    @property
    def is_available(self) -> bool:
        """Check if template is available for deployment"""
        return self.is_active  # Allow deployment with or without backup file
    
    @property
    def backup_file_size_mb(self) -> int:
        """Get backup file size in MB"""
        if self.backup_file_size:
            return round(self.backup_file_size / (1024 * 1024))
        return 0
    
    @property
    def supported_versions(self) -> list:
        """Get list of supported Odoo versions"""
        if self.version == "latest":
            return ["17", "16", "15", "14", "13"]
        return [self.version]
    
    def increment_deployment_count(self):
        """Increment the deployment counter"""
        self.deployment_count += 1
    
    def increment_download_count(self):
        """Increment the download counter"""
        self.download_count += 1


class OdooTemplateFile(Base, BaseModel):
    """Model for storing template files (backup databases, configurations, etc.)"""
    __tablename__ = "odoo_template_files"
    
    # Template reference
    template_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # File information
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # backup, config, addon, script
    file_path = Column(String, nullable=False)  # Path to the actual file
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String, nullable=True)
    
    # File metadata
    description = Column(Text, nullable=True)
    version = Column(String, nullable=True)  # Version this file is for
    is_required = Column(Boolean, default=True, nullable=False)
    
    # Upload information
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)  # Admin who uploaded
    upload_date = Column(DateTime(timezone=True), nullable=True)
    checksum = Column(String, nullable=True)  # File integrity check
    
    def __repr__(self):
        return f"<OdooTemplateFile(template_id='{self.template_id}', file_name='{self.file_name}', file_type='{self.file_type}')>"
    
    @property
    def file_size_mb(self) -> int:
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024))
        return 0


class OdooDeployment(Base, BaseModel):
    """Model for tracking Odoo deployments from templates"""
    __tablename__ = "odoo_deployments"
    
    # Template and instance references
    template_id = Column(UUID(as_uuid=True), nullable=False)
    instance_id = Column(UUID(as_uuid=True), nullable=True)  # Will be set after successful deployment
    vps_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Deployment information
    deployment_name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    selected_version = Column(String, nullable=False)
    
    # Deployment status
    status = Column(String, default="pending", nullable=False)  # pending, deploying, completed, failed, rollback
    progress = Column(Integer, default=0, nullable=False)  # 0-100 percentage
    
    # Deployment configuration
    port = Column(Integer, nullable=False)
    db_name = Column(String, nullable=False)
    admin_password = Column(String, nullable=True)  # Encrypted
    
    # Customizations
    selected_modules = Column(JSON, nullable=True)  # Modules to install
    custom_config = Column(JSON, nullable=True)  # Custom configuration overrides
    custom_env_vars = Column(JSON, nullable=True)  # Custom environment variables
    
    # Deployment logs and details
    deployment_logs = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Deployed by
    deployed_by = Column(UUID(as_uuid=True), nullable=False)  # Admin who initiated deployment
    
    # Rollback information
    can_rollback = Column(Boolean, default=False, nullable=False)
    rollback_point = Column(String, nullable=True)  # Snapshot or backup point for rollback
    
    def __repr__(self):
        return f"<OdooDeployment(deployment_name='{self.deployment_name}', status='{self.status}', progress={self.progress})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if deployment is completed successfully"""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Check if deployment failed"""
        return self.status == "failed"
    
    @property
    def is_in_progress(self) -> bool:
        """Check if deployment is currently in progress"""
        return self.status in ["pending", "deploying"]
    
    @property
    def duration_seconds(self) -> int:
        """Get deployment duration in seconds"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return 0