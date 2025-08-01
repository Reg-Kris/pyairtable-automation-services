"""
File processing service for PyAirtable Automation Services.
"""

import os
import uuid
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from config import settings, is_file_allowed, get_upload_path
from database import FileRecord, FileStatus, DatabaseManager, WorkflowExecution
from utils.file_utils import FileExtractor

logger = logging.getLogger(__name__)


class FileService:
    """File processing service."""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIRECTORY
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def upload_file(
        self,
        file: UploadFile,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> FileRecord:
        """Upload and store a file."""
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not is_file_allowed(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        unique_filename = f"{file_id}{file_extension}"
        file_path = get_upload_path(unique_filename)
        
        try:
            # Save file
            contents = await file.read()
            
            # Check file size
            if len(contents) > settings.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max size: {settings.MAX_FILE_SIZE} bytes"
                )
            
            with open(file_path, "wb") as f:
                f.write(contents)
            
            # Get file info
            file_size = len(contents)
            mime_type = FileExtractor.get_mime_type(file_path)
            file_hash = FileExtractor.get_file_hash(file_path)
            
            # Create database record
            file_record = await DatabaseManager.create_file_record(
                filename=unique_filename,
                original_filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                db=db
            )
            
            logger.info(f"File uploaded: {file.filename} -> {unique_filename}")
            
            # Trigger workflows for file upload
            await self._trigger_file_workflows(file_record, db)
            
            return file_record
            
        except Exception as e:
            # Cleanup file if database operation fails
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if isinstance(e, HTTPException):
                raise e
            
            logger.error(f"File upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    async def get_file(self, file_id: int, db: AsyncSession) -> Optional[FileRecord]:
        """Get file record by ID."""
        return await DatabaseManager.get_file_by_id(file_id, db)
    
    async def list_files(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[FileRecord]:
        """List files with optional filtering."""
        query = select(FileRecord).offset(skip).limit(limit).order_by(FileRecord.created_at.desc())
        
        if status_filter:
            try:
                status_enum = FileStatus(status_filter)
                query = query.where(FileRecord.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def process_file(
        self,
        file_id: int,
        db: AsyncSession,
        background_tasks = None
    ) -> FileRecord:
        """Process file to extract content."""
        file_record = await self.get_file(file_id, db)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_record.status == FileStatus.PROCESSING:
            raise HTTPException(status_code=409, detail="File is already being processed")
        
        if file_record.status == FileStatus.PROCESSED:
            return file_record
        
        # Update status to processing
        file_record = await DatabaseManager.update_file_status(
            file_id, FileStatus.PROCESSING, db
        )
        
        if background_tasks:
            # Process in background
            background_tasks.add_task(self._process_file_content, file_record, db)
        else:
            # Process immediately
            await self._process_file_content(file_record, db)
        
        return file_record
    
    async def _process_file_content(self, file_record: FileRecord, db: AsyncSession):
        """Process file content extraction."""
        try:
            logger.info(f"Processing file: {file_record.filename}")
            
            # Extract content
            extraction_result = await FileExtractor.extract_text_content(file_record.file_path)
            
            if "error" in extraction_result:
                # Processing failed
                await DatabaseManager.update_file_status(
                    file_record.id,
                    FileStatus.FAILED,
                    db,
                    error=extraction_result["error"],
                    metadata=extraction_result.get("metadata", {})
                )
                logger.error(f"File processing failed: {extraction_result['error']}")
            else:
                # Processing succeeded
                await DatabaseManager.update_file_status(
                    file_record.id,
                    FileStatus.PROCESSED,
                    db,
                    content=extraction_result["content"],
                    metadata=extraction_result.get("metadata", {})
                )
                logger.info(f"File processed successfully: {file_record.filename}")
                
                # Trigger workflows for processed file
                updated_file = await self.get_file(file_record.id, db)
                if updated_file:
                    await self._trigger_file_workflows(updated_file, db, trigger_type="file_processed")
        
        except Exception as e:
            logger.error(f"File processing error: {e}")
            await DatabaseManager.update_file_status(
                file_record.id,
                FileStatus.FAILED,
                db,
                error=str(e)
            )
    
    async def extract_content(self, file_id: int, db: AsyncSession) -> Dict[str, Any]:
        """Get extracted content from file."""
        file_record = await self.get_file(file_id, db)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_record.status == FileStatus.FAILED:
            return {
                "content": "",
                "metadata": file_record.metadata or {},
                "error": file_record.processing_error,
                "status": file_record.status.value
            }
        
        if file_record.status != FileStatus.PROCESSED:
            return {
                "content": "",
                "metadata": file_record.metadata or {},
                "error": "File not processed yet",
                "status": file_record.status.value
            }
        
        return {
            "content": file_record.content or "",
            "metadata": file_record.metadata or {},
            "status": file_record.status.value
        }
    
    async def delete_file(self, file_id: int, db: AsyncSession) -> bool:
        """Delete file and its record."""
        file_record = await self.get_file(file_id, db)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            # Delete physical file
            if os.path.exists(file_record.file_path):
                os.remove(file_record.file_path)
            
            # Update database record
            await DatabaseManager.update_file_status(
                file_id, FileStatus.DELETED, db
            )
            
            logger.info(f"File deleted: {file_record.filename}")
            return True
            
        except Exception as e:
            logger.error(f"File deletion failed: {e}")
            raise HTTPException(status_code=500, detail=f"File deletion failed: {str(e)}")
    
    async def get_file_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get file processing statistics."""
        from sqlalchemy import func
        
        # Count files by status
        status_counts = {}
        for status in FileStatus:
            query = select(func.count()).where(FileRecord.status == status)
            result = await db.execute(query)
            status_counts[status.value] = result.scalar() or 0
        
        # Total file size
        size_query = select(func.sum(FileRecord.file_size))
        size_result = await db.execute(size_query)
        total_size = size_result.scalar() or 0
        
        # Recent uploads (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_query = select(func.count()).where(FileRecord.created_at >= yesterday)
        recent_result = await db.execute(recent_query)
        recent_uploads = recent_result.scalar() or 0
        
        return {
            "total_files": sum(status_counts.values()),
            "status_breakdown": status_counts,
            "total_size_bytes": total_size,
            "recent_uploads_24h": recent_uploads,
        }
    
    async def _trigger_file_workflows(
        self,
        file_record: FileRecord,
        db: AsyncSession,
        trigger_type: str = "file_upload"
    ):
        """Trigger workflows based on file upload/processing."""
        try:
            from database import Workflow, WorkflowStatus
            
            # Find workflows with file triggers
            query = select(Workflow).where(
                and_(
                    Workflow.status == WorkflowStatus.ACTIVE,
                    Workflow.is_enabled == True
                )
            )
            result = await db.execute(query)
            workflows = result.scalars().all()
            
            for workflow in workflows:
                if self._should_trigger_workflow(workflow, file_record, trigger_type):
                    await self._create_workflow_execution(
                        workflow, file_record, trigger_type, db
                    )
        
        except Exception as e:
            logger.error(f"Error triggering file workflows: {e}")
    
    def _should_trigger_workflow(
        self,
        workflow,
        file_record: FileRecord,
        trigger_type: str
    ) -> bool:
        """Check if workflow should be triggered for this file."""
        if not workflow.triggers:
            return False
        
        for trigger in workflow.triggers:
            if trigger.get("type") != trigger_type:
                continue
            
            # Check file extension
            if "file_extensions" in trigger:
                file_ext = Path(file_record.original_filename).suffix.lower()
                if file_ext not in trigger["file_extensions"]:
                    continue
            
            # Check file size
            if "max_file_size" in trigger:
                if file_record.file_size > trigger["max_file_size"]:
                    continue
            
            # Check mime type
            if "mime_types" in trigger:
                if file_record.mime_type not in trigger["mime_types"]:
                    continue
            
            return True
        
        return False
    
    async def _create_workflow_execution(
        self,
        workflow,
        file_record: FileRecord,
        trigger_type: str,
        db: AsyncSession
    ):
        """Create workflow execution for file trigger."""
        try:
            execution = await DatabaseManager.create_execution(
                workflow_id=workflow.id,
                trigger_type=trigger_type,
                trigger_data={
                    "file_id": file_record.id,
                    "filename": file_record.original_filename,
                    "file_size": file_record.file_size,
                    "mime_type": file_record.mime_type,
                },
                triggered_file_id=file_record.id,
                db=db
            )
            
            logger.info(f"Created workflow execution {execution.id} for file {file_record.id}")
            
        except Exception as e:
            logger.error(f"Error creating workflow execution: {e}")


# Global file service instance
file_service = FileService()