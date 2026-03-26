"""
Base executor class for all language runtimes
Provides lifecycle management, resource monitoring, and safe termination
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import signal
import logging

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of an execution"""
    PREPARING = "preparing"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"


class TerminationMethod(str, Enum):
    """How to terminate a process"""
    GRACEFUL = "graceful"      # SIGTERM → wait → SIGKILL
    IMMEDIATE = "immediate"     # SIGKILL immediately
    CUSTOM = "custom"          # User-defined command


@dataclass
class ResourceLimits:
    """Resource constraints for execution"""
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_execution_time: int = 300  # seconds
    max_disk_mb: int = 100
    network_enabled: bool = False


@dataclass
class ShutdownConfig:
    """User-configurable shutdown behavior"""
    method: TerminationMethod = TerminationMethod.GRACEFUL
    grace_period: int = 5  # seconds before force kill
    custom_command: Optional[str] = None
    cleanup_script: Optional[str] = None
    max_force_attempts: int = 3


@dataclass
class ResourceUsage:
    """Tracked resource usage"""
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    disk_written_mb: float = 0.0
    duration_seconds: float = 0.0


@dataclass
class ExecutionContext:
    """Complete context for an execution"""
    execution_id: str
    code: str
    language: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    shutdown_config: ShutdownConfig = field(default_factory=ShutdownConfig)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    working_directory: Optional[str] = None
    process: Optional[asyncio.subprocess.Process] = None
    pid: Optional[int] = None
    start_time: Optional[float] = None
    status: ExecutionStatus = ExecutionStatus.PREPARING


@dataclass
class ExecutionResult:
    """Result from an execution"""
    success: bool = False
    output: str = ""
    error: str = ""
    exit_code: Optional[int] = None
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    status: ExecutionStatus = ExecutionStatus.FAILED
    termination_reason: Optional[str] = None


