from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, validator
from datetime import datetime
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.models.odoo_template import OdooTemplate, OdooDeployment
from app.models.vps_host import VPSHost
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
    # Database configuration
    db_name: Optional[str] = None
    db_user: Optional[str] = os.getenv("DB_USER", "odoo_master")
    db_password: Optional[str] = os.getenv("DB_PASSWORD", "secure_password_123")
    db_host: Optional[str] = os.getenv("DB_HOST_EXTERNAL", "192.168.50.2")
    db_port: Optional[int] = int(os.getenv("DB_PORT_EXTERNAL", "5433"))


class OdooDeploymentResponse(BaseModel):
    id: str
    template_id: str
    instance_id: Optional[str]
    vps_id: str
    deployment_name: str
    name: str  # alias for deployment_name for frontend compatibility
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
    # Additional fields for frontend display
    template_name: Optional[str] = None
    vps_name: Optional[str] = None


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
            # Fetch template name
            template_query = select(OdooTemplate).where(OdooTemplate.id == deployment.template_id)
            template_result = await db.execute(template_query)
            template = template_result.scalar_one_or_none()
            template_name = template.name if template else "Unknown Template"

            # Fetch VPS name
            vps_query = select(VPSHost).where(VPSHost.id == deployment.vps_id)
            vps_result = await db.execute(vps_query)
            vps = vps_result.scalar_one_or_none()
            vps_name = vps.name if vps else "Unknown VPS"

            deployments.append(OdooDeploymentResponse(
                id=str(deployment.id),
                template_id=str(deployment.template_id),
                instance_id=str(deployment.instance_id) if deployment.instance_id else None,
                vps_id=str(deployment.vps_id),
                deployment_name=deployment.deployment_name,
                name=deployment.deployment_name,  # alias for frontend
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
                created_at=deployment.created_at,
                template_name=template_name,
                vps_name=vps_name
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
            admin_password=deployment_data.admin_password,
            db_name=deployment_data.db_name,
            db_user=deployment_data.db_user,
            db_password=deployment_data.db_password,
            db_host=deployment_data.db_host,
            db_port=deployment_data.db_port
        )

        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create deployment"
            )

        # Fetch template name for response
        template_query = select(OdooTemplate).where(OdooTemplate.id == deployment.template_id)
        template_result = await db.execute(template_query)
        template = template_result.scalar_one_or_none()
        template_name = template.name if template else "Unknown Template"

        # Fetch VPS name for response
        vps_query = select(VPSHost).where(VPSHost.id == deployment.vps_id)
        vps_result = await db.execute(vps_query)
        vps = vps_result.scalar_one_or_none()
        vps_name = vps.name if vps else "Unknown VPS"

        return OdooDeploymentResponse(
            id=str(deployment.id),
            template_id=str(deployment.template_id),
            instance_id=str(deployment.instance_id) if deployment.instance_id else None,
            vps_id=str(deployment.vps_id),
            deployment_name=deployment.deployment_name,
            name=deployment.deployment_name,  # Required field
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
            created_at=deployment.created_at,
            template_name=template_name,
            vps_name=vps_name
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


class SimpleDeployRequest(BaseModel):
    vps_id: str
    domain: str
    version: str = "16"
    db_name: str = "postgres"
    db_user: str = "root"
    db_password: str = "root_password_123"
    db_host: str = "192.168.50.2"
    db_port: int = 5432

async def find_available_port_simple(vps_id: str, host_info: dict, ssh_service, start_port: int = 8000, end_port: int = 9000) -> int:
    """Find an available port on the VPS between start_port and end_port"""
    for port in range(start_port, end_port + 1):
        # Check if port is in use - both netstat and docker port usage
        check_cmd = f"netstat -tuln | grep ':{port} '"
        result = await ssh_service.execute_command(vps_id, check_cmd, host_info=host_info)

        # If netstat command succeeds but returns empty output, port is available
        if result.get("success") and not result.get("stdout", "").strip():
            # Double check with docker
            docker_check_cmd = f"docker ps --format 'table {{{{.Ports}}}}' | grep ':{port}->' || true"
            docker_result = await ssh_service.execute_command(vps_id, docker_check_cmd, host_info=host_info)

            if docker_result.get("success") and not docker_result.get("stdout", "").strip():
                print(f"Found available port {port} on VPS {vps_id}")
                return port

    # If no ports available, throw error
    raise Exception(f"No available ports in range {start_port}-{end_port} on VPS {vps_id}")

@router.post("/simple-deploy")
async def simple_deploy_odoo(
    request: SimpleDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Simple Odoo deployment without complex template validation"""
    try:
        from app.services.ssh_service import SSHService
        from app.core.security import generate_secure_token

        # Get VPS info
        vps_query = select(VPSHost).where(VPSHost.id == request.vps_id)
        vps_result = await db.execute(vps_query)
        vps = vps_result.scalar_one_or_none()
        if not vps:
            raise HTTPException(status_code=404, detail="VPS not found")

        # Generate deployment details with unique database
        deployment_name = f"odoo_{generate_secure_token(8)}"
        container_name = f"odoo_{deployment_name}"
        admin_password = generate_secure_token(16)
        unique_db_name = f"odoo_{deployment_name}_{generate_secure_token(4)}"

        # VPS connection info
        host_info = {
            'ip_address': vps.ip_address,
            'port': vps.port,
            'username': vps.username,
            'password_encrypted': vps.password_encrypted,
            'private_key_encrypted': vps.private_key_encrypted
        }

        # SSH service
        ssh_service = SSHService()

        # Port assignment - check available ports between 8001-8100
        port = 8001  # Start with 8001 (skip 8000 as it's commonly used)

        # Simple approach: check individual ports with Docker port availability
        for test_port in range(8001, 8101):  # Try ports 8001-8100
            # Check if port is in use with simple netstat command
            check_cmd = f"netstat -tuln | grep ':{test_port} ' || echo 'PORT_AVAILABLE'"
            result = await ssh_service.execute_command(request.vps_id, check_cmd, host_info=host_info)

            # If netstat finds nothing or command succeeds with PORT_AVAILABLE, port is free
            if result.get("success"):
                output = result.get("stdout", "").strip()
                print(f"Port {test_port} check output: '{output}'")

                # Port is available if netstat finds no matches (returns only PORT_AVAILABLE)
                if output == "PORT_AVAILABLE" or not output or "PORT_AVAILABLE" in output:
                    port = test_port
                    print(f"Using available port: {port}")
                    break
        else:
            print(f"No available port found in range 8001-8100, using default: {port}")

        print(f"Final port selected: {port}")

        # Validate port is in expected range
        if not (8001 <= port <= 8100):
            raise Exception(f"Port {port} is outside expected range 8001-8100")

        # Create unique database first with proper template and encoding
        pg_env = f"PGPASSWORD='{request.db_password}'"
        create_db_cmd = f"{pg_env} createdb -h {request.db_host} -p {request.db_port} -U {request.db_user} -T template0 -E UTF8 --locale=C --lc-collate=C --lc-ctype=C {unique_db_name}"

        print(f"Creating unique database: {unique_db_name}")
        db_result = await ssh_service.execute_command(request.vps_id, create_db_cmd, host_info=host_info)

        if not db_result.get("success"):
            error_msg = db_result.get('stderr', 'Unknown error')
            if "already exists" not in error_msg.lower():
                raise Exception(f"Failed to create database {unique_db_name}: {error_msg}")

        # Configure database settings for Odoo compatibility
        db_config_commands = [
            f"{pg_env} psql -h {request.db_host} -p {request.db_port} -U {request.db_user} -d {unique_db_name} -c \"ALTER DATABASE {unique_db_name} SET lock_timeout = '30s';\"",
            f"{pg_env} psql -h {request.db_host} -p {request.db_port} -U {request.db_user} -d {unique_db_name} -c \"ALTER DATABASE {unique_db_name} SET statement_timeout = '300s';\""
        ]

        for config_cmd in db_config_commands:
            config_result = await ssh_service.execute_command(request.vps_id, config_cmd, host_info=host_info)
            if config_result.get("success"):
                print(f"✓ Database configuration applied")
            else:
                print(f"⚠ Database configuration warning: {config_result.get('stderr', '')}")

        # Create Docker run command (single line to avoid SSH issues) with database initialization
        docker_cmd = f"docker run -d --name {container_name} --restart unless-stopped -p {port}:8069 -e POSTGRES_HOST={request.db_host} -e POSTGRES_PORT={request.db_port} -e POSTGRES_DB={unique_db_name} -e POSTGRES_USER={request.db_user} -e POSTGRES_PASSWORD={request.db_password} -e ODOO_DB={unique_db_name} -e ODOO_ADMIN_PASSWD={admin_password} --memory=2g --cpus=1 odoo:{request.version} -- --init=base --without-demo=all"

        print(f"Executing Docker command: {docker_cmd}")
        print(f"Port mapping: {port}:8069")

        # Clean up any existing container with the same name
        cleanup_cmd = f"docker rm -f {container_name} 2>/dev/null || true"
        await ssh_service.execute_command(request.vps_id, cleanup_cmd, host_info=host_info)

        # Execute deployment
        result = await ssh_service.execute_command(request.vps_id, docker_cmd, host_info=host_info)

        if not result.get("success"):
            raise Exception(f"Docker deployment failed: {result.get('stderr', 'Unknown error')}")

        return {
            "success": True,
            "deployment_name": deployment_name,
            "container_name": container_name,
            "port": port,
            "domain": request.domain,
            "admin_password": admin_password,
            "url": f"http://{vps.ip_address}:{port}",
            "database": {
                "host": request.db_host,
                "port": request.db_port,
                "name": unique_db_name,
                "user": request.db_user
            }
        }

    except Exception as e:
        logger.error(f"Simple deploy failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {str(e)}"
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