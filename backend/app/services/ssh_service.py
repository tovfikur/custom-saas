import paramiko
import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
from app.core.security import decrypt_data, sanitize_error_message, generate_secure_token
from app.core.config import settings

logger = logging.getLogger(__name__)


class SSHService:
    """Service for managing SSH connections and remote operations"""
    
    def __init__(self):
        self.connections = {}  # Cache for SSH connections
        self.connection_timeout = settings.SSH_TIMEOUT
    
    async def get_connection(self, vps_id: str, host_info: Dict[str, Any]) -> paramiko.SSHClient:
        """Get or create SSH connection to VPS"""
        
        # Check if we have a cached connection
        if vps_id in self.connections:
            try:
                # Test the connection
                conn = self.connections[vps_id]
                transport = conn.get_transport()
                if transport and transport.is_active():
                    return conn
                else:
                    # Connection is dead, remove from cache
                    del self.connections[vps_id]
            except Exception:
                # Connection error, remove from cache
                if vps_id in self.connections:
                    del self.connections[vps_id]
        
        # Create new connection
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Decrypt credentials if needed
            password = None
            private_key = None
            
            if host_info.get('password_encrypted'):
                password = decrypt_data(host_info['password_encrypted'])
            
            if host_info.get('private_key_encrypted'):
                private_key_str = decrypt_data(host_info['private_key_encrypted'])
                from io import StringIO
                private_key = paramiko.RSAKey.from_private_key(StringIO(private_key_str))
            
            # Connect
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.connect(
                    hostname=host_info['ip_address'],
                    port=host_info.get('port', 22),
                    username=host_info['username'],
                    password=password,
                    pkey=private_key,
                    timeout=self.connection_timeout,
                    banner_timeout=30
                )
            )
            
            # Cache the connection
            self.connections[vps_id] = client
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to VPS {vps_id}: {e}")
            try:
                client.close()
            except:
                pass
            raise
    
    async def execute_command(
        self, 
        vps_id: str, 
        command: str, 
        timeout: int = 300,
        host_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute command on remote VPS"""
        
        task_id = generate_secure_token(8)
        
        try:
            if not host_info:
                # This would normally fetch from database
                raise ValueError("Host info required for new connections")
            
            client = await self.get_connection(vps_id, host_info)
            
            # Execute command
            stdin, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.exec_command(command, timeout=timeout)
            )
            
            # Read output
            stdout_data = await asyncio.get_event_loop().run_in_executor(
                None, stdout.read
            )
            stderr_data = await asyncio.get_event_loop().run_in_executor(
                None, stderr.read
            )
            
            exit_code = stdout.channel.recv_exit_status()
            
            return {
                "success": exit_code == 0,
                "exit_code": exit_code,
                "stdout": stdout_data.decode('utf-8', errors='replace'),
                "stderr": stderr_data.decode('utf-8', errors='replace'),
                "task_id": task_id
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": error_msg["error"],
                "task_id": task_id
            }
    
    async def write_file(
        self, 
        vps_id: str, 
        remote_path: str, 
        content: str,
        mode: str = '644',
        host_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Write content to file on remote VPS"""
        
        task_id = generate_secure_token(8)
        
        try:
            if not host_info:
                raise ValueError("Host info required for new connections")
            
            client = await self.get_connection(vps_id, host_info)
            
            # Use SFTP to write file
            sftp = client.open_sftp()
            
            # Write file
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sftp.put(
                    localpath=None,  # We'll use file-like object
                    remotepath=remote_path
                )
            )
            
            # Actually write using a temporary local approach for safety
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, sftp.put, tmp_file_path, remote_path
                )
                
                # Set file permissions
                await asyncio.get_event_loop().run_in_executor(
                    None, sftp.chmod, remote_path, int(mode, 8)
                )
                
            finally:
                os.unlink(tmp_file_path)
                sftp.close()
            
            return {
                "success": True,
                "message": f"File written to {remote_path}",
                "task_id": task_id
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "error": error_msg["error"],
                "task_id": task_id
            }
    
    async def read_file(
        self, 
        vps_id: str, 
        remote_path: str,
        host_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Read file content from remote VPS"""
        
        task_id = generate_secure_token(8)
        
        try:
            if not host_info:
                raise ValueError("Host info required for new connections")
            
            client = await self.get_connection(vps_id, host_info)
            
            # Use SFTP to read file
            sftp = client.open_sftp()
            
            try:
                # Read file
                with sftp.file(remote_path, 'r') as remote_file:
                    content = await asyncio.get_event_loop().run_in_executor(
                        None, remote_file.read
                    )
                
                return {
                    "success": True,
                    "content": content.decode('utf-8', errors='replace'),
                    "task_id": task_id
                }
                
            finally:
                sftp.close()
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "error": error_msg["error"],
                "task_id": task_id
            }
    
    async def file_exists(
        self, 
        vps_id: str, 
        remote_path: str,
        host_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if file exists on remote VPS"""
        
        try:
            result = await self.execute_command(
                vps_id, f"test -f {remote_path}", host_info=host_info
            )
            return result["exit_code"] == 0
        except Exception:
            return False
    
    async def backup_nginx_config(
        self, 
        vps_id: str, 
        task_id: str,
        host_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create backup of current nginx configuration"""
        
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"/srv/backups/nginx/{timestamp}"
            
            commands = [
                f"mkdir -p {backup_dir}",
                f"cp -r /etc/nginx {backup_dir}/",
                f"systemctl status nginx > {backup_dir}/nginx_status.txt || true",
                f"nginx -t 2> {backup_dir}/nginx_test.txt || true"
            ]
            
            for cmd in commands:
                result = await self.execute_command(vps_id, cmd, host_info=host_info)
                if not result["success"] and "mkdir" in cmd:
                    # If mkdir fails, the directory might exist
                    continue
            
            return {
                "success": True,
                "backup_path": backup_dir,
                "task_id": task_id
            }
            
        except Exception as e:
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "error": error_msg["error"],
                "task_id": task_id
            }
    
    async def test_connection(self, host_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test SSH connection to a VPS"""
        
        task_id = generate_secure_token(8)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Prepare credentials
            password = None
            private_key = None
            
            if host_info.get('password_encrypted'):
                password = decrypt_data(host_info['password_encrypted'])
            
            if host_info.get('private_key_encrypted'):
                private_key_str = decrypt_data(host_info['private_key_encrypted'])
                from io import StringIO
                private_key = paramiko.RSAKey.from_private_key(StringIO(private_key_str))
            
            # Test connection
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.connect(
                    hostname=host_info['ip_address'],
                    port=host_info.get('port', 22),
                    username=host_info['username'],
                    password=password,
                    pkey=private_key,
                    timeout=10,  # Shorter timeout for testing
                    banner_timeout=10
                )
            )
            
            # Test basic command
            stdin, stdout, stderr = client.exec_command('whoami', timeout=10)
            whoami_result = stdout.read().decode().strip()
            
            client.close()
            
            return {
                "success": True,
                "message": f"Connection successful as user: {whoami_result}",
                "task_id": task_id
            }
            
        except Exception as e:
            try:
                client.close()
            except:
                pass
            
            error_msg = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "error": error_msg["error"],
                "task_id": task_id
            }
    
    def close_connection(self, vps_id: str):
        """Close and remove cached SSH connection"""
        if vps_id in self.connections:
            try:
                self.connections[vps_id].close()
            except:
                pass
            del self.connections[vps_id]
    
    def close_all_connections(self):
        """Close all cached SSH connections"""
        for vps_id in list(self.connections.keys()):
            self.close_connection(vps_id)