from typing import Dict, List, Optional, Any
import os
import json
import logging
import shutil
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.odoo_template import OdooTemplate, OdooTemplateFile, OdooDeployment
from app.models.odoo_instance import OdooInstance
from app.models.vps_host import VPSHost
from app.services.ssh_service import SSHService
from app.services.docker_service import DockerService
from app.services.audit_service import AuditService
from app.core.security import encrypt_data, decrypt_data, generate_secure_token
import tempfile

logger = logging.getLogger(__name__)


class OdooDeploymentService:
    """Service for managing Odoo template deployments"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ssh_service = SSHService()
        self.docker_service = DockerService(self.ssh_service, AuditService(db))
        self.audit_service = AuditService(db)
    
    async def get_templates(self, industry: Optional[str] = None, version: Optional[str] = None, 
                           is_public: bool = True, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get available Odoo templates with filtering"""
        try:
            query = select(OdooTemplate).where(OdooTemplate.is_active == True)
            
            if industry:
                query = query.where(OdooTemplate.industry == industry)
            if version:
                query = query.where(OdooTemplate.version == version)
            if is_public is not None:
                query = query.where(OdooTemplate.is_public == is_public)
            
            # Add pagination
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)
            
            result = await self.db.execute(query)
            templates = result.scalars().all()
            
            # Get total count
            count_query = select(OdooTemplate).where(OdooTemplate.is_active == True)
            if industry:
                count_query = count_query.where(OdooTemplate.industry == industry)
            if version:
                count_query = count_query.where(OdooTemplate.version == version)
            if is_public is not None:
                count_query = count_query.where(OdooTemplate.is_public == is_public)
            
            count_result = await self.db.execute(count_query)
            total = len(count_result.scalars().all())
            
            return {
                "templates": templates,
                "total": total,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Failed to get templates: {e}")
            return {"templates": [], "total": 0, "page": page, "per_page": per_page}
    
    async def create_template(self, name: str, industry: str, version: str,
                             backup_file_path: str, admin_id: str, **kwargs) -> Optional[OdooTemplate]:
        """Create a new Odoo template"""
        try:
            template = OdooTemplate(
                name=name,
                industry=industry,
                version=version,
                backup_file_path=backup_file_path,
                description=kwargs.get('description'),
                docker_image=kwargs.get('docker_image'),
                default_modules=kwargs.get('default_modules'),
                config_template=kwargs.get('config_template'),
                env_vars_template=kwargs.get('env_vars_template'),
                is_public=kwargs.get('is_public', False),
                tags=kwargs.get('tags'),
                category=kwargs.get('category'),
                complexity_level=kwargs.get('complexity_level', 'beginner'),
                setup_instructions=kwargs.get('setup_instructions'),
                post_install_script=kwargs.get('post_install_script'),
                required_addons=kwargs.get('required_addons')
            )

            # Set backup file size if file exists
            if backup_file_path and os.path.exists(backup_file_path):
                template.backup_file_size = os.path.getsize(backup_file_path)
                template.backup_created_at = datetime.now(timezone.utc)
                template.backup_odoo_version = version
            
            self.db.add(template)
            await self.db.commit()
            await self.db.refresh(template)
            
            # Log template creation
            await self.audit_service.log_action(
                task_id=generate_secure_token(8),
                action="odoo_template_create",
                resource_type="odoo_template",
                resource_id=template.id,
                actor_id=admin_id,
                description=f"Created Odoo template '{name}' for {industry} industry",
                details={
                    "template_name": name,
                    "industry": industry,
                    "version": version,
                    "backup_file_path": backup_file_path
                }
            )
            
            return template
        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            await self.db.rollback()
            return None
    
    async def get_template(self, template_id: str) -> Optional[OdooTemplate]:
        """Get a specific template by ID"""
        try:
            query = select(OdooTemplate).where(OdooTemplate.id == template_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}")
            return None

    async def delete_template(self, template_id: str, admin_id: str) -> bool:
        """Delete a template by ID"""
        try:
            # Get template first to check if it exists
            template = await self.get_template(template_id)
            if not template:
                return False
            
            # Check if template has any active deployments
            deployment_query = select(OdooDeployment).where(
                OdooDeployment.template_id == template_id,
                OdooDeployment.status.in_(['pending', 'running'])
            )
            deployment_result = await self.db.execute(deployment_query)
            active_deployments = deployment_result.scalars().all()
            
            if active_deployments:
                raise ValueError("Cannot delete template with active deployments")
            
            # Delete template
            await self.db.delete(template)
            await self.db.commit()
            
            # Log template deletion
            await self.audit_service.log_action(
                task_id=generate_secure_token(8),
                action="odoo_template_delete",
                resource_type="odoo_template", 
                resource_id=template.id,
                actor_id=admin_id,
                description=f"Deleted Odoo template '{template.name}'",
                details={
                    "template_name": template.name,
                    "industry": template.industry,
                    "version": template.version
                }
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}")
            await self.db.rollback()
            raise
    
    async def find_available_port(self, vps_id: str, start_port: int = 8001, end_port: int = 8100) -> int:
        """Find an available port on the VPS for the new Odoo instance"""
        try:
            # Get VPS connection info
            vps_query = select(VPSHost).where(VPSHost.id == vps_id)
            vps_result = await self.db.execute(vps_query)
            vps = vps_result.scalar_one_or_none()

            if not vps:
                raise ValueError("VPS not found")

            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }

            # Use improved port detection logic (same as simple-deploy)
            for test_port in range(start_port, end_port + 1):
                # Check if port is in use with simple netstat command
                check_cmd = f"netstat -tuln | grep ':{test_port} ' || echo 'PORT_AVAILABLE'"
                result = await self.ssh_service.execute_command(vps_id, check_cmd, host_info=host_info)

                # If netstat finds nothing or command succeeds with PORT_AVAILABLE, port is free
                if result.get("success"):
                    output = result.get("stdout", "").strip()
                    print(f"Port {test_port} check output: '{output}'")

                    # Port is available if netstat finds no matches (returns only PORT_AVAILABLE)
                    if output == "PORT_AVAILABLE" or not output or "PORT_AVAILABLE" in output:
                        logger.info(f"Found available port {test_port} on VPS {vps_id}")
                        print(f"Using available port: {test_port}")
                        return test_port

            raise ValueError(f"No available ports in range {start_port}-{end_port} on VPS {vps_id}")
        except Exception as e:
            logger.error(f"Failed to find available port on VPS {vps_id}: {e}")
            raise
    
    async def deploy_odoo(self, template_id: str, vps_id: str, deployment_name: str, 
                         domain: str, admin_id: str, **kwargs) -> Optional[OdooDeployment]:
        """Deploy an Odoo instance from a template"""
        deployment = None
        
        
        try:
            # Get template
            template = await self.get_template(template_id)
            if not template or not template.is_available:
                raise ValueError("Template not found or not available")
            
            # Get VPS
            vps_query = select(VPSHost).where(VPSHost.id == vps_id)
            vps_result = await self.db.execute(vps_query)
            vps = vps_result.scalar_one_or_none()
            if not vps:
                raise ValueError("VPS not found")
            
            # Find available port
            port = await self.find_available_port(vps_id, 
                                                template.default_port_range_start,
                                                template.default_port_range_end)
            
                       
            
            
            # Generate database name and admin password
            db_name = f"{deployment_name.lower().replace('-', '_').replace(' ', '_')}"
            admin_password = kwargs.get('admin_password') or generate_secure_token(16)

            # Ensure admin_password is a string
            if not isinstance(admin_password, str):
                admin_password = str(admin_password)

            print(f"Admin password type: {type(admin_password)}, value length: {len(admin_password)}")
            
            # Generate deployment ID
            deployment_id = str(uuid.uuid4())            
            deployment_name = f"{deployment_name.lower().replace('-', '_').replace(' ', '_')}_{deployment_id[:8]}"
            
    
            
            print("Preparing to create deployment record")

            # Encrypt admin password with better error handling
            try:
                print(f"Encrypting password: {admin_password[:5]}...")
                encrypted_password = encrypt_data(admin_password)
                print("Password encrypted successfully")
            except Exception as e:
                logger.error(f"Failed to encrypt admin password: {e}")
                print(f"Encryption error: {e}")
                raise

            # Create deployment record
            deployment = OdooDeployment(
                template_id=template_id,
                vps_id=vps_id,
                deployment_name=deployment_name,
                domain=domain,
                selected_version=kwargs.get('selected_version', template.version),
                port=port,
                db_name=db_name,
                admin_password=encrypted_password,
                selected_modules=kwargs.get('selected_modules', template.default_modules),
                custom_config=kwargs.get('custom_config'),
                custom_env_vars=kwargs.get('custom_env_vars'),
                deployed_by=admin_id,
                started_at=datetime.now(timezone.utc)
            )
            
            print("Created deployment record")
            
            self.db.add(deployment)
            
            print("Added deployment to DB session")
            await self.db.commit()
            print("Committed DB session")
            await self.db.refresh(deployment)
            print("Refreshed deployment from DB")
            
            # Start deployment process - remove admin_password from kwargs to avoid duplicate
            kwargs_without_admin_password = {k: v for k, v in kwargs.items() if k != 'admin_password'}
            await self._deploy_container(deployment, template, vps, admin_password, **kwargs_without_admin_password)
            
            # Increment template deployment counter
            template.increment_deployment_count()
            await self.db.commit()
            
            return deployment
        except Exception as e:
            logger.error(f"Failed to deploy Odoo: {e}")
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.now(timezone.utc)
                await self.db.commit()
            return deployment
    
    async def _deploy_container(self, deployment: OdooDeployment, template: OdooTemplate,
                               vps: VPSHost, admin_password: str, **kwargs):
        """Deploy the actual Docker container"""
        try:
            deployment.status = "deploying"
            deployment.progress = 10
            await self.db.commit()
            
            # Get VPS connection info
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            
            # Connect to VPS
            ssh_client = await self.ssh_service.get_connection(vps.id, host_info)
            if not ssh_client:
                raise Exception("Failed to connect to VPS")
            
            deployment.progress = 20
            await self.db.commit()
            
            # Create container name
            container_name = f"odoo_{deployment.deployment_name.lower().replace('-', '_').replace(' ', '_')}"
            
            # Get database credentials from deployment form
            db_host = kwargs.get('db_host', 'localhost')
            db_port = kwargs.get('db_port', 5432)
            db_name = kwargs.get('db_name', deployment.db_name)
            db_user = kwargs.get('db_user', 'postgres')
            db_password = kwargs.get('db_password')

            # Ensure we have a database password
            if not db_password:
                raise Exception("Database password is required for external PostgreSQL connection")

            print(f"Using external PostgreSQL: {db_host}:{db_port}, DB: {db_name}, User: {db_user}")

            # Prepare environment variables for external PostgreSQL
            env_vars = {
                "POSTGRES_HOST": db_host,
                "POSTGRES_PORT": str(db_port),
                "POSTGRES_DB": db_name,
                "POSTGRES_USER": db_user,
                "POSTGRES_PASSWORD": db_password,
                "ODOO_DB": db_name,
                "ODOO_ADMIN_PASSWD": admin_password
            }
            
            # Add template environment variables
            if template.env_vars_template:
                env_vars.update(template.env_vars_template)
            
            # Add custom environment variables
            if deployment.custom_env_vars:
                env_vars.update(deployment.custom_env_vars)
            
            deployment.progress = 30
            await self.db.commit()
            
            # Copy backup file to VPS if needed
            if template.backup_file_path and os.path.exists(template.backup_file_path):
                remote_backup_path = f"/tmp/{deployment.db_name}_backup.zip"
                await self._copy_backup_to_vps(template.backup_file_path, remote_backup_path, host_info)
                deployment.progress = 50
                await self.db.commit()
            
            # Create Docker run command (using external PostgreSQL)
            docker_image = template.docker_image or f"odoo:{deployment.selected_version}"
            env_string = " ".join([f"-e {k}={v}" for k, v in env_vars.items()])

            # Create single-line Docker command for better SSH execution
            docker_cmd = f"docker run -d --name {container_name} --restart unless-stopped -p {deployment.port}:8069 {env_string} --memory={template.default_memory_limit} --cpus={template.default_cpu_limit} {docker_image}"

            print(f"Docker command: {docker_cmd}")
            
            deployment.progress = 60
            await self.db.commit()
            
            # Execute Docker command
            result = await self.ssh_service.execute_command(vps.id, docker_cmd, host_info=host_info)
            if not result.get("success"):
                raise Exception(f"Failed to start container: {result.get('stderr', 'Unknown error')}")
            
            deployment.progress = 70
            await self.db.commit()
            
            # Wait for container to be ready
            await self._wait_for_container_ready(vps.id, container_name, host_info)
            deployment.progress = 80
            await self.db.commit()
            
            # Restore backup if available (for external PostgreSQL)
            if template.backup_file_path:
                await self._restore_backup_external(vps.id, container_name, db_name,
                                                   remote_backup_path, host_info,
                                                   db_host, db_port, db_user, db_password)
                deployment.progress = 90
                await self.db.commit()
            
            # Create OdooInstance record
            instance = OdooInstance(
                vps_id=deployment.vps_id,
                name=deployment.deployment_name,
                domain=deployment.domain,
                container_name=container_name,
                odoo_version=deployment.selected_version,
                industry=template.industry,
                port=deployment.port,
                db_name=db_name,  # Use the actual database name from form
                status="running",
                env_vars=env_vars,
                backup_enabled=True,
                ssl_enabled=True
            )
            
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            # Update deployment
            deployment.instance_id = instance.id
            deployment.status = "completed"
            deployment.progress = 100
            deployment.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            
            # Log successful deployment
            await self.audit_service.log_action(
                task_id=generate_secure_token(8),
                action="odoo_deploy_success",
                resource_type="odoo_deployment",
                resource_id=deployment.id,
                actor_id=deployment.deployed_by,
                description=f"Successfully deployed Odoo instance '{deployment.deployment_name}'",
                details={
                    "template_id": str(template.id),
                    "template_name": template.name,
                    "instance_id": str(instance.id),
                    "container_name": container_name,
                    "port": deployment.port,
                    "domain": deployment.domain
                }
            )
            
        except Exception as e:
            logger.error(f"Container deployment failed: {e}")
            deployment.status = "failed"
            deployment.error_message = str(e)
            deployment.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            raise
    
    async def _copy_backup_to_vps(self, local_path: str, remote_path: str, host_info: dict):
        """Copy backup file from local storage to VPS"""
        # This would use SCP or SFTP to copy the file
        # For now, we'll simulate it
        logger.info(f"Copying backup from {local_path} to {remote_path}")
        # Implementation would depend on your file transfer method
    
    async def _wait_for_container_ready(self, vps_id: str, container_name: str, host_info: dict, 
                                       timeout: int = 300):
        """Wait for container to be ready"""
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            # Check if container is running
            result = await self.ssh_service.execute_command(
                vps_id, f"docker ps --filter name={container_name} --format json", 
                host_info=host_info
            )
            
            if result.get("success") and result.get("stdout"):
                container_info = json.loads(result["stdout"])
                if "Up" in container_info.get("Status", ""):
                    logger.info(f"Container {container_name} is ready")
                    return
            
            await asyncio.sleep(10)
        
        raise Exception(f"Container {container_name} not ready within {timeout} seconds")
    
    async def _restore_backup(self, vps_id: str, container_name: str, db_name: str,
                             backup_path: str, host_info: dict):
        """Restore database backup to the container"""
        try:
            # Create database in container
            create_db_cmd = f"docker exec {container_name} createdb -U odoo {db_name}"
            result = await self.ssh_service.execute_command(vps_id, create_db_cmd, host_info=host_info)

            # Restore backup
            restore_cmd = f"docker exec {container_name} pg_restore -U odoo -d {db_name} {backup_path}"
            result = await self.ssh_service.execute_command(vps_id, restore_cmd, host_info=host_info)

            if not result.get("success"):
                logger.warning(f"Backup restore may have failed: {result.get('stderr', '')}")

            logger.info(f"Backup restored for {container_name}")
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            # Don't fail deployment for backup restore issues

    async def _restore_backup_external(self, vps_id: str, container_name: str, db_name: str,
                                     backup_path: str, host_info: dict, db_host: str,
                                     db_port: int, db_user: str, db_password: str):
        """Restore database backup to external PostgreSQL"""
        try:
            # Set PostgreSQL connection environment for the commands
            pg_env = f"PGPASSWORD='{db_password}'"

            # Create database on external PostgreSQL if it doesn't exist
            create_db_cmd = f"{pg_env} createdb -h {db_host} -p {db_port} -U {db_user} {db_name} || true"
            result = await self.ssh_service.execute_command(vps_id, create_db_cmd, host_info=host_info)

            # Restore backup to external PostgreSQL
            restore_cmd = f"{pg_env} pg_restore -h {db_host} -p {db_port} -U {db_user} -d {db_name} {backup_path}"
            result = await self.ssh_service.execute_command(vps_id, restore_cmd, host_info=host_info)

            if not result.get("success"):
                logger.warning(f"External backup restore may have failed: {result.get('stderr', '')}")

            logger.info(f"Backup restored to external PostgreSQL: {db_host}:{db_port}/{db_name}")
        except Exception as e:
            logger.error(f"Failed to restore backup to external PostgreSQL: {e}")
            # Don't fail deployment for backup restore issues
    
    async def get_deployments(self, vps_id: Optional[str] = None, status: Optional[str] = None,
                             page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get deployments with filtering"""
        try:
            query = select(OdooDeployment)
            
            if vps_id:
                query = query.where(OdooDeployment.vps_id == vps_id)
            if status:
                query = query.where(OdooDeployment.status == status)
            
            # Add pagination
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)
            query = query.order_by(OdooDeployment.created_at.desc())
            
            result = await self.db.execute(query)
            deployments = result.scalars().all()
            
            # Get total count
            count_query = select(OdooDeployment)
            if vps_id:
                count_query = count_query.where(OdooDeployment.vps_id == vps_id)
            if status:
                count_query = count_query.where(OdooDeployment.status == status)
            
            count_result = await self.db.execute(count_query)
            total = len(count_result.scalars().all())
            
            return {
                "deployments": deployments,
                "total": total,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Failed to get deployments: {e}")
            return {"deployments": [], "total": 0, "page": page, "per_page": per_page}
    
    async def get_deployment(self, deployment_id: str) -> Optional[OdooDeployment]:
        """Get specific deployment"""
        try:
            query = select(OdooDeployment).where(OdooDeployment.id == deployment_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get deployment {deployment_id}: {e}")
            return None
    
    async def delete_deployment(self, deployment_id: str, admin_id: str) -> bool:
        """Delete a deployment and its associated container"""
        try:
            deployment = await self.get_deployment(deployment_id)
            if not deployment:
                return False
            
            # Get VPS info
            vps_query = select(VPSHost).where(VPSHost.id == deployment.vps_id)
            vps_result = await self.db.execute(vps_query)
            vps = vps_result.scalar_one_or_none()
            
            if vps:
                # Stop and remove container if exists
                host_info = {
                    'ip_address': vps.ip_address,
                    'port': vps.port,
                    'username': vps.username,
                    'password_encrypted': vps.password_encrypted,
                    'private_key_encrypted': vps.private_key_encrypted
                }
                
                container_name = f"odoo_{deployment.deployment_name.lower().replace('-', '_').replace(' ', '_')}"
                
                # Remove container
                await self.ssh_service.execute_command(
                    vps.id, f"docker stop {container_name} && docker rm {container_name}", 
                    host_info=host_info
                )
            
            # Delete associated OdooInstance if exists
            if deployment.instance_id:
                instance_query = select(OdooInstance).where(OdooInstance.id == deployment.instance_id)
                instance_result = await self.db.execute(instance_query)
                instance = instance_result.scalar_one_or_none()
                if instance:
                    await self.db.delete(instance)
            
            # Delete deployment
            await self.db.delete(deployment)
            await self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete deployment {deployment_id}: {e}")
            await self.db.rollback()
            return False