from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.services.nginx_config_service import NginxConfigService
from app.services.audit_service import AuditService
from app.core.security import generate_secure_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request/response
class NginxConfigPreviewRequest(BaseModel):
    content: str = Field(..., description="Nginx configuration content")
    vps_id: str = Field(..., description="VPS ID")
    config_name: str = Field(default="default", description="Configuration name")
    config_type: str = Field(default="server_block", description="Configuration type")


class NginxConfigCreateRequest(BaseModel):
    content: str = Field(..., description="Nginx configuration content")
    vps_id: str = Field(..., description="VPS ID")
    config_name: str = Field(..., description="Configuration name")
    config_type: str = Field(default="server_block", description="Configuration type")
    summary: Optional[str] = Field(None, description="Summary of changes")
    template_used: Optional[str] = Field(None, description="Template used")


class NginxConfigApplyRequest(BaseModel):
    config_id: str = Field(..., description="Configuration ID to apply")
    dry_run: bool = Field(default=False, description="Perform dry run only")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule apply for later")
    watch_window_seconds: int = Field(default=120, description="Watch window for auto-rollback")


class NginxConfigRevertRequest(BaseModel):
    vps_id: str = Field(..., description="VPS ID")
    target_version: Optional[int] = Field(None, description="Target version to revert to")


class NginxConfigResponse(BaseModel):
    id: str
    version: int
    author_id: str
    summary: Optional[str]
    status: str
    config_name: str
    config_type: str
    applied_at: Optional[str]
    created_at: str
    is_active: bool
    rollback_triggered: bool


class ValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    task_id: str
    nginx_test_output: Optional[str] = None


@router.get("/vps/{vps_id}/nginx/configs", response_model=List[NginxConfigResponse])
async def list_nginx_configs(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """List all nginx configuration versions for a VPS"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        configs = await nginx_service.get_config_versions(vps_id)
        
        return [NginxConfigResponse(**config) for config in configs]
        
    except Exception as e:
        logger.error(f"Failed to list nginx configs for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration list"
        )


@router.get("/vps/{vps_id}/nginx/configs/{version}")
async def get_nginx_config(
    vps_id: str,
    version: int,
    mask_sensitive: bool = True,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get specific nginx configuration version content"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Get config by version
        configs = await nginx_service.get_config_versions(vps_id)
        config = next((c for c in configs if c["version"] == version), None)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuration version not found"
            )
        
        content = await nginx_service.get_config_content(config["id"], mask_sensitive)
        
        return {
            "config": config,
            "content": content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get nginx config {vps_id}/{version}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration"
        )


@router.post("/vps/{vps_id}/nginx/preview", response_model=ValidationResponse)
async def preview_nginx_config(
    vps_id: str,
    request_data: NginxConfigPreviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Preview and validate nginx configuration without applying"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Log preview action
        task_id = generate_secure_token(8)
        await audit_service.log_action(
            task_id=task_id,
            action="nginx_config_preview",
            resource_type="nginx_config",
            actor_id=str(current_admin.id),
            actor_ip=request.client.host if request.client else None,
            description=f"Previewing nginx config for VPS {vps_id}",
            details={
                "vps_id": vps_id,
                "config_name": request_data.config_name,
                "config_type": request_data.config_type,
                "content_length": len(request_data.content)
            }
        )
        
        # Validate configuration
        validation_result = await nginx_service.validate_config(
            vps_id, request_data.content, dry_run=True
        )
        
        # Complete audit log
        await audit_service.complete_action(
            task_id,
            "success" if validation_result.is_valid else "failed",
            result={
                "is_valid": validation_result.is_valid,
                "error_count": len(validation_result.errors),
                "warning_count": len(validation_result.warnings)
            }
        )
        
        return ValidationResponse(
            is_valid=validation_result.is_valid,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            task_id=validation_result.task_id,
            nginx_test_output=validation_result.nginx_test_output
        )
        
    except Exception as e:
        logger.error(f"Failed to preview nginx config for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview configuration"
        )


@router.post("/vps/{vps_id}/nginx/configs")
async def create_nginx_config(
    vps_id: str,
    request_data: NginxConfigCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Create new nginx configuration version"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Log creation action
        task_id = generate_secure_token(8)
        await audit_service.log_action(
            task_id=task_id,
            action="nginx_config_create",
            resource_type="nginx_config",
            actor_id=str(current_admin.id),
            actor_ip=request.client.host if request.client else None,
            description=f"Creating nginx config version for VPS {vps_id}",
            details={
                "vps_id": vps_id,
                "config_name": request_data.config_name,
                "config_type": request_data.config_type,
                "summary": request_data.summary,
                "template_used": request_data.template_used
            }
        )
        
        # Create configuration version
        config = await nginx_service.create_config_version(
            vps_id=vps_id,
            content=request_data.content,
            author_id=str(current_admin.id),
            summary=request_data.summary,
            config_name=request_data.config_name,
            config_type=request_data.config_type,
            template_used=request_data.template_used
        )
        
        # Complete audit log
        await audit_service.complete_action(
            task_id,
            "success",
            result={
                "config_id": str(config.id),
                "version": config.version
            }
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "config_id": str(config.id),
            "version": config.version,
            "message": "Configuration version created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create nginx config for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create configuration"
        )


@router.post("/vps/{vps_id}/nginx/apply")
async def apply_nginx_config(
    vps_id: str,
    request_data: NginxConfigApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Apply nginx configuration with safety checks"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Apply configuration
        result = await nginx_service.apply_config(
            config_id=request_data.config_id,
            author_id=str(current_admin.id),
            dry_run=request_data.dry_run,
            scheduled_at=request_data.scheduled_at,
            watch_window_seconds=request_data.watch_window_seconds
        )
        
        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to apply configuration")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply nginx config {request_data.config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply configuration"
        )


@router.post("/vps/{vps_id}/nginx/revert")
async def revert_nginx_config(
    vps_id: str,
    request_data: NginxConfigRevertRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Revert to previous nginx configuration version"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Perform rollback
        result = await nginx_service.rollback_config(
            vps_id=vps_id,
            target_version=request_data.target_version,
            author_id=str(current_admin.id)
        )
        
        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to revert configuration")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revert nginx config for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revert configuration"
        )


@router.get("/vps/{vps_id}/nginx/status")
async def get_nginx_status(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get current nginx status and configuration info for a VPS"""
    try:
        audit_service = AuditService(db)
        nginx_service = NginxConfigService(db, audit_service=audit_service)
        
        # Get current configs
        configs = await nginx_service.get_config_versions(vps_id)
        active_configs = [c for c in configs if c["is_active"]]
        
        # Get recent audit logs
        recent_logs = await audit_service.get_recent_failures(
            resource_type="nginx_config", hours=24, limit=10
        )
        
        return {
            "vps_id": vps_id,
            "active_configs": active_configs,
            "total_versions": len(configs),
            "recent_failures": [
                log for log in recent_logs 
                if log.get("details", {}).get("vps_id") == vps_id
            ],
            "last_activity": configs[0]["created_at"] if configs else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get nginx status for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve nginx status"
        )


@router.get("/nginx/templates")
async def list_nginx_templates(
    current_admin: Admin = Depends(get_current_active_admin)
):
    """List available nginx configuration templates"""
    # This would be implemented to return predefined templates
    # For now, returning a basic set
    templates = [
        {
            "name": "basic_server_block",
            "display_name": "Basic Server Block",
            "description": "Basic nginx server block with proxy_pass",
            "category": "server_block",
            "template": """server {
    listen 80;
    server_name {{ domain }};
    
    location / {
        proxy_pass http://{{ upstream_host }}:{{ upstream_port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}"""
        },
        {
            "name": "ssl_server_block",
            "display_name": "SSL Server Block",
            "description": "Server block with SSL/TLS configuration",
            "category": "server_block",
            "template": """server {
    listen 443 ssl http2;
    server_name {{ domain }};
    
    ssl_certificate {{ ssl_cert_path }};
    ssl_certificate_key {{ ssl_key_path }};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://{{ upstream_host }}:{{ upstream_port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name {{ domain }};
    return 301 https://$server_name$request_uri;
}"""
        },
        {
            "name": "load_balancer",
            "display_name": "Load Balancer",
            "description": "Load balancer with multiple upstream servers",
            "category": "upstream",
            "template": """upstream {{ upstream_name }} {
    {{ #servers }}
    server {{ host }}:{{ port }}{{ #weight }} weight={{ weight }}{{ /weight }};
    {{ /servers }}
}

server {
    listen 80;
    server_name {{ domain }};
    
    location / {
        proxy_pass http://{{ upstream_name }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}"""
        }
    ]
    
    return {"templates": templates}