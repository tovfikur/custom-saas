import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.worker import celery_app
from app.core.database import AsyncSessionLocal
from app.models.docker_schedule import DockerSchedule, DockerScheduleExecution
from app.services.docker_service import DockerService
from app.services.ssh_service import SSHService
from app.services.audit_service import AuditService
from app.core.security import generate_secure_token
from croniter import croniter

logger = logging.getLogger(__name__)


class DockerScheduleTask(Task):
    """Base task for Docker schedule operations"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Docker schedule task {task_id} failed: {exc}")
        
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Docker schedule task {task_id} completed successfully")


@celery_app.task(base=DockerScheduleTask, bind=True, max_retries=3)
def execute_docker_schedule(self, execution_id: str):
    """Execute a scheduled Docker container action"""
    import asyncio
    return asyncio.run(_execute_docker_schedule(self, execution_id))


async def _execute_docker_schedule(task_self, execution_id: str) -> Dict[str, Any]:
    """Async implementation of Docker schedule execution"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Get execution record
            exec_query = select(DockerScheduleExecution).options(
                selectinload(DockerScheduleExecution.schedule).selectinload(DockerSchedule.vps_host)
            ).where(DockerScheduleExecution.id == execution_id)
            
            exec_result = await db.execute(exec_query)
            execution = exec_result.scalar_one_or_none()
            
            if not execution:
                logger.error(f"Execution {execution_id} not found")
                return {"success": False, "error": "Execution not found"}
            
            schedule = execution.schedule
            vps_host = schedule.vps_host
            
            # Mark execution as running
            execution.status = "running"
            execution.started_at = datetime.utcnow()
            await db.commit()
            
            # Mark schedule as running
            schedule.is_running = True
            await db.commit()
            
            # Set up services
            ssh_service = SSHService()
            audit_service = AuditService(db)
            docker_service = DockerService(ssh_service, audit_service)
            
            try:
                # Execute Docker action
                result = await docker_service.container_action(
                    vps_id=str(vps_host.id),
                    db=db,
                    container_id=schedule.container_id,
                    action=schedule.action,
                    actor_id=str(schedule.created_by)
                )
                
                # Update execution with results
                execution.completed_at = datetime.utcnow()
                execution.duration_seconds = int((execution.completed_at - execution.started_at).total_seconds())
                
                if result.get("success"):
                    execution.status = "success"
                    execution.stdout = f"Container {schedule.action} successful"
                    
                    # Update schedule success count
                    schedule.success_count += 1
                    
                else:
                    execution.status = "failed"
                    execution.error_message = result.get("message", "Unknown error")
                    execution.stderr = result.get("message", "")
                    
                    # Update schedule failure count
                    schedule.failure_count += 1
                
            except Exception as e:
                logger.error(f"Docker action failed: {e}")
                
                execution.status = "failed"
                execution.error_message = str(e)
                execution.stderr = str(e)
                execution.completed_at = datetime.utcnow()
                execution.duration_seconds = int((execution.completed_at - execution.started_at).total_seconds())
                
                schedule.failure_count += 1
            
            finally:
                # Update schedule statistics
                schedule.is_running = False
                schedule.run_count += 1
                schedule.last_run = execution.started_at
                
                # Calculate next run time
                schedule.next_run = await _calculate_next_run(schedule)
                
                await db.commit()
            
            return {
                "success": execution.status == "success",
                "status": execution.status,
                "duration": execution.duration_seconds,
                "message": execution.error_message or "Execution completed"
            }
            
        except Exception as e:
            logger.error(f"Failed to execute schedule {execution_id}: {e}")
            
            # Mark execution as failed if we can still access it
            try:
                if 'execution' in locals() and execution:
                    execution.status = "failed"
                    execution.error_message = str(e)
                    execution.completed_at = datetime.utcnow()
                    
                    if execution.started_at:
                        execution.duration_seconds = int((execution.completed_at - execution.started_at).total_seconds())
                    
                    if 'schedule' in locals() and schedule:
                        schedule.is_running = False
                        schedule.failure_count += 1
                    
                    await db.commit()
                    
            except Exception as commit_error:
                logger.error(f"Failed to update execution status: {commit_error}")
            
            # Retry logic
            if task_self.request.retries < task_self.max_retries:
                logger.info(f"Retrying execution {execution_id} (attempt {task_self.request.retries + 1})")
                
                # Update execution for retry
                if 'execution' in locals() and execution:
                    execution.status = "pending"
                    execution.is_retry = True
                    execution.attempt_number = task_self.request.retries + 2
                    await db.commit()
                
                # Retry with exponential backoff
                countdown = 60 * (2 ** task_self.request.retries)  # 60s, 120s, 240s
                raise task_self.retry(countdown=countdown)
            
            return {"success": False, "error": str(e)}


