import os
import json
import tempfile
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import ansible_runner
from app.core.config import settings
from app.core.security import decrypt_data, sanitize_error_message, generate_secure_token
import logging

logger = logging.getLogger(__name__)


class AnsibleService:
    """Service for executing Ansible playbooks and roles"""
    
    def __init__(self):
        self.ansible_dir = Path(__file__).parent.parent.parent.parent / "ansible"
        self.playbooks_dir = self.ansible_dir / "playbooks"
        self.inventory_dir = self.ansible_dir / "inventory"
        self.roles_path = self.ansible_dir / "roles"
        
    async def run_nginx_config_apply(
        self,
        vps_host_info: Dict[str, Any],
        config_name: str,
        config_content: str,
        config_version: str,
        dry_run: bool = False,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run ansible playbook to apply nginx configuration"""
        
        if not task_id:
            task_id = generate_secure_token(8)
        
        try:
            # Create temporary inventory
            inventory = await self._create_temp_inventory([vps_host_info])
            
            # Prepare extra variables
            extra_vars = {
                "config_name_param": config_name,
                "config_content_param": config_content,
                "config_version_param": config_version,
                "task_id_param": task_id,
                "dry_run_param": dry_run,
                "target_host": vps_host_info['hostname']
            }
            
            # Run playbook
            result = await self._run_playbook(
                "nginx_config_apply.yml",
                inventory,
                extra_vars,
                task_id
            )
            
            return {
                "success": result["success"],
                "task_id": task_id,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "results": result.get("results", {}),
                "dry_run": dry_run
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def run_nginx_config_rollback(
        self,
        vps_host_info: Dict[str, Any],
        config_name: str,
        rollback_version: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run ansible playbook to rollback nginx configuration"""
        
        if not task_id:
            task_id = generate_secure_token(8)
        
        try:
            # Create temporary inventory
            inventory = await self._create_temp_inventory([vps_host_info])
            
            # Prepare extra variables
            extra_vars = {
                "config_name_param": config_name,
                "rollback_version_param": rollback_version,
                "task_id_param": task_id,
                "target_host": vps_host_info['hostname']
            }
            
            # Run playbook
            result = await self._run_playbook(
                "nginx_config_rollback.yml",
                inventory,
                extra_vars,
                task_id
            )
            
            return {
                "success": result["success"],
                "task_id": task_id,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "results": result.get("results", {}),
                "rollback_version": rollback_version
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def run_vps_bootstrap(
        self,
        vps_host_info: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run ansible playbook to bootstrap a VPS"""
        
        if not task_id:
            task_id = generate_secure_token(8)
        
        try:
            # Create temporary inventory
            inventory = await self._create_temp_inventory([vps_host_info])
            
            # Prepare extra variables
            extra_vars = {
                "task_id_param": task_id,
                "target_host": vps_host_info['hostname']
            }
            
            # Run playbook
            result = await self._run_playbook(
                "vps_bootstrap.yml",
                inventory,
                extra_vars,
                task_id
            )
            
            return {
                "success": result["success"],
                "task_id": task_id,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "results": result.get("results", {}),
                "bootstrap_results": result.get("results", {}).get("bootstrap_results", {})
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg["error"]
            }
    
    async def _create_temp_inventory(self, hosts: List[Dict[str, Any]]) -> str:
        """Create temporary ansible inventory file"""
        
        inventory_content = "[vps_hosts]\n"
        
        for host in hosts:
            # Decrypt credentials
            password = None
            private_key_file = None
            
            if host.get('password_encrypted'):
                password = decrypt_data(host['password_encrypted'])
            
            if host.get('private_key_encrypted'):
                # Create temporary key file
                private_key_content = decrypt_data(host['private_key_encrypted'])
                key_fd, key_file = tempfile.mkstemp(suffix='.pem', prefix='ansible_key_')
                try:
                    os.write(key_fd, private_key_content.encode())
                    os.chmod(key_file, 0o600)
                    private_key_file = key_file
                finally:
                    os.close(key_fd)
            
            # Build inventory entry
            host_entry = f"{host['hostname']} ansible_host={host['ip_address']}"
            host_entry += f" ansible_port={host.get('port', 22)}"
            host_entry += f" ansible_user={host['username']}"
            
            if password:
                host_entry += f" ansible_ssh_pass={password}"
            elif private_key_file:
                host_entry += f" ansible_ssh_private_key_file={private_key_file}"
            
            inventory_content += host_entry + "\n"
        
        # Add common variables
        inventory_content += "\n[vps_hosts:vars]\n"
        inventory_content += "ansible_python_interpreter=/usr/bin/python3\n"
        inventory_content += "ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        
        # Write to temporary file
        fd, temp_file = tempfile.mkstemp(suffix='.ini', prefix='ansible_inventory_')
        try:
            os.write(fd, inventory_content.encode())
            return temp_file
        finally:
            os.close(fd)
    
    async def _run_playbook(
        self,
        playbook_name: str,
        inventory_file: str,
        extra_vars: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """Execute ansible playbook"""
        
        playbook_path = self.playbooks_dir / playbook_name
        
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")
        
        # Create temporary directory for ansible run
        with tempfile.TemporaryDirectory(prefix=f'ansible_run_{task_id}_') as temp_dir:
            
            # Run ansible playbook
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_ansible_runner,
                str(playbook_path),
                inventory_file,
                extra_vars,
                temp_dir
            )
            
            # Clean up inventory file
            try:
                os.unlink(inventory_file)
            except:
                pass
            
            return result
    
    def _execute_ansible_runner(
        self,
        playbook_path: str,
        inventory_file: str,
        extra_vars: Dict[str, Any],
        private_data_dir: str
    ) -> Dict[str, Any]:
        """Execute ansible-runner in thread executor"""
        
        try:
            # Run the playbook
            runner_result = ansible_runner.run(
                private_data_dir=private_data_dir,
                playbook=os.path.basename(playbook_path),
                inventory=inventory_file,
                extravars=extra_vars,
                roles_path=str(self.roles_path),
                verbosity=2 if settings.DEBUG else 1,
                quiet=False,
                suppress_ansible_output=False
            )
            
            # Collect results
            stdout_lines = []
            stderr_lines = []
            
            # Collect stdout
            for event in runner_result.events:
                if event.get('event') in ['runner_on_ok', 'runner_on_failed', 'runner_on_unreachable']:
                    if 'stdout' in event.get('event_data', {}):
                        stdout_lines.append(event['event_data']['stdout'])
                
                if event.get('event') == 'runner_on_failed':
                    if 'stderr' in event.get('event_data', {}):
                        stderr_lines.append(event['event_data']['stderr'])
            
            # Try to extract results from final events
            results = {}
            for event in reversed(runner_result.events):
                if event.get('event') == 'runner_on_ok':
                    event_data = event.get('event_data', {})
                    if 'res' in event_data:
                        res = event_data['res']
                        if 'ansible_facts' in res:
                            results.update(res['ansible_facts'])
                        break
            
            return {
                "success": runner_result.status == "successful",
                "status": runner_result.status,
                "rc": runner_result.rc,
                "stdout": "\n".join(stdout_lines),
                "stderr": "\n".join(stderr_lines),
                "results": results,
                "stats": runner_result.stats
            }
            
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "rc": 1,
                "stdout": "",
                "stderr": str(e),
                "results": {},
                "stats": {}
            }
    
    def get_available_playbooks(self) -> List[str]:
        """Get list of available playbooks"""
        try:
            playbooks = []
            for file in self.playbooks_dir.glob("*.yml"):
                playbooks.append(file.name)
            return sorted(playbooks)
        except Exception:
            return []
    
    def get_available_roles(self) -> List[str]:
        """Get list of available roles"""
        try:
            roles = []
            for role_dir in self.roles_path.iterdir():
                if role_dir.is_dir() and (role_dir / "tasks" / "main.yml").exists():
                    roles.append(role_dir.name)
            return sorted(roles)
        except Exception:
            return []