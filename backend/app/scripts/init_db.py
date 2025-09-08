import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.admin import Admin
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_admin_user():
    """Create default admin user"""
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
                full_name="System Administrator",
                is_active=True,
                is_superuser=True
            )
            
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            logger.info(f"Created admin user: {settings.ADMIN_EMAIL}")
            logger.info(f"Admin password: {settings.ADMIN_PASSWORD}")
            
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            await db.rollback()
            raise


async def main():
    """Initialize database and create admin user"""
    try:
        logger.info("Initializing database...")
        await init_db()
        
        logger.info("Creating default admin user...")
        await create_admin_user()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())