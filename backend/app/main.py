from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys

from app.core.config import settings
from app.core.database import init_db, close_db, AsyncSessionLocal
from app.api.v1.api import api_router
from app.services.metrics_service import create_metrics_middleware
from app.core.security import get_password_hash
from app.models.admin import Admin

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.LOG_FORMAT != 'json' else None,
    stream=sys.stdout
)

logger = logging.getLogger(__name__)


async def create_default_admin():
    """Create default admin user automatically"""
    async with AsyncSessionLocal() as db:
        try:
            # Check if admin already exists
            from sqlalchemy import select
            query = select(Admin).where(Admin.email == settings.ADMIN_EMAIL)
            result = await db.execute(query)
            existing_admin = result.scalar_one_or_none()
            
            if existing_admin:
                logger.info(f"Admin user {settings.ADMIN_EMAIL} already exists")
                return
            
            # Create new admin user
            admin = Admin(
                email=settings.ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                full_name="Default Administrator",
                is_active=True,
                is_superuser=True
            )
            
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            logger.info(f"Created default admin user: {settings.ADMIN_EMAIL}")
            logger.info(f"Default admin password: {settings.ADMIN_PASSWORD}")
            
        except Exception as e:
            logger.error(f"Failed to create default admin user: {e}")
            await db.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting SaaS Orchestration Platform")
    try:
        await init_db()
        logger.info("Database initialized successfully")
        
        # Create default admin user
        await create_default_admin()
        logger.info("Admin user initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SaaS Orchestration Platform")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A secure, production-ready SaaS orchestration platform with Nginx configuration editor",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Add metrics middleware
app.add_middleware(create_metrics_middleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SaaS Orchestration Platform",
        "version": "1.0.0",
        "timezone": settings.TIMEZONE
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler"""
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )
    # Add CORS headers for error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """General exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    response = JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500
        }
    )
    # Add CORS headers for error responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )