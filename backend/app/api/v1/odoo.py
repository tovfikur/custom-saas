from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
from datetime import datetime
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.models.odoo_template import OdooTemplate, OdooDeployment
from app.services.odoo_deployment_service import OdooDeploymentService
import logging
import json
import os

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for templates
class OdooTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    version: str = Field(..., pattern="^(13|14|15|16|17|latest)$")
    description: Optional[str] = None
    
    # Database backup credentials
    backup_db_name: Optional[str] = None
    backup_db_user: Optional[str] = None
    backup_db_password: Optional[str] = None
    backup_db_host: Optional[str] = Field(default="localhost")
    backup_db_port: Optional[int] = Field(default=5432)
    
    # Template configuration
    docker_image: Optional[str] = None
    default_modules: Optional[List[str]] = None
    config_template: Optional[Dict[str, Any]] = None
    env_vars_template: Optional[Dict[str, Any]] = None
    is_public: bool = False
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    complexity_level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")
    setup_instructions: Optional[str] = None
    post_install_script: Optional[str] = None
    required_addons: Optional[List[str]] = None
    screenshots: Optional[List[str]] = None
    demo_url: Optional[str] = None
    documentation_url: Optional[str] = None


class OdooTemplateResponse(BaseModel):
    id: str
    name: str
    industry: str
    version: str
    description: Optional[str]
    is_active: bool
    is_public: bool
    deployment_count: int
    download_count: int
    backup_file_size_mb: int
    category: Optional[str]
    complexity_level: str
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class OdooTemplateListResponse(BaseModel):
    templates: List[OdooTemplateResponse]
    total: int
    page: int
    per_page: int


# Pydantic models for deployments
class OdooDeploymentCreate(BaseModel):
    template_id: str
    vps_id: str
    deployment_name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    selected_version: Optional[str] = Field(None, pattern="^(13|14|15|16|17|latest)$")
    selected_modules: Optional[List[str]] = None
    custom_config: Optional[Dict[str, Any]] = None
    custom_env_vars: Optional[Dict[str, Any]] = None
    admin_password: Optional[str] = None


class OdooDeploymentResponse(BaseModel):
    id: str
    template_id: str
    instance_id: Optional[str]
    vps_id: str
    deployment_name: str
    domain: str
    selected_version: str
    status: str
    progress: int
    port: int
    db_name: str
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: int
    deployed_by: str
    created_at: datetime


class OdooDeploymentListResponse(BaseModel):
    deployments: List[OdooDeploymentResponse]
    total: int
    page: int
    per_page: int


