import asyncio
import logging
import subprocess
import sys
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import (
    Execution, ExecutionCreate, ExecutionStatus, 
    ResourceUsage, Tool, ToolType
)

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Manages tool execution (basic version without Docker for now)"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.executions
        self.active_executions: Dict[str, asyncio.Task] = {}
    
    async def create_execution(self, exec_data: ExecutionCreate) -> Execution:
        """Create a new execution record"""
        execution = Execution(
            **exec_data.model_dump(),
            status=ExecutionStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        doc = execution.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc['started_at']:
            doc['started_at'] = doc['started_at'].isoformat()
        if doc['ended_at']:
            doc['ended_at'] = doc['ended_at'].isoformat()
        doc['resource_usage'] = dict(doc['resource_usage'])
        
        await self.collection.insert_one(doc)
        logger.info(f"Created execution: {execution.id}")
        
        return execution
    
    async def get_execution(self, execution_id: str) -> Optional[Execution]:
        """Get an execution by ID"""
        doc = await self.collection.find_one({"id": execution_id}, {"_id": 0})
        
        if doc:
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            if doc.get('started_at'):
                doc['started_at'] = datetime.fromisoformat(doc['started_at'])
            if doc.get('ended_at'):
                doc['ended_at'] = datetime.fromisoformat(doc['ended_at'])
            return Execution(**doc)
        
        return None
    
    async def update_execution_status(self, 
                                     execution_id: str, 
                                     status: ExecutionStatus,
                                     result: Optional[str] = None,
                                     error: Optional[str] = None,
                                     output_data: Optional[Dict[str, Any]] = None) -> bool:
        """Update execution status"""
        update_data = {
            "status": status
        }
        
        if status == ExecutionStatus.RUNNING and not await self._get_started_at(execution_id):
            update_data['started_at'] = datetime.now(timezone.utc).isoformat()
        
        if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            update_data['ended_at'] = datetime.now(timezone.utc).isoformat()
        
        if result:
            update_data['result'] = result
        
        if error:
            update_data['error'] = error
        
        if output_data:
            update_data['output_data'] = output_data
        
        result = await self.collection.update_one(
            {"id": execution_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def _get_started_at(self, execution_id: str) -> Optional[str]:
        """Helper to check if execution has started_at"""
        doc = await self.collection.find_one({"id": execution_id}, {"_id": 0, "started_at": 1})
        return doc.get('started_at') if doc else None
    
    async def add_log(self, execution_id: str, log_message: str):
        """Add a log message to execution"""
        await self.collection.update_one(
            {"id": execution_id},
            {"$push": {"logs": f"[{datetime.now(timezone.utc).isoformat()}] {log_message}"}}
        )
    
    async def execute_tool(self, tool: Tool, execution: Execution) -> Dict[str, Any]:
        """Execute a tool (basic Python execution for now)"""
        
        logger.info(f"Executing tool {tool.name} (ID: {tool.id})")
        await self.update_execution_status(execution.id, ExecutionStatus.RUNNING)
        await self.add_log(execution.id, f"Started execution of tool: {tool.name}")
        
        try:
            if tool.type == ToolType.SCRIPT:
                result = await self._execute_python_script(tool, execution)
            elif tool.type == ToolType.FUNCTION:
                result = await self._execute_function(tool, execution)
            else:
                result = {
                    "success": False,
                    "error": f"Tool type {tool.type} not yet supported"
                }
            
            if result.get('success'):
                await self.update_execution_status(
                    execution.id, 
                    ExecutionStatus.COMPLETED,
                    result=result.get('output', ''),
                    output_data=result
                )
                await self.add_log(execution.id, "Execution completed successfully")
            else:
                await self.update_execution_status(
                    execution.id,
                    ExecutionStatus.FAILED,
                    error=result.get('error', 'Unknown error')
                )
                await self.add_log(execution.id, f"Execution failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            await self.update_execution_status(
                execution.id,
                ExecutionStatus.FAILED,
                error=str(e)
            )
            await self.add_log(execution.id, f"Execution error: {str(e)}")
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_python_script(self, tool: Tool, execution: Execution) -> Dict[str, Any]:
        """Execute Python script in subprocess"""
        
        await self.add_log(execution.id, "Executing Python script...")
        
        try:
            # Create a temporary file with the script
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(tool.code)
                script_path = f.name
            
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=tool.config.timeout
                )
                
                output = stdout.decode('utf-8')
                error = stderr.decode('utf-8')
                
                # Clean up temp file
                import os
                os.unlink(script_path)
                
                if process.returncode == 0:
                    await self.add_log(execution.id, f"Script output: {output[:200]}...")
                    return {
                        "success": True,
                        "output": output,
                        "stderr": error
                    }
                else:
                    await self.add_log(execution.id, f"Script error: {error}")
                    return {
                        "success": False,
                        "error": error,
                        "output": output
                    }
            
            except asyncio.TimeoutError:
                process.kill()
                await self.add_log(execution.id, "Script execution timeout")
                return {
                    "success": False,
                    "error": f"Execution timeout ({tool.config.timeout}s)"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Script execution error: {str(e)}"
            }
    
    async def _execute_function(self, tool: Tool, execution: Execution) -> Dict[str, Any]:
        """Execute function-type tool"""
        
        await self.add_log(execution.id, "Executing function...")
        
        try:
            # Create a safe execution environment
            namespace = {
                '__builtins__': __builtins__,
                'input_data': execution.input_data
            }
            
            # Execute the code
            exec(tool.code, namespace)
            
            # Look for a 'result' variable or 'main' function
            if 'result' in namespace:
                result = namespace['result']
            elif 'main' in namespace and callable(namespace['main']):
                result = namespace['main'](execution.input_data)
            else:
                result = "Function executed successfully (no return value)"
            
            await self.add_log(execution.id, f"Function result: {str(result)[:200]}...")
            
            return {
                "success": True,
                "output": str(result),
                "result": result
            }
        
        except Exception as e:
            await self.add_log(execution.id, f"Function error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution"""
        
        if execution_id in self.active_executions:
            task = self.active_executions[execution_id]
            task.cancel()
            del self.active_executions[execution_id]
            
            await self.update_execution_status(
                execution_id,
                ExecutionStatus.CANCELLED
            )
            await self.add_log(execution_id, "Execution cancelled by user")
            
            logger.info(f"Cancelled execution: {execution_id}")
            return True
        
        return False
    
    async def get_recent_executions(self, limit: int = 50):
        """Get recent executions"""
        cursor = self.collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        
        executions = []
        async for doc in cursor:
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            if doc.get('started_at'):
                doc['started_at'] = datetime.fromisoformat(doc['started_at'])
            if doc.get('ended_at'):
                doc['ended_at'] = datetime.fromisoformat(doc['ended_at'])
            executions.append(Execution(**doc))
        
        return executions
