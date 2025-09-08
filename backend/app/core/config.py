from pydantic import Field
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_TEST_URL: str = Field(default="", env="DATABASE_TEST_URL")
    
    # Redis
    REDIS_URL: str = Field(..., env="REDIS_URL")
    
    # Security
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")
    
    # Timezone
    TIMEZONE: str = Field(default="Asia/Dhaka", env="TIMEZONE")
    
    # Admin
    ADMIN_EMAIL: str = Field(..., env="ADMIN_EMAIL")
    ADMIN_PASSWORD: str = Field(..., env="ADMIN_PASSWORD")
    
    # SSH
    SSH_PRIVATE_KEY_PATH: str = Field(default="/app/keys/id_rsa", env="SSH_PRIVATE_KEY_PATH")
    SSH_TIMEOUT: int = Field(default=30, env="SSH_TIMEOUT")
    
    # Nginx Configuration
    NGINX_CONFIG_WATCH_WINDOW_SECONDS: int = Field(default=120, env="NGINX_CONFIG_WATCH_WINDOW_SECONDS")
    NGINX_CONFIG_MAX_VERSIONS: int = Field(default=10, env="NGINX_CONFIG_MAX_VERSIONS")
    
    # Monitoring
    PROMETHEUS_PORT: int = Field(default=8001, env="PROMETHEUS_PORT")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # Celery
    CELERY_BROKER_URL: str = Field(..., env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(..., env="CELERY_RESULT_BACKEND")
    
    # Development
    DEBUG: bool = Field(default=False, env="DEBUG")
    RELOAD: bool = Field(default=False, env="RELOAD")
    
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SaaS Orchestration Platform"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()