@celery_app.task(base=DockerScheduleTask)
def process_due_schedules():
    """Process all schedules that are due for execution"""
    import asyncio
    return asyncio.run(_process_due_schedules())


async def _process_due_schedules() -> Dict[str, Any]:
    """Async implementation of due schedules processing"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Get due schedules
            now = datetime.utcnow()
            
            due_query = select(DockerSchedule).where(
                DockerSchedule.is_active == True,
                DockerSchedule.is_running == False,
                DockerSchedule.next_run <= now
            ).limit(50)  # Process up to 50 schedules at a time
            
            result = await db.execute(due_query)
            due_schedules = result.scalars().all()
            
            executed_count = 0
            failed_count = 0
            
            for schedule in due_schedules:
                try:
                    # Create execution record
                    execution = DockerScheduleExecution(
                        schedule_id=schedule.id,
                        status="pending",
                        task_id=generate_secure_token(16)
                    )
                    
                    db.add(execution)
                    await db.commit()
                    await db.refresh(execution)
                    
                    # Queue execution task
                    execute_docker_schedule.delay(str(execution.id))
                    executed_count += 1
                    
                    logger.info(f"Queued execution for schedule {schedule.name} (ID: {schedule.id})")
                    
                except Exception as e:
                    logger.error(f"Failed to queue schedule {schedule.id}: {e}")
                    failed_count += 1
            
            return {
                "success": True,
                "processed": len(due_schedules),
                "executed": executed_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"Failed to process due schedules: {e}")
            return {"success": False, "error": str(e)}


@celery_app.task(base=DockerScheduleTask)
def cleanup_old_executions(days_to_keep: int = 30):
    """Clean up old schedule executions"""
    import asyncio
    return asyncio.run(_cleanup_old_executions(days_to_keep))


async def _cleanup_old_executions(days_to_keep: int) -> Dict[str, Any]:
    """Async implementation of execution cleanup"""
    
    async with AsyncSessionLocal() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old executions
            delete_query = select(DockerScheduleExecution).where(
                DockerScheduleExecution.created_at < cutoff_date
            )
            
            result = await db.execute(delete_query)
            old_executions = result.scalars().all()
            
            for execution in old_executions:
                await db.delete(execution)
            
            await db.commit()
            
            logger.info(f"Cleaned up {len(old_executions)} old schedule executions")
            
            return {
                "success": True,
                "cleaned": len(old_executions),
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup executions: {e}")
            return {"success": False, "error": str(e)}


async def _calculate_next_run(schedule: DockerSchedule) -> datetime:
    """Calculate the next run time for a schedule"""
    
    if schedule.schedule_type == "cron" and schedule.cron_expression:
        try:
            cron = croniter(schedule.cron_expression, datetime.utcnow())
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"Invalid cron expression for schedule {schedule.id}: {e}")
            
    elif schedule.schedule_type == "interval" and schedule.interval_seconds:
        return datetime.utcnow() + timedelta(seconds=schedule.interval_seconds)
        
    elif schedule.schedule_type == "once":
        # For one-time schedules, don't set next run
        return None
    
    # Default: run in 1 hour if we can't calculate
    return datetime.utcnow() + timedelta(hours=1)