from fastapi import APIRouter
from .auth import router as auth_router
from .nginx import router as nginx_router
from .vps import router as vps_router
from .monitoring import router as monitoring_router
from .docker import router as docker_router
from .docker_schedule import router as docker_schedule_router
from .odoo import router as odoo_router
from .deployments import router as deployments_router

api_router = APIRouter()

# Include all API routes
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(nginx_router, tags=["nginx-config"])
api_router.include_router(vps_router, tags=["vps-management"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(docker_router, tags=["docker-management"])
api_router.include_router(docker_schedule_router, tags=["docker-scheduling"])
api_router.include_router(odoo_router, prefix="/odoo", tags=["odoo-deployment"])
api_router.include_router(deployments_router)