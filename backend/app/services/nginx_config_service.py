from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from app.models.nginx_config import NginxConfig
from app.models.vps_host import VPSHost
from app.core.security import encrypt_data, decrypt_data, sanitize_error_message, generate_secure_token
from app.services.nginx_validator import NginxConfigValidator, ValidationResult
from app.services.audit_service import AuditService
import difflib
import json
import asyncio


class NginxConfigService:
    """Service for managing Nginx configurations with safety-first operations"""
    
    def __init__(self, db: AsyncSession, ssh_service=None, audit_service: AuditService = None):
        self.db = db
        self.ssh_service = ssh_service
        self.audit_service = audit_service
        self.validator = NginxConfigValidator(ssh_service)
    
    async def create_config_version(
        self,
        vps_id: str,
        content: str,
        author_id: str,
        summary: Optional[str] = None,
        config_name: str = "default",
        config_type: str = "server_block",
        template_used: Optional[str] = None
    ) -> NginxConfig:
        """Create a new configuration version"""
        
        # Get current version number
        current_version = await self._get_latest_version(vps_id)
        new_version = (current_version or 0) + 1
        
        # Generate diff if there's a previous version
        diff_json = None
        if current_version:
            previous_config = await self._get_config_by_version(vps_id, current_version)
            if previous_config:
                previous_content = decrypt_data(previous_config.content_encrypted)
                diff_json = self._generate_diff(previous_content, content)
        
        # Encrypt content
        content_encrypted = encrypt_data(content)
        
        # Create new config record
        config = NginxConfig(
            vps_id=vps_id,
            version=new_version,
            author_id=author_id,
            content_encrypted=content_encrypted,
            summary=summary,
            diff_json=diff_json,
            config_name=config_name,
            config_type=config_type,
            template_used=template_used
        )
        
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        
        return config
    
    async def validate_config(
        self,
        vps_id: str,
        content: str,
        dry_run: bool = True
    ) -> ValidationResult:
        """Validate configuration with comprehensive checks"""
        return await self.validator.validate_config(content, vps_id, dry_run)
    
    async def apply_config(
        self,
        config_id: str,
        author_id: str,
        dry_run: bool = False,
        scheduled_at: Optional[datetime] = None,
        watch_window_seconds: int = 120
    ) -> Dict[str, Any]:
        """Apply configuration with safety checks and automatic rollback"""
        
        task_id = generate_secure_token(8)
        
        try:
            # Get config
            config = await self._get_config_by_id(config_id)
            if not config:
                raise ValueError("Configuration not found")
            
            # Decrypt content
            content = decrypt_data(config.content_encrypted)
            
            # Log start of operation
            if self.audit_service:
                await self.audit_service.log_action(
                    task_id=task_id,
                    action="nginx_config_apply",
                    resource_type="nginx_config",
                    resource_id=config.id,
                    actor_id=author_id,
                    description=f"Applying nginx config version {config.version}",
                    details={
                        "vps_id": str(config.vps_id),
                        "config_name": config.config_name,
                        "dry_run": dry_run,
                        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                        "watch_window_seconds": watch_window_seconds
                    }
                )
            
            # Schedule for later if requested
            if scheduled_at and scheduled_at > datetime.utcnow():
                config.scheduled_apply_at = scheduled_at
                await self.db.commit()
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": f"Configuration scheduled for {scheduled_at}",
                    "scheduled": True
                }
            
            # Validate before apply
            validation = await self.validate_config(str(config.vps_id), content, dry_run=False)
            config.nginx_test_result = {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "output": validation.nginx_test_output
            }
            
            if not validation.is_valid:
                config.status = "failed"
                await self.db.commit()
                
                error_message = "; ".join(validation.errors)
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "failed", error_message=error_message
                    )
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "errors": validation.errors,
                    "warnings": validation.warnings
                }
            
            # If dry run, stop here
            if dry_run:
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "Dry run validation passed",
                    "warnings": validation.warnings,
                    "dry_run": True
                }
            
            # Apply configuration
            apply_result = await self._apply_config_to_vps(config, content, task_id)
            
            if apply_result["success"]:
                config.status = "applied"
                config.applied_at = datetime.utcnow()
                config.watch_window_seconds = watch_window_seconds
                await self.db.commit()
                
                # Start health monitoring if watch window > 0
                if watch_window_seconds > 0:
                    asyncio.create_task(
                        self._monitor_health_and_rollback(config.id, watch_window_seconds, task_id)
                    )
                
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "success", 
                        result={"applied_at": config.applied_at.isoformat()}
                    )
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "Configuration applied successfully",
                    "applied_at": config.applied_at.isoformat(),
                    "watch_window_seconds": watch_window_seconds
                }
            else:
                config.status = "failed"
                await self.db.commit()
                
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "failed", error_message=apply_result.get("error", "Unknown error")
                    )
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": apply_result.get("error", "Failed to apply configuration")
                }
                
        except Exception as e:
            sanitized_error = sanitize_error_message(str(e), task_id)
            
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "failed", error_message=sanitized_error["error"]
                )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": sanitized_error["error"]
            }
    
    async def rollback_config(
        self,
        vps_id: str,
        target_version: Optional[int] = None,
        author_id: str = None
    ) -> Dict[str, Any]:
        """Rollback to previous or specified version"""
        
        task_id = generate_secure_token(8)
        
        try:
            if target_version is None:
                # Find last successful version
                target_config = await self._get_last_successful_config(vps_id)
            else:
                target_config = await self._get_config_by_version(vps_id, target_version)
            
            if not target_config:
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": "No suitable version found for rollback"
                }
            
            # Log rollback start
            if self.audit_service:
                await self.audit_service.log_action(
                    task_id=task_id,
                    action="nginx_config_rollback",
                    resource_type="nginx_config",
                    resource_id=target_config.id,
                    actor_id=author_id,
                    description=f"Rolling back to nginx config version {target_config.version}",
                    details={"vps_id": str(vps_id), "target_version": target_config.version}
                )
            
            # Decrypt and apply target configuration
            content = decrypt_data(target_config.content_encrypted)
            apply_result = await self._apply_config_to_vps(target_config, content, task_id)
            
            if apply_result["success"]:
                # Mark current configs as rolled back
                current_configs = await self._get_current_configs(vps_id)
                for config in current_configs:
                    if config.id != target_config.id:
                        config.status = "rolled_back"
                        config.rollback_triggered = True
                
                # Update target config status
                target_config.status = "applied"
                target_config.applied_at = datetime.utcnow()
                await self.db.commit()
                
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "success",
                        result={"rolled_back_to_version": target_config.version}
                    )
                
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": f"Successfully rolled back to version {target_config.version}",
                    "version": target_config.version
                }
            else:
                if self.audit_service:
                    await self.audit_service.complete_action(
                        task_id, "failed", error_message=apply_result.get("error", "Rollback failed")
                    )
                
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": apply_result.get("error", "Rollback failed")
                }
                
        except Exception as e:
            sanitized_error = sanitize_error_message(str(e), task_id)
            
            if self.audit_service:
                await self.audit_service.complete_action(
                    task_id, "failed", error_message=sanitized_error["error"]
                )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": sanitized_error["error"]
            }
    
    async def get_config_versions(self, vps_id: str) -> List[Dict[str, Any]]:
        """Get all configuration versions for a VPS"""
        query = (
            select(NginxConfig)
            .where(NginxConfig.vps_id == vps_id)
            .order_by(desc(NginxConfig.version))
        )
        result = await self.db.execute(query)
        configs = result.scalars().all()
        
        return [
            {
                "id": str(config.id),
                "version": config.version,
                "author_id": str(config.author_id),
                "summary": config.summary,
                "status": config.status,
                "config_name": config.config_name,
                "config_type": config.config_type,
                "applied_at": config.applied_at.isoformat() if config.applied_at else None,
                "created_at": config.created_at.isoformat(),
                "is_active": config.is_active,
                "rollback_triggered": config.rollback_triggered
            }
            for config in configs
        ]
    
    async def get_config_content(self, config_id: str, mask_sensitive: bool = True) -> Optional[str]:
        """Get decrypted configuration content"""
        config = await self._get_config_by_id(config_id)
        if not config:
            return None
        
        content = decrypt_data(config.content_encrypted)
        
        if mask_sensitive:
            # Mask sensitive information like passwords
            content = self._mask_sensitive_content(content)
        
        return content
    
    # Private helper methods
    
    async def _get_latest_version(self, vps_id: str) -> Optional[int]:
        """Get the latest version number for a VPS"""
        query = (
            select(NginxConfig.version)
            .where(NginxConfig.vps_id == vps_id)
            .order_by(desc(NginxConfig.version))
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar()
    
    async def _get_config_by_id(self, config_id: str) -> Optional[NginxConfig]:
        """Get config by ID"""
        query = select(NginxConfig).where(NginxConfig.id == config_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_config_by_version(self, vps_id: str, version: int) -> Optional[NginxConfig]:
        """Get config by VPS and version"""
        query = (
            select(NginxConfig)
            .where(and_(NginxConfig.vps_id == vps_id, NginxConfig.version == version))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_last_successful_config(self, vps_id: str) -> Optional[NginxConfig]:
        """Get the last successfully applied config"""
        query = (
            select(NginxConfig)
            .where(and_(
                NginxConfig.vps_id == vps_id,
                NginxConfig.status == "applied",
                NginxConfig.rollback_triggered == False
            ))
            .order_by(desc(NginxConfig.applied_at))
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_current_configs(self, vps_id: str) -> List[NginxConfig]:
        """Get currently applied configs"""
        query = (
            select(NginxConfig)
            .where(and_(
                NginxConfig.vps_id == vps_id,
                NginxConfig.status == "applied"
            ))
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    def _generate_diff(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """Generate diff between two configurations"""
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="previous",
            tofile="current"
        ))
        
        return {
            "diff_lines": diff,
            "added_lines": len([line for line in diff if line.startswith('+') and not line.startswith('+++')]),
            "removed_lines": len([line for line in diff if line.startswith('-') and not line.startswith('---')])
        }
    
    async def _apply_config_to_vps(self, config: NginxConfig, content: str, task_id: str) -> Dict[str, Any]:
        """Apply configuration to VPS via SSH"""
        if not self.ssh_service:
            return {"success": False, "error": "SSH service not available"}
        
        try:
            vps_id = str(config.vps_id)
            
            # Create backup of current config
            backup_result = await self.ssh_service.backup_nginx_config(vps_id, task_id)
            if not backup_result["success"]:
                return {"success": False, "error": f"Failed to backup current config: {backup_result['error']}"}
            
            # Write new config to drafts directory
            drafts_path = f"/etc/nginx/managed.d/drafts/{config.config_name}_{config.version}.conf"
            write_result = await self.ssh_service.write_file(vps_id, drafts_path, content)
            if not write_result["success"]:
                return {"success": False, "error": f"Failed to write config file: {write_result['error']}"}
            
            # Test configuration
            test_result = await self.ssh_service.execute_command(vps_id, "nginx -t")
            if test_result["exit_code"] != 0:
                # Clean up draft file
                await self.ssh_service.execute_command(vps_id, f"rm -f {drafts_path}")
                return {"success": False, "error": f"nginx -t failed: {test_result['stderr']}"}
            
            # Move to active directory and create symlink
            active_path = f"/etc/nginx/managed.d/{config.config_name}_{config.version}.conf"
            enabled_path = f"/etc/nginx/sites-enabled/{config.config_name}.conf"
            
            commands = [
                f"mv {drafts_path} {active_path}",
                f"ln -sf {active_path} {enabled_path}",
                "systemctl reload nginx"
            ]
            
            for cmd in commands:
                result = await self.ssh_service.execute_command(vps_id, cmd)
                if result["exit_code"] != 0:
                    return {"success": False, "error": f"Command failed '{cmd}': {result['stderr']}"}
            
            return {"success": True, "message": "Configuration applied successfully"}
            
        except Exception as e:
            sanitized_error = sanitize_error_message(str(e), task_id)
            return {"success": False, "error": sanitized_error["error"]}
    
    async def _monitor_health_and_rollback(self, config_id: str, watch_window_seconds: int, task_id: str):
        """Monitor health and trigger automatic rollback if needed"""
        await asyncio.sleep(watch_window_seconds)
        
        try:
            config = await self._get_config_by_id(config_id)
            if not config or config.status != "applied":
                return
            
            # Perform health check
            health_result = await self._perform_health_check(config)
            
            config.health_check_passed = health_result["healthy"]
            config.health_check_details = health_result["details"]
            
            if not health_result["healthy"]:
                # Trigger automatic rollback
                config.rollback_triggered = True
                config.rollback_reason = f"Automatic rollback due to health check failure: {health_result['reason']}"
                config.status = "rolled_back"
                
                # Perform rollback
                rollback_result = await self.rollback_config(
                    str(config.vps_id), 
                    author_id=None  # System rollback
                )
                
                if self.audit_service:
                    await self.audit_service.log_action(
                        task_id=f"{task_id}_auto_rollback",
                        action="nginx_config_auto_rollback",
                        resource_type="nginx_config",
                        resource_id=config.id,
                        actor_id=None,
                        description="Automatic rollback triggered by health check failure",
                        details={
                            "original_task_id": task_id,
                            "health_check_result": health_result,
                            "rollback_result": rollback_result
                        },
                        status="success" if rollback_result["success"] else "failed"
                    )
            
            await self.db.commit()
            
        except Exception as e:
            # Log error but don't raise - this is a background task
            if self.audit_service:
                sanitized_error = sanitize_error_message(str(e), f"{task_id}_health_monitor")
                await self.audit_service.log_action(
                    task_id=f"{task_id}_health_monitor_error",
                    action="nginx_config_health_monitor_error",
                    resource_type="nginx_config",
                    resource_id=config_id,
                    actor_id=None,
                    description="Health monitoring failed",
                    details={"error": sanitized_error["error"]},
                    status="failed"
                )
    
    async def _perform_health_check(self, config: NginxConfig) -> Dict[str, Any]:
        """Perform health check on nginx and proxied services"""
        if not self.ssh_service:
            return {"healthy": True, "reason": "No SSH service available for health check", "details": {}}
        
        try:
            vps_id = str(config.vps_id)
            
            # Check nginx status
            nginx_status = await self.ssh_service.execute_command(vps_id, "systemctl is-active nginx")
            if nginx_status["stdout"].strip() != "active":
                return {
                    "healthy": False,
                    "reason": "Nginx service is not active",
                    "details": {"nginx_status": nginx_status["stdout"].strip()}
                }
            
            # Check for recent nginx errors
            error_check = await self.ssh_service.execute_command(
                vps_id, 
                "journalctl -u nginx --since='2 minutes ago' | grep -i error | wc -l"
            )
            
            error_count = int(error_check["stdout"].strip() or "0")
            if error_count > 10:  # Threshold for error spike
                return {
                    "healthy": False,
                    "reason": f"High error rate detected: {error_count} errors in last 2 minutes",
                    "details": {"error_count": error_count}
                }
            
            return {
                "healthy": True,
                "reason": "All health checks passed",
                "details": {"nginx_status": "active", "error_count": error_count}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "reason": f"Health check failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def _mask_sensitive_content(self, content: str) -> str:
        """Mask sensitive information in configuration content"""
        import re
        
        # Mask basic auth credentials
        content = re.sub(
            r'(auth_basic_user_file\s+[^;]+;.*?)([^\n]+)',
            r'\1[MASKED_AUTH_FILE]',
            content,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # Mask SSL certificate content
        content = re.sub(
            r'(-----BEGIN [^-]+-----)(.*?)(-----END [^-]+-----)',
            r'\1[MASKED_CERTIFICATE]\3',
            content,
            flags=re.DOTALL
        )
        
        return content