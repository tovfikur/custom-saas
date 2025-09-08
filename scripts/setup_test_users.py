#!/usr/bin/env python3
"""
Script to create test admin users in the test database for login testing.
This replaces the need for demo/hardcoded credentials.
"""
import asyncio
import sys
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import uuid

# Set environment variables for the script
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://test_user:test_password@localhost:5433/test_saas_orchestrator')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-secret-key-for-testing-only')
os.environ.setdefault('ENCRYPTION_KEY', 'test-32-byte-encryption-key-test-only')
os.environ.setdefault('ADMIN_EMAIL', 'admin@example.com')
os.environ.setdefault('ADMIN_PASSWORD', 'admin123')
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379')

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.models.admin import Admin, Base
from app.core.security import get_password_hash

# Test database configuration
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_password@localhost:5433/test_saas_orchestrator"

async def setup_test_database():
    """Create tables and test admin users"""
    engine = create_async_engine(TEST_DATABASE_URL)
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as session:
            # Test admin users
            test_admins = [
                {
                    "email": "admin",
                    "full_name": "Default Admin",
                    "password": "admin",
                    "is_superuser": True
                },
                {
                    "email": "test.admin@example.com",
                    "full_name": "Test Admin",
                    "password": "test123456",
                    "is_superuser": True
                },
                {
                    "email": "regular.admin@example.com", 
                    "full_name": "Regular Admin",
                    "password": "regular123456",
                    "is_superuser": False
                }
            ]
            
            for admin_data in test_admins:
                admin = Admin(
                    id=str(uuid.uuid4()),
                    email=admin_data["email"],
                    full_name=admin_data["full_name"],
                    hashed_password=get_password_hash(admin_data["password"]),
                    is_active=admin_data.get("is_active", True),
                    is_superuser=admin_data["is_superuser"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(admin)
            
            await session.commit()
            
        print("SUCCESS: Test database setup completed!")
        print("\nTest Admin Users Created:")
        print("1. admin / admin (Default Super Admin)")
        print("2. test.admin@example.com / test123456 (Super Admin)")
        print("3. regular.admin@example.com / regular123456 (Regular Admin)")
        
    except Exception as e:
        print(f"ERROR: Setting up test database: {e}")
        return False
    finally:
        await engine.dispose()
    
    return True

async def main():
    """Main function"""
    print("Setting up test database and users...")
    success = await setup_test_database()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())