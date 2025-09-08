from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.models.docker_schedule import DockerSchedule, DockerScheduleExecution
from app.models.vps_host import VPSHost
from app.services.docker_schedule_service import DockerScheduleService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models
class DockerScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    container_id: str
    container_name: str
    action: str = Field(..., pattern="^(start|stop|restart)$")
    schedule_type: str = Field(..., pattern="^(cron|interval|once)$")
    
    # Schedule configuration
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    
    # Options
    timeout_seconds: int = Field(default=300, ge=30, le=3600)  # 30s to 1 hour
    retry_count: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=10, le=300)
    tags: Optional[List[str]] = None
    is_active: bool = True
    
    @validator('scheduled_at')
    def normalize_timezone(cls, v):
        """Convert timezone-aware datetimes to timezone-naive UTC"""
        if v and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class DockerScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(start|stop|restart)$")
    schedule_type: Optional[str] = Field(None, pattern="^(cron|interval|once)$")
    
    # Schedule configuration
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    
    # Options
    timeout_seconds: Optional[int] = Field(None, ge=30, le=3600)
    retry_count: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=10, le=300)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    @validator('scheduled_at')
    def normalize_timezone(cls, v):
        """Convert timezone-aware datetimes to timezone-naive UTC"""
        if v and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class DockerScheduleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    vps_id: str
    vps_name: str
    container_id: str
    container_name: str
    action: str
    schedule_type: str
    cron_expression: Optional[str]
    interval_seconds: Optional[int]
    scheduled_at: Optional[datetime]
    is_active: bool
    is_running: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    run_count: int
    success_count: int
    failure_count: int
    timeout_seconds: int
    retry_count: int
    retry_delay_seconds: int
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    created_by: str


class DockerScheduleExecutionResponse(BaseModel):
    id: str
    schedule_id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    exit_code: Optional[int]
    error_message: Optional[str]
    attempt_number: int
    is_retry: bool
    task_id: Optional[str]
    created_at: datetime


class DockerScheduleListResponse(BaseModel):
    schedules: List[DockerScheduleResponse]
    total: int
    page: int
    per_page: int


@router.get("/vps/{vps_id}/schedules", response_model=DockerScheduleListResponse)
async def get_vps_schedules(
    vps_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    active_only: bool = Query(True),
    action_filter: Optional[str] = Query(None, pattern="^(start|stop|restart)$"),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Docker schedules for a specific VPS"""
    try:
        service = DockerScheduleService(db)
        
        result = await service.get_schedules(
            vps_id=vps_id,
            page=page,
            per_page=per_page,
            active_only=active_only,
            action_filter=action_filter
        )
        
        return DockerScheduleListResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get schedules for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get schedules"
        )


@router.post("/vps/{vps_id}/schedules", response_model=DockerScheduleResponse)
async def create_schedule(
    vps_id: str,
    schedule_data: DockerScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Create a new Docker container schedule"""
    try:
        service = DockerScheduleService(db)
        
        # Verify VPS exists
        vps_query = select(VPSHost).where(VPSHost.id == vps_id)
        vps_result = await db.execute(vps_query)
        vps = vps_result.scalar_one_or_none()
        
        if not vps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="VPS not found"
            )
        
        # Create schedule
        schedule_dict = schedule_data.dict()
        schedule = await service.create_schedule(
            vps_id=vps_id,
            creator_id=str(current_admin.id),
            name=schedule_dict['name'],
            container_id=schedule_dict['container_id'],
            container_name=schedule_dict['container_name'],
            action=schedule_dict['action'],
            schedule_type=schedule_dict['schedule_type'],
            description=schedule_dict.get('description'),
            cron_expression=schedule_dict.get('cron_expression'),
            interval_seconds=schedule_dict.get('interval_seconds'),
            scheduled_at=schedule_dict.get('scheduled_at'),
            timeout_seconds=schedule_dict.get('timeout_seconds', 300),
            retry_count=schedule_dict.get('retry_count', 3),
            retry_delay_seconds=schedule_dict.get('retry_delay_seconds', 60),
            tags=schedule_dict.get('tags'),
            is_active=schedule_dict.get('is_active', True)
        )
        
        return DockerScheduleResponse(
            id=str(schedule.id),
            name=schedule.name,
            description=schedule.description,
            vps_id=str(schedule.vps_id),
            vps_name=vps.name,
            container_id=schedule.container_id,
            container_name=schedule.container_name,
            action=schedule.action,
            schedule_type=schedule.schedule_type,
            cron_expression=schedule.cron_expression,
            interval_seconds=schedule.interval_seconds,
            scheduled_at=schedule.scheduled_at,
            is_active=schedule.is_active,
            is_running=schedule.is_running,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            success_count=schedule.success_count,
            failure_count=schedule.failure_count,
            timeout_seconds=schedule.timeout_seconds,
            retry_count=schedule.retry_count,
            retry_delay_seconds=schedule.retry_delay_seconds,
            tags=schedule.tags or [],
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            created_by=str(schedule.created_by)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create schedule: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )


@router.get("/schedules/{schedule_id}", response_model=DockerScheduleResponse)
async def get_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get a specific Docker schedule"""
    try:
        service = DockerScheduleService(db)
        schedule = await service.get_schedule(schedule_id)
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        return DockerScheduleResponse(
            id=str(schedule.id),
            name=schedule.name,
            description=schedule.description,
            vps_id=str(schedule.vps_id),
            vps_name=schedule.vps_host.name,
            container_id=schedule.container_id,
            container_name=schedule.container_name,
            action=schedule.action,
            schedule_type=schedule.schedule_type,
            cron_expression=schedule.cron_expression,
            interval_seconds=schedule.interval_seconds,
            scheduled_at=schedule.scheduled_at,
            is_active=schedule.is_active,
            is_running=schedule.is_running,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            success_count=schedule.success_count,
            failure_count=schedule.failure_count,
            timeout_seconds=schedule.timeout_seconds,
            retry_count=schedule.retry_count,
            retry_delay_seconds=schedule.retry_delay_seconds,
            tags=schedule.tags or [],
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            created_by=str(schedule.created_by)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get schedule"
        )


@router.put("/schedules/{schedule_id}", response_model=DockerScheduleResponse)
async def update_schedule(
    schedule_id: str,
    schedule_data: DockerScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Update a Docker schedule"""
    try:
        service = DockerScheduleService(db)
        schedule = await service.update_schedule(
            schedule_id=schedule_id,
            **schedule_data.dict(exclude_unset=True)
        )
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        return DockerScheduleResponse(
            id=str(schedule.id),
            name=schedule.name,
            description=schedule.description,
            vps_id=str(schedule.vps_id),
            vps_name=schedule.vps_host.name,
            container_id=schedule.container_id,
            container_name=schedule.container_name,
            action=schedule.action,
            schedule_type=schedule.schedule_type,
            cron_expression=schedule.cron_expression,
            interval_seconds=schedule.interval_seconds,
            scheduled_at=schedule.scheduled_at,
            is_active=schedule.is_active,
            is_running=schedule.is_running,
            last_run=schedule.last_run,
            next_run=schedule.next_run,
            run_count=schedule.run_count,
            success_count=schedule.success_count,
            failure_count=schedule.failure_count,
            timeout_seconds=schedule.timeout_seconds,
            retry_count=schedule.retry_count,
            retry_delay_seconds=schedule.retry_delay_seconds,
            tags=schedule.tags or [],
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            created_by=str(schedule.created_by)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update schedule"
        )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Delete a Docker schedule"""
    try:
        service = DockerScheduleService(db)
        success = await service.delete_schedule(schedule_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        return {"success": True, "message": "Schedule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete schedule"
        )


@router.post("/schedules/{schedule_id}/execute")
async def execute_schedule_now(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Execute a schedule immediately (manual trigger)"""
    try:
        service = DockerScheduleService(db)
        execution = await service.execute_schedule_now(schedule_id)
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        return {
            "success": True, 
            "message": "Schedule execution started",
            "execution_id": str(execution.id),
            "task_id": execution.task_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute schedule"
        )


@router.post("/schedules/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Toggle schedule active/inactive status"""
    try:
        service = DockerScheduleService(db)
        schedule = await service.toggle_schedule(schedule_id)
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        return {
            "success": True,
            "message": f"Schedule {'activated' if schedule.is_active else 'deactivated'}",
            "is_active": schedule.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle schedule"
        )


@router.get("/schedules/{schedule_id}/executions", response_model=List[DockerScheduleExecutionResponse])
async def get_schedule_executions(
    schedule_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get execution history for a specific schedule"""
    try:
        service = DockerScheduleService(db)
        executions = await service.get_schedule_executions(schedule_id, limit)
        
        return [
            DockerScheduleExecutionResponse(
                id=str(exec.id),
                **{k: v for k, v in exec.__dict__.items() if not k.startswith('_')}
            )
            for exec in executions
        ]
        
    except Exception as e:
        logger.error(f"Failed to get executions for schedule {schedule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get schedule executions"
        )