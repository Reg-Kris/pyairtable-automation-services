"""
Database models and connection management for PyAirtable Automation Services.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
import json

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, LargeBinary, Float, Enum as SQLEnum
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func
import redis.asyncio as redis

from config import settings, get_database_url, get_redis_url

# Database setup
Base = declarative_base()
engine = None
async_session = None
redis_client = None


class FileStatus(str, Enum):
    """File processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DELETED = "deleted"


class WorkflowStatus(str, Enum):
    """Workflow status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


class ExecutionStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileRecord(Base):
    """File record model."""
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    file_hash = Column(String(64), index=True)
    
    status = Column(SQLEnum(FileStatus), default=FileStatus.UPLOADED, index=True)
    
    # Extracted content
    content = Column(Text)
    metadata = Column(JSON, default=dict)
    
    # Processing info
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    workflow_executions = relationship("WorkflowExecution", back_populates="triggered_file")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "file_hash": self.file_hash,
            "status": self.status.value if self.status else None,
            "metadata": self.metadata or {},
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "processing_completed_at": self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            "processing_error": self.processing_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Workflow(Base):
    """Workflow model."""
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    
    # Configuration
    config = Column(JSON, nullable=False)
    triggers = Column(JSON, default=list)  # List of trigger conditions
    
    # Scheduling
    cron_expression = Column(String(100))  # Cron schedule
    next_run = Column(DateTime(timezone=True))
    
    # Status
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.ACTIVE, index=True)
    is_enabled = Column(Boolean, default=True, index=True)
    
    # Statistics
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_execution_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "config": self.config or {},
            "triggers": self.triggers or [],
            "cron_expression": self.cron_expression,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "status": self.status.value if self.status else None,
            "is_enabled": self.is_enabled,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_execution_at": self.last_execution_at.isoformat() if self.last_execution_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowExecution(Base):
    """Workflow execution model."""
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    
    # Execution details
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING, index=True)
    trigger_type = Column(String(50))  # manual, scheduled, file_upload, etc.
    trigger_data = Column(JSON)
    
    # File trigger (if applicable)
    triggered_file_id = Column(Integer, ForeignKey("files.id"), nullable=True, index=True)
    
    # Execution results
    result = Column(JSON)
    error_message = Column(Text)
    logs = Column(Text)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration = Column(Float)  # seconds
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    triggered_file = relationship("FileRecord", back_populates="workflow_executions")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status.value if self.status else None,
            "trigger_type": self.trigger_type,
            "trigger_data": self.trigger_data or {},
            "triggered_file_id": self.triggered_file_id,
            "result": self.result or {},
            "error_message": self.error_message,
            "logs": self.logs,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    try:
        redis_client = redis.from_url(
            get_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await redis_client.ping()
        return redis_client
    except Exception as e:
        print(f"Redis connection failed: {e}")
        redis_client = None
        return None


async def init_db():
    """Initialize database connection and create tables."""
    global engine, async_session
    
    # Convert sync database URL to async
    database_url = get_database_url()
    if database_url.startswith("sqlite"):
        async_database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    else:
        async_database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Create async engine
    engine = create_async_engine(
        async_database_url,
        echo=settings.DATABASE_ECHO,
        future=True,
    )
    
    # Create session factory
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize Redis
    await init_redis()


async def get_db() -> AsyncSession:
    """Get database session."""
    if not async_session:
        await init_db()
    
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> Optional[redis.Redis]:
    """Get Redis client."""
    global redis_client
    if not redis_client:
        redis_client = await init_redis()
    return redis_client


class DatabaseManager:
    """Database operations manager."""
    
    @staticmethod
    async def create_file_record(
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        file_hash: str,
        db: AsyncSession
    ) -> FileRecord:
        """Create a new file record."""
        file_record = FileRecord(
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
        )
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
        return file_record
    
    @staticmethod
    async def get_file_by_id(file_id: int, db: AsyncSession) -> Optional[FileRecord]:
        """Get file record by ID."""
        result = await db.get(FileRecord, file_id)
        return result
    
    @staticmethod
    async def update_file_status(
        file_id: int,
        status: FileStatus,
        db: AsyncSession,
        content: Optional[str] = None,
        metadata: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> Optional[FileRecord]:
        """Update file processing status."""
        file_record = await db.get(FileRecord, file_id)
        if not file_record:
            return None
        
        file_record.status = status
        if content is not None:
            file_record.content = content
        if metadata is not None:
            file_record.metadata = metadata
        if error is not None:
            file_record.processing_error = error
        
        if status == FileStatus.PROCESSING:
            file_record.processing_started_at = datetime.now(timezone.utc)
        elif status in [FileStatus.PROCESSED, FileStatus.FAILED]:
            file_record.processing_completed_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(file_record)
        return file_record
    
    @staticmethod
    async def create_workflow(
        name: str,
        description: str,
        config: Dict[str, Any],
        triggers: List[Dict[str, Any]],
        cron_expression: Optional[str],
        db: AsyncSession
    ) -> Workflow:
        """Create a new workflow."""
        workflow = Workflow(
            name=name,
            description=description,
            config=config,
            triggers=triggers,
            cron_expression=cron_expression,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        return workflow
    
    @staticmethod
    async def get_workflow_by_id(workflow_id: int, db: AsyncSession) -> Optional[Workflow]:
        """Get workflow by ID."""
        result = await db.get(Workflow, workflow_id)
        return result
    
    @staticmethod
    async def create_execution(
        workflow_id: int,
        trigger_type: str,
        trigger_data: Optional[Dict] = None,
        triggered_file_id: Optional[int] = None,
        db: AsyncSession = None
    ) -> WorkflowExecution:
        """Create a new workflow execution."""
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            trigger_type=trigger_type,
            trigger_data=trigger_data or {},
            triggered_file_id=triggered_file_id,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution