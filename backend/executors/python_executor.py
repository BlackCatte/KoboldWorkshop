"""
Python executor with full safety and monitoring
"""

import tempfile
import sys
import ast
import os
import asyncio
import time
import logging
from pathlib import Path
from typing import Optional

from .base_executor import (
    BaseExecutor,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    ResourceUsage
)

logger = logging.getLogger(__name__)


class PythonExecutor(BaseExecutor):
    """
    Execute Python scripts safely with:
    - Syntax validation
    - Resource monitoring
    - Network isolation (optional)
    - Timeout enforcement
    """
    
    async def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """Validate Python syntax using AST parser"""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            logger.warning(f"Python validation failed: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def prepare_environment(self, context: ExecutionContext) -> bool:
        """
        Prepare Python execution environment
        - Create temp directory
        - Write code to script.py
        - Set up environment variables
        """
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="aitool_python_")
            context.working_directory = temp_dir
            
            # Write code to file
            script_path = Path(temp_dir) / "script.py"
            script_path.write_text(context.code, encoding='utf-8')
            
            logger.info(f"Created Python script at {script_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare environment: {e}")
            return False
    
    async def execute_code(self, context: ExecutionContext) -> ExecutionResult:
        """Execute Python script in subprocess with full monitoring"""
        
        result = ExecutionResult()
        result.status = ExecutionStatus.PREPARING
        
        try:
            # Prepare environment
            if not await self.prepare_environment(context):
                result.error = "Failed to prepare execution environment"
                result.status = ExecutionStatus.FAILED
                return result
            
            # Build command
            script_path = Path(context.working_directory) / "script.py"
            cmd = [sys.executable, str(script_path)]
            
            # Set up environment variables
            env = os.environ.copy()
            env.update(context.environment_vars)
            
            # Disable network if needed
            if not context.resource_limits.network_enabled:
                env['http_proxy'] = 'http://127.0.0.1:0'
                env['https_proxy'] = 'http://127.0.0.1:0'
                env['HTTP_PROXY'] = 'http://127.0.0.1:0'
                env['HTTPS_PROXY'] = 'http://127.0.0.1:0'
            
            logger.info(f"Starting Python execution: {context.execution_id}")
            
            # Start process
            context.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=context.working_directory
            )
            
            context.pid = context.process.pid
            context.start_time = time.time()
            context.status = ExecutionStatus.RUNNING
            
            # Store context
            self.active_contexts[context.execution_id] = context
            
            # Start resource monitoring
            monitor_task = asyncio.create_task(
                self.monitor_resources(context)
            )
            self.monitoring_tasks[context.execution_id] = monitor_task
            
            logger.info(f"Python process started with PID {context.pid}")
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    context.process.communicate(),
                    timeout=context.resource_limits.max_execution_time
                )
                
                duration = time.time() - context.start_time
                
                result.success = context.process.returncode == 0
                result.output = stdout.decode('utf-8', errors='replace')
                result.error = stderr.decode('utf-8', errors='replace')
                result.exit_code = context.process.returncode
                result.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                
                result.resource_usage = ResourceUsage(
                    duration_seconds=duration
                )
                
                logger.info(f"Python execution completed: {context.execution_id} (exit code: {result.exit_code})")
                
            except asyncio.TimeoutError:
                logger.error(f"Python execution timeout: {context.execution_id}")
                result.success = False
                result.error = f"Execution timeout ({context.resource_limits.max_execution_time}s)"
                result.status = ExecutionStatus.TIMEOUT
                result.termination_reason = "timeout"
                await self.terminate(context.execution_id, context.shutdown_config.method)
                
        except Exception as e:
            logger.error(f"Python execution error: {e}")
            result.success = False
            result.error = str(e)
            result.status = ExecutionStatus.FAILED
            
        finally:
            # Cleanup
            await self.cleanup(context)
            self.active_contexts.pop(context.execution_id, None)
        
        return result
