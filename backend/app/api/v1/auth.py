from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.admin import Admin
from app.api.deps import get_current_active_admin
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login: str


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Admin login endpoint"""
    try:
        # Get admin by email or username (special case for "admin")
        if form_data.username == "admin":
            # Special case: allow login with just "admin" username
            from app.core.config import settings
            query = select(Admin).where(Admin.email == settings.ADMIN_EMAIL)
        else:
            # Normal case: use email
            query = select(Admin).where(Admin.email == form_data.username)
        
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, admin.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if admin is active
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account is inactive"
            )
        
        # Update last login
        admin.last_login = datetime.utcnow()
        await db.commit()
        
        # Create access token
        access_token_expires = timedelta(minutes=1440)  # 24 hours
        access_token = create_access_token(
            data={"sub": str(admin.id)}, expires_delta=access_token_expires
        )
        
        logger.info(f"Admin {admin.email} logged in successfully")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_active_admin)
):
    """Get current admin information"""
    return AdminResponse(
        id=str(current_admin.id),
        email=current_admin.email,
        full_name=current_admin.full_name or "",
        is_active=current_admin.is_active,
        is_superuser=current_admin.is_superuser,
        last_login=current_admin.last_login.isoformat() if current_admin.last_login else ""
    )