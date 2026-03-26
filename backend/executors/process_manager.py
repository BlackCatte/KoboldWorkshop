"""
Process Manager - Unified control for all executors
Central coordination point for multi-language execution
"""

import logging
from typing import Dict, Any, List, Optional
import time

from .base_executor import (
    BaseExecutor,
    ExecutionContext,
    ExecutionResult,
    ResourceLimits,
    ShutdownConfig,
    TerminationMethod,
    ExecutionStatus
)
from .python_executor import PythonExecutor

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Unified process management across all executors
    
    Features:
    - Single source of truth for all executions
    - Language detection and routing
    - Resource limit enforcement
    - Emergency shutdown capabilities
    - Execution tracking and statistics
    """
    
    def __init__(self):
        # Initialize all executors
        from .javascript_executor import JavaScriptExecutor
        from .bash_executor import BashExecutor
        
        self.executors: Dict[str, BaseExecutor] = {
            'python': PythonExecutor(),
            'script': PythonExecutor(),  # Alias for compatibility
            'javascript': JavaScriptExecutor(),
            'js': JavaScriptExecutor(),  # Alias
            'bash': BashExecutor(),
            'shell': BashExecutor(),  # Alias
            'sh': BashExecutor(),  # Alias
        }
        
        # Track all executions across all executors
        self.execution_history: List[Dict[str, Any]] = []
        
        logger.info(f"ProcessManager initialized with executors: {list(set(self.executors.values()))}")
    
    def register_executor(self, language: str, executor: BaseExecutor):
        """Register a new executor for a language"""
        self.executors[language] = executor
        logger.info(f"Registered executor for language: {language}")
    
    async def execute(
        self,
        execution_id: str,
        code: str,
        language: str,
        input_data: Optional[Dict[str, Any]] = None,
        resource_limits: Optional[ResourceLimits] = None,
        shutdown_config: Optional[ShutdownConfig] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """
        Execute code in appropriate runtime
        
        Args:
            execution_id: Unique execution identifier
            code: Code to execute
            language: Programming language
            input_data: Input data for the execution
            resource_limits: Resource constraints
            shutdown_config: Shutdown configuration
            environment_vars: Environment variables
        
        Returns:
            ExecutionResult with output, errors, and metadata
        """
        
        # Get executor for language
        executor = self.executors.get(language.lower())
        if not executor:
            logger.error(f"Unsupported language: {language}")
            result = ExecutionResult()
            result.success = False
            result.error = f"Unsupported language: {language}. Available: {list(self.executors.keys())}"
            result.status = ExecutionStatus.FAILED
            return result
        
        # Validate code
        is_valid, error = await executor.validate_code(code)
        if not is_valid:
            logger.warning(f"Code validation failed: {error}")
            result = ExecutionResult()
            result.success = False
            result.error = f"Validation failed: {error}"
            result.status = ExecutionStatus.FAILED
            return result
        
        # Create execution context
        context = ExecutionContext(
            execution_id=execution_id,
            code=code,
            language=language,
            input_data=input_data or {},
            resource_limits=resource_limits or ResourceLimits(),
            shutdown_config=shutdown_config or ShutdownConfig(),
            environment_vars=environment_vars or {}
        )
        
        logger.info(f"Executing {language} code: {execution_id}")
        
        # Record execution start
        self.execution_history.append({
            'execution_id': execution_id,
            'language': language,
            'started_at': time.time(),
            'status': 'started'
        })
        
        # Execute
        result = await executor.execute_code(context)
        
        # Record completion
        self.execution_history.append({
            'execution_id': execution_id,
            'language': language,
            'completed_at': time.time(),
            'status': 'completed' if result.success else 'failed',
            'exit_code': result.exit_code
        })
        
        logger.info(f"Execution completed: {execution_id} (success: {result.success})")
        
        return result
    
    async def terminate(
        self,
        execution_id: str,
        method: TerminationMethod = TerminationMethod.GRACEFUL
    ) -> bool:
        """
        Terminate any running execution
        
        Args:
            execution_id: ID of execution to terminate
            method: How to terminate (graceful, immediate, custom)
        
        Returns:
            True if successfully terminated
        """
        
        # Find which executor has this execution
        for language, executor in self.executors.items():
            if execution_id in executor.active_contexts:
                logger.info(f"Terminating {language} execution: {execution_id}")
                return await executor.terminate(execution_id, method)
        
        logger.warning(f"No active execution found: {execution_id}")
        return False
    
    async def terminate_all(
        self,
        method: TerminationMethod = TerminationMethod.GRACEFUL
    ) -> Dict[str, bool]:
        """
        Emergency: Stop all executions across all executors
        
        Args:
            method: Termination method to use
        
        Returns:
            Dict mapping execution_id to termination success
        """
        logger.warning("EMERGENCY: Terminating all executions")
        
        results = {}
        
        for language, executor in self.executors.items():
            for execution_id in list(executor.active_contexts.keys()):
                logger.info(f"Terminating {language} execution: {execution_id}")
                success = await executor.terminate(execution_id, method)
                results[execution_id] = success
        
        logger.info(f"Terminated {len(results)} executions")
        return results
    
    def get_active_executions(self) -> List[Dict[str, Any]]:
        """
        Get all currently running executions across all executors
        
        Returns:
            List of execution info dictionaries
        """
        active = []
        
        for language, executor in self.executors.items():
            for exec_id, context in executor.active_contexts.items():
                elapsed = time.time() - context.start_time if context.start_time else 0
                
                active.append({
                    'execution_id': exec_id,
                    'language': language,
                    'pid': context.pid,
                    'status': context.status.value,
                    'elapsed_time': round(elapsed, 2),
                    'resource_limits': {
                        'max_memory_mb': context.resource_limits.max_memory_mb,
                        'max_execution_time': context.resource_limits.max_execution_time,
                        'network_enabled': context.resource_limits.network_enabled
                    }
                })
        
        return active
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics
        
        Returns:
            Statistics about all executions
        """
        total = len(self.execution_history)
        
        # Count by status
        completed = sum(1 for e in self.execution_history if e.get('status') == 'completed')
        failed = sum(1 for e in self.execution_history if e.get('status') == 'failed')
        
        # Count by language
        by_language = {}
        for entry in self.execution_history:
            lang = entry.get('language', 'unknown')
            by_language[lang] = by_language.get(lang, 0) + 1
        
        # Active count
        active_count = sum(len(e.active_contexts) for e in self.executors.values())
        
        return {
            'total_executions': total,
            'completed': completed,
            'failed': failed,
            'currently_active': active_count,
            'by_language': by_language,
            'available_executors': list(self.executors.keys())
        }
    
    def clear_history(self, older_than_seconds: Optional[int] = None):
        """
        Clear execution history
        
        Args:
            older_than_seconds: Only clear entries older than this
        """
        if older_than_seconds is None:
            self.execution_history.clear()
            logger.info("Cleared all execution history")
        else:
            cutoff = time.time() - older_than_seconds
            original_count = len(self.execution_history)
            self.execution_history = [
                e for e in self.execution_history
                if e.get('completed_at', 0) > cutoff
            ]
            removed = original_count - len(self.execution_history)
            logger.info(f"Cleared {removed} old execution history entries")
