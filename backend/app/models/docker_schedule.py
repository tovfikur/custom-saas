from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import BaseModel


class DockerSchedule(Base, BaseModel):
    """Model for Docker container scheduling"""
    
    __tablename__ = "docker_schedules"
    
    # Basic info
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # VPS and container reference
    vps_id = Column(UUID(as_uuid=True), ForeignKey("vps_hosts.id"), nullable=False)
    container_id = Column(String, nullable=False)  # Docker container ID
    container_name = Column(String, nullable=False)  # Human-readable container name
    
    # Schedule configuration
    action = Column(String, nullable=False)  # start, stop, restart
    schedule_type = Column(String, nullable=False)  # cron, interval, once
    
    # Cron expression (for cron type)
    cron_expression = Column(String)  # e.g., "0 9 * * MON-FRI" (9 AM weekdays)
    
    # Interval configuration (for interval type)
    interval_seconds = Column(Integer)  # Run every X seconds
    
    # One-time schedule (for once type)
    scheduled_at = Column(DateTime(timezone=True))  # Specific datetime to run
    
    # Status and control
    is_active = Column(Boolean, default=True, nullable=False)
    is_running = Column(Boolean, default=False, nullable=False)  # Currently executing
    
    # Execution tracking
    last_run = Column(DateTime(timezone=True))
    next_run = Column(DateTime(timezone=True))
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    
    # Configuration
    timeout_seconds = Column(Integer, default=300)  # 5 minutes default timeout
    retry_count = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)  # 1 minute between retries
    
    # Additional metadata
    tags = Column(JSON)  # For categorization and filtering
    created_by = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    
    # Relationships
    vps_host = relationship("VPSHost", back_populates="docker_schedules")
    creator = relationship("Admin")
    executions = relationship("DockerScheduleExecution", back_populates="schedule", cascade="all, delete-orphan")


class DockerScheduleExecution(Base, BaseModel):
    """Model for tracking individual schedule executions"""
    
    __tablename__ = "docker_schedule_executions"
    
    # Reference to schedule
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("docker_schedules.id"), nullable=False)
    
    # Execution details
    status = Column(String, nullable=False)  # pending, running, success, failed, timeout
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    # Results
    stdout = Column(Text)
    stderr = Column(Text)
    exit_code = Column(Integer)
    error_message = Column(Text)
    
    # Retry information
    attempt_number = Column(Integer, default=1)
    is_retry = Column(Boolean, default=False)
    
    # Metadata
    task_id = Column(String)  # Celery task ID for tracking
    context = Column(JSON)  # Additional execution context
    
    # Relationships
    schedule = relationship("DockerSchedule", back_populates="executions")