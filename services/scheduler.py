"""
Workflow scheduler for PyAirtable Automation Services.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import croniter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from config import settings
from database import (
    async_session, Workflow, WorkflowStatus, WorkflowExecution, 
    ExecutionStatus, DatabaseManager
)

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Cron-based workflow scheduler."""
    
    def __init__(self):
        self.running = False
        self.scheduler_task = None
        self.execution_tasks = {}  # Track running executions
    
    async def start(self):
        """Start the scheduler."""
        if self.running:
            return
        
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Workflow scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running executions
        for task in self.execution_tasks.values():
            task.cancel()
        
        if self.execution_tasks:
            await asyncio.gather(*self.execution_tasks.values(), return_exceptions=True)
        
        logger.info("Workflow scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.running
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                await self._check_scheduled_workflows()
                await self._cleanup_old_executions()
                await asyncio.sleep(settings.SCHEDULER_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(settings.SCHEDULER_INTERVAL)
    
    async def _check_scheduled_workflows(self):
        """Check for workflows that need to be executed."""
        async with async_session() as db:
            try:
                # Find workflows with cron expressions that are due
                now = datetime.now(timezone.utc)
                
                query = select(Workflow).where(
                    and_(
                        Workflow.status == WorkflowStatus.ACTIVE,
                        Workflow.is_enabled == True,
                        Workflow.cron_expression.isnot(None),
                        or_(
                            Workflow.next_run.is_(None),
                            Workflow.next_run <= now
                        )
                    )
                )
                
                result = await db.execute(query)
                workflows = result.scalars().all()
                
                for workflow in workflows:
                    await self._schedule_workflow_execution(workflow, db)
                
            except Exception as e:
                logger.error(f"Error checking scheduled workflows: {e}")
    
    async def _schedule_workflow_execution(self, workflow: Workflow, db: AsyncSession):
        """Schedule a workflow execution."""
        try:
            # Check if workflow is already running
            running_query = select(WorkflowExecution).where(
                and_(
                    WorkflowExecution.workflow_id == workflow.id,
                    WorkflowExecution.status == ExecutionStatus.RUNNING
                )
            )
            running_result = await db.execute(running_query)
            if running_result.scalars().first():
                logger.debug(f"Workflow {workflow.id} is already running, skipping")
                return
            
            # Create execution
            execution = await DatabaseManager.create_execution(
                workflow_id=workflow.id,
                trigger_type="scheduled",
                trigger_data={"cron_expression": workflow.cron_expression},
                db=db
            )
            
            # Update workflow next run time
            await self._update_workflow_next_run(workflow, db)
            
            # Start execution in background
            task = asyncio.create_task(
                self._execute_workflow(execution.id, workflow.id)
            )
            self.execution_tasks[execution.id] = task
            
            logger.info(f"Scheduled execution {execution.id} for workflow {workflow.id}")
            
        except Exception as e:
            logger.error(f"Error scheduling workflow {workflow.id}: {e}")
    
    async def _update_workflow_next_run(self, workflow: Workflow, db: AsyncSession):
        """Update the next run time for a workflow."""
        try:
            if not workflow.cron_expression:
                return
            
            cron = croniter.croniter(workflow.cron_expression, datetime.now(timezone.utc))
            next_run = cron.get_next(datetime)
            
            await db.execute(
                update(Workflow)
                .where(Workflow.id == workflow.id)
                .values(next_run=next_run)
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error updating next run for workflow {workflow.id}: {e}")
    
    async def _execute_workflow(self, execution_id: int, workflow_id: int):
        """Execute a workflow."""
        from services.workflow_service import workflow_service
        
        try:
            await workflow_service.execute_workflow_by_execution_id(execution_id)
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_id}: {e}")
        finally:
            # Remove from tracking
            if execution_id in self.execution_tasks:
                del self.execution_tasks[execution_id]
    
    async def _cleanup_old_executions(self):
        """Clean up old workflow executions."""
        async with async_session() as db:
            try:
                # Delete executions older than configured limit
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
                
                # Keep only recent executions up to the limit
                from sqlalchemy import func, desc
                
                # For each workflow, keep only the most recent executions
                workflows_query = select(Workflow.id)
                workflows_result = await db.execute(workflows_query)
                workflow_ids = [row[0] for row in workflows_result.fetchall()]
                
                for workflow_id in workflow_ids:
                    # Get execution IDs to keep (most recent ones)
                    keep_query = (
                        select(WorkflowExecution.id)
                        .where(WorkflowExecution.workflow_id == workflow_id)
                        .order_by(desc(WorkflowExecution.created_at))
                        .limit(settings.MAX_WORKFLOW_EXECUTIONS)
                    )
                    keep_result = await db.execute(keep_query)
                    keep_ids = [row[0] for row in keep_result.fetchall()]
                    
                    if keep_ids:
                        # Delete old executions
                        delete_query = (
                            select(WorkflowExecution)
                            .where(
                                and_(
                                    WorkflowExecution.workflow_id == workflow_id,
                                    WorkflowExecution.id.notin_(keep_ids),
                                    WorkflowExecution.status.in_([
                                        ExecutionStatus.COMPLETED,
                                        ExecutionStatus.FAILED,
                                        ExecutionStatus.CANCELLED
                                    ])
                                )
                            )
                        )
                        delete_result = await db.execute(delete_query)
                        old_executions = delete_result.scalars().all()
                        
                        for execution in old_executions:
                            await db.delete(execution)
                        
                        if old_executions:
                            await db.commit()
                            logger.debug(f"Cleaned up {len(old_executions)} old executions for workflow {workflow_id}")
                
            except Exception as e:
                logger.error(f"Error cleaning up old executions: {e}")
    
    async def trigger_workflow_manually(self, workflow_id: int, trigger_data: Optional[Dict] = None) -> int:
        """Manually trigger a workflow execution."""
        async with async_session() as db:
            try:
                # Check if workflow exists and is active
                workflow = await db.get(Workflow, workflow_id)
                if not workflow:
                    raise ValueError(f"Workflow {workflow_id} not found")
                
                if workflow.status != WorkflowStatus.ACTIVE:
                    raise ValueError(f"Workflow {workflow_id} is not active")
                
                # Create execution
                execution = await DatabaseManager.create_execution(
                    workflow_id=workflow_id,
                    trigger_type="manual",
                    trigger_data=trigger_data or {},
                    db=db
                )
                
                # Start execution in background
                task = asyncio.create_task(
                    self._execute_workflow(execution.id, workflow_id)
                )
                self.execution_tasks[execution.id] = task
                
                logger.info(f"Manually triggered execution {execution.id} for workflow {workflow_id}")
                return execution.id
                
            except Exception as e:
                logger.error(f"Error manually triggering workflow {workflow_id}: {e}")
                raise
    
    async def cancel_execution(self, execution_id: int) -> bool:
        """Cancel a running workflow execution."""
        try:
            # Cancel the task if it's running
            if execution_id in self.execution_tasks:
                self.execution_tasks[execution_id].cancel()
                del self.execution_tasks[execution_id]
            
            # Update execution status in database
            async with async_session() as db:
                execution = await db.get(WorkflowExecution, execution_id)
                if execution and execution.status == ExecutionStatus.RUNNING:
                    execution.status = ExecutionStatus.CANCELLED
                    execution.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    
                    logger.info(f"Cancelled execution {execution_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling execution {execution_id}: {e}")
            return False
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status information."""
        return {
            "running": self.running,
            "active_executions": len(self.execution_tasks),
            "scheduler_interval": settings.SCHEDULER_INTERVAL,
        }
    
    def validate_cron_expression(self, cron_expression: str) -> bool:
        """Validate a cron expression."""
        try:
            croniter.croniter(cron_expression)
            return True
        except (ValueError, TypeError):
            return False
    
    def get_next_run_times(self, cron_expression: str, count: int = 5) -> List[datetime]:
        """Get the next N run times for a cron expression."""
        try:
            cron = croniter.croniter(cron_expression, datetime.now(timezone.utc))
            return [cron.get_next(datetime) for _ in range(count)]
        except (ValueError, TypeError):
            return []