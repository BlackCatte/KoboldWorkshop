"""
Bash/Shell Script Executor with Safety Features
Executes shell scripts with dangerous command blocking
"""

import tempfile
import os
import asyncio
import time
import logging
import re
from pathlib import Path
from typing import Optional, Set

from .base_executor import (
    BaseExecutor,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    ResourceUsage
)

logger = logging.getLogger(__name__)


class BashExecutor(BaseExecutor):
    """
    Execute Bash/Shell scripts safely
    
    Safety Features:
    - Dangerous command blacklist
    - Syntax validation
    - Resource monitoring
    - Network isolation (optional)
    - Read-only filesystem option
    - Timeout enforcement
    """
    
    def __init__(self):
        super().__init__()
        self.bash_path = self._find_bash()
        self.dangerous_commands = self._load_blacklist()
        logger.info(f"BashExecutor initialized with {len(self.dangerous_commands)} blacklisted commands")
    
    def _find_bash(self) -> str:
        """Find Bash executable"""
        import shutil
        
        bash_candidates = ['bash', '/bin/bash', '/usr/bin/bash']
        
        for candidate in bash_candidates:
            bash_path = shutil.which(candidate) if not candidate.startswith('/') else candidate
            if bash_path and os.path.exists(bash_path):
                return bash_path
        
        logger.warning("Bash not found, using 'bash'")
        return 'bash'
    
    def _load_blacklist(self) -> Set[str]:
        """
        Load dangerous command blacklist
        These commands are BLOCKED for safety
        """
        return {
            # Destructive file operations
            'rm -rf /',
            'rm -rf /*',
            'rm -rf ~',
            'rm -rf ~/*',
            'rm -rf .',
            'rm -rf ..',
            ':(){:|:&};:',  # Fork bomb
            
            # Disk operations
            'dd if=/dev/zero',
            'dd if=/dev/random',
            'mkfs',
            'mkfs.ext',
            'mkfs.ext4',
            'mkfs.xfs',
            'fdisk',
            'parted',
            
            # System modification
            'chmod -R 777 /',
            'chown -R',
            'chmod 777 /',
            
            # Network attacks
            'wget http',
            'curl http',
            '> /dev/sda',
            '> /dev/hda',
            
            # Kernel/system
            '/dev/mem',
            '/dev/kmem',
            'insmod',
            'rmmod',
            'modprobe',
            
            # Privilege escalation attempts
            'sudo su',
            'sudo -i',
            'sudo bash',
            'sudo sh',
        }
    
    def _check_dangerous_commands(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Check for dangerous commands in code
        Returns (is_safe, blocked_command)
        """
        code_lower = code.lower()
        
        # Check blacklist
        for dangerous in self.dangerous_commands:
            if dangerous.lower() in code_lower:
                return False, dangerous
        
        # Check for suspicious patterns
        suspicious_patterns = [
            (r'rm\s+-rf\s+/', 'recursive rm on root'),
            (r':\(\)\{.*\|.*&\};:', 'fork bomb pattern'),
            (r'dd.*of=/dev/[sh]d', 'dd to disk device'),
            (r'>\s*/dev/[sh]d', 'redirect to disk device'),
            (r'mkfs', 'filesystem creation'),
            (r'chmod.*-R.*777.*/', 'dangerous chmod on root'),
        ]
        
        for pattern, description in suspicious_patterns:
            if re.search(pattern, code_lower):
                return False, description
        
        return True, None
    
    async def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Bash script
        1. Check for dangerous commands
        2. Check syntax with bash -n
        """
        
        # First, check for dangerous commands
        is_safe, blocked = self._check_dangerous_commands(code)
        if not is_safe:
            error_msg = f"🚫 BLOCKED: Dangerous command detected: {blocked}"
            logger.warning(f"Bash validation failed: {error_msg}")
            return False, error_msg
        
        # Then check syntax
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Use bash -n for syntax check (no execution)
                process = await asyncio.create_subprocess_exec(
                    self.bash_path,
                    '-n',
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
                    logger.warning(f"Bash syntax error: {error_msg}")
                    return False, f"Syntax error: {error_msg}"
                    
            finally:
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
        Prepare Bash execution environment
        - Create temp directory
        - Write script.sh with shebang
        - Make executable
        - Set up restricted environment
        """
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="aitool_bash_")
            context.working_directory = temp_dir
            
            # Ensure code has shebang
            code = context.code
            if not code.startswith('#!'):
                code = f"#!/bin/bash\nset -e\n\n{code}"
            
            # Write code to file
            script_path = Path(temp_dir) / "script.sh"
            script_path.write_text(code, encoding='utf-8')
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            logger.info(f"Created Bash script at {script_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare environment: {e}")
            return False
    
    async def execute_code(self, context: ExecutionContext) -> ExecutionResult:
        """Execute Bash script with safety monitoring"""
        
        result = ExecutionResult()
        result.status = ExecutionStatus.PREPARING
        
        try:
            # Prepare environment
            if not await self.prepare_environment(context):
                result.error = "Failed to prepare execution environment"
                result.status = ExecutionStatus.FAILED
                return result
            
            # Build command
            script_path = Path(context.working_directory) / "script.sh"
            cmd = [self.bash_path, str(script_path)]
            
            # Set up restricted environment
            env = os.environ.copy()
            env.update(context.environment_vars)
            
            # Restrict PATH to safe directories
            env['PATH'] = '/usr/bin:/bin:/usr/local/bin'
            
            # Disable network if needed
            if not context.resource_limits.network_enabled:
                env['http_proxy'] = 'http://127.0.0.1:0'
                env['https_proxy'] = 'http://127.0.0.1:0'
                env['HTTP_PROXY'] = 'http://127.0.0.1:0'
                env['HTTPS_PROXY'] = 'http://127.0.0.1:0'
            
            # Set safe defaults
            env['PS4'] = '+ '  # Disable verbose tracing
            
            logger.info(f"Starting Bash execution: {context.execution_id}")
            
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
            
            logger.info(f"Bash process started with PID {context.pid}")
            
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
                
                logger.info(f"Bash execution completed: {context.execution_id} (exit code: {result.exit_code})")
                
            except asyncio.TimeoutError:
                logger.error(f"Bash execution timeout: {context.execution_id}")
                result.success = False
                result.error = f"Execution timeout ({context.resource_limits.max_execution_time}s)"
                result.status = ExecutionStatus.TIMEOUT
                result.termination_reason = "timeout"
                await self.terminate(context.execution_id, context.shutdown_config.method)
                
        except Exception as e:
            logger.error(f"Bash execution error: {e}")
            result.success = False
            result.error = str(e)
            result.status = ExecutionStatus.FAILED
            
        finally:
            # Cleanup
            await self.cleanup(context)
            self.active_contexts.pop(context.execution_id, None)
        
        return result
    
    def get_blacklist(self) -> Set[str]:
        """Get the current command blacklist"""
        return self.dangerous_commands.copy()
    
    def add_to_blacklist(self, command: str):
        """Add a command to the blacklist"""
        self.dangerous_commands.add(command)
        logger.info(f"Added to blacklist: {command}")
    
    def remove_from_blacklist(self, command: str):
        """Remove a command from the blacklist"""
        if command in self.dangerous_commands:
            self.dangerous_commands.remove(command)
            logger.info(f"Removed from blacklist: {command}")
