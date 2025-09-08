from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.services.vps_service import VPSService
from app.services.ssh_service import SSHService
from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class VPSOnboardRequest(BaseModel):
    name: str = Field(..., description="VPS name")
    hostname: str = Field(..., description="VPS hostname")
    ip_address: str = Field(..., description="VPS IP address")
    username: str = Field(..., description="SSH username")
    port: int = Field(default=22, description="SSH port")
    password: Optional[str] = Field(None, description="SSH password")
    private_key: Optional[str] = Field(None, description="SSH private key")
    bootstrap: bool = Field(default=True, description="Run bootstrap after onboarding")


class VPSResponse(BaseModel):
    id: str
    name: str
    hostname: str
    ip_address: str
    status: str
    last_ping: Optional[str]
    last_successful_connection: Optional[str]
    docker_version: Optional[str]
    nginx_version: Optional[str]
    max_odoo_instances: int
    created_at: str
    is_healthy: bool


class VPSHealthResponse(BaseModel):
    success: bool
    task_id: str
    status: str
    services: dict


@router.post("/vps/onboard")
async def onboard_vps(
    request_data: VPSOnboardRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Onboard a new VPS with optional bootstrap"""
    try:
        print("Onboarding VPS with data:", request_data)
        audit_service = AuditService(db)
        print("Initialized audit service")
        ssh_service = SSHService()
        print("Initialized SSH service")
        vps_service = VPSService(db, ssh_service, audit_service)
        print("Initialized services")
        # Validate that we have either password or private key
        if not request_data.password and not request_data.private_key:
            print("No password or private key provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either password or private_key must be provided"
            )
        print("Validated credentials")
        result = await vps_service.onboard_vps(
            name=request_data.name,
            hostname=request_data.hostname,
            ip_address=request_data.ip_address,
            username=request_data.username,
            actor_id=str(current_admin.id),
            port=request_data.port,
            password=request_data.password,
            private_key=request_data.private_key,
            bootstrap=request_data.bootstrap
        )
        print("Onboard result:", result)
        if result["success"]:
            return result
        else:
            # Extract detailed error from bootstrap result if available
            error_detail = result.get("error", "Onboarding failed")
            
            # If it's a bootstrap failure, provide more helpful error message
            if "bootstrap failed" in result.get("message", "").lower():
                bootstrap_result = result.get("bootstrap_result", {})
                failed_steps = [step for step in bootstrap_result.get("steps", []) if not step.get("success")]
                
                if failed_steps:
                    step_errors = []
                    for step in failed_steps:
                        step_name = step.get("step", "unknown")
                        step_error = step.get("error", "Unknown error")
                        step_errors.append(f"{step_name}: {step_error}")
                    
                    error_detail = f"Bootstrap failed - {'; '.join(step_errors)}"
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to onboard VPS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to onboard VPS"
        )


@router.post("/vps/{vps_id}/bootstrap")
async def bootstrap_vps(
    vps_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Bootstrap an existing VPS with Docker and Nginx"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        vps_service = VPSService(db, ssh_service, audit_service)
        
        result = await vps_service.bootstrap_vps(vps_id, str(current_admin.id))
        
        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Bootstrap failed")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bootstrap VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bootstrap VPS"
        )


@router.get("/vps", response_model=List[VPSResponse])
async def list_vps(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """List all VPS hosts"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        vps_service = VPSService(db, ssh_service, audit_service)
        
        vps_list = await vps_service.get_vps_list(active_only=active_only)
        
        return [VPSResponse(**vps) for vps in vps_list]
        
    except Exception as e:
        logger.error(f"Failed to list VPS hosts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve VPS list"
        )


@router.post("/vps/{vps_id}/health", response_model=VPSHealthResponse)
async def check_vps_health(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Check VPS health status"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        vps_service = VPSService(db, ssh_service, audit_service)
        
        result = await vps_service.check_vps_health(vps_id)
        
        return VPSHealthResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to check VPS {vps_id} health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check VPS health"
        )


@router.get("/vps/{vps_id}")
async def get_vps_details(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get detailed VPS information"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        vps_service = VPSService(db, ssh_service, audit_service)
        
        # Get VPS info
        vps_list = await vps_service.get_vps_list()
        vps = next((v for v in vps_list if v["id"] == vps_id), None)
        
        if not vps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="VPS not found"
            )
        
        # Get health status
        health_result = await vps_service.check_vps_health(vps_id)
        
        # Get recent audit logs
        recent_logs = await audit_service.get_audit_logs(
            limit=10,
            resource_type="vps_host",
            resource_id=vps_id
        )
        
        return {
            "vps": vps,
            "health": health_result,
            "recent_activities": recent_logs["logs"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get VPS {vps_id} details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve VPS details"
        )


@router.delete("/vps/{vps_id}")
async def delete_vps(
    vps_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Delete a VPS host (WARNING: This will remove all associated data)"""
    try:
        from sqlalchemy import select
        from app.models.vps_host import VPSHost
        from app.core.security import generate_secure_token
        
        # Get VPS
        query = select(VPSHost).where(VPSHost.id == vps_id)
        result = await db.execute(query)
        vps = result.scalar_one_or_none()
        
        if not vps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="VPS not found"
            )
        
        # Log deletion
        audit_service = AuditService(db)
        task_id = generate_secure_token(8)
        
        await audit_service.log_action(
            task_id=task_id,
            action="vps_delete",
            resource_type="vps_host",
            resource_id=vps.id,
            actor_id=str(current_admin.id),
            actor_ip=request.client.host if request.client else None,
            description=f"Deleting VPS {vps.name} ({vps.ip_address})",
            details={
                "vps_name": vps.name,
                "ip_address": vps.ip_address,
                "hostname": vps.hostname
            }
        )
        
        # Delete VPS (cascade will handle related records)
        await db.delete(vps)
        await db.commit()
        
        await audit_service.complete_action(task_id, "success")
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"VPS {vps.name} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete VPS"
        )