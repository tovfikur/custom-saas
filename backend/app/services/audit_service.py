from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from app.models.audit_log import AuditLog
from app.core.security import sanitize_error_message


class AuditService:
    """Service for comprehensive audit logging"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        task_id: str,
        action: str,
        resource_type: str,
        description: str,
        actor_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        status: str = "pending"
    ) -> AuditLog:
        """Log a new action"""
        
        audit_log = AuditLog(
            task_id=task_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            actor_ip=actor_ip,
            user_agent=user_agent,
            description=description,
            details=details,
            status=status,
            started_at=datetime.now(timezone.utc),
            context=context
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        
        return audit_log
    
    async def complete_action(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[AuditLog]:
        """Complete an existing audit log entry"""
        
        query = select(AuditLog).where(AuditLog.task_id == task_id)
        result_obj = await self.db.execute(query)
        audit_log = result_obj.scalar_one_or_none()
        
        if audit_log:
            audit_log.status = status
            audit_log.completed_at = datetime.now(timezone.utc)
            audit_log.result = result
            
            if error_message:
                # Sanitize error message before storing
                sanitized = sanitize_error_message(error_message, task_id)
                audit_log.error_message = sanitized["error"]
            
            # Calculate duration
            if audit_log.started_at:
                duration = (audit_log.completed_at - audit_log.started_at).total_seconds()
                audit_log.duration_seconds = int(duration)
            
            await self.db.commit()
            await self.db.refresh(audit_log)
        
        return audit_log
    
    async def get_audit_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get audit logs with filtering"""
        
        query = select(AuditLog)
        
        # Apply filters
        conditions = []
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if actor_id:
            conditions.append(AuditLog.actor_id == actor_id)
        if status:
            conditions.append(AuditLog.status == status)
        if start_date:
            conditions.append(AuditLog.started_at >= start_date)
        if end_date:
            conditions.append(AuditLog.started_at <= end_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by most recent first
        query = query.order_by(desc(AuditLog.started_at))
        
        # Get total count for pagination
        count_query = select(AuditLog.id)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        count_result = await self.db.execute(count_query)
        total_count = len(count_result.scalars().all())
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        return {
            "logs": [
                {
                    "id": str(log.id),
                    "task_id": log.task_id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id) if log.resource_id else None,
                    "actor_id": str(log.actor_id) if log.actor_id else None,
                    "actor_ip": log.actor_ip,
                    "description": log.description,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "duration_seconds": log.duration_seconds,
                    "error_message": log.error_message,
                    "details": log.details,
                    "is_sensitive": log.is_sensitive_action
                }
                for log in logs
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
    
    async def get_audit_log_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit log by task ID"""
        
        query = select(AuditLog).where(AuditLog.task_id == task_id)
        result = await self.db.execute(query)
        log = result.scalar_one_or_none()
        
        if not log:
            return None
        
        return {
            "id": str(log.id),
            "task_id": log.task_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "actor_ip": log.actor_ip,
            "user_agent": log.user_agent,
            "description": log.description,
            "status": log.status,
            "started_at": log.started_at.isoformat(),
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "duration_seconds": log.duration_seconds,
            "error_message": log.error_message,
            "details": log.details,
            "context": log.context,
            "result": log.result,
            "is_sensitive": log.is_sensitive_action
        }
    
    async def get_recent_failures(
        self,
        resource_type: Optional[str] = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent failed actions for monitoring"""
        
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        query = select(AuditLog).where(
            and_(
                AuditLog.status == "failed",
                AuditLog.started_at >= start_time
            )
        )
        
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        
        query = query.order_by(desc(AuditLog.started_at)).limit(limit)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        return [
            {
                "task_id": log.task_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "description": log.description,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat(),
                "actor_id": str(log.actor_id) if log.actor_id else None
            }
            for log in logs
        ]