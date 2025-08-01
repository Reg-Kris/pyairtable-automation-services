"""
Configuration management for PyAirtable Automation Services.
"""

import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8006
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    WORKERS: int = 4
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./automation_services.db"
    DATABASE_ECHO: bool = False
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    
    # File Storage Configuration
    UPLOAD_DIRECTORY: str = "./uploads"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx", ".xls"
    ]
    
    # Workflow Configuration
    MAX_WORKFLOW_EXECUTIONS: int = 1000
    EXECUTION_TIMEOUT: int = 3600  # 1 hour
    SCHEDULER_INTERVAL: int = 60  # seconds
    
    # PyAirtable Configuration
    AIRTABLE_API_KEY: str = ""
    AIRTABLE_BASE_ID: str = ""
    
    # Background Tasks
    TASK_QUEUE_SIZE: int = 100
    TASK_WORKER_COUNT: int = 4
    
    # File Processing
    TEXT_EXTRACTION_TIMEOUT: int = 300  # 5 minutes
    PDF_MAX_PAGES: int = 1000
    
    # Monitoring
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL: int = 30
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string or list."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v):
        """Parse allowed extensions from string or list."""
        if isinstance(v, str):
            extensions = [ext.strip() for ext in v.split(",")]
            return [ext if ext.startswith(".") else f".{ext}" for ext in extensions]
        return v
    
    @field_validator("UPLOAD_DIRECTORY")
    @classmethod
    def validate_upload_directory(cls, v):
        """Ensure upload directory exists."""
        os.makedirs(v, exist_ok=True)
        return v
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


# Create global settings instance
settings = Settings()


def get_database_url() -> str:
    """Get database URL with proper formatting."""
    if settings.DATABASE_URL.startswith("sqlite"):
        # Ensure SQLite directory exists
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    return settings.DATABASE_URL


def get_redis_url() -> str:
    """Get Redis URL with authentication if provided."""
    if settings.REDIS_PASSWORD:
        # Insert password into Redis URL
        if "://" in settings.REDIS_URL:
            protocol, rest = settings.REDIS_URL.split("://", 1)
            return f"{protocol}://:{settings.REDIS_PASSWORD}@{rest}"
    
    return settings.REDIS_URL


def is_file_allowed(filename: str) -> bool:
    """Check if file extension is allowed."""
    if not filename:
        return False
    
    extension = os.path.splitext(filename.lower())[1]
    return extension in [ext.lower() for ext in settings.ALLOWED_EXTENSIONS]


def get_file_size_limit() -> int:
    """Get maximum file size in bytes."""
    return settings.MAX_FILE_SIZE


def get_upload_path(filename: str) -> str:
    """Get full upload path for a file."""
    return os.path.join(settings.UPLOAD_DIRECTORY, filename)