# Template endpoints
@router.get("/templates", response_model=OdooTemplateListResponse)
async def get_templates(
    industry: Optional[str] = Query(None),
    version: Optional[str] = Query(None, pattern="^(13|14|15|16|17|latest)$"),
    is_public: Optional[bool] = Query(True),
    category: Optional[str] = Query(None),
    complexity_level: Optional[str] = Query(None, pattern="^(beginner|intermediate|advanced)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Odoo templates with filtering"""
    try:
        service = OdooDeploymentService(db)
        result = await service.get_templates(
            industry=industry,
            version=version,
            is_public=is_public,
            page=page,
            per_page=per_page
        )
        
        templates = []
        for template in result["templates"]:
            templates.append(OdooTemplateResponse(
                id=str(template.id),
                name=template.name,
                industry=template.industry,
                version=template.version,
                description=template.description,
                is_active=template.is_active,
                is_public=template.is_public,
                deployment_count=template.deployment_count,
                download_count=template.download_count,
                backup_file_size_mb=template.backup_file_size_mb,
                category=template.category,
                complexity_level=template.complexity_level,
                tags=template.tags or [],
                created_at=template.created_at,
                updated_at=template.updated_at
            ))
        
        return OdooTemplateListResponse(
            templates=templates,
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get templates"
        )


@router.post("/templates", response_model=OdooTemplateResponse)
async def create_template(
    name: str = Form(...),
    industry: str = Form(...),
    version: str = Form(...),
    description: str = Form(None),
    backup_db_name: str = Form(None),
    backup_db_user: str = Form(None),
    backup_db_password: str = Form(None),
    backup_db_host: str = Form("localhost"),
    backup_db_port: int = Form(5432),
    backup_file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Create a new Odoo template"""
    try:
        service = OdooDeploymentService(db)
        
        # Handle backup file upload
        backup_file_path = None
        if backup_file and backup_file.filename:
            # Create uploads directory if it doesn't exist
            import os
            uploads_dir = "/app/uploads/templates"
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Generate secure filename
            import uuid
            file_extension = backup_file.filename.split('.')[-1] if '.' in backup_file.filename else ''
            secure_filename = f"{uuid.uuid4()}.{file_extension}"
            backup_file_path = os.path.join(uploads_dir, secure_filename)
            
            # Save the file
            with open(backup_file_path, "wb") as buffer:
                content = await backup_file.read()
                buffer.write(content)
        
        created_template = await service.create_template(
            name=name,
            industry=industry,
            version=version,
            backup_file_path=backup_file_path,
            admin_id=str(current_admin.id),
            backup_db_name=backup_db_name,
            backup_db_user=backup_db_user,
            backup_db_password=backup_db_password,
            backup_db_host=backup_db_host,
            backup_db_port=backup_db_port,
            description=description,
            is_public=False,
            category="business",
            complexity_level="beginner"
        )
        
        if not created_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create template"
            )
        
        return OdooTemplateResponse(
            id=str(created_template.id),
            name=created_template.name,
            industry=created_template.industry,
            version=created_template.version,
            description=created_template.description,
            is_active=created_template.is_active,
            is_public=created_template.is_public,
            deployment_count=created_template.deployment_count,
            download_count=created_template.download_count,
            backup_file_size_mb=created_template.backup_file_size_mb,
            category=created_template.category,
            complexity_level=created_template.complexity_level,
            tags=created_template.tags or [],
            created_at=created_template.created_at,
            updated_at=created_template.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template"
        )


@router.get("/templates/{template_id}", response_model=OdooTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get a specific template"""
    try:
        service = OdooDeploymentService(db)
        template = await service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        return OdooTemplateResponse(
            id=str(template.id),
            name=template.name,
            industry=template.industry,
            version=template.version,
            description=template.description,
            is_active=template.is_active,
            is_public=template.is_public,
            deployment_count=template.deployment_count,
            download_count=template.download_count,
            backup_file_size_mb=template.backup_file_size_mb,
            category=template.category,
            complexity_level=template.complexity_level,
            tags=template.tags or [],
            created_at=template.created_at,
            updated_at=template.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get template"
        )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Delete a template"""
    try:
        service = OdooDeploymentService(db)
        success = await service.delete_template(template_id, str(current_admin.id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        return {"message": "Template deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        )


# Deployment endpoints
@router.get("/deployments", response_model=OdooDeploymentListResponse)
async def get_deployments(
    vps_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|deploying|completed|failed|rollback)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get deployments with filtering"""
    try:
        service = OdooDeploymentService(db)
        result = await service.get_deployments(
            vps_id=vps_id,
            status=status,
            page=page,
            per_page=per_page
        )
        
        deployments = []
        for deployment in result["deployments"]:
            deployments.append(OdooDeploymentResponse(
                id=str(deployment.id),
                template_id=str(deployment.template_id),
                instance_id=str(deployment.instance_id) if deployment.instance_id else None,
                vps_id=str(deployment.vps_id),
                deployment_name=deployment.deployment_name,
                domain=deployment.domain,
                selected_version=deployment.selected_version,
                status=deployment.status,
                progress=deployment.progress,
                port=deployment.port,
                db_name=deployment.db_name,
                error_message=deployment.error_message,
                started_at=deployment.started_at,
                completed_at=deployment.completed_at,
                duration_seconds=deployment.duration_seconds,
                deployed_by=str(deployment.deployed_by),
                created_at=deployment.created_at
            ))
        
        return OdooDeploymentListResponse(
            deployments=deployments,
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get deployments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get deployments"
        )


@router.post("/deployments", response_model=OdooDeploymentResponse)
async def deploy_odoo(
    deployment_data: OdooDeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Deploy an Odoo instance from a template"""
    try:
        service = OdooDeploymentService(db)
        
        deployment = await service.deploy_odoo(
            template_id=deployment_data.template_id,
            vps_id=deployment_data.vps_id,
            deployment_name=deployment_data.deployment_name,
            domain=deployment_data.domain,
            admin_id=str(current_admin.id),
            selected_version=deployment_data.selected_version,
            selected_modules=deployment_data.selected_modules,
            custom_config=deployment_data.custom_config,
            custom_env_vars=deployment_data.custom_env_vars,
            admin_password=deployment_data.admin_password
        )
        
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create deployment"
            )
        
        return OdooDeploymentResponse(
            id=str(deployment.id),
            template_id=str(deployment.template_id),
            instance_id=str(deployment.instance_id) if deployment.instance_id else None,
            vps_id=str(deployment.vps_id),
            deployment_name=deployment.deployment_name,
            domain=deployment.domain,
            selected_version=deployment.selected_version,
            status=deployment.status,
            progress=deployment.progress,
            port=deployment.port,
            db_name=deployment.db_name,
            error_message=deployment.error_message,
            started_at=deployment.started_at,
            completed_at=deployment.completed_at,
            duration_seconds=deployment.duration_seconds,
            deployed_by=str(deployment.deployed_by),
            created_at=deployment.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy Odoo: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy Odoo: {str(e)}"
        )


@router.get("/deployments/{deployment_id}", response_model=OdooDeploymentResponse)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get a specific deployment"""
    try:
        service = OdooDeploymentService(db)
        deployment = await service.get_deployment(deployment_id)
        
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deployment not found"
            )
        
        return OdooDeploymentResponse(
            id=str(deployment.id),
            template_id=str(deployment.template_id),
            instance_id=str(deployment.instance_id) if deployment.instance_id else None,
            vps_id=str(deployment.vps_id),
            deployment_name=deployment.deployment_name,
            domain=deployment.domain,
            selected_version=deployment.selected_version,
            status=deployment.status,
            progress=deployment.progress,
            port=deployment.port,
            db_name=deployment.db_name,
            error_message=deployment.error_message,
            started_at=deployment.started_at,
            completed_at=deployment.completed_at,
            duration_seconds=deployment.duration_seconds,
            deployed_by=str(deployment.deployed_by),
            created_at=deployment.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deployment {deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get deployment"
        )


@router.delete("/deployments/{deployment_id}")
async def delete_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Delete a deployment"""
    try:
        service = OdooDeploymentService(db)
        success = await service.delete_deployment(deployment_id, str(current_admin.id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deployment not found"
            )
        
        return {"success": True, "message": "Deployment deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete deployment {deployment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete deployment"
        )


# Additional endpoints for managing templates
@router.get("/industries")
async def get_industries(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get list of available industries"""
    # This could be dynamic based on existing templates or predefined
    industries = [
        "healthcare",
        "retail",
        "manufacturing",
        "education",
        "finance",
        "real_estate",
        "hospitality",
        "logistics",
        "construction",
        "consulting",
        "non_profit",
        "government",
        "other"
    ]
    return {"industries": industries}


@router.get("/versions")
async def get_odoo_versions(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get list of supported Odoo versions"""
    versions = [
        {"version": "17", "name": "Odoo 17 (Latest)", "is_lts": False},
        {"version": "16", "name": "Odoo 16", "is_lts": False},
        {"version": "15", "name": "Odoo 15", "is_lts": False},
        {"version": "14", "name": "Odoo 14", "is_lts": False},
        {"version": "13", "name": "Odoo 13", "is_lts": False},
        {"version": "latest", "name": "Latest (17)", "is_lts": False}
    ]
    return {"versions": versions}


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get list of available categories"""
    categories = [
        "ERP",
        "CRM",
        "Manufacturing",
        "Inventory",
        "Accounting",
        "HR",
        "Project Management",
        "E-commerce",
        "Website Builder",
        "Marketing",
        "Sales",
        "Custom"
    ]
    return {"categories": categories}