class BaseExecutor(ABC):
    """
    Abstract base class for all language executors
    
    Provides:
    - Code validation
    - Environment preparation
    - Safe execution with monitoring
    - Graceful and forced termination
    - Resource tracking and limits
    - Cleanup
    """
    
    def __init__(self):
        self.active_contexts: Dict[str, ExecutionContext] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        logger.info(f"{self.__class__.__name__} initialized")
    
    @abstractmethod
    async def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate code syntax before execution
        
        Returns:
            (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def prepare_environment(self, context: ExecutionContext) -> bool:
        """
        Set up execution environment
        - Create temp directory
        - Write code to file
        - Set up runtime-specific config
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def execute_code(self, context: ExecutionContext) -> ExecutionResult:
        """
        Execute the code with full monitoring
        
        Should:
        - Start the process
        - Monitor resources
        - Capture output
        - Handle errors
        - Return results
        """
        pass
    
    async def terminate(
        self, 
        execution_id: str, 
        method: Optional[TerminationMethod] = None
    ) -> bool:
        """
        Terminate a running execution
        
        Termination flow:
        1. Try custom command (if provided and method is CUSTOM)
        2. Send SIGTERM (graceful)
        3. Wait grace period
        4. Send SIGKILL (force)
        5. Cleanup resources
        
        Args:
            execution_id: ID of execution to terminate
            method: Termination method (or use context's default)
        
        Returns:
            True if successfully terminated
        """
        context = self.active_contexts.get(execution_id)
        if not context or not context.process:
            logger.warning(f"No active execution found: {execution_id}")
            return False
        
        shutdown = context.shutdown_config
        method = method or shutdown.method
        
        logger.info(f"Terminating execution {execution_id} with method: {method}")
        context.status = ExecutionStatus.STOPPING
        
        try:
            if method == TerminationMethod.CUSTOM and shutdown.custom_command:
                # Try user-defined shutdown command first
                success = await self._custom_shutdown(context)
                if success:
                    context.status = ExecutionStatus.KILLED
                    await self.cleanup(context)
                    return True
            
            if method == TerminationMethod.IMMEDIATE:
                # Force kill immediately
                result = await self._force_kill(context)
                context.status = ExecutionStatus.KILLED
                return result
            
            # Graceful shutdown
            result = await self._graceful_shutdown(context)
            context.status = ExecutionStatus.KILLED
            return result
            
        except Exception as e:
            logger.error(f"Error during termination: {e}")
            return False
        finally:
            # Always cleanup
            await self.cleanup(context)
            self.active_contexts.pop(execution_id, None)
    
    async def _custom_shutdown(self, context: ExecutionContext) -> bool:
        """Execute user-defined shutdown command"""
        try:
            cmd = context.shutdown_config.custom_command
            logger.info(f"Executing custom shutdown: {cmd}")
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for custom command with timeout
            await asyncio.wait_for(
                process.wait(),
                timeout=context.shutdown_config.grace_period
            )
            
            # Check if main process stopped
            if context.process.returncode is not None:
                logger.info("Custom shutdown successful")
                return True
            
            logger.warning("Custom shutdown command completed but process still running")
                
        except asyncio.TimeoutError:
            logger.warning("Custom shutdown command timed out")
        except Exception as e:
            logger.error(f"Custom shutdown failed: {e}")
        
        return False
    
    async def _graceful_shutdown(self, context: ExecutionContext) -> bool:
        """Graceful shutdown: SIGTERM → wait → SIGKILL"""
        try:
            logger.info(f"Sending SIGTERM to PID {context.pid}")
            context.process.send_signal(signal.SIGTERM)
            
            # Wait grace period
            await asyncio.wait_for(
                context.process.wait(),
                timeout=context.shutdown_config.grace_period
            )
            
            logger.info("Process terminated gracefully")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Grace period expired, forcing kill")
            # Grace period expired, force kill
            return await self._force_kill(context)
        except Exception as e:
            logger.error(f"Graceful shutdown error: {e}")
            return await self._force_kill(context)
    
    async def _force_kill(self, context: ExecutionContext) -> bool:
        """Force kill with SIGKILL"""
        try:
            logger.info(f"Sending SIGKILL to PID {context.pid}")
            context.process.send_signal(signal.SIGKILL)
            await asyncio.wait_for(context.process.wait(), timeout=5)
            logger.info("Process force killed")
            return True
        except Exception as e:
            logger.error(f"Force kill failed: {e}")
            return False
    
    async def monitor_resources(self, context: ExecutionContext):
        """
        Monitor resource usage and enforce limits
        Kills process if limits exceeded
        """
        try:
            # Try to import psutil for resource monitoring
            import psutil
            
            if not context.pid:
                logger.warning("No PID for resource monitoring")
                return
            
            try:
                process = psutil.Process(context.pid)
            except psutil.NoSuchProcess:
                logger.warning(f"Process {context.pid} not found for monitoring")
                return
            
            limits = context.resource_limits
            samples = []
            
            while context.process.returncode is None:
                try:
                    # Check memory
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    if memory_mb > limits.max_memory_mb:
                        logger.error(f"Memory limit exceeded: {memory_mb:.1f}MB > {limits.max_memory_mb}MB")
                        await self.terminate(context.execution_id, TerminationMethod.IMMEDIATE)
                        return
                    
                    # Check CPU (sample over 1 second)
                    cpu_percent = process.cpu_percent(interval=1)
                    samples.append({'cpu': cpu_percent, 'memory': memory_mb})
                    
                    # Check execution time
                    if context.start_time:
                        elapsed = time.time() - context.start_time
                        if elapsed > limits.max_execution_time:
                            logger.error(f"Execution timeout: {elapsed:.1f}s > {limits.max_execution_time}s")
                            context.status = ExecutionStatus.TIMEOUT
                            await self.terminate(context.execution_id, TerminationMethod.GRACEFUL)
                            return
                    
                    await asyncio.sleep(1)
                    
                except psutil.NoSuchProcess:
                    # Process ended
                    break
                except Exception as e:
                    logger.error(f"Error in resource monitoring: {e}")
                    break
            
            # Calculate average resource usage
            if samples:
                avg_cpu = sum(s['cpu'] for s in samples) / len(samples)
                peak_memory = max(s['memory'] for s in samples)
                logger.info(f"Resource usage - CPU: {avg_cpu:.1f}%, Peak Memory: {peak_memory:.1f}MB")
                
        except ImportError:
            logger.warning("psutil not available, resource monitoring disabled")
        except Exception as e:
            logger.error(f"Resource monitoring error: {e}")
    
    async def cleanup(self, context: ExecutionContext):
        """
        Cleanup after execution
        - Run cleanup script
        - Remove temp files
        - Stop monitoring
        """
        logger.info(f"Cleaning up execution {context.execution_id}")
        
        # Run user-defined cleanup script
        if context.shutdown_config.cleanup_script:
            try:
                logger.info("Running cleanup script")
                process = await asyncio.create_subprocess_shell(
                    context.shutdown_config.cleanup_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(process.wait(), timeout=30)
            except Exception as e:
                logger.error(f"Cleanup script failed: {e}")
        
        # Remove working directory
        if context.working_directory:
            import shutil
            try:
                shutil.rmtree(context.working_directory, ignore_errors=True)
                logger.info(f"Removed temp directory: {context.working_directory}")
            except Exception as e:
                logger.error(f"Failed to remove temp dir: {e}")
        
        # Stop monitoring
        monitor_task = self.monitoring_tasks.pop(context.execution_id, None)
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
