"""
File processing API routes for PyAirtable Automation Services.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, FileRecord
from services.file_service import file_service

router = APIRouter()


@router.post("/upload", response_model=dict)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file for processing.
    
    Supported file types: PDF, DOC, DOCX, TXT, CSV, XLSX, XLS
    """
    file_record = await file_service.upload_file(file, db)
    return {
        "message": "File uploaded successfully",
        "file": file_record.to_dict()
    }


@router.get("/{file_id}", response_model=dict)
async def get_file_info(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get file information by ID."""
    file_record = await file_service.get_file(file_id, db)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "file": file_record.to_dict()
    }


@router.get("", response_model=dict)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status: uploaded, processing, processed, failed, deleted"),
    db: AsyncSession = Depends(get_db)
):
    """List files with optional filtering."""
    files = await file_service.list_files(db, skip=skip, limit=limit, status_filter=status)
    
    return {
        "files": [file.to_dict() for file in files],
        "total": len(files),
        "skip": skip,
        "limit": limit
    }


@router.post("/process/{file_id}", response_model=dict)
async def process_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Process a file to extract content."""
    file_record = await file_service.process_file(file_id, db, background_tasks)
    
    return {
        "message": "File processing started" if file_record.status.value == "processing" else "File processed",
        "file": file_record.to_dict()
    }


@router.get("/extract/{file_id}", response_model=dict)
async def extract_file_content(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get extracted content from a processed file."""
    content_data = await file_service.extract_content(file_id, db)
    
    return {
        "file_id": file_id,
        **content_data
    }


@router.delete("/{file_id}", response_model=dict)
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a file and its record."""
    success = await file_service.delete_file(file_id, db)
    
    return {
        "message": "File deleted successfully" if success else "File deletion failed",
        "file_id": file_id
    }


@router.get("/stats/summary", response_model=dict)
async def get_file_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get file processing statistics."""
    stats = await file_service.get_file_stats(db)
    
    return {
        "statistics": stats
    }


# Legacy endpoints for backward compatibility
@router.post("/files/upload", response_model=dict, include_in_schema=False)
async def upload_file_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /upload instead."""
    return await upload_file(background_tasks, file, db)


@router.get("/files/{file_id}", response_model=dict, include_in_schema=False)
async def get_file_info_legacy(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{file_id} instead."""
    return await get_file_info(file_id, db)


@router.post("/files/process/{file_id}", response_model=dict, include_in_schema=False)
async def process_file_legacy(
    file_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /process/{file_id} instead."""
    return await process_file(file_id, background_tasks, db)


@router.get("/files/extract/{file_id}", response_model=dict, include_in_schema=False)
async def extract_file_content_legacy(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /extract/{file_id} instead."""
    return await extract_file_content(file_id, db)


@router.delete("/files/{file_id}", response_model=dict, include_in_schema=False)
async def delete_file_legacy(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{file_id} instead."""
    return await delete_file(file_id, db)