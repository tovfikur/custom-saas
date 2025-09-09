from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.vps_host import VPSHost
from app.services.ssh_service import SSHService
from app.services.audit_service import AuditService
from app.core.security import decrypt_data, generate_secure_token

logger = logging.getLogger(__name__)


class DockerService:
    """Service for managing Docker operations on VPS hosts"""
    
    def __init__(self, ssh_service: SSHService, audit_service: AuditService):
        self.ssh_service = ssh_service
        self.audit_service = audit_service
    
    async def get_vps(self, vps_id: str, db: AsyncSession) -> Optional[VPSHost]:
        """Get VPS host by ID"""
        query = select(VPSHost).where(VPSHost.id == vps_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_docker_status(self, vps_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Get Docker status and system information"""
        vps = await self.get_vps(vps_id, db)
        if not vps:
            raise ValueError("VPS not found")
        
        try:
            # Get decrypted credentials
            password = decrypt_data(vps.password_encrypted) if vps.password_encrypted else None
            private_key = decrypt_data(vps.private_key_encrypted) if vps.private_key_encrypted else None
            
            # Connect via SSH  
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await self.ssh_service.get_connection(vps.id, host_info)
            
            if not ssh_client:
                return {
                    "success": False,
                    "status": "disconnected",
                    "version": "N/A",
                    "containers_running": 0,
                    "containers_total": 0,
                    "images_count": 0,
                    "system_info": {"error": "Cannot connect to VPS"}
                }
            
            # First, detect if Docker CLI is present on the host
            docker_present_check = await self.ssh_service.execute_command(
                vps.id, "command -v docker >/dev/null 2>&1 && echo present || echo absent", host_info=host_info
            )
            docker_present = docker_present_check.get("stdout", "").strip() == "present"

            if not docker_present:
                return {
                    "success": True,
                    "status": "not_present",
                    "version": "N/A",
                    "containers_running": 0,
                    "containers_total": 0,
                    "images_count": 0,
                    "system_info": {"error": "Docker not installed on host"}
                }

            # Get Docker version (Docker is present)
            version_result = await self.ssh_service.execute_command(
                vps.id, "docker --version", host_info=host_info
            )
            docker_version = version_result.get("stdout", "Unknown").strip() or "Unknown"
            
            # Get Docker system info
            info_result = await self.ssh_service.execute_command(
                vps.id, "docker system info --format json", host_info=host_info
            )
            
            system_info = {}
            if info_result.get("success") and info_result.get("stdout"):
                try:
                    system_info = json.loads(info_result["stdout"])
                except json.JSONDecodeError:
                    system_info = {"error": "Failed to parse Docker info"}
            
            # Get container counts
            running_result = await self.ssh_service.execute_command(
                vps.id, "docker ps -q | wc -l", host_info=host_info
            )
            containers_running = int(running_result.get("stdout", "0").strip())
            
            total_result = await self.ssh_service.execute_command(
                vps.id, "docker ps -aq | wc -l", host_info=host_info
            )
            containers_total = int(total_result.get("stdout", "0").strip())
            
            # Get image count
            images_result = await self.ssh_service.execute_command(
                vps.id, "docker images -q | wc -l", host_info=host_info
            )
            images_count = int(images_result.get("stdout", "0").strip())
            
            # Check if Docker daemon is running
            status_result = await self.ssh_service.execute_command(
                vps.id, "docker info > /dev/null 2>&1 && echo 'running' || echo 'stopped'", host_info=host_info
            )
            docker_status = status_result.get("stdout", "unknown").strip()
            
            
            return {
                "success": True,
                "status": docker_status,
                "version": docker_version,
                "containers_running": containers_running,
                "containers_total": containers_total,
                "images_count": images_count,
                "system_info": system_info
            }
            
        except Exception as e:
            logger.error(f"Failed to get Docker status for VPS {vps_id}: {e}")
            return {
                "success": False,
                "status": "error",
                "version": "N/A", 
                "containers_running": 0,
                "containers_total": 0,
                "images_count": 0,
                "system_info": {"error": str(e)}
            }
    
    async def get_containers(self, vps_id: str, db: AsyncSession, all_containers: bool = False) -> Dict[str, Any]:
        """Get Docker containers list"""
        vps = await self.get_vps(vps_id, db)
        if not vps:
            raise ValueError("VPS not found")
        
        try:
            password = decrypt_data(vps.password_encrypted) if vps.password_encrypted else None
            private_key = decrypt_data(vps.private_key_encrypted) if vps.private_key_encrypted else None
            
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await self.ssh_service.get_connection(vps.id, host_info)
            
            if not ssh_client:
                return {"success": False, "containers": []}
            
            # Get containers in JSON format
            flag = "-a" if all_containers else ""
            result = await self.ssh_service.execute_command(
                vps.id, f"docker ps {flag} --format json", host_info=host_info
            )
            
            containers = []
            if result.get("success") and result.get("stdout"):
                lines = result["stdout"].strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            container_data = json.loads(line)
                            
                            # Parse ports
                            ports = []
                            if container_data.get("Ports"):
                                ports = [p.strip() for p in container_data["Ports"].split(',')]
                            
                            # Parse labels
                            labels = {}
                            if container_data.get("Labels"):
                                label_pairs = container_data["Labels"].split(',')
                                for pair in label_pairs:
                                    if '=' in pair:
                                        key, value = pair.split('=', 1)
                                        labels[key.strip()] = value.strip()
                            
                            containers.append({
                                "id": container_data.get("ID", "")[:12],
                                "name": container_data.get("Names", "").lstrip('/'),
                                "image": container_data.get("Image", ""),
                                "status": container_data.get("Status", ""),
                                "created": container_data.get("CreatedAt", ""),
                                "ports": ports,
                                "labels": labels
                            })
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse container JSON: {e}")
            
            
            return {
                "success": True,
                "containers": containers
            }
            
        except Exception as e:
            logger.error(f"Failed to get containers for VPS {vps_id}: {e}")
            return {"success": False, "containers": []}
    
    async def container_action(self, vps_id: str, db: AsyncSession, container_id: str, action: str, actor_id: str) -> Dict[str, Any]:
        """Perform action on Docker container"""
        vps = await self.get_vps(vps_id, db)
        if not vps:
            raise ValueError("VPS not found")
        
        task_id = generate_secure_token(8)
        
        # Log the action
        if self.audit_service:
            await self.audit_service.log_action(
                task_id=task_id,
                action=f"docker_container_{action}",
                resource_type="docker_container",
                resource_id=None,  # Container IDs are not UUIDs, store in details instead
                actor_id=actor_id,
                description=f"Docker {action} on container {container_id} in VPS {vps.name}",
                details={
                    "vps_id": vps_id,
                    "vps_name": vps.name,
                    "container_id": container_id,
                    "action": action
                }
            )
        
        try:
            password = decrypt_data(vps.password_encrypted) if vps.password_encrypted else None
            private_key = decrypt_data(vps.private_key_encrypted) if vps.private_key_encrypted else None
            
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await self.ssh_service.get_connection(vps.id, host_info)
            
            if not ssh_client:
                if self.audit_service:
                    await self.audit_service.complete_action(task_id, "failed", error_message="Cannot connect to VPS")
                return {"success": False, "message": "Cannot connect to VPS"}
            
            # Execute Docker command
            valid_actions = ["start", "stop", "restart", "remove", "pause", "unpause"]
            if action not in valid_actions:
                if self.audit_service:
                    await self.audit_service.complete_action(task_id, "failed", error_message=f"Invalid action: {action}")
                return {"success": False, "message": f"Invalid action: {action}"}
            
            # Build Docker command with proper handling for different actions
            if action == "stop":
                # Disable restart policy first, then stop container
                docker_cmd = f"docker update --restart=no {container_id} && docker stop {container_id}"
            elif action == "remove":
                # Stop and force remove container
                docker_cmd = f"docker stop {container_id} && docker rm --force {container_id}"
            else:
                docker_cmd = f"docker {action} {container_id}"
            
            result = await self.ssh_service.execute_command(vps.id, docker_cmd, host_info=host_info)
            
            if result.get("success"):
                # Verify the action was successful by checking container status
                verification_msg = ""
                if action in ["stop", "start", "restart"]:
                    verify_cmd = f"docker ps -a --filter id={container_id} --format 'table {{.Status}}'"
                    verify_result = await self.ssh_service.execute_command(vps.id, verify_cmd, host_info=host_info)
                    if verify_result.get("success") and verify_result.get("stdout"):
                        status_output = verify_result["stdout"].strip()
                        verification_msg = f" (Verified: {status_output})"
                
                if self.audit_service:
                    await self.audit_service.complete_action(task_id, "success", result={"action": action, "container_id": container_id})
                return {"success": True, "message": f"Container {action} successful{verification_msg}", "task_id": task_id}
            else:
                error_msg = result.get("stderr", "Unknown error")
                if self.audit_service:
                    await self.audit_service.complete_action(task_id, "failed", error_message=error_msg)
                return {"success": False, "message": error_msg}
                
        except Exception as e:
            logger.error(f"Failed to {action} container {container_id}: {e}")
            if self.audit_service:
                await self.audit_service.complete_action(task_id, "failed", error_message=str(e))
            return {"success": False, "message": str(e)}
    
    async def get_images(self, vps_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Get Docker images list"""
        vps = await self.get_vps(vps_id, db)
        if not vps:
            raise ValueError("VPS not found")
        
        try:
            password = decrypt_data(vps.password_encrypted) if vps.password_encrypted else None
            private_key = decrypt_data(vps.private_key_encrypted) if vps.private_key_encrypted else None
            
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await self.ssh_service.get_connection(vps.id, host_info)
            
            if not ssh_client:
                return {"success": False, "images": []}
            
            # Get images in JSON format
            result = await self.ssh_service.execute_command(
                vps.id, "docker images --format json", host_info=host_info
            )
            
            images = []
            if result.get("success") and result.get("stdout"):
                lines = result["stdout"].strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            image_data = json.loads(line)
                            images.append({
                                "id": image_data.get("ID", "")[:12],
                                "repository": image_data.get("Repository", ""),
                                "tag": image_data.get("Tag", ""),
                                "created": image_data.get("CreatedAt", ""),
                                "size": image_data.get("Size", "")
                            })
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse image JSON: {e}")
            
            
            return {
                "success": True,
                "images": images
            }
            
        except Exception as e:
            logger.error(f"Failed to get images for VPS {vps_id}: {e}")
            return {"success": False, "images": []}
