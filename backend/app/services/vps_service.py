from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.vps_host import VPSHost
from app.services.ssh_service import SSHService
from app.services.audit_service import AuditService
from app.core.security import encrypt_data, decrypt_data, generate_secure_token, sanitize_error_message
import json
import logging

logger = logging.getLogger(__name__)


class VPSService:
    """Service for managing VPS hosts with bootstrap and onboarding"""
    
    def __init__(self, db: AsyncSession, ssh_service: SSHService = None, audit_service: AuditService = None):
        self.db = db
        self.ssh_service = ssh_service or SSHService()
        self.audit_service = audit_service
    
    async def onboard_vps(
        self,
        name: str,
        hostname: str,
        ip_address: str,
        username: str,
        actor_id: str,
        port: int = 22,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        bootstrap: bool = True
    ) -> Dict[str, Any]:
        """Onboard a new VPS with optional bootstrap"""
        
        task_id = generate_secure_token(8)
        print(f"Starting onboarding for VPS {name} ({ip_address}) with task ID {task_id}")
        try:
            # Log onboarding start
            if self.audit_service:
                await self.audit_service.log_action(
                    task_id=task_id,
                    action="vps_onboard",
                    resource_type="vps_host",
                    actor_id=actor_id,
                    description=f"Onboarding VPS {name} ({ip_address})",
                    details={
                        "hostname": hostname,
                        "ip_address": ip_address,
                        "username": username,
                        "port": port,
                        "bootstrap": bootstrap
                    }
                )
            print("Audit log created")
            # Encrypt sensitive data
            password_encrypted = encrypt_data(password) if password else None
            private_key_encrypted = encrypt_data(private_key) if private_key else None
            print("Sensitive data encrypted")
            
            # Test connection first
            host_info = {
                "ip_address": ip_address,
                "port": port,
                "username": username,
                "password_encrypted": password_encrypted,
                "private_key_encrypted": private_key_encrypted
            }
            print("Testing connection to VPS")
            
            connection_test = await self.ssh_service.test_connection(host_info)
            print("Connection test result:", connection_test)
            if not connection_test["success"]:
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "failed", 
                        error_message=f"Connection test failed: {connection_test['error']}"
                    )
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": f"Connection test failed: {connection_test['error']}"
                }
            print("Connection test successful")
            # Create VPS record
            vps_host = VPSHost(
                name=name,
                hostname=hostname,
                ip_address=ip_address,
                port=port,
                username=username,
                password_encrypted=password_encrypted,
                private_key_encrypted=private_key_encrypted,
                status="pending"
            )
            print("VPS record created")
            self.db.add(vps_host)
            await self.db.commit()
            await self.db.refresh(vps_host)
            
            # Update audit log with VPS ID
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "success" if not bootstrap else "pending",
                    result={"vps_id": str(vps_host.id)}
                )
            
            # Perform bootstrap if requested
            if bootstrap:
                bootstrap_result = await self.bootstrap_vps(str(vps_host.id), actor_id)
                
                if bootstrap_result["success"]:
                    vps_host.status = "active"
                    vps_host.last_successful_connection = datetime.utcnow()
                else:
                    vps_host.status = "error"
                    vps_host.notes = f"Bootstrap failed: {bootstrap_result.get('error', 'Unknown error')}"
                
                await self.db.commit()
                
                return {
                    "success": bootstrap_result["success"],
                    "task_id": task_id,
                    "vps_id": str(vps_host.id),
                    "message": "VPS onboarded and bootstrap completed" if bootstrap_result["success"] else "VPS onboarded but bootstrap failed",
                    "bootstrap_result": bootstrap_result
                }
            else:
                vps_host.status = "active"
                vps_host.last_successful_connection = datetime.utcnow()
                await self.db.commit()
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "vps_id": str(vps_host.id),
                    "message": "VPS onboarded successfully (no bootstrap)"
                }
        
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "failed", error_message=error_msg["error"]
                )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def bootstrap_vps(self, vps_id: str, actor_id: str) -> Dict[str, Any]:
        """Bootstrap VPS with Docker and Nginx if missing"""
        
        task_id = generate_secure_token(8)
        
        try:
            # Get VPS info
            vps = await self._get_vps_by_id(vps_id)
            if not vps:
                return {"success": False, "task_id": task_id, "error": "VPS not found"}
            
            host_info = self._get_host_info(vps)
            
            # Log bootstrap start
            if self.audit_service:
                await self.audit_service.log_action(
                    task_id=task_id,
                    action="vps_bootstrap",
                    resource_type="vps_host",
                    resource_id=vps.id,
                    actor_id=actor_id,
                    description=f"Bootstrapping VPS {vps.name}",
                    details={"vps_id": vps_id}
                )
            
            bootstrap_steps = []
            
            # 1. Gather system information
            system_info = await self._gather_system_info(vps_id, host_info)
            bootstrap_steps.append({"step": "system_info", "success": True, "data": system_info})
            
            # Update VPS with system info
            vps.os_info = system_info
            
            # 2. Install Docker if missing
            docker_result = await self._ensure_docker_installed(vps_id, host_info)
            bootstrap_steps.append({"step": "docker_install", **docker_result})
            
            if docker_result["success"]:
                vps.docker_version = docker_result.get("version")
            
            # 3. Install/Configure Nginx if missing
            nginx_result = await self._ensure_nginx_configured(vps_id, host_info)
            bootstrap_steps.append({"step": "nginx_configure", **nginx_result})
            
            if nginx_result["success"]:
                vps.nginx_version = nginx_result.get("version")
                vps.nginx_config_checksum = nginx_result.get("config_checksum")
            
            # 4. Create managed directories
            dirs_result = await self._create_managed_directories(vps_id, host_info)
            bootstrap_steps.append({"step": "managed_dirs", **dirs_result})
            
            # 5. Set up monitoring
            monitoring_result = await self._setup_basic_monitoring(vps_id, host_info)
            bootstrap_steps.append({"step": "monitoring", **monitoring_result})
            
            # Update VPS status
            all_successful = all(step.get("success", False) for step in bootstrap_steps)
            
            if all_successful:
                vps.status = "active"
                vps.last_successful_connection = datetime.utcnow()
            else:
                vps.status = "error"
            
            await self.db.commit()
            
            # Complete audit log
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "success" if all_successful else "failed",
                    result={"bootstrap_steps": bootstrap_steps}
                )
            
            return {
                "success": all_successful,
                "task_id": task_id,
                "steps": bootstrap_steps,
                "message": "Bootstrap completed successfully" if all_successful else "Bootstrap completed with errors"
            }
        
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "failed", error_message=error_msg["error"]
                )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def check_vps_health(self, vps_id: str) -> Dict[str, Any]:
        """Check VPS health and update status"""
        
        task_id = generate_secure_token(8)
        
        try:
            vps = await self._get_vps_by_id(vps_id)
            if not vps:
                return {"success": False, "task_id": task_id, "error": "VPS not found"}
            
            host_info = self._get_host_info(vps)
            
            # Test basic connectivity
            connection_test = await self.ssh_service.test_connection(host_info)
            
            if connection_test["success"]:
                # Check services
                services_status = await self._check_services_status(vps_id, host_info)
                
                vps.last_successful_connection = datetime.utcnow()
                vps.last_ping = datetime.utcnow()
                
                # Determine overall health - VPS is active if we can connect
                # Don't mark as error just because some services aren't running
                docker_active = services_status.get("docker", {}).get("active", False)
                nginx_active = services_status.get("nginx", {}).get("active", False)
                
                # VPS is active if we can connect and Docker is working (nginx is optional)
                if docker_active:
                    vps.status = "active"
                elif nginx_active:
                    vps.status = "active"  # Even if just nginx is running
                else:
                    # Only mark as error if no critical services are running
                    vps.status = "inactive"  # Changed from "error" to "inactive"
                    
            else:
                vps.last_ping = datetime.utcnow()
                vps.status = "inactive"
                services_status = {"error": connection_test["error"]}
            
            await self.db.commit()
            
            return {
                "success": connection_test["success"],
                "task_id": task_id,
                "status": vps.status,
                "services": services_status
            }
        
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def get_vps_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get list of VPS hosts"""
        
        query = select(VPSHost)
        if active_only:
            query = query.where(VPSHost.status == "active")
        
        result = await self.db.execute(query)
        vps_hosts = result.scalars().all()
        
        return [
            {
                "id": str(vps.id),
                "name": vps.name,
                "hostname": vps.hostname,
                "ip_address": vps.ip_address,
                "status": vps.status,
                "last_ping": vps.last_ping.isoformat() if vps.last_ping else None,
                "last_successful_connection": vps.last_successful_connection.isoformat() if vps.last_successful_connection else None,
                "docker_version": vps.docker_version,
                "nginx_version": vps.nginx_version,
                "max_odoo_instances": vps.max_odoo_instances,
                "created_at": vps.created_at.isoformat(),
                "is_healthy": vps.is_healthy
            }
            for vps in vps_hosts
        ]
    
    # Private helper methods
    
    async def _get_vps_by_id(self, vps_id: str) -> Optional[VPSHost]:
        """Get VPS by ID"""
        query = select(VPSHost).where(VPSHost.id == vps_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    def _get_host_info(self, vps: VPSHost) -> Dict[str, Any]:
        """Extract host connection info from VPS model"""
        return {
            "ip_address": vps.ip_address,
            "port": vps.port,
            "username": vps.username,
            "password_encrypted": vps.password_encrypted,
            "private_key_encrypted": vps.private_key_encrypted
        }
    
    async def _gather_system_info(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Gather system information from VPS"""
        
        commands = {
            "os_release": "cat /etc/os-release 2>/dev/null || echo 'Unknown'",
            "kernel": "uname -r",
            "memory": "free -h | head -n 2",
            "disk": "df -h / | tail -n 1",
            "cpu": "nproc",
            "uptime": "uptime"
        }
        
        system_info = {}
        
        for key, cmd in commands.items():
            try:
                result = await self.ssh_service.execute_command(vps_id, cmd, host_info=host_info)
                if result["success"]:
                    system_info[key] = result["stdout"].strip()
                else:
                    system_info[key] = f"Error: {result['stderr']}"
            except Exception as e:
                system_info[key] = f"Error: {str(e)}"
        
        return system_info
    
    async def _ensure_docker_installed(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure Docker is installed and running"""
        
        try:
            # Check if Docker is installed
            check_result = await self.ssh_service.execute_command(
                vps_id, "docker --version", host_info=host_info
            )
            
            if check_result["success"]:
                # Docker is installed, check if it's running
                status_result = await self.ssh_service.execute_command(
                    vps_id, "systemctl is-active docker", host_info=host_info
                )
                
                if status_result["stdout"].strip() != "active":
                    # Start Docker
                    start_result = await self.ssh_service.execute_command(
                        vps_id, "sudo systemctl start docker && sudo systemctl enable docker", 
                        host_info=host_info
                    )
                    
                    if not start_result["success"]:
                        return {"success": False, "error": f"Failed to start Docker: {start_result['stderr']}"}
                
                # Get version
                version_match = check_result["stdout"].strip()
                return {"success": True, "version": version_match, "action": "verified"}
            
            else:
                # Install Docker
                install_commands = [
                    "sudo apt-get update",
                    "sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release",
                    "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg",
                    "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
                    "sudo apt-get update",
                    "sudo apt-get install -y docker-ce docker-ce-cli containerd.io",
                    "sudo systemctl start docker",
                    "sudo systemctl enable docker",
                    f"sudo usermod -aG docker {host_info['username']}"
                ]
                
                for cmd in install_commands:
                    result = await self.ssh_service.execute_command(vps_id, cmd, host_info=host_info, timeout=600)
                    if not result["success"] and "usermod" not in cmd:
                        return {"success": False, "error": f"Docker installation failed at: {cmd}"}
                
                # Verify installation
                verify_result = await self.ssh_service.execute_command(
                    vps_id, "docker --version", host_info=host_info
                )
                
                if verify_result["success"]:
                    return {"success": True, "version": verify_result["stdout"].strip(), "action": "installed"}
                else:
                    return {"success": False, "error": "Docker installation verification failed"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _ensure_nginx_configured(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure Nginx is installed and configured with managed directories"""
        
        try:
            # Check if Nginx is installed
            check_result = await self.ssh_service.execute_command(
                vps_id, "nginx -v 2>&1", host_info=host_info
            )
            
            if not check_result["success"] or "nginx version" not in check_result["stderr"]:
                # Install Nginx
                install_commands = [
                    "sudo apt-get update",
                    "sudo apt-get install -y nginx",
                    "sudo systemctl start nginx",
                    "sudo systemctl enable nginx"
                ]
                
                for cmd in install_commands:
                    result = await self.ssh_service.execute_command(vps_id, cmd, host_info=host_info, timeout=300)
                    if not result["success"]:
                        return {"success": False, "error": f"Nginx installation failed at: {cmd}"}
            
            # Get version
            version_result = await self.ssh_service.execute_command(
                vps_id, "nginx -v 2>&1", host_info=host_info
            )
            
            nginx_version = "unknown"
            if "nginx version" in version_result["stderr"]:
                nginx_version = version_result["stderr"].strip()
            
            # Backup original nginx.conf
            backup_result = await self.ssh_service.execute_command(
                vps_id, "sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.original.$(date +%Y%m%d)", 
                host_info=host_info
            )
            
            # Get current config checksum
            checksum_result = await self.ssh_service.execute_command(
                vps_id, "sudo md5sum /etc/nginx/nginx.conf | cut -d' ' -f1", 
                host_info=host_info
            )
            
            config_checksum = checksum_result["stdout"].strip() if checksum_result["success"] else "unknown"
            
            return {
                "success": True, 
                "version": nginx_version, 
                "config_checksum": config_checksum,
                "action": "configured"
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _create_managed_directories(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create managed nginx directories"""
        
        try:
            commands = [
                "sudo mkdir -p /etc/nginx/managed.d",
                "sudo mkdir -p /etc/nginx/managed.d/drafts",
                "sudo mkdir -p /srv/backups/nginx",
                "sudo chown -R root:root /etc/nginx/managed.d",
                "sudo chmod -R 755 /etc/nginx/managed.d"
            ]
            
            for cmd in commands:
                result = await self.ssh_service.execute_command(vps_id, cmd, host_info=host_info)
                if not result["success"]:
                    return {"success": False, "error": f"Failed to create directories: {cmd}"}
            
            return {"success": True, "message": "Managed directories created"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_basic_monitoring(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Set up basic monitoring tools"""
        
        try:
            # Install basic monitoring tools
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y htop iotop netstat-nat"
            ]
            
            for cmd in commands:
                result = await self.ssh_service.execute_command(vps_id, cmd, host_info=host_info, timeout=300)
                # Continue even if some tools fail to install
            
            return {"success": True, "message": "Basic monitoring tools installed"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _check_services_status(self, vps_id: str, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of critical services"""
        
        services = ["nginx", "docker"]
        status = {}
        
        for service in services:
            try:
                result = await self.ssh_service.execute_command(
                    vps_id, f"systemctl is-active {service}", host_info=host_info
                )
                
                status[service] = {
                    "active": result["stdout"].strip() == "active",
                    "status": result["stdout"].strip()
                }
                
            except Exception as e:
                status[service] = {
                    "active": False,
                    "error": str(e)
                }
        
        return status