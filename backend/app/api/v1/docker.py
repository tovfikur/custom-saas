from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.admin import Admin
from app.services.docker_service import DockerService
from app.services.ssh_service import SSHService
from app.services.audit_service import AuditService
import logging
import json
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models
class DockerStatusResponse(BaseModel):
    success: bool
    status: str
    version: str
    containers_running: int
    containers_total: int
    images_count: int
    system_info: Dict[str, Any]


class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    status: str
    created: str
    ports: List[str]
    labels: Dict[str, str]


class ContainerActionRequest(BaseModel):
    action: str  # start, stop, restart, remove
    container_id: str


class DockerContainersResponse(BaseModel):
    success: bool
    containers: List[ContainerInfo]


@router.get("/vps/{vps_id}/docker/status", response_model=DockerStatusResponse)
async def get_docker_status(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Docker status on VPS"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        docker_service = DockerService(ssh_service, audit_service)
        
        result = await docker_service.get_docker_status(vps_id, db)
        
        return DockerStatusResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get Docker status for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Docker status"
        )


@router.get("/vps/{vps_id}/docker/containers", response_model=DockerContainersResponse)
async def get_docker_containers(
    vps_id: str,
    all_containers: bool = True,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Docker containers on VPS"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        docker_service = DockerService(ssh_service, audit_service)
        
        result = await docker_service.get_containers(vps_id, db, all_containers)
        
        return DockerContainersResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get Docker containers for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Docker containers"
        )


@router.post("/vps/{vps_id}/docker/container/action")
async def docker_container_action(
    vps_id: str,
    request_data: ContainerActionRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Perform action on Docker container"""
    print('Request Data:', request_data)
    print('VPS ID:', vps_id)
    print('Admin ID:', current_admin.id)
    print('Action:', request_data.action)
    print('Container ID:', request_data.container_id)
    print('DB Session:', db)
    print("-------------------------------------------------------------------------------------------")
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        docker_service = DockerService(ssh_service, audit_service)
        print("Initialized services")
        print("-------------------------------------------------------------------------------------------")        
        result = await docker_service.container_action(
            vps_id, 
            db, 
            request_data.container_id, 
            request_data.action,
            str(current_admin.id)
        )
        print("Result:", result)
        print("-------------------------------------------------------------------------------------------")
        return result
        
    except Exception as e:
        logger.error(f"Failed to perform Docker action {request_data.action} on container {request_data.container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {request_data.action} container"
        )


@router.get("/vps/{vps_id}/docker/images")
async def get_docker_images(
    vps_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get Docker images on VPS"""
    try:
        audit_service = AuditService(db)
        ssh_service = SSHService()
        docker_service = DockerService(ssh_service, audit_service)
        
        result = await docker_service.get_images(vps_id, db)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Docker images for VPS {vps_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Docker images"
        )


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
    
    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
    
    async def send_personal_message(self, message: str, connection_id: str):
        if connection_id in self.active_connections:
            await self.active_connections[connection_id].send_text(message)


manager = ConnectionManager()


@router.websocket("/vps/{vps_id}/terminal")
async def vps_terminal_websocket(websocket: WebSocket, vps_id: str):
    """WebSocket endpoint for VPS terminal"""
    connection_id = f"vps_terminal_{vps_id}"
    await manager.connect(websocket, connection_id)
    
    ssh_service = SSHService()
    ssh_client = None
    
    try:
        # Get VPS details and establish SSH connection
        from sqlalchemy import select
        from app.models.vps_host import VPSHost
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            query = select(VPSHost).where(VPSHost.id == vps_id)
            result = await db.execute(query)
            vps = result.scalar_one_or_none()
            
            if not vps:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "VPS not found"
                }))
                return
            
            # Establish SSH connection
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await ssh_service.get_connection(vps_id, host_info)
            
            if not ssh_client:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": "Failed to connect to VPS"
                }))
                return
            
            # Create interactive shell
            shell = ssh_client.invoke_shell()
            shell.settimeout(0.1)
            
            await websocket.send_text(json.dumps({
                "type": "connected",
                "message": f"Connected to {vps.name} ({vps.ip_address})"
            }))
            
            # Handle bidirectional communication
            async def read_from_shell():
                while True:
                    try:
                        if shell.recv_ready():
                            output = shell.recv(1024).decode('utf-8', errors='ignore')
                            await manager.send_personal_message(json.dumps({
                                "type": "output",
                                "data": output
                            }), connection_id)
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.error(f"Error reading from shell: {e}")
                        break
            
            # Start reading from shell
            read_task = asyncio.create_task(read_from_shell())
            
            while True:
                try:
                    # Receive command from WebSocket
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message.get("type") == "command":
                        command = message.get("data", "")
                        shell.send(command)
                        
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
            
            # Cleanup
            read_task.cancel()
            
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        if ssh_client:
            ssh_client.close()
        manager.disconnect(connection_id)


@router.websocket("/vps/{vps_id}/container/{container_id}/terminal") 
async def container_terminal_websocket(websocket: WebSocket, vps_id: str, container_id: str):
    """WebSocket endpoint for container terminal"""
    connection_id = f"container_terminal_{vps_id}_{container_id}"
    await manager.connect(websocket, connection_id)
    
    ssh_service = SSHService()
    ssh_client = None
    
    try:
        # Get VPS details and establish SSH connection
        from sqlalchemy import select
        from app.models.vps_host import VPSHost
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            query = select(VPSHost).where(VPSHost.id == vps_id)
            result = await db.execute(query)
            vps = result.scalar_one_or_none()
            
            if not vps:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "VPS not found"
                }))
                return
            
            # Establish SSH connection
            host_info = {
                'ip_address': vps.ip_address,
                'port': vps.port,
                'username': vps.username,
                'password_encrypted': vps.password_encrypted,
                'private_key_encrypted': vps.private_key_encrypted
            }
            ssh_client = await ssh_service.get_connection(vps_id, host_info)
            
            if not ssh_client:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Failed to connect to VPS" 
                }))
                return
            
            # Execute docker exec command for interactive shell
            command = f"docker exec -it {container_id} /bin/bash || docker exec -it {container_id} /bin/sh"
            shell = ssh_client.invoke_shell()
            shell.send(f"{command}\n")
            
            await websocket.send_text(json.dumps({
                "type": "connected",
                "message": f"Connected to container {container_id}"
            }))
            
            # Handle bidirectional communication (similar to VPS terminal)
            async def read_from_shell():
                while True:
                    try:
                        if shell.recv_ready():
                            output = shell.recv(1024).decode('utf-8', errors='ignore')
                            await manager.send_personal_message(json.dumps({
                                "type": "output",
                                "data": output
                            }), connection_id)
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.error(f"Error reading from container shell: {e}")
                        break
            
            read_task = asyncio.create_task(read_from_shell())
            
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message.get("type") == "command":
                        command = message.get("data", "")
                        shell.send(command)
                        
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Container WebSocket error: {e}")
                    break
            
            read_task.cancel()
            
    except Exception as e:
        logger.error(f"Container terminal WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
    finally:
        if ssh_client:
            ssh_client.close()
        manager.disconnect(connection_id)