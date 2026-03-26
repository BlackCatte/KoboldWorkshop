"""
JavaScript/Node.js Executor
Safe execution of JavaScript code with Node.js runtime
"""

import tempfile
import os
import asyncio
import time
import logging
import json
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


class JavaScriptExecutor(BaseExecutor):
    """
    Execute JavaScript scripts safely using Node.js
    
    Features:
    - Syntax validation
    - Resource monitoring
    - Network isolation (optional)
    - Timeout enforcement
    - Safe package.json handling
    """
    
    def __init__(self):
        super().__init__()
        self.node_path = self._find_node()
        logger.info(f"JavaScriptExecutor initialized with Node.js at: {self.node_path}")
    
    def _find_node(self) -> str:
        """Find Node.js executable"""
        import shutil
        
        # Try common paths
        node_candidates = ['node', 'nodejs', '/usr/bin/node', '/usr/local/bin/node']
        
        for candidate in node_candidates:
            node_path = shutil.which(candidate)
            if node_path:
                return node_path
        
        # Fallback
        logger.warning("Node.js not found in PATH, using 'node'")
        return 'node'
    
    async def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate JavaScript syntax using Node.js --check
        """
        try:
            # Create temporary file for validation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Use Node.js --check flag for syntax validation
                process = await asyncio.create_subprocess_exec(
                    self.node_path,
                    '--check',
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=5
                )
                
                if process.returncode == 0:
                    return True, None
                else:
                    error_msg = stderr.decode('utf-8', errors='replace')
                    logger.warning(f"JavaScript validation failed: {error_msg}")
                    return False, f"Syntax error: {error_msg}"
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except asyncio.TimeoutError:
            return False, "Validation timeout"
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def prepare_environment(self, context: ExecutionContext) -> bool:
        """
        Prepare JavaScript execution environment
        - Create temp directory
        - Write script.js
        - Create minimal package.json (if needed)
        - Set up environment variables
        """
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="aitool_js_")
            context.working_directory = temp_dir
            
            # Write code to file
            script_path = Path(temp_dir) / "script.js"
            script_path.write_text(context.code, encoding='utf-8')
            
            # Create minimal package.json for better compatibility
            package_json = {
                "name": "ai-tool-script",
                "version": "1.0.0",
                "type": "commonjs",
                "private": True
            }
            
            package_path = Path(temp_dir) / "package.json"
            package_path.write_text(json.dumps(package_json, indent=2))
            
            logger.info(f"Created JavaScript script at {script_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare environment: {e}")
            return False
    
    async def execute_code(self, context: ExecutionContext) -> ExecutionResult:
        """Execute JavaScript script with Node.js"""
        
        result = ExecutionResult()
        result.status = ExecutionStatus.PREPARING
        
        try:
            # Prepare environment
            if not await self.prepare_environment(context):
                result.error = "Failed to prepare execution environment"
                result.status = ExecutionStatus.FAILED
                return result
            
            # Build command
            script_path = Path(context.working_directory) / "script.js"
            cmd = [self.node_path, str(script_path)]
            
            # Set up environment variables
            env = os.environ.copy()
            env.update(context.environment_vars)
            
            # Disable network if needed
            if not context.resource_limits.network_enabled:
                # Note: Node.js doesn't have built-in network isolation
                # This is best effort - use proxy settings
                env['HTTP_PROXY'] = 'http://127.0.0.1:0'
                env['HTTPS_PROXY'] = 'http://127.0.0.1:0'
                env['NO_PROXY'] = '*'
            
            # Set Node.js specific options
            env['NODE_ENV'] = 'production'
            env['NODE_NO_WARNINGS'] = '1'
            
            logger.info(f"Starting JavaScript execution: {context.execution_id}")
            
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
            
            logger.info(f"JavaScript process started with PID {context.pid}")
            
            # Wait for completion
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
                
                logger.info(f"JavaScript execution completed: {context.execution_id} (exit code: {result.exit_code})")
                
            except asyncio.TimeoutError:
                logger.error(f"JavaScript execution timeout: {context.execution_id}")
                result.success = False
                result.error = f"Execution timeout ({context.resource_limits.max_execution_time}s)"
                result.status = ExecutionStatus.TIMEOUT
                result.termination_reason = "timeout"
                await self.terminate(context.execution_id, context.shutdown_config.method)
                
        except Exception as e:
            logger.error(f"JavaScript execution error: {e}")
            result.success = False
            result.error = str(e)
            result.status = ExecutionStatus.FAILED
            
        finally:
            # Cleanup
            await self.cleanup(context)
            self.active_contexts.pop(context.execution_id, None)
        
        return result
