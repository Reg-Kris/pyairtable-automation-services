"""
Workflow execution service for PyAirtable Automation Services.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import traceback

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func, update

from config import settings
from database import (
    async_session, Workflow, WorkflowStatus, WorkflowExecution,
    ExecutionStatus, FileRecord, DatabaseManager
)

logger = logging.getLogger(__name__)


class WorkflowService:
    """Workflow execution and management service."""
    
    def __init__(self):
        self.execution_timeout = settings.EXECUTION_TIMEOUT
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        config: Dict[str, Any],
        triggers: List[Dict[str, Any]] = None,
        cron_expression: Optional[str] = None,
        db: AsyncSession = None
    ) -> Workflow:
        """Create a new workflow."""
        if triggers is None:
            triggers = []
        
        # Validate cron expression if provided
        if cron_expression:
            from services.scheduler import WorkflowScheduler
            scheduler = WorkflowScheduler()
            if not scheduler.validate_cron_expression(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")
        
        workflow = await DatabaseManager.create_workflow(
            name=name,
            description=description,
            config=config,
            triggers=triggers,
            cron_expression=cron_expression,
            db=db
        )
        
        logger.info(f"Created workflow {workflow.id}: {name}")
        return workflow
    
    async def get_workflow(self, workflow_id: int, db: AsyncSession) -> Optional[Workflow]:
        """Get workflow by ID."""
        return await DatabaseManager.get_workflow_by_id(workflow_id, db)
    
    async def list_workflows(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[Workflow]:
        """List workflows with optional filtering."""
        query = select(Workflow).offset(skip).limit(limit).order_by(Workflow.created_at.desc())
        
        if status_filter:
            try:
                status_enum = WorkflowStatus(status_filter)
                query = query.where(Workflow.status == status_enum)
            except ValueError:
                raise ValueError(f"Invalid status: {status_filter}")
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def update_workflow(
        self,
        workflow_id: int,
        db: AsyncSession,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        triggers: Optional[List[Dict[str, Any]]] = None,
        cron_expression: Optional[str] = None,
        status: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> Optional[Workflow]:
        """Update workflow."""
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            return None
        
        # Validate cron expression if provided
        if cron_expression:
            from services.scheduler import WorkflowScheduler
            scheduler = WorkflowScheduler()
            if not scheduler.validate_cron_expression(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")
        
        # Update fields
        if name is not None:
            workflow.name = name
        if description is not None:
            workflow.description = description
        if config is not None:
            workflow.config = config
        if triggers is not None:
            workflow.triggers = triggers
        if cron_expression is not None:
            workflow.cron_expression = cron_expression
        if status is not None:
            workflow.status = WorkflowStatus(status)
        if is_enabled is not None:
            workflow.is_enabled = is_enabled
        
        workflow.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(f"Updated workflow {workflow_id}")
        return workflow
    
    async def delete_workflow(self, workflow_id: int, db: AsyncSession) -> bool:
        """Delete workflow."""
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            return False
        
        # Cancel any running executions
        running_query = select(WorkflowExecution).where(
            and_(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.status == ExecutionStatus.RUNNING
            )
        )
        running_result = await db.execute(running_query)
        running_executions = running_result.scalars().all()
        
        for execution in running_executions:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now(timezone.utc)
        
        # Delete workflow (executions will be cascade deleted)
        await db.delete(workflow)
        await db.commit()
        
        logger.info(f"Deleted workflow {workflow_id}")
        return True
    
    async def trigger_workflow(
        self,
        workflow_id: int,
        db: AsyncSession,
        trigger_data: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """Manually trigger a workflow execution."""
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if workflow.status != WorkflowStatus.ACTIVE:
            raise ValueError(f"Workflow {workflow_id} is not active")
        
        if not workflow.is_enabled:
            raise ValueError(f"Workflow {workflow_id} is disabled")
        
        # Create execution
        execution = await DatabaseManager.create_execution(
            workflow_id=workflow_id,
            trigger_type="manual",
            trigger_data=trigger_data or {},
            db=db
        )
        
        # Execute in background
        asyncio.create_task(self.execute_workflow_by_execution_id(execution.id))
        
        logger.info(f"Triggered workflow {workflow_id}, execution {execution.id}")
        return execution
    
    async def execute_workflow_by_execution_id(self, execution_id: int):
        """Execute a workflow by execution ID."""
        async with async_session() as db:
            try:
                # Get execution and workflow
                execution = await db.get(WorkflowExecution, execution_id)
                if not execution:
                    logger.error(f"Execution {execution_id} not found")
                    return
                
                workflow = await db.get(Workflow, execution.workflow_id)
                if not workflow:
                    logger.error(f"Workflow {execution.workflow_id} not found")
                    return
                
                await self._execute_workflow(execution, workflow, db)
                
            except Exception as e:
                logger.error(f"Error executing workflow execution {execution_id}: {e}")
    
    async def _execute_workflow(
        self,
        execution: WorkflowExecution,
        workflow: Workflow,
        db: AsyncSession
    ):
        """Execute a workflow."""
        try:
            # Update execution status
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            execution.logs = "Workflow execution started\n"
            
            await db.commit()
            
            logger.info(f"Starting execution {execution.id} for workflow {workflow.id}")
            
            # Execute workflow steps
            result = await self._run_workflow_steps(workflow, execution, db)
            
            # Update execution with results
            execution.status = ExecutionStatus.COMPLETED
            execution.result = result
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration = (
                execution.completed_at - execution.started_at
            ).total_seconds()
            execution.logs += "Workflow execution completed successfully\n"
            
            # Update workflow statistics
            workflow.execution_count += 1
            workflow.success_count += 1
            workflow.last_execution_at = execution.completed_at
            
            await db.commit()
            
            logger.info(f"Completed execution {execution.id} for workflow {workflow.id}")
            
        except Exception as e:
            # Handle execution failure
            await self._handle_execution_failure(execution, workflow, db, e)
    
    async def _run_workflow_steps(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Run workflow steps."""
        config = workflow.config or {}
        steps = config.get("steps", [])
        
        if not steps:
            return {"message": "No steps configured"}
        
        results = []
        context = {
            "workflow_id": workflow.id,
            "execution_id": execution.id,
            "trigger_data": execution.trigger_data or {},
            "triggered_file_id": execution.triggered_file_id,
        }
        
        # Add file context if triggered by file
        if execution.triggered_file_id:
            file_record = await db.get(FileRecord, execution.triggered_file_id)
            if file_record:
                context["file"] = {
                    "id": file_record.id,
                    "filename": file_record.original_filename,
                    "content": file_record.content,
                    "metadata": file_record.metadata or {},
                }
        
        for i, step in enumerate(steps):
            try:
                execution.logs += f"Executing step {i + 1}: {step.get('name', 'Unnamed')}\n"
                await db.commit()
                
                step_result = await self._execute_step(step, context, db)
                results.append({
                    "step": i + 1,
                    "name": step.get("name", f"Step {i + 1}"),
                    "result": step_result,
                    "status": "success"
                })
                
                # Update context with step result
                context[f"step_{i + 1}_result"] = step_result
                
            except Exception as e:
                error_msg = f"Step {i + 1} failed: {str(e)}"
                execution.logs += f"{error_msg}\n"
                logger.error(f"Execution {execution.id} step {i + 1} failed: {e}")
                
                results.append({
                    "step": i + 1,
                    "name": step.get("name", f"Step {i + 1}"),
                    "error": str(e),
                    "status": "failed"
                })
                
                # Stop on error unless configured to continue
                if not step.get("continue_on_error", False):
                    raise Exception(f"Workflow stopped at step {i + 1}: {str(e)}")
        
        return {
            "steps_executed": len(results),
            "steps_successful": len([r for r in results if r["status"] == "success"]),
            "steps_failed": len([r for r in results if r["status"] == "failed"]),
            "results": results,
        }
    
    async def _execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute a single workflow step."""
        step_type = step.get("type")
        
        if step_type == "log":
            return await self._execute_log_step(step, context)
        elif step_type == "file_process":
            return await self._execute_file_process_step(step, context, db)
        elif step_type == "airtable_create":
            return await self._execute_airtable_create_step(step, context)
        elif step_type == "airtable_update":
            return await self._execute_airtable_update_step(step, context)
        elif step_type == "delay":
            return await self._execute_delay_step(step, context)
        elif step_type == "condition":
            return await self._execute_condition_step(step, context, db)
        else:
            raise ValueError(f"Unknown step type: {step_type}")
    
    async def _execute_log_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a log step."""
        message = step.get("message", "Log step executed")
        # Simple template substitution
        for key, value in context.items():
            if isinstance(value, (str, int, float)):
                message = message.replace(f"{{{key}}}", str(value))
        
        logger.info(f"Workflow log: {message}")
        return {"message": message}
    
    async def _execute_file_process_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute a file processing step."""
        file_id = step.get("file_id") or context.get("triggered_file_id")
        if not file_id:
            raise ValueError("No file ID specified for file processing step")
        
        file_record = await db.get(FileRecord, file_id)
        if not file_record:
            raise ValueError(f"File {file_id} not found")
        
        # Process file if not already processed
        if file_record.status.value != "processed":
            from services.file_service import file_service
            await file_service._process_file_content(file_record, db)
            await db.refresh(file_record)
        
        return {
            "file_id": file_id,
            "status": file_record.status.value,
            "content_length": len(file_record.content or ""),
            "metadata": file_record.metadata or {}
        }
    
    async def _execute_airtable_create_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Airtable record creation step."""
        # This would integrate with PyAirtable library
        # For now, return a mock response
        table_name = step.get("table")
        fields = step.get("fields", {})
        
        # Template substitution for field values
        processed_fields = {}
        for key, value in fields.items():
            if isinstance(value, str):
                for ctx_key, ctx_value in context.items():
                    if isinstance(ctx_value, (str, int, float)):
                        value = value.replace(f"{{{ctx_key}}}", str(ctx_value))
            processed_fields[key] = value
        
        # Mock Airtable API call
        logger.info(f"Mock Airtable create in table {table_name}: {processed_fields}")
        
        return {
            "table": table_name,
            "fields": processed_fields,
            "record_id": f"mock_record_{datetime.now().timestamp()}",
            "success": True
        }
    
    async def _execute_airtable_update_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Airtable record update step."""
        # This would integrate with PyAirtable library
        # For now, return a mock response
        table_name = step.get("table")
        record_id = step.get("record_id")
        fields = step.get("fields", {})
        
        # Template substitution
        processed_fields = {}
        for key, value in fields.items():
            if isinstance(value, str):
                for ctx_key, ctx_value in context.items():
                    if isinstance(ctx_value, (str, int, float)):
                        value = value.replace(f"{{{ctx_key}}}", str(ctx_value))
            processed_fields[key] = value
        
        # Mock Airtable API call
        logger.info(f"Mock Airtable update in table {table_name}, record {record_id}: {processed_fields}")
        
        return {
            "table": table_name,
            "record_id": record_id,
            "fields": processed_fields,
            "success": True
        }
    
    async def _execute_delay_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a delay step."""
        delay_seconds = step.get("delay", 1)
        await asyncio.sleep(delay_seconds)
        
        return {"delayed_seconds": delay_seconds}
    
    async def _execute_condition_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute a condition step."""
        condition = step.get("condition", {})
        condition_type = condition.get("type", "equals")
        left_value = condition.get("left")
        right_value = condition.get("right")
        
        # Simple template substitution
        if isinstance(left_value, str):
            for key, value in context.items():
                if isinstance(value, (str, int, float)):
                    left_value = left_value.replace(f"{{{key}}}", str(value))
        
        # Evaluate condition
        result = False
        if condition_type == "equals":
            result = str(left_value) == str(right_value)
        elif condition_type == "not_equals":
            result = str(left_value) != str(right_value)
        elif condition_type == "contains":
            result = str(right_value) in str(left_value)
        elif condition_type == "not_contains":
            result = str(right_value) not in str(left_value)
        
        return {
            "condition_met": result,
            "left_value": left_value,
            "right_value": right_value,
            "condition_type": condition_type
        }
    
    async def _handle_execution_failure(
        self,
        execution: WorkflowExecution,
        workflow: Workflow,
        db: AsyncSession,
        error: Exception
    ):
        """Handle workflow execution failure."""
        try:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(error)
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration = (
                execution.completed_at - execution.started_at
            ).total_seconds() if execution.started_at else 0
            execution.logs += f"Workflow execution failed: {str(error)}\n"
            execution.logs += f"Traceback:\n{traceback.format_exc()}\n"
            
            # Update workflow statistics
            workflow.execution_count += 1
            workflow.failure_count += 1
            workflow.last_execution_at = execution.completed_at
            
            await db.commit()
            
            logger.error(f"Failed execution {execution.id} for workflow {workflow.id}: {error}")
            
        except Exception as e:
            logger.error(f"Error handling execution failure: {e}")
    
    async def list_executions(
        self,
        db: AsyncSession,
        workflow_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None
    ) -> List[WorkflowExecution]:
        """List workflow executions."""
        query = (
            select(WorkflowExecution)
            .offset(skip)
            .limit(limit)
            .order_by(desc(WorkflowExecution.created_at))
        )
        
        if workflow_id:
            query = query.where(WorkflowExecution.workflow_id == workflow_id)
        
        if status_filter:
            try:
                status_enum = ExecutionStatus(status_filter)
                query = query.where(WorkflowExecution.status == status_enum)
            except ValueError:
                raise ValueError(f"Invalid status: {status_filter}")
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_execution(self, execution_id: int, db: AsyncSession) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        return await db.get(WorkflowExecution, execution_id)
    
    async def get_workflow_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get workflow statistics."""
        # Count workflows by status
        status_counts = {}
        for status in WorkflowStatus:
            query = select(func.count()).where(Workflow.status == status)
            result = await db.execute(query)
            status_counts[status.value] = result.scalar() or 0
        
        # Execution statistics
        exec_status_counts = {}
        for status in ExecutionStatus:
            query = select(func.count()).where(WorkflowExecution.status == status)
            result = await db.execute(query)
            exec_status_counts[status.value] = result.scalar() or 0
        
        # Recent executions (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_query = select(func.count()).where(WorkflowExecution.created_at >= yesterday)
        recent_result = await db.execute(recent_query)
        recent_executions = recent_result.scalar() or 0
        
        return {
            "total_workflows": sum(status_counts.values()),
            "workflow_status_breakdown": status_counts,
            "total_executions": sum(exec_status_counts.values()),
            "execution_status_breakdown": exec_status_counts,
            "recent_executions_24h": recent_executions,
        }


# Global workflow service instance
workflow_service = WorkflowService()