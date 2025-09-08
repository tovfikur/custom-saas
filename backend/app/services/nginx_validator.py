import re
import tempfile
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from app.core.security import sanitize_error_message


@dataclass
class ValidationResult:
    """Result of nginx configuration validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    task_id: str
    nginx_test_output: Optional[str] = None


class NginxConfigValidator:
    """Comprehensive Nginx configuration validator with safety checks"""
    
    # Forbidden directives for security
    FORBIDDEN_DIRECTIVES = [
        "exec",
        "lua_code_cache off",
        "perl_modules",
        "perl_require"
    ]
    
    # Dangerous include patterns
    DANGEROUS_INCLUDE_PATTERNS = [
        r"/etc/passwd",
        r"/etc/shadow",
        r"/root/",
        r"/home/[^/]*/\.",
        r"/var/log/",
        r"/proc/"
    ]
    
    # Required security headers
    RECOMMENDED_SECURITY_HEADERS = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection"
    ]
    
    def __init__(self, ssh_service=None):
        self.ssh_service = ssh_service
    
    async def validate_config(
        self, 
        config_content: str, 
        vps_id: str, 
        dry_run: bool = True
    ) -> ValidationResult:
        """
        Comprehensive validation of nginx configuration
        
        Args:
            config_content: The nginx configuration to validate
            vps_id: ID of the VPS where config will be applied
            dry_run: Whether to only validate without applying
            
        Returns:
            ValidationResult with validation details
        """
        from app.core.security import generate_secure_token
        task_id = generate_secure_token(8)
        
        errors = []
        warnings = []
        
        # 1. Static validation (syntax, security, policy)
        static_result = self._static_validation(config_content)
        errors.extend(static_result['errors'])
        warnings.extend(static_result['warnings'])
        
        # 2. Remote nginx -t validation if not dry_run
        nginx_test_output = None
        if not dry_run and self.ssh_service:
            try:
                nginx_result = await self._remote_nginx_test(config_content, vps_id, task_id)
                nginx_test_output = nginx_result['output']
                if not nginx_result['success']:
                    errors.extend(nginx_result['errors'])
            except Exception as e:
                errors.append(f"Failed to perform remote nginx test: {str(e)}")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            task_id=task_id,
            nginx_test_output=nginx_test_output
        )
    
    def _static_validation(self, config_content: str) -> Dict[str, List[str]]:
        """Perform static validation checks"""
        errors = []
        warnings = []
        
        # Check for forbidden directives
        for directive in self.FORBIDDEN_DIRECTIVES:
            if directive in config_content:
                errors.append(f"Forbidden directive '{directive}' detected")
        
        # Check for dangerous includes
        for pattern in self.DANGEROUS_INCLUDE_PATTERNS:
            if re.search(pattern, config_content, re.IGNORECASE):
                errors.append(f"Dangerous include pattern detected: {pattern}")
        
        # Check for basic syntax issues
        if not self._has_balanced_braces(config_content):
            errors.append("Unbalanced braces detected in configuration")
        
        # Check server block structure
        server_blocks = self._extract_server_blocks(config_content)
        for i, block in enumerate(server_blocks):
            block_errors = self._validate_server_block(block, i)
            errors.extend(block_errors)
        
        # Security recommendations
        if not re.search(r'client_max_body_size\s+', config_content):
            warnings.append("Consider setting client_max_body_size to prevent large uploads")
        
        if not re.search(r'proxy_read_timeout\s+', config_content):
            warnings.append("Consider setting proxy_read_timeout to prevent hanging connections")
        
        # Check for security headers
        for header in self.RECOMMENDED_SECURITY_HEADERS:
            if header not in config_content:
                warnings.append(f"Consider adding security header: {header}")
        
        return {"errors": errors, "warnings": warnings}
    
    async def _remote_nginx_test(self, config_content: str, vps_id: str, task_id: str) -> Dict:
        """Run nginx -t on remote VPS with candidate configuration"""
        try:
            # Create temporary config file on remote host
            temp_config_path = f"/tmp/nginx_test_{task_id}.conf"
            
            # Upload config content to temp file
            await self.ssh_service.write_file(vps_id, temp_config_path, config_content)
            
            # Run nginx -t with the temp config
            result = await self.ssh_service.execute_command(
                vps_id, 
                f"nginx -t -c {temp_config_path}",
                timeout=30
            )
            
            # Clean up temp file
            await self.ssh_service.execute_command(vps_id, f"rm -f {temp_config_path}")
            
            if result['exit_code'] == 0:
                return {
                    "success": True,
                    "output": result['stdout'],
                    "errors": []
                }
            else:
                # Sanitize error output
                sanitized_error = sanitize_error_message(result['stderr'], task_id)
                return {
                    "success": False,
                    "output": result['stderr'],
                    "errors": [f"nginx -t failed: {sanitized_error['error']}"]
                }
        
        except Exception as e:
            sanitized_error = sanitize_error_message(str(e), task_id)
            return {
                "success": False,
                "output": "",
                "errors": [f"Remote validation failed: {sanitized_error['error']}"]
            }
    
    def _has_balanced_braces(self, content: str) -> bool:
        """Check if braces are balanced in the configuration"""
        open_count = 0
        in_string = False
        escape_next = False
        
        for char in content:
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char in ['"', "'"]:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    open_count += 1
                elif char == '}':
                    open_count -= 1
                    if open_count < 0:
                        return False
        
        return open_count == 0
    
    def _extract_server_blocks(self, content: str) -> List[str]:
        """Extract server blocks from configuration"""
        blocks = []
        lines = content.split('\n')
        current_block = []
        in_server_block = False
        brace_count = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('server {') or stripped.startswith('server{'):
                in_server_block = True
                current_block = [line]
                brace_count = 1
            elif in_server_block:
                current_block.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count == 0:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                    in_server_block = False
        
        return blocks
    
    def _validate_server_block(self, block: str, block_index: int) -> List[str]:
        """Validate individual server block"""
        errors = []
        
        # Check for required directives
        if 'listen' not in block:
            errors.append(f"Server block {block_index + 1}: Missing 'listen' directive")
        
        if 'server_name' not in block:
            errors.append(f"Server block {block_index + 1}: Missing 'server_name' directive")
        
        # Check for potential issues
        if 'proxy_pass' in block and 'proxy_set_header Host' not in block:
            errors.append(f"Server block {block_index + 1}: proxy_pass without proper Host header")
        
        # Check client_max_body_size limits
        body_size_match = re.search(r'client_max_body_size\s+(\d+[kmg]?);', block, re.IGNORECASE)
        if body_size_match:
            size_str = body_size_match.group(1).lower()
            try:
                # Convert to MB for comparison
                if size_str.endswith('g'):
                    size_mb = int(size_str[:-1]) * 1024
                elif size_str.endswith('k'):
                    size_mb = int(size_str[:-1]) / 1024
                elif size_str.endswith('m'):
                    size_mb = int(size_str[:-1])
                else:
                    size_mb = int(size_str) / (1024 * 1024)  # bytes to MB
                
                if size_mb > 100:  # Limit to 100MB
                    errors.append(f"Server block {block_index + 1}: client_max_body_size too large ({size_str})")
            except ValueError:
                errors.append(f"Server block {block_index + 1}: Invalid client_max_body_size format")
        
        return errors