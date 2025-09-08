from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from croniter import croniter
from app.models.docker_schedule import DockerSchedule, DockerScheduleExecution
from app.models.vps_host import VPSHost
from app.core.security import generate_secure_token
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class DockerScheduleService:
    """Service for managing Docker container schedules"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
    
    async def create_schedule(
        self, 
        vps_id: str, 
        creator_id: str, 
        name: str,
        container_id: str,
        container_name: str,
        action: str,
        schedule_type: str,
        **kwargs
    ) -> DockerSchedule:
        """Create a new Docker schedule"""
        
        try:
            # Validate schedule configuration
            await self._validate_schedule_config(schedule_type, **kwargs)
            
            # Calculate next run time
            next_run = await self._calculate_next_run(schedule_type, **kwargs)
            
            # Create schedule
            schedule = DockerSchedule(
                name=name,
                vps_id=vps_id,
                container_id=container_id,
                container_name=container_name,
                action=action,
                schedule_type=schedule_type,
                created_by=creator_id,
                next_run=next_run,
                **kwargs
            )
            
            self.db.add(schedule)
            await self.db.commit()
            await self.db.refresh(schedule)
            
            # Log creation
            if self.audit_service:
                await self.audit_service.log_action(
                    task_id=generate_secure_token(8),
                    action="docker_schedule_create",
                    resource_type="docker_schedule",
                    resource_id=str(schedule.id),
                    actor_id=creator_id,
                    description=f"Created Docker schedule '{name}' for container {container_name}",
                    details={
                        "vps_id": vps_id,
                        "container_id": container_id,
                        "action": action,
                        "schedule_type": schedule_type
                    }
                )
            
            return schedule
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create schedule: {e}")
            raise
    
    async def get_schedule(self, schedule_id: str) -> Optional[DockerSchedule]:
        """Get a specific schedule by ID"""
        try:
            query = select(DockerSchedule).options(
                selectinload(DockerSchedule.vps_host)
            ).where(DockerSchedule.id == schedule_id)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}")
            raise
    
    async def get_schedules(
        self, 
        vps_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        active_only: bool = True,
        action_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Docker schedules with filtering and pagination"""
        try:
            # Build query conditions
            conditions = []
            
            if vps_id:
                conditions.append(DockerSchedule.vps_id == vps_id)
            if active_only:
                conditions.append(DockerSchedule.is_active == True)
            if action_filter:
                conditions.append(DockerSchedule.action == action_filter)
            
            # Count query
            count_query = select(func.count(DockerSchedule.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()
            
            # Main query with pagination
            query = select(DockerSchedule).options(
                selectinload(DockerSchedule.vps_host)
            ).order_by(desc(DockerSchedule.created_at))
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Apply pagination
            offset = (page - 1) * per_page
            query = query.limit(per_page).offset(offset)
            
            result = await self.db.execute(query)
            schedules = result.scalars().all()
            
            # Format response
            schedule_list = []
            for schedule in schedules:
                schedule_dict = {
                    "id": str(schedule.id),
                    "vps_name": schedule.vps_host.name if schedule.vps_host else "Unknown",
                    "created_by": str(schedule.created_by),
                    "tags": schedule.tags or [],
                    "name": schedule.name,
                    "description": schedule.description,
                    "vps_id": str(schedule.vps_id),
                    "container_id": schedule.container_id,
                    "container_name": schedule.container_name,
                    "action": schedule.action,
                    "schedule_type": schedule.schedule_type,
                    "cron_expression": schedule.cron_expression,
                    "interval_seconds": schedule.interval_seconds,
                    "scheduled_at": schedule.scheduled_at,
                    "is_active": schedule.is_active,
                    "is_running": schedule.is_running,
                    "last_run": schedule.last_run,
                    "next_run": schedule.next_run,
                    "run_count": schedule.run_count,
                    "success_count": schedule.success_count,
                    "failure_count": schedule.failure_count,
                    "timeout_seconds": schedule.timeout_seconds,
                    "retry_count": schedule.retry_count,
                    "retry_delay_seconds": schedule.retry_delay_seconds,
                    "created_at": schedule.created_at,
                    "updated_at": schedule.updated_at
                }
                schedule_list.append(schedule_dict)
            
            return {
                "schedules": schedule_list,
                "total": total,
                "page": page,
                "per_page": per_page
            }
            
        except Exception as e:
            logger.error(f"Failed to get schedules: {e}")
            raise
    
    async def update_schedule(self, schedule_id: str, **kwargs) -> Optional[DockerSchedule]:
        """Update an existing schedule"""
        try:
            # Get existing schedule
            query = select(DockerSchedule).options(
                selectinload(DockerSchedule.vps_host)
            ).where(DockerSchedule.id == schedule_id)
            
            result = await self.db.execute(query)
            schedule = result.scalar_one_or_none()
            
            if not schedule:
                return None
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(schedule, key) and value is not None:
                    setattr(schedule, key, value)
            
            # Recalculate next run if schedule config changed
            if any(key in kwargs for key in ['schedule_type', 'cron_expression', 'interval_seconds', 'scheduled_at']):
                schedule.next_run = await self._calculate_next_run(
                    schedule.schedule_type,
                    cron_expression=schedule.cron_expression,
                    interval_seconds=schedule.interval_seconds,
                    scheduled_at=schedule.scheduled_at
                )
            
            await self.db.commit()
            await self.db.refresh(schedule)
            
            return schedule
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update schedule {schedule_id}: {e}")
            raise
    
    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        try:
            query = select(DockerSchedule).where(DockerSchedule.id == schedule_id)
            result = await self.db.execute(query)
            schedule = result.scalar_one_or_none()
            
            if not schedule:
                return False
            
            await self.db.delete(schedule)
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete schedule {schedule_id}: {e}")
            raise
    
    async def toggle_schedule(self, schedule_id: str) -> Optional[DockerSchedule]:
        """Toggle schedule active status"""
        try:
            query = select(DockerSchedule).where(DockerSchedule.id == schedule_id)
            result = await self.db.execute(query)
            schedule = result.scalar_one_or_none()
            
            if not schedule:
                return None
            
            schedule.is_active = not schedule.is_active
            await self.db.commit()
            await self.db.refresh(schedule)
            
            return schedule
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to toggle schedule {schedule_id}: {e}")
            raise
    
    async def execute_schedule_now(self, schedule_id: str) -> Optional[DockerScheduleExecution]:
        """Execute a schedule immediately"""
        try:
            # Get schedule
            query = select(DockerSchedule).where(DockerSchedule.id == schedule_id)
            result = await self.db.execute(query)
            schedule = result.scalar_one_or_none()
            
            if not schedule:
                return None
            
            # Create execution record
            execution = DockerScheduleExecution(
                schedule_id=schedule.id,
                status="pending",
                task_id=generate_secure_token(16)
            )
            
            self.db.add(execution)
            await self.db.commit()
            await self.db.refresh(execution)
            
            # Queue Celery task for execution
            from app.tasks.docker_schedule_tasks import execute_docker_schedule
            execute_docker_schedule.delay(str(execution.id))
            
            return execution
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to execute schedule {schedule_id}: {e}")
            raise
    
    async def get_schedule_executions(
        self, 
        schedule_id: str, 
        limit: int = 50
    ) -> List[DockerScheduleExecution]:
        """Get execution history for a schedule"""
        try:
            query = select(DockerScheduleExecution).where(
                DockerScheduleExecution.schedule_id == schedule_id
            ).order_by(desc(DockerScheduleExecution.created_at)).limit(limit)
            
            result = await self.db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get executions for schedule {schedule_id}: {e}")
            raise
    
    async def get_due_schedules(self) -> List[DockerSchedule]:
        """Get schedules that are due for execution"""
        try:
            now = datetime.utcnow()
            
            query = select(DockerSchedule).where(
                and_(
                    DockerSchedule.is_active == True,
                    DockerSchedule.is_running == False,
                    DockerSchedule.next_run <= now
                )
            )
            
            result = await self.db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get due schedules: {e}")
            raise
    
    async def _validate_schedule_config(self, schedule_type: str, **kwargs):
        """Validate schedule configuration"""
        if schedule_type == "cron":
            cron_expr = kwargs.get("cron_expression")
            if not cron_expr:
                raise ValueError("Cron expression required for cron schedule type")
            
            try:
                croniter(cron_expr)  # Test if cron expression is valid
            except Exception:
                raise ValueError("Invalid cron expression")
                
        elif schedule_type == "interval":
            interval = kwargs.get("interval_seconds")
            if not interval or interval < 60:  # Minimum 1 minute interval
                raise ValueError("Interval must be at least 60 seconds")
                
        elif schedule_type == "once":
            scheduled_at = kwargs.get("scheduled_at")
            if not scheduled_at:
                raise ValueError("Scheduled datetime required for once schedule type")
            
            # Ensure both datetimes are timezone-naive UTC for comparison
            if hasattr(scheduled_at, 'tzinfo') and scheduled_at.tzinfo is not None:
                scheduled_utc = scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                scheduled_utc = scheduled_at if isinstance(scheduled_at, datetime) else datetime.fromisoformat(str(scheduled_at).replace('Z', '+00:00')).replace(tzinfo=None)
                
            # Ensure current time is also timezone-naive UTC
            current_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if scheduled_utc <= current_utc:
                raise ValueError("Scheduled time must be in the future")
    
    async def _calculate_next_run(self, schedule_type: str, **kwargs) -> Optional[datetime]:
        """Calculate the next run time for a schedule"""
        if schedule_type == "cron":
            cron_expr = kwargs.get("cron_expression")
            if cron_expr:
                cron = croniter(cron_expr, datetime.utcnow())
                return cron.get_next(datetime)
                
        elif schedule_type == "interval":
            interval = kwargs.get("interval_seconds")
            if interval:
                return datetime.utcnow() + timedelta(seconds=interval)
                
        elif schedule_type == "once":
            scheduled_at = kwargs.get("scheduled_at")
            if scheduled_at:
                # Ensure timezone-naive UTC datetime for consistency
                if hasattr(scheduled_at, 'tzinfo') and scheduled_at.tzinfo is not None:
                    return scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
                elif isinstance(scheduled_at, datetime):
                    return scheduled_at
                else:
                    # Handle string datetime formats
                    return datetime.fromisoformat(str(scheduled_at).replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
        
        return None