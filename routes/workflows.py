"""
Workflow management API routes for PyAirtable Automation Services.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.workflow_service import workflow_service

router = APIRouter()


class WorkflowCreate(BaseModel):
    """Workflow creation model."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    triggers: List[Dict[str, Any]] = Field(default_factory=list)
    cron_expression: Optional[str] = None


class WorkflowUpdate(BaseModel):
    """Workflow update model."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    triggers: Optional[List[Dict[str, Any]]] = None
    cron_expression: Optional[str] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None


class WorkflowTrigger(BaseModel):
    """Workflow trigger model."""
    trigger_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.post("", response_model=dict)
async def create_workflow(
    workflow_data: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new workflow."""
    try:
        workflow = await workflow_service.create_workflow(
            name=workflow_data.name,
            description=workflow_data.description,
            config=workflow_data.config,
            triggers=workflow_data.triggers,
            cron_expression=workflow_data.cron_expression,
            db=db
        )
        
        return {
            "message": "Workflow created successfully",
            "workflow": workflow.to_dict()
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.get("", response_model=dict)
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status: active, inactive, paused"),
    db: AsyncSession = Depends(get_db)
):
    """List workflows with optional filtering."""
    try:
        workflows = await workflow_service.list_workflows(
            db=db,
            skip=skip,
            limit=limit,
            status_filter=status
        )
        
        return {
            "workflows": [workflow.to_dict() for workflow in workflows],
            "total": len(workflows),
            "skip": skip,
            "limit": limit
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get workflow details by ID."""
    workflow = await workflow_service.get_workflow(workflow_id, db)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "workflow": workflow.to_dict()
    }


@router.put("/{workflow_id}", response_model=dict)
async def update_workflow(
    workflow_id: int,
    workflow_data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update workflow."""
    try:
        workflow = await workflow_service.update_workflow(
            workflow_id=workflow_id,
            db=db,
            name=workflow_data.name,
            description=workflow_data.description,
            config=workflow_data.config,
            triggers=workflow_data.triggers,
            cron_expression=workflow_data.cron_expression,
            status=workflow_data.status,
            is_enabled=workflow_data.is_enabled
        )
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return {
            "message": "Workflow updated successfully",
            "workflow": workflow.to_dict()
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.delete("/{workflow_id}", response_model=dict)
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete workflow."""
    try:
        success = await workflow_service.delete_workflow(workflow_id, db)
        
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return {
            "message": "Workflow deleted successfully",
            "workflow_id": workflow_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


@router.post("/{workflow_id}/trigger", response_model=dict)
async def trigger_workflow(
    workflow_id: int,
    trigger_data: WorkflowTrigger,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a workflow execution."""
    try:
        execution = await workflow_service.trigger_workflow(
            workflow_id=workflow_id,
            db=db,
            trigger_data=trigger_data.trigger_data
        )
        
        return {
            "message": "Workflow triggered successfully",
            "execution": execution.to_dict()
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")


@router.get("/{workflow_id}/executions", response_model=dict)
async def list_workflow_executions(
    workflow_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status: pending, running, completed, failed, cancelled"),
    db: AsyncSession = Depends(get_db)
):
    """List executions for a specific workflow."""
    try:
        executions = await workflow_service.list_executions(
            db=db,
            workflow_id=workflow_id,
            skip=skip,
            limit=limit,
            status_filter=status
        )
        
        return {
            "executions": [execution.to_dict() for execution in executions],
            "workflow_id": workflow_id,
            "total": len(executions),
            "skip": skip,
            "limit": limit
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


@router.get("/executions", response_model=dict)
async def list_all_executions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status: pending, running, completed, failed, cancelled"),
    db: AsyncSession = Depends(get_db)
):
    """List all workflow executions."""
    try:
        executions = await workflow_service.list_executions(
            db=db,
            skip=skip,
            limit=limit,
            status_filter=status
        )
        
        return {
            "executions": [execution.to_dict() for execution in executions],
            "total": len(executions),
            "skip": skip,
            "limit": limit
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


@router.get("/executions/{execution_id}", response_model=dict)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get execution details by ID."""
    execution = await workflow_service.get_execution(execution_id, db)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {
        "execution": execution.to_dict()
    }


@router.get("/stats/summary", response_model=dict)
async def get_workflow_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get workflow statistics."""
    try:
        stats = await workflow_service.get_workflow_stats(db)
        
        return {
            "statistics": stats
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/validate-cron", response_model=dict)
async def validate_cron_expression(
    cron_expression: str = Query(..., description="Cron expression to validate")
):
    """Validate a cron expression and show next run times."""
    from services.scheduler import WorkflowScheduler
    
    scheduler = WorkflowScheduler()
    is_valid = scheduler.validate_cron_expression(cron_expression)
    
    result = {
        "cron_expression": cron_expression,
        "is_valid": is_valid
    }
    
    if is_valid:
        next_runs = scheduler.get_next_run_times(cron_expression, 5)
        result["next_runs"] = [run.isoformat() for run in next_runs]
    else:
        result["error"] = "Invalid cron expression"
    
    return result


# Legacy endpoints for backward compatibility
@router.post("/workflows", response_model=dict, include_in_schema=False)
async def create_workflow_legacy(
    workflow_data: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use / instead."""
    return await create_workflow(workflow_data, db)


@router.get("/workflows", response_model=dict, include_in_schema=False)
async def list_workflows_legacy(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use / instead."""
    return await list_workflows(skip, limit, status, db)


@router.get("/workflows/{workflow_id}", response_model=dict, include_in_schema=False)
async def get_workflow_legacy(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{workflow_id} instead."""
    return await get_workflow(workflow_id, db)


@router.put("/workflows/{workflow_id}", response_model=dict, include_in_schema=False)
async def update_workflow_legacy(
    workflow_id: int,
    workflow_data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{workflow_id} instead."""
    return await update_workflow(workflow_id, workflow_data, db)


@router.delete("/workflows/{workflow_id}", response_model=dict, include_in_schema=False)
async def delete_workflow_legacy(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{workflow_id} instead."""
    return await delete_workflow(workflow_id, db)


@router.post("/workflows/{workflow_id}/trigger", response_model=dict, include_in_schema=False)
async def trigger_workflow_legacy(
    workflow_id: int,
    trigger_data: WorkflowTrigger,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /{workflow_id}/trigger instead."""
    return await trigger_workflow(workflow_id, trigger_data, db)


@router.get("/executions", response_model=dict, include_in_schema=False)
async def list_all_executions_legacy(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint - use /executions instead."""
    return await list_all_executions(skip, limit, status